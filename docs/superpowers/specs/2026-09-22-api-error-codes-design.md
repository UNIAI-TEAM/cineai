# Mã lỗi API: backend trả mã, frontend dịch

- Ngày: 2026-09-22
- Trạng thái: đã duyệt thiết kế, chờ lập kế hoạch
- Thuộc: kế hoạch Việt hoá giai đoạn 1 (xem `docs/I18N.md`)

## 1. Vấn đề

Backend trả lỗi bằng câu tiếng Trung trong `detail`, frontend hiện nguyên văn. Người dùng để giao diện tiếng Việt hoặc tiếng Anh vẫn thấy lỗi tiếng Trung.

Hiện trạng:

- Khoảng 60 `HTTPException(detail="…tiếng Trung…")` trong `api/` (không tính drama/admin).
- Khoảng 50 `raise ValueError("…tiếng Trung…")` trong các service mà giai đoạn 1 dùng, được đưa ra ngoài qua `http_exception_for_value_error` (27 chỗ gọi) hoặc `detail=str(exc)`.
- Có logic dựa vào câu chữ: `services/billing/http.py` trả 402 khi câu lỗi bắt đầu bằng `余额不足`; frontend so `余额不足|请先充值` (`lib/billingError.ts`) và `合成成片` (`StoryboardPage`, `StyleConfigPage`).
- `services/billing/settlement.py` (dòng ~191, ~465) đưa `¥` vào câu lỗi, trái với quy tắc không hiện nhân dân tệ trên giao diện.

## 2. Phạm vi

**Làm:** lỗi trả về ngay từ các API `auth`, `billing`, `projects`, `tasks`, `tools`, `api_keys`, `templates`, cùng lỗi từ các service mà các API này trả ra (`services/tasks/service.py`, `services/tasks/handlers.py`, `services/studio_tools.py`, `services/billing/*`, `services/pipeline.py`).

**Không làm:**

- `api/drama`, `api/admin`, `api/v1` và service chỉ drama dùng: giữ nguyên. Drama sẽ làm ở giai đoạn 2.
- Lỗi lưu trong DB (`TaskRun.error_message`, lỗi của step): để đợt sau, vì cần thêm cột và phân loại lỗi từ nhà cung cấp mô hình.
- Lỗi validate của FastAPI (422, `detail` dạng mảng): giữ cách hiện tại.

## 3. Định dạng lỗi

```json
{
  "detail": "余额不足：需要 12.000 ₫，当前 3.000 ₫，请先充值",
  "code": "billing.insufficient_balance",
  "params": { "need_fen": 1200, "available_fen": 300 }
}
```

- `detail`: câu tiếng Trung, giữ để tương thích với admin, drama, khách dùng `/api/v1`. Câu có tiền được định dạng bằng `services/billing/money.py::format_money`, không dùng `¥`.
- `code`: `<nhóm>.<tên_lỗi>`, viết thường, nối bằng gạch dưới. Nhóm: `auth`, `billing`, `project`, `task`, `tool`, `api_key`, `template`, `common`.
- `params`: chỉ dữ liệu thô (số, id, tên do người dùng đặt). Trường tiền đặt tên kết thúc bằng `_fen`, giá trị là số nguyên (fen).
- Không đưa câu lỗi của hệ thống bên ngoài (nhà cung cấp mô hình, thư viện) vào `detail` hay `params`. Ví dụ `f"AI 生成失败：{exc}"` đổi thành mã `project.ai_generate_failed`; `exc` chỉ ghi vào log.
- `HTTPException` không phải `AppError` giữ nguyên dạng `{detail}` như cũ.

## 4. Backend

### 4.1 `app/errors.py` (file mới)

- `ERRORS: dict[str, tuple[int, str]]`: mã → (HTTP status mặc định, mẫu câu tiếng Trung dùng `str.format` với tên placeholder trùng key trong `params`).
- `class AppError(ValueError)`: `AppError(code, status=None, **params)`.
  - Mã không có trong `ERRORS` → `KeyError` ngay lúc tạo (lộ lỗi khi test, không để lọt ra production với mã sai).
  - `str(exc)` trả về câu `detail` tiếng Trung đã ghép, để các `except ValueError` + `str(exc)` hiện có (drama, admin) vẫn nhận câu hợp lệ.
  - Placeholder tiền: mẫu câu dùng `{need}`, `{available}`; `AppError` tự tạo từ `need_fen`/`available_fen` qua `format_money` (quy tắc: placeholder `{x}` có param `x_fen` thì định dạng tiền).
- Kế thừa `ValueError` để mọi `except ValueError` ở service và drama tiếp tục bắt được.

### 4.2 Bộ xử lý chung (`main.py`)

`@app.exception_handler(AppError)` → `JSONResponse(status_code=exc.status, content={"detail": str(exc), "code": exc.code, "params": exc.params})`.

### 4.3 Chuyển `ValueError` thành lỗi HTTP

- `services/billing/http.py::http_exception_for_value_error`: nếu là `AppError` thì trả lại chính nó để chỗ gọi `raise` và bộ xử lý chung xử lý, giữ nguyên `code`; `ValueError` thường → `HTTPException(400, str(exc))`. Bỏ phép so `startswith("余额不足")`: 402 đến từ status của mã `billing.insufficient_balance`.
  - Kiểu trả về đổi thành `HTTPException | AppError`; chỗ gọi vẫn là `raise http_exception_for_value_error(exc) from exc`.
- Các chỗ `detail=str(exc)` trong API thuộc phạm vi (`auth`, `billing`, `tools`, `projects`, `tasks`) đổi sang dùng helper trên.

### 4.4 Chỗ phát sinh lỗi

- `api/` thuộc phạm vi: `raise HTTPException(404, detail="项目不存在")` → `raise AppError("project.not_found")`.
- Service thuộc phạm vi: `raise ValueError("…")` → `raise AppError(…)`.
- Trước khi đổi câu, tìm trong backend (kể cả drama, admin, test) chỗ nào so câu chữ đó; nếu có, đổi sang so `code` (`isinstance(exc, AppError) and exc.code == …`).

## 5. Frontend

### 5.1 Đọc lỗi (`lib/apiError.ts`)

- `class ApiError extends Error { status; code?; params? }`.
- `parseApiError(status, body, fallback): ApiError`, thứ tự ưu tiên câu hiển thị:
  1. có `code` và có bản dịch trong `m.errors` → câu dịch, nội suy params đã định dạng;
  2. `detail` chuỗi → `detail`; `detail` mảng (422) → ghép `msg` như hiện nay;
  3. còn lại → `fallback` hoặc `apiErrorText('requestFailed')`.
- Params kết thúc bằng `_fen` được định dạng bằng `currency/store.ts::formatFenActive` và truyền vào câu dịch dưới tên đã bỏ hậu tố (`need_fen` → `{need}`).
- `throwApiError(status, body, fallback)` nhận cả body thay vì chỉ `detail`, gọi `parseApiError`, giữ việc hiện hộp nhắc nạp tiền.
- Các chỗ tự đọc lỗi (`api.ts::request` và các hàm upload, `api/tools.ts`, `api/tasks.ts`, `api/apiKeys.ts`, `api/agentSkills.ts`) chuyển sang `throwApiError`/`parseApiError`.

### 5.2 Bỏ so câu chữ

- `lib/billingError.ts`: nhận biết lỗi số dư bằng `status === 402` hoặc `code === 'billing.insufficient_balance'`. Giữ regex cũ làm dự phòng cho drama cho tới giai đoạn 2.
- `StoryboardPage`, `StyleConfigPage`: `msg.includes('合成成片')` → so `err.code`.
- `ToolDetailPage`: chuyển trang đăng nhập khi `err.status === 401`.

### 5.3 File dịch

- `i18n/locales/{zh,en,vi}/errors.ts`: object phẳng, key là mã lỗi (`'project.not_found': '…'`), gắn vào namespace `errors` của từng ngôn ngữ. Vì key có dấu chấm, `parseApiError` tra thẳng `m.errors[code]` rồi nội suy bằng hàm của `i18n/lookup.ts`, không dùng `t('errors.<code>')`.
- Câu tiếng Việt theo `docs/I18N_GLOSSARY_VI.md`.
- Cập nhật `docs/I18N.md`: cách thêm mã lỗi mới (thêm vào `ERRORS` + 3 file `errors.ts`).

## 6. Kiểm thử

Backend (pytest, không cần DB), file `tests/test_app_errors.py`:

- mọi mã trong `ERRORS` đúng định dạng tên và có status hợp lệ; mẫu câu ghép được với params mẫu;
- mã lạ → `KeyError`;
- bộ xử lý chung trả đúng status, `detail`, `code`, `params` (dùng app FastAPI tối giản);
- `http_exception_for_value_error`: `AppError` đi qua nguyên vẹn; `billing.insufficient_balance` → 402; `ValueError` thường → 400;
- câu `detail` có tiền không chứa `¥`;
- đồng bộ: đọc `frontend/src/i18n/locales/{zh,en,vi}/errors.ts`, báo lỗi nếu mã nào trong `ERRORS` thiếu bản dịch hoặc file dịch có mã không tồn tại.

Test cũ đang so câu lỗi tiếng Trung sửa theo `code`. Chạy `pytest` toàn bộ (phần cần DB chạy khi Postgres bật).

Frontend: `tsc -b`, `npm run lint`, `npm run build`. Chạy app kiểm tra bằng giao diện tiếng Việt và tiếng Anh: sai mật khẩu, số dư không đủ (402), tạo ở trang công cụ khi chưa đăng nhập (401).

## 7. Rủi ro

- Bỏ sót chỗ `detail=str(exc)` → mất `code`, người dùng thấy lại tiếng Trung. Không gây vỡ; phát hiện bằng cách grep lại sau khi làm.
- Khách dùng `/api/v1` nhận thêm hai trường `code`, `params` khi service trả `AppError`: chỉ thêm trường, không đổi trường cũ.
