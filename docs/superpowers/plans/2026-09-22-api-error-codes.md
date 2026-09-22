# Mã lỗi API — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend trả `code` + `params` cho lỗi thuộc giai đoạn 1, frontend dịch theo ngôn ngữ giao diện; không làm vỡ admin, drama, `/api/v1`.

**Architecture:** `backend/app/errors.py` khai báo toàn bộ mã lỗi và `AppError(ValueError)`; một exception handler trong `main.py` trả `{detail, code, params}`. Frontend `lib/apiError.ts` có `ApiError` + `parseApiError()` tra `m.errors[code]` trong `i18n/locales/{zh,en,vi}/errors.ts`, chưa có bản dịch thì hiện `detail` như cũ.

**Tech Stack:** Python 3.12 / FastAPI / pytest (backend, chạy bằng `backend/.venv/bin/python -m pytest`); React 19 / TypeScript / Vite / oxlint (frontend).

**Spec:** `docs/superpowers/specs/2026-09-22-api-error-codes-design.md`

## Global Constraints

- Phạm vi: API `auth`, `billing`, `projects`, `tasks`, `tools`, `api_keys`, `templates` + service `tasks/service.py`, `tasks/handlers.py`, `studio_tools.py`, `billing/settlement.py`, `billing/topup.py`, `pipeline.py` (chỉ 3 `ValueError`), `profile.py`, `password_reset.py` (chỉ chỗ API bắt). **Không** sửa `api/drama/*`, `api/admin/*`, `api/v1/*`.
- Không đổi `TaskRun.error_message` / lỗi lưu DB, không đổi thông điệp tiến độ trong `pipeline.py`.
- `detail` luôn là câu tiếng Trung (để tương thích). `str(AppError)` == `detail`.
- Mã lỗi: `^[a-z_]+\.[a-z_]+$`. Nhóm: `common`, `auth`, `billing`, `task`, `tool`, `api_key`, `template`, `project`.
- `params` chỉ chứa dữ liệu thô; tiền là số nguyên fen, key kết thúc `_fen`; placeholder trong mẫu câu bỏ hậu tố (`need_fen` → `{need}`).
- Không đưa câu lỗi của hệ thống ngoài (`str(exc)` của lỗi upstream/thư viện) ra response; ghi log bằng `logger.exception`.
- Không dùng `¥` trong câu lỗi.
- Mỗi hàm mới có comment chức năng ở đầu (tiếng Trung, theo `docs/STANDARDS.md`); tiếng Việt theo `docs/I18N_GLOSSARY_VI.md`.
- Commit message tiếng Việt, kết thúc bằng dòng `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- Test cần DB (fixture `db_session`) chỉ chạy được khi Postgres bật; nếu không bật, ghi rõ là đã bỏ qua, không coi là đạt.

---

### Task 1: Lõi backend — `AppError`, danh mục mã, handler, helper chuyển `ValueError`

**Files:**
- Create: `backend/app/errors.py`
- Modify: `backend/app/main.py` (sau dòng `app = FastAPI(...)`, khoảng dòng 28)
- Modify: `backend/app/services/billing/http.py`
- Create: `backend/tests/test_app_errors.py`
- Modify: `backend/tests/test_billing_settlement.py:26-29`

**Interfaces:**
- Produces:
  - `app.errors.ERRORS: dict[str, tuple[int, str]]`
  - `app.errors.AppError(code: str, status: int | None = None, **params)` với thuộc tính `code: str`, `status: int`, `params: dict`, `detail: str`; method `to_payload() -> dict`, `clone() -> AppError`
  - `app.errors.register_app_error_handler(app: FastAPI) -> None`
  - `app.services.billing.http.http_exception_for_value_error(exc: ValueError) -> HTTPException | AppError`

- [ ] **Step 1: Viết test lõi (fail)**

`backend/tests/test_app_errors.py`:

```python
# -*- coding: utf-8 -*-
"""AppError / 错误码目录 / 全局处理器 单测（不需要数据库）。"""
from __future__ import annotations

import re
import string

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import ERRORS, AppError, register_app_error_handler
from app.services.billing.http import http_exception_for_value_error

CODE_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")
MONEY_FIELDS = {"need", "available", "pending"}


def _sample_params(template: str) -> dict[str, object]:
    """按模板占位符造参数：金额字段给 *_fen，其余给普通值。"""
    params: dict[str, object] = {}
    for _, field, _, _ in string.Formatter().parse(template):
        if not field:
            continue
        if field in MONEY_FIELDS:
            params[f"{field}_fen"] = 1234
        else:
            params[field] = 7
    return params


@pytest.mark.parametrize("code", sorted(ERRORS))
def test_every_code_is_well_formed_and_renders(code: str) -> None:
    status, template = ERRORS[code]
    assert CODE_RE.match(code), code
    assert 400 <= status <= 599
    exc = AppError(code, **_sample_params(template))
    assert exc.detail and "{" not in exc.detail
    assert str(exc) == exc.detail


def test_unknown_code_raises_key_error() -> None:
    with pytest.raises(KeyError):
        AppError("nope.not_registered")


def test_app_error_is_value_error_and_keeps_params() -> None:
    exc = AppError("project.download_limit", max=50)
    assert isinstance(exc, ValueError)
    assert exc.status == 400
    assert exc.params == {"max": 50}
    assert exc.to_payload() == {"detail": "一次最多打包 50 个", "code": "project.download_limit", "params": {"max": 50}}


def test_status_override() -> None:
    assert AppError("project.not_found", status=410).status == 410


def test_money_detail_has_no_yuan_sign() -> None:
    exc = AppError("billing.insufficient_balance", need_fen=1200, available_fen=300)
    assert exc.status == 402
    assert "¥" not in exc.detail
    assert exc.detail.startswith("余额不足")
    assert exc.params == {"need_fen": 1200, "available_fen": 300}


def test_handler_returns_code_and_params() -> None:
    app = FastAPI()
    register_app_error_handler(app)

    @app.get("/boom")
    async def boom() -> None:
        raise AppError("project.download_limit", max=50)

    res = TestClient(app).get("/boom")
    assert res.status_code == 400
    assert res.json() == {"detail": "一次最多打包 50 个", "code": "project.download_limit", "params": {"max": 50}}


def test_http_helper_passes_app_error_through() -> None:
    original = AppError("billing.insufficient_balance", need_fen=100, available_fen=0)
    out = http_exception_for_value_error(original)
    assert isinstance(out, AppError)
    assert out.code == "billing.insufficient_balance"
    assert out.status == 402
    assert out.params == original.params


def test_http_helper_plain_value_error_is_400() -> None:
    out = http_exception_for_value_error(ValueError("余额不足：老格式"))
    assert isinstance(out, HTTPException)
    assert out.status_code == 400
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.errors'`

- [ ] **Step 3: Tạo `backend/app/errors.py`**

```python
# -*- coding: utf-8 -*-
"""业务错误码：AppError + 错误码目录 + 全局异常处理器。

响应体 {detail, code, params}：detail 为中文（兼容管理端 / 漫剧 / 开放 API），
前端按 code 查 i18n/locales/*/errors.ts 翻译。新增错误码时三份前端文案要同步加，
tests/test_app_errors.py 会校验。
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# code -> (默认 HTTP 状态码, 中文 detail 模板)；占位符 {x} 若参数里只有 x_fen 则按展示货币格式化
ERRORS: dict[str, tuple[int, str]] = {
    # 通用
    "common.unsupported_image_type": (400, "仅支持 JPG / PNG / WebP / GIF"),
    "common.empty_file": (400, "空文件"),
    "common.file_too_large": (400, "文件不能超过 {max_mb}MB"),
    "common.invalid_image": (400, "文件不是有效图片"),
    "common.user_not_found": (404, "用户不存在"),
    # 账号
    "auth.email_registered": (400, "邮箱已注册"),
    "auth.invalid_credentials": (401, "邮箱或密码错误"),
    "auth.wrong_current_password": (400, "当前密码不正确"),
    "auth.same_password": (400, "新密码不能与当前密码相同"),
    "auth.email_taken": (400, "该邮箱已被使用"),
    "auth.service_unavailable": (503, "服务暂时不可用，请稍后再试"),
    "auth.reset_token_invalid": (400, "重置链接无效或已过期"),
    "auth.username_required": (400, "用户名不能为空"),
    "auth.username_too_long": (400, "用户名不能超过 {max} 个字符"),
    "auth.email_invalid": (400, "邮箱格式不正确"),
    "auth.phone_invalid": (400, "手机号格式不正确"),
    # 计费
    "billing.insufficient_balance": (402, "余额不足：需要 {need}，当前 {available}，请先充值"),
    "billing.insufficient_balance_pending": (
        402,
        "余额不足：本次需要 {need}（含排队中 {pending}），当前 {available}，请先充值",
    ),
    "billing.insufficient_balance_batch": (
        402,
        "余额不足：批量生成 {qty} 项需 {need}（含排队中 {pending}），当前 {available}，请先充值",
    ),
    "billing.unknown_package": (400, "未知充值包"),
    "billing.topup_unavailable": (503, "充值暂未开放：尚未配置收款账户"),
    "billing.alert_not_found": (404, "告警不存在"),
    "billing.order_not_found": (404, "订单不存在"),
    "billing.order_paid_cannot_close": (400, "已支付订单无法关闭"),
    "billing.order_cannot_close": (400, "当前状态不可关闭"),
    "billing.order_closed": (400, "订单已关闭，无法确认到账"),
    # 任务平台
    "task.not_found": (404, "任务不存在"),
    "task.mock_limit": (429, "模拟延时任务最多同时运行 {max} 个"),
    "task.type_not_supported": (400, "当前任务类型尚未接入任务平台"),
    "task.target_not_found": (404, "任务目标不存在或无权限"),
    "task.target_mismatch": (400, "任务目标不匹配"),
    "task.invalid_payload": (400, "任务参数无效：{field}"),
    "task.cancel_not_supported": (400, "任务不支持取消"),
    "task.already_finished": (400, "任务已结束，不能取消"),
    # 工具中心
    "tool.unknown": (400, "未知工具"),
    "tool.missing_task": (400, "缺少任务"),
    "tool.run_not_found": (404, "记录不存在"),
    "tool.unsupported_file_type": (400, "仅支持 png / jpg / webp / gif / mp4 / mov / webm"),
    "tool.prompt_required": (400, "请填写提示词"),
    "tool.reference_required": (400, "请上传参考图"),
    "tool.product_image_required": (400, "请上传商品图"),
    "tool.stitch_min_images": (400, "拼接至少上传 {min} 张图片"),
    "tool.video_script_required": (400, "请填写视频脚本"),
    "tool.video_source_required": (400, "请上传源视频或首帧图"),
    "tool.first_frame_extract_failed": (400, "无法从视频抽取首帧"),
    "tool.first_frame_required": (400, "缺少首帧图，无法生成视频"),
    "tool.run_failed": (500, "生成失败，请稍后重试"),
    # API Key / 模板
    "api_key.not_found": (404, "Key 不存在或已撤销"),
    "template.not_found": (404, "模板不存在"),
    # 科普 / 获客短视频项目
    "project.not_found": (404, "项目不存在"),
    "project.invalid_template": (400, "无效模板"),
    "project.topic_required": (400, "请输入选题"),
    "project.ai_generate_failed": (502, "AI 生成失败，请稍后重试"),
    "project.voice_preview_failed": (502, "试听生成失败，请稍后重试"),
    "project.full_generation_running": (409, "整片生成进行中，请稍后"),
    "project.generation_running": (409, "生成进行中，请稍后"),
    "project.locked_while_generating": (409, "生成进行中，无法修改"),
    "project.cover_locked": (409, "生成进行中，无法更换封面"),
    "project.download_selection_required": (400, "请选择要下载的作品"),
    "project.download_limit": (400, "一次最多打包 {max} 个"),
    "project.no_downloadable_video": (400, "所选作品暂无成片可下载（需状态为已完成）"),
    "project.invalid_cover_url": (400, "无效封面地址"),
    "project.invalid_image_model": (400, "无效图片模型"),
    "project.invalid_video_model": (400, "无效视频模型"),
    "project.ready_to_compose": (409, "素材已齐，请点击合成成片"),
    "project.cannot_cancel": (400, "当前状态不可取消"),
    "project.shot_list_incomplete": (400, "镜头列表不完整"),
    "project.shot_not_found": (404, "分镜不存在"),
    "project.image_text_no_video": (400, "图文模式无需生成 AI 视频，请直接重新合成成片"),
    "project.shot_image_required": (400, "请先生成该镜画面"),
    "project.no_shots": (400, "暂无分镜，请先生成"),
    "project.compose_missing_media": (400, "缺少分镜图或镜头视频，无法合成"),
    "project.not_ready_to_publish": (400, "成片未完成，无法发布"),
    "project.narration_empty": (400, "全部镜头旁白为空，无法配音"),
    "project.shot_narration_empty": (400, "旁白为空，无法配音"),
}


def _render(template: str, params: dict[str, Any]) -> str:
    """用参数填充中文模板；*_fen 额外生成去后缀的格式化金额（如 need_fen → {need}）。"""
    values: dict[str, Any] = dict(params)
    for key, value in params.items():
        if key.endswith("_fen"):
            # 延迟导入：billing 包初始化会反向导入本模块
            from app.services.billing.money import format_money

            values[key[: -len("_fen")]] = format_money(int(value))
    return template.format(**values)


class AppError(ValueError):
    """带错误码的业务错误；继承 ValueError，已有 except ValueError 仍能捕获。

    参数:
        code: ERRORS 中登记的错误码，未登记直接 KeyError
        status: 覆盖默认 HTTP 状态码
        **params: 原始数据（数字 / id / 用户输入的名称），金额用 *_fen
    """

    def __init__(self, code: str, status: int | None = None, **params: Any) -> None:
        default_status, template = ERRORS[code]
        self.code = code
        self.status = status or default_status
        self.params = params
        self.detail = _render(template, params)
        super().__init__(self.detail)

    def to_payload(self) -> dict[str, Any]:
        """HTTP 响应体。"""
        return {"detail": self.detail, "code": self.code, "params": self.params}

    def clone(self) -> "AppError":
        """复制一份，供 `raise ... from exc` 时避免异常以自身为 cause。"""
        return AppError(self.code, status=self.status, **self.params)


def register_app_error_handler(app: FastAPI) -> None:
    """注册全局处理器：AppError → JSON {detail, code, params}。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_payload())
```

- [ ] **Step 4: Sửa `backend/app/services/billing/http.py`**

Thay toàn bộ file bằng:

```python
# -*- coding: utf-8 -*-
"""ValueError → HTTP 异常映射。"""
from __future__ import annotations

from fastapi import HTTPException

from app.errors import AppError


def http_exception_for_value_error(exc: ValueError) -> HTTPException | AppError:
    """AppError 原样交给全局处理器（保留 code / 状态码，余额不足即 402）；其余 ValueError → 400。"""
    if isinstance(exc, AppError):
        return exc.clone()
    return HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 5: Gắn handler trong `backend/app/main.py`**

Thêm import cạnh các import `app.*` khác:

```python
from app.errors import register_app_error_handler
```

Ngay sau dòng `app = FastAPI(title=settings.app_name, version="0.2.0")`:

```python
register_app_error_handler(app)
```

- [ ] **Step 6: Sửa test cũ `backend/tests/test_billing_settlement.py:26-29`**

Thay hàm `test_http_exception_maps_insufficient_balance_to_402` bằng:

```python
def test_http_exception_maps_insufficient_balance_to_402() -> None:
    exc = http_exception_for_value_error(AppError("billing.insufficient_balance", need_fen=100, available_fen=0))
    assert isinstance(exc, AppError)
    assert exc.status == 402
    assert "余额不足" in exc.detail
```

và thêm `from app.errors import AppError` vào phần import đầu file.

- [ ] **Step 7: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py tests/test_billing_settlement.py -q`
Expected: tất cả PASS (trong `test_billing_settlement.py`, test nào dùng `db_session` sẽ ERROR nếu Postgres không bật — ghi lại, không tính là fail của task này).

Run: `cd backend && .venv/bin/python -c "import app.main"`
Expected: không lỗi import (xác nhận không vòng import).

- [ ] **Step 8: Commit**

```bash
git add backend/app/errors.py backend/app/main.py backend/app/services/billing/http.py backend/tests/test_app_errors.py backend/tests/test_billing_settlement.py
git commit -m "feat: thêm AppError và danh mục mã lỗi API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Lỗi tính phí (billing)

**Files:**
- Modify: `backend/app/services/billing/settlement.py` (dòng ~118, ~128-132, ~148, ~157-160, ~191, ~465)
- Modify: `backend/app/services/studio_tools.py:231`
- Modify: `backend/app/services/billing/topup.py:153,180`
- Modify: `backend/app/api/billing.py` (dòng 123-126, 199, 309, 332, 334, 338)
- Test: `backend/tests/test_billing_integration.py` (3 hàm dùng `match="余额不足"`)

**Interfaces:**
- Consumes: `AppError` từ Task 1.

- [ ] **Step 1: Thêm assert mã lỗi vào test tích hợp (fail)**

Trong `backend/tests/test_billing_integration.py`, ở cả ba chỗ `with pytest.raises(ValueError, match="余额不足"):` đổi thành `with pytest.raises(ValueError, match="余额不足") as exc_info:` và thêm ngay sau khối `with` (thụt lề ngang `with`):

```python
    assert getattr(exc_info.value, "code", "").startswith("billing.insufficient_balance")
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_billing_integration.py -q -k "insufficient or pending_unfrozen"`
Expected: FAIL ở assert `code` (cần Postgres; nếu không có DB thì ghi lại là ERROR do thiếu DB và làm tiếp).

- [ ] **Step 3: Sửa `settlement.py`**

Thêm `from app.errors import AppError` vào import. Thay:

| Hiện tại | Thay bằng |
|---|---|
| `raise ValueError("用户不存在")` (2 chỗ) | `raise AppError("common.user_not_found")` |
| khối `raise ValueError(f"余额不足：本次需要 … （含排队中 …），当前 …")` trong `if pending > 0:` | `raise AppError("billing.insufficient_balance_pending", need_fen=need, pending_fen=pending, available_fen=available)` |
| `raise ValueError(f"余额不足：需要 {format_money(need)}，当前 {format_money(available)}，请先充值")` | `raise AppError("billing.insufficient_balance", need_fen=need, available_fen=available)` |
| khối `raise ValueError(f"余额不足：批量生成 {qty} 项需 …")` | `raise AppError("billing.insufficient_balance_batch", qty=qty, need_fen=additional, pending_fen=pending, available_fen=available)` |
| `raise ValueError(f"余额不足：需要 ¥{need/100:.2f}，当前 ¥{available/100:.2f}，请先充值")` | `raise AppError("billing.insufficient_balance", need_fen=need, available_fen=available)` |
| `raise ValueError(f"余额不足：需要 ¥{need / 100:.2f}，当前 ¥{available / 100:.2f}，请先充值")` | `raise AppError("billing.insufficient_balance", need_fen=need, available_fen=available)` |

Nếu sau khi sửa `format_money` không còn được dùng trong file, xoá import đó.

- [ ] **Step 4: Sửa `studio_tools.py:231`**

`raise ValueError(f"余额不足：需要 {format_money(need)}，当前 {format_money(available)}，请先充值")` → `raise AppError("billing.insufficient_balance", need_fen=need, available_fen=available)`; thêm `from app.errors import AppError`; xoá import `format_money` nếu không còn dùng.

- [ ] **Step 5: Sửa `topup.py`**

- dòng 153: `raise ValueError("订单已关闭，无法确认到账")` → `raise AppError("billing.order_closed")`
- dòng 180: `raise ValueError("已支付订单无法关闭")` → `raise AppError("billing.order_paid_cannot_close")`
- dòng 97 (`RuntimeError("充值暂未开放…")`) giữ nguyên; API xử lý ở bước sau.
- Thêm `from app.errors import AppError`.

- [ ] **Step 6: Sửa `api/billing.py`**

Thêm `from app.errors import AppError`. Thay:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 124 | `raise HTTPException(status_code=400, detail="未知充值包") from exc` | `raise AppError("billing.unknown_package") from exc` |
| 126 | `raise HTTPException(status_code=503, detail=str(exc)) from exc` | `raise AppError("billing.topup_unavailable") from exc` |
| 199 | `raise HTTPException(status_code=404, detail="告警不存在")` | `raise AppError("billing.alert_not_found")` |
| 309, 332 | `raise HTTPException(status_code=404, detail="订单不存在")` | `raise AppError("billing.order_not_found")` |
| 334 | `raise HTTPException(status_code=400, detail="已支付订单无法关闭")` | `raise AppError("billing.order_paid_cannot_close")` |
| 338 | `raise HTTPException(status_code=400, detail="当前状态不可关闭")` | `raise AppError("billing.order_cannot_close")` |

- [ ] **Step 7: Tìm chỗ còn so câu chữ số dư**

Run: `cd backend && grep -rn "startswith(\"余额不足\")\|\"余额不足\" in" app tests | grep -v __pycache__`
Expected: không còn kết quả. (`executor.py` và `ephemeral.py` coi mọi `ValueError` khi `freeze_for_task` là thiếu số dư — giữ nguyên, không so chuỗi.)

- [ ] **Step 8: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py tests/test_billing_settlement.py tests/test_billing_integration.py tests/test_task_executor_freeze_steps.py -q`
Expected: PASS (test cần DB: PASS khi Postgres bật; ghi rõ nếu bỏ qua).

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/billing/settlement.py backend/app/services/studio_tools.py backend/app/services/billing/topup.py backend/app/api/billing.py backend/tests/test_billing_integration.py
git commit -m "feat: gắn mã lỗi cho lỗi tính phí, bỏ ký hiệu ¥ trong câu lỗi

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Tài khoản, API Key, mẫu

**Files:**
- Modify: `backend/app/services/profile.py` (class `ProfileError`, dòng 35-52)
- Modify: `backend/app/api/auth.py` (dòng 43, 76, 93, 95, 109-110, 121-124, 141-142, 147, 178, 182, 184)
- Modify: `backend/app/api/api_keys.py:43`
- Modify: `backend/app/api/templates.py:24`
- Test: `backend/tests/test_profile.py`

**Interfaces:**
- Consumes: `AppError`.
- Produces: `ProfileError(AppError)` — tạo bằng `ProfileError("<code>", **params)`.

- [ ] **Step 1: Thêm test mã lỗi hồ sơ (fail)**

Thêm vào cuối `backend/tests/test_profile.py`:

```python
def test_profile_errors_carry_codes():
    with pytest.raises(ProfileError) as bad_phone:
        prepare_profile_update(nickname="创作者", email="a@b.com", phone="abc")
    assert bad_phone.value.code == "auth.phone_invalid"

    with pytest.raises(ProfileError) as too_long:
        prepare_profile_update(nickname="x" * 65, email="a@b.com", phone="")
    assert too_long.value.code == "auth.username_too_long"
    assert too_long.value.params == {"max": 64}
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_profile.py -q`
Expected: FAIL — `AttributeError: 'ProfileError' object has no attribute 'code'`

- [ ] **Step 2: Sửa `services/profile.py`**

```python
from app.errors import AppError


class ProfileError(AppError):
    """资料校验错误（带错误码）。"""
```

(giữ docstring cũ nếu có, chỉ đổi lớp cha). Thay các raise:

| Hiện tại | Thay bằng |
|---|---|
| `raise ProfileError("用户名不能为空")` | `raise ProfileError("auth.username_required")` |
| `raise ProfileError("用户名不能超过 64 个字符")` | `raise ProfileError("auth.username_too_long", max=64)` |
| `raise ProfileError("邮箱格式不正确") from exc` | `raise ProfileError("auth.email_invalid") from exc` |
| `raise ProfileError("手机号格式不正确")` (2 chỗ) | `raise ProfileError("auth.phone_invalid")` |

- [ ] **Step 3: Sửa `api/auth.py`**

Thêm `from app.errors import AppError`. Thay:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 43 | `raise HTTPException(status_code=400, detail="邮箱已注册")` | `raise AppError("auth.email_registered")` |
| 76 | `raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")` | `raise AppError("auth.invalid_credentials")` |
| 93 | `…detail="当前密码不正确")` | `raise AppError("auth.wrong_current_password")` |
| 95 | `…detail="新密码不能与当前密码相同")` | `raise AppError("auth.same_password")` |
| 110, 122 | `raise HTTPException(status_code=503, detail=str(exc)) from exc` | `raise AppError("auth.service_unavailable") from exc` |
| 124 | `raise HTTPException(status_code=400, detail=str(exc)) from exc` | `raise AppError("auth.reset_token_invalid") from exc` |
| 141-142 | `except ProfileError as exc:` + `raise HTTPException(status_code=400, detail=str(exc)) from exc` | xoá khối `try/except`, gọi `prepare_profile_update(...)` trực tiếp (ProfileError là AppError, handler chung xử lý) |
| 147 | `…detail="该邮箱已被使用")` | `raise AppError("auth.email_taken")` |
| 178 | `…detail="仅支持 JPG / PNG / WebP / GIF")` | `raise AppError("common.unsupported_image_type")` |
| 182 | `…detail="空文件")` | `raise AppError("common.empty_file")` |
| 184 | `…detail="头像不能超过 5MB")` | `raise AppError("common.file_too_large", max_mb=5)` |

Sau khi sửa, nếu `HTTPException`, `status` hoặc `ProfileError` không còn dùng trong file thì xoá import tương ứng.

- [ ] **Step 4: Sửa `api/api_keys.py:43` và `api/templates.py:24`**

- `raise HTTPException(status_code=404, detail="Key 不存在或已撤销")` → `raise AppError("api_key.not_found")`
- `raise HTTPException(status_code=404, detail="模板不存在")` → `raise AppError("template.not_found")`
- Thêm `from app.errors import AppError` vào mỗi file; xoá import `HTTPException` nếu không còn dùng.

- [ ] **Step 5: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_profile.py tests/test_password_reset.py tests/test_change_password.py tests/test_app_errors.py -q`
Expected: PASS (test cần DB: ghi rõ nếu bỏ qua).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/profile.py backend/app/api/auth.py backend/app/api/api_keys.py backend/app/api/templates.py backend/tests/test_profile.py
git commit -m "feat: gắn mã lỗi cho tài khoản, API Key và mẫu

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Nền tảng tác vụ (tasks)

**Files:**
- Modify: `backend/app/api/tasks.py` (dòng 36, 46, 76-77, 126-127)
- Modify: `backend/app/services/tasks/service.py` (dòng 106, 860-912, 996, 998, 1160, 1162)
- Modify: `backend/app/services/tasks/handlers.py` (dòng 78, 108, 232, 236, 260)
- Test: `backend/tests/test_app_errors.py`

**Interfaces:**
- Consumes: `AppError`.

- [ ] **Step 1: Viết test cho validate payload (fail)**

Hàm ở dòng ~257 là `_require_int(value: int | None, field_name: str) -> int` (đồng bộ). Thêm vào `backend/tests/test_app_errors.py`:

```python
def test_task_payload_missing_field_has_code() -> None:
    from app.services.tasks.handlers import _require_int

    with pytest.raises(AppError) as exc_info:
        _require_int(None, "project_id")
    assert exc_info.value.code == "task.invalid_payload"
    assert exc_info.value.params == {"field": "project_id"}
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q -k task_payload`
Expected: FAIL — `ValueError` không phải `AppError`.

- [ ] **Step 2: Sửa `handlers.py`**

Thêm `from app.errors import AppError`:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 78 | `raise ValueError("fragment_ids 必须为数组")` | `raise AppError("task.invalid_payload", field="fragment_ids")` |
| 108 | `raise ValueError("reference_asset_ids 必须为数组")` | `raise AppError("task.invalid_payload", field="reference_asset_ids")` |
| 232 | `raise ValueError("delay_seconds 必须在 1-600 秒之间")` | `raise AppError("task.invalid_payload", field="delay_seconds")` |
| 236 | `raise ValueError("succeed 必须为布尔值")` | `raise AppError("task.invalid_payload", field="succeed")` |
| 260 | `raise ValueError(f"任务缺少 {field_name}")` | `raise AppError("task.invalid_payload", field=field_name)` |

- [ ] **Step 3: Sửa `service.py`**

Thêm `from app.errors import AppError`. Thay theo bảng (giữ nguyên hai `raise LookupError("任务不存在")` ở dòng 923, 1098 — API tự đổi sang mã):

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 106 | `raise ValueError("当前任务类型尚未接入任务平台")` | `raise AppError("task.type_not_supported")` |
| 860 | `"科普项目不存在或无权限"` | `raise AppError("task.target_not_found", target="kepu_project")` |
| 864, 867 | `"镜头不存在"`, `"镜头不存在或无权限"` | `raise AppError("task.target_not_found", target="shot")` |
| 869 | `"镜头与项目不匹配"` | `raise AppError("task.target_mismatch", target="shot")` |
| 875 | `"漫剧项目不存在或无权限"` | `raise AppError("task.target_not_found", target="drama_project")` |
| 879, 882 | `"剧本不存在"`, `"剧本不存在或无权限"` | `raise AppError("task.target_not_found", target="script")` |
| 884 | `"剧本与漫剧项目不匹配"` | `raise AppError("task.target_mismatch", target="script")` |
| 888, 891 | `"分集不存在"`, `"分集不存在或无权限"` | `raise AppError("task.target_not_found", target="episode")` |
| 893 | `"分集与漫剧项目不匹配"` | `raise AppError("task.target_mismatch", target="episode")` |
| 897, 901 | `"分镜不存在"`, `"分镜不存在或无权限"` | `raise AppError("task.target_not_found", target="fragment")` |
| 903 | `"分镜与分集不匹配"` | `raise AppError("task.target_mismatch", target="fragment")` |
| 907, 910 | `"资产不存在"`, `"资产不存在或无权限"` | `raise AppError("task.target_not_found", target="asset")` |
| 912 | `"资产与漫剧项目不匹配"` | `raise AppError("task.target_mismatch", target="asset")` |
| 996, 1160 | `raise ValueError("任务不支持取消")` | `raise AppError("task.cancel_not_supported")` |
| 998, 1162 | `raise ValueError("任务已结束，不能取消")` | `raise AppError("task.already_finished")` |

Trước khi đổi, chạy `grep -rn "不存在或无权限\|不匹配\|任务不支持取消\|任务已结束" backend/app backend/tests backend/../frontend/src | grep -v __pycache__` để chắc không có chỗ nào so các câu này; nếu có test so câu, đổi sang so `exc.code`.

- [ ] **Step 4: Sửa `api/tasks.py`**

Thêm `from app.errors import AppError`:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 36 | `raise HTTPException(status_code=404, detail="任务不存在")` | `raise AppError("task.not_found")` |
| 46 | `raise HTTPException(status_code=429, detail="模拟延时任务最多同时运行 3 个")` | `raise AppError("task.mock_limit", max=3)` |
| 77, 127 | `raise HTTPException(status_code=404, detail="任务不存在") from exc` | `raise AppError("task.not_found") from exc` |

- [ ] **Step 5: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py tests/test_task_fragment_ids.py tests/test_side_task_gate.py tests/test_kepu_cancel_propagation.py tests/test_drama_cancel_scope.py tests/test_finalizing_cancel_race.py tests/test_task_executor_freeze_steps.py -q`
Expected: PASS (test cần DB: ghi rõ nếu bỏ qua).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/tasks.py backend/app/services/tasks/service.py backend/app/services/tasks/handlers.py backend/tests/test_app_errors.py
git commit -m "feat: gắn mã lỗi cho nền tảng tác vụ

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Trung tâm công cụ (tools)

**Files:**
- Modify: `backend/app/api/tools.py` (dòng 60-127, 138, 149, 222)
- Modify: `backend/app/services/studio_tools.py` (dòng 113, 162, 165, 180, 185, 191, 383, 408, 413, 420, 423)
- Test: `backend/tests/test_app_errors.py`

**Interfaces:**
- Consumes: `AppError`, `http_exception_for_value_error`.

Lưu ý lỗi có sẵn cần sửa luôn: trong `run_tool`, mọi `ValueError` từ `enqueue_image_tool` / `run_billed_ephemeral_deferred` đều bị trả 402 (kể cả "请填写提示词"), và `HTTPException(402)` ở khối trong bị `except Exception` bên ngoài bọc thành 500.

- [ ] **Step 1: Viết test (fail)**

Thêm vào `backend/tests/test_app_errors.py`:

```python
def test_tool_router_maps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具入口：参数错误 400 带码；未知异常 500 且不回传原始报错。"""
    from app.api import tools as tools_api
    from app.database import get_db
    from app.deps import get_current_user

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(tools_api.router, prefix="/api")

    class _User:
        id = 1

    async def _fake_db():
        class _Db:
            async def commit(self) -> None: ...
        yield _Db()

    app.dependency_overrides[get_current_user] = lambda: _User()
    app.dependency_overrides[get_db] = _fake_db

    async def _prompt_missing(*_a, **_k):
        raise AppError("tool.prompt_required")

    monkeypatch.setattr(tools_api, "enqueue_image_tool", _prompt_missing)
    client = TestClient(app)
    res = client.post("/api/tools/run", data={"tool_id": "t2i"})
    assert res.status_code == 400
    assert res.json()["code"] == "tool.prompt_required"

    async def _boom(*_a, **_k):
        raise RuntimeError("upstream secret stack")

    monkeypatch.setattr(tools_api, "enqueue_image_tool", _boom)
    res = client.post("/api/tools/run", data={"tool_id": "t2i"})
    assert res.status_code == 500
    assert res.json()["code"] == "tool.run_failed"
    assert "secret" not in res.text
```

Route là `POST /api/tools/run` (router `prefix="/tools"`), form field bắt buộc `tool_id`; `t2i` thuộc `IMAGE_TOOLS`; `get_db` import từ `app.database`, `get_current_user` từ `app.deps` — test trên đã khớp.

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q -k tool_router`
Expected: FAIL (hiện trả 402 / 500 với detail chứa "upstream secret stack").

- [ ] **Step 2: Sửa `api/tools.py`**

Thêm ở đầu file (nếu chưa có):

```python
import logging

from app.errors import AppError
from app.services.billing.http import http_exception_for_value_error

logger = logging.getLogger(__name__)
```

Trong `run_tool`:
- Xoá hai khối `try: … except ValueError as exc: raise HTTPException(status_code=402, detail=str(exc)) from exc` bao quanh `enqueue_image_tool(...)` và `run_billed_ephemeral_deferred(...)` (giữ nguyên lời gọi bên trong, chỉ bỏ `try/except`).
- `raise ValueError("单个文件不能超过 40MB")` → `raise AppError("common.file_too_large", max_mb=40)`
- `raise ValueError("未知工具")` → `raise AppError("tool.unknown")`
- Thay hai nhánh `except` cuối:

```python
    except HTTPException:
        raise
    except ValueError as exc:
        raise http_exception_for_value_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool run failed tool_id=%s", tid)
        raise AppError("tool.run_failed") from exc
```

Các dòng khác:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 138 | `raise HTTPException(status_code=400, detail="缺少任务")` | `raise AppError("tool.missing_task")` |
| 149 | `raise HTTPException(status_code=404, detail="任务不存在")` | `raise AppError("task.not_found")` |
| 222 | `raise HTTPException(status_code=404, detail="记录不存在")` | `raise AppError("tool.run_not_found")` |

- [ ] **Step 3: Sửa `services/studio_tools.py`**

Thêm `from app.errors import AppError` (nếu Task 2 chưa thêm):

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 113 | `raise ValueError("仅支持 png / jpg / webp / gif / mp4 / mov / webm")` | `raise AppError("tool.unsupported_file_type")` |
| 162 | `raise ValueError("请填写提示词")` | `raise AppError("tool.prompt_required")` |
| 165 | `raise ValueError("请上传参考图")` | `raise AppError("tool.reference_required")` |
| 180 | `raise ValueError("请上传商品图")` | `raise AppError("tool.product_image_required")` |
| 185 | `raise ValueError("拼接至少上传 2 张图片")` | `raise AppError("tool.stitch_min_images", min=2)` |
| 191 | `raise ValueError("不支持的生图工具")` | `raise AppError("tool.unknown")` |
| 383 | `raise ValueError("请填写视频脚本")` | `raise AppError("tool.video_script_required")` |
| 408 | `raise ValueError("请上传源视频或首帧图")` | `raise AppError("tool.video_source_required")` |
| 413 | `raise ValueError("无法从视频抽取首帧")` | `raise AppError("tool.first_frame_extract_failed")` |
| 420 | `raise ValueError("不支持的视频工具")` | `raise AppError("tool.unknown")` |
| 423 | `raise ValueError("缺少首帧图，无法生成视频")` | `raise AppError("tool.first_frame_required")` |

`RuntimeError` ở dòng 123, 138 giữ nguyên (API bọc thành `tool.run_failed`).

- [ ] **Step 4: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/tools.py backend/app/services/studio_tools.py backend/tests/test_app_errors.py
git commit -m "feat: gắn mã lỗi cho trung tâm công cụ, sửa lỗi mọi lỗi đều trả 402

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Dự án video ngắn (projects)

**Files:**
- Modify: `backend/app/api/projects.py` (các dòng trong bảng dưới)
- Modify: `backend/app/services/pipeline.py` (dòng 297, 1564, 1660)
- Test: `backend/tests/test_app_errors.py`

**Interfaces:**
- Consumes: `AppError`.

- [ ] **Step 1: Viết test catalogue dùng trong projects (fail)**

Thêm vào `backend/tests/test_app_errors.py`:

```python
def test_projects_api_has_no_chinese_http_detail() -> None:
    """projects.py 不再直接抛中文 detail 的 HTTPException。"""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("app/api/projects.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in src.splitlines()
        if "detail=" in line and re.search(r"[一-鿿]", line)
    ]
    assert offenders == []
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q -k projects_api`
Expected: FAIL, liệt kê các dòng còn tiếng Trung.

- [ ] **Step 2: Sửa `api/projects.py`**

Thêm ở đầu file (nếu chưa có):

```python
import logging

from app.errors import AppError

logger = logging.getLogger(__name__)
```

Thay:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 103-104 | `except Exception as exc:` + `raise HTTPException(status_code=502, detail=f"试听生成失败：{exc}") from exc` | `except Exception as exc:  # noqa: BLE001` + `logger.exception("voice preview failed")` + `raise AppError("project.voice_preview_failed") from exc` |
| 117 | `…detail="请输入选题")` | `raise AppError("project.topic_required")` |
| 122-123 | `except Exception as exc:` + `raise HTTPException(status_code=502, detail=f"AI 生成失败：{exc}") from exc` | `except Exception as exc:  # noqa: BLE001` + `logger.exception("ai generate failed")` + `raise AppError("project.ai_generate_failed") from exc` |
| 158 | `…detail="项目不存在")` | `raise AppError("project.not_found")` |
| 195 | `…detail="整片生成进行中，请稍后")` | `raise AppError("project.full_generation_running")` |
| 202, 211, 699, 1136 | `…detail="生成进行中，请稍后")` | `raise AppError("project.generation_running")` |
| 304, 589 | `…detail="无效模板")` | `raise AppError("project.invalid_template")` |
| 494 | `…detail="请选择要下载的作品")` | `raise AppError("project.download_selection_required")` |
| 496 | `…detail="一次最多打包 50 个")` | `raise AppError("project.download_limit", max=50)` |
| 505 | `…detail=f"项目不存在: {missing[:5]}")` | `raise AppError("project.not_found", ids=list(missing[:5]))` |
| 527-530 | `raise HTTPException(status_code=400, detail="所选作品暂无成片可下载（需状态为已完成）",)` (nhiều dòng) | `raise AppError("project.no_downloadable_video")` |
| 581 | `…detail="生成进行中，无法修改")` | `raise AppError("project.locked_while_generating")` |
| 600 | `…detail="无效封面地址")` | `raise AppError("project.invalid_cover_url")` |
| 608 | `…detail="无效图片模型")` | `raise AppError("project.invalid_image_model")` |
| 613 | `…detail="无效视频模型")` | `raise AppError("project.invalid_video_model")` |
| 643 | `…detail="生成进行中，无法更换封面")` | `raise AppError("project.cover_locked")` |
| 660, 934 | `…detail="仅支持 JPG / PNG / WebP / GIF")` | `raise AppError("common.unsupported_image_type")` |
| 664, 937 | `…detail="空文件")` | `raise AppError("common.empty_file")` |
| 666 | `…detail="封面不能超过 8MB")` | `raise AppError("common.file_too_large", max_mb=8)` |
| 715 | `…detail="素材已齐，请点击合成成片")` | `raise AppError("project.ready_to_compose")` |
| 768 | `…detail="当前状态不可取消")` | `raise AppError("project.cannot_cancel")` |
| 899 | `…detail="镜头列表不完整")` | `raise AppError("project.shot_list_incomplete")` |
| 920, 971, 1054, 1106 | `…detail="分镜不存在")` | `raise AppError("project.shot_not_found")` |
| 939 | `…detail="画面不能超过 8MB")` | `raise AppError("common.file_too_large", max_mb=8)` |
| 942 | `…detail="文件不是有效图片")` | `raise AppError("common.invalid_image")` |
| 1078 | `…detail="图文模式无需生成 AI 视频，请直接重新合成成片")` | `raise AppError("project.image_text_no_video")` |
| 1081 | `…detail="请先生成该镜画面")` | `raise AppError("project.shot_image_required")` |
| 1138 | `…detail="暂无分镜，请先生成")` | `raise AppError("project.no_shots")` |
| 1165 | `…detail="缺少分镜图或镜头视频，无法合成")` | `raise AppError("project.compose_missing_media")` |
| 1187 | `…detail="成片未完成，无法发布")` | `raise AppError("project.not_ready_to_publish")` |

Số dòng có thể lệch vài dòng sau mỗi lần sửa — tìm theo câu tiếng Trung. Các chỗ `raise http_exception_for_value_error(exc) from exc` (dòng 141, 272, 746) giữ nguyên.

- [ ] **Step 3: Sửa `services/pipeline.py`**

Thêm `from app.errors import AppError`:

| Dòng | Hiện tại | Thay bằng |
|---|---|---|
| 297 | `raise ValueError("全部镜头旁白为空，无法配音")` | `raise AppError("project.narration_empty")` |
| 1564 | `raise ValueError("图文模式无需生成 AI 视频，请直接重新合成成片")` | `raise AppError("project.image_text_no_video")` |
| 1660 | `raise ValueError("旁白为空，无法配音")` | `raise AppError("project.shot_narration_empty")` |

Không đổi các `RuntimeError` và thông điệp tiến độ khác trong file.

- [ ] **Step 4: Chạy test**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q && .venv/bin/python -c "import app.main"`
Expected: PASS, import không lỗi.

Run: `cd backend && .venv/bin/python -m pytest -q -k "kepu or project or pipeline or compose"`
Expected: PASS (test cần DB: ghi rõ nếu bỏ qua).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/projects.py backend/app/services/pipeline.py backend/tests/test_app_errors.py
git commit -m "feat: gắn mã lỗi cho API dự án video ngắn

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Frontend — `ApiError`, bản dịch mã lỗi, test đồng bộ

**Files:**
- Create: `frontend/src/i18n/locales/zh/errors.ts`, `frontend/src/i18n/locales/en/errors.ts`, `frontend/src/i18n/locales/vi/errors.ts`
- Modify: `frontend/src/i18n/locales/zh.ts`, `en.ts`, `vi.ts` (spread thêm `...zhErrors` / `...enErrors` / `...viErrors`)
- Modify: `frontend/src/lib/apiError.ts`, `frontend/src/lib/billingError.ts`
- Modify: `frontend/src/api.ts` (hàm `request` dòng ~24-32 và 4 hàm upload/download dòng ~403-412, ~473-481, ~536-544, ~589-592)
- Modify: `frontend/src/api/tools.ts`, `frontend/src/api/tasks.ts:28-29`, `frontend/src/api/drama.ts:62`, `frontend/src/api/apiKeys.ts:40-48`, `frontend/src/api/agentSkills.ts:21-24,65-67`
- Test: `backend/tests/test_app_errors.py` (test đồng bộ)

**Interfaces:**
- Consumes: danh sách mã trong `backend/app/errors.py::ERRORS` (Task 1).
- Produces (`frontend/src/lib/apiError.ts`):
  - `class ApiError extends Error { status: number; code?: string; params?: Record<string, unknown> }`
  - `parseApiError(status: number, body: unknown, fallback?: string): ApiError`
  - `throwApiError(status: number, body: unknown, fallback?: string): never` (đổi tham số thứ 2 từ `detail` sang cả `body`)
  - `isInsufficientBalanceCode(code?: string): boolean`
  - `apiErrorText(key)` giữ nguyên
- Produces (`frontend/src/lib/billingError.ts`): `markBillingMessage(message: string): void`

- [ ] **Step 1: Viết test đồng bộ (fail)**

Thêm vào `backend/tests/test_app_errors.py`:

```python
LOCALES_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "locales"
KEY_RE = re.compile(r"^\s*'([a-z_]+\.[a-z_]+)':", re.MULTILINE)


@pytest.mark.parametrize("locale", ["zh", "en", "vi"])
def test_frontend_error_translations_match_catalog(locale: str) -> None:
    src = (LOCALES_DIR / locale / "errors.ts").read_text(encoding="utf-8")
    keys = set(KEY_RE.findall(src))
    assert sorted(set(ERRORS) - keys) == [], f"{locale} 缺少翻译"
    assert sorted(keys - set(ERRORS)) == [], f"{locale} 有多余的码"
```

và thêm `from pathlib import Path` vào import đầu file.

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q -k translations`
Expected: FAIL — `FileNotFoundError` cho `errors.ts`.

- [ ] **Step 2: Tạo `frontend/src/i18n/locales/zh/errors.ts`**

```ts
/** 中文：接口错误码文案（key 与 backend/app/errors.py 的 ERRORS 一致） */

export const zhErrors = {
  errors: {
    'common.unsupported_image_type': '仅支持 JPG / PNG / WebP / GIF',
    'common.empty_file': '空文件',
    'common.file_too_large': '文件不能超过 {max_mb}MB',
    'common.invalid_image': '文件不是有效图片',
    'common.user_not_found': '用户不存在',
    'auth.email_registered': '邮箱已注册',
    'auth.invalid_credentials': '邮箱或密码错误',
    'auth.wrong_current_password': '当前密码不正确',
    'auth.same_password': '新密码不能与当前密码相同',
    'auth.email_taken': '该邮箱已被使用',
    'auth.service_unavailable': '服务暂时不可用，请稍后再试',
    'auth.reset_token_invalid': '重置链接无效或已过期',
    'auth.username_required': '用户名不能为空',
    'auth.username_too_long': '用户名不能超过 {max} 个字符',
    'auth.email_invalid': '邮箱格式不正确',
    'auth.phone_invalid': '手机号格式不正确',
    'billing.insufficient_balance': '余额不足：需要 {need}，当前 {available}，请先充值',
    'billing.insufficient_balance_pending': '余额不足：本次需要 {need}（含排队中 {pending}），当前 {available}，请先充值',
    'billing.insufficient_balance_batch': '余额不足：批量生成 {qty} 项需 {need}（含排队中 {pending}），当前 {available}，请先充值',
    'billing.unknown_package': '未知充值包',
    'billing.topup_unavailable': '充值暂未开放：尚未配置收款账户',
    'billing.alert_not_found': '告警不存在',
    'billing.order_not_found': '订单不存在',
    'billing.order_paid_cannot_close': '已支付订单无法关闭',
    'billing.order_cannot_close': '当前状态不可关闭',
    'billing.order_closed': '订单已关闭，无法确认到账',
    'task.not_found': '任务不存在',
    'task.mock_limit': '模拟延时任务最多同时运行 {max} 个',
    'task.type_not_supported': '当前任务类型尚未接入任务平台',
    'task.target_not_found': '内容不存在或无权访问',
    'task.target_mismatch': '数据不匹配，请刷新页面',
    'task.invalid_payload': '任务参数无效：{field}',
    'task.cancel_not_supported': '任务不支持取消',
    'task.already_finished': '任务已结束，不能取消',
    'tool.unknown': '未知工具',
    'tool.missing_task': '缺少任务',
    'tool.run_not_found': '记录不存在',
    'tool.unsupported_file_type': '仅支持 png / jpg / webp / gif / mp4 / mov / webm',
    'tool.prompt_required': '请填写提示词',
    'tool.reference_required': '请上传参考图',
    'tool.product_image_required': '请上传商品图',
    'tool.stitch_min_images': '拼接至少上传 {min} 张图片',
    'tool.video_script_required': '请填写视频脚本',
    'tool.video_source_required': '请上传源视频或首帧图',
    'tool.first_frame_extract_failed': '无法从视频抽取首帧',
    'tool.first_frame_required': '缺少首帧图，无法生成视频',
    'tool.run_failed': '生成失败，请稍后重试',
    'api_key.not_found': 'Key 不存在或已撤销',
    'template.not_found': '模板不存在',
    'project.not_found': '项目不存在',
    'project.invalid_template': '无效模板',
    'project.topic_required': '请输入选题',
    'project.ai_generate_failed': 'AI 生成失败，请稍后重试',
    'project.voice_preview_failed': '试听生成失败，请稍后重试',
    'project.full_generation_running': '整片生成进行中，请稍后',
    'project.generation_running': '生成进行中，请稍后',
    'project.locked_while_generating': '生成进行中，无法修改',
    'project.cover_locked': '生成进行中，无法更换封面',
    'project.download_selection_required': '请选择要下载的作品',
    'project.download_limit': '一次最多打包 {max} 个',
    'project.no_downloadable_video': '所选作品暂无成片可下载（需状态为已完成）',
    'project.invalid_cover_url': '无效封面地址',
    'project.invalid_image_model': '无效图片模型',
    'project.invalid_video_model': '无效视频模型',
    'project.ready_to_compose': '素材已齐，请点击合成成片',
    'project.cannot_cancel': '当前状态不可取消',
    'project.shot_list_incomplete': '镜头列表不完整',
    'project.shot_not_found': '分镜不存在',
    'project.image_text_no_video': '图文模式无需生成 AI 视频，请直接重新合成成片',
    'project.shot_image_required': '请先生成该镜画面',
    'project.no_shots': '暂无分镜，请先生成',
    'project.compose_missing_media': '缺少分镜图或镜头视频，无法合成',
    'project.not_ready_to_publish': '成片未完成，无法发布',
    'project.narration_empty': '全部镜头旁白为空，无法配音',
    'project.shot_narration_empty': '旁白为空，无法配音',
  },
}
```

- [ ] **Step 3: Tạo `frontend/src/i18n/locales/en/errors.ts`**

```ts
/** 英文：接口错误码文案（key 与 backend/app/errors.py 的 ERRORS 一致） */

export const enErrors = {
  errors: {
    'common.unsupported_image_type': 'Only JPG, PNG, WebP or GIF images are supported',
    'common.empty_file': 'The file is empty',
    'common.file_too_large': 'File must be {max_mb} MB or smaller',
    'common.invalid_image': 'This file isn’t a valid image',
    'common.user_not_found': 'Account not found',
    'auth.email_registered': 'This email is already registered',
    'auth.invalid_credentials': 'Incorrect email or password',
    'auth.wrong_current_password': 'Current password is incorrect',
    'auth.same_password': 'New password must be different from the current one',
    'auth.email_taken': 'This email is already in use',
    'auth.service_unavailable': 'Service is temporarily unavailable. Please try again later',
    'auth.reset_token_invalid': 'This reset link is invalid or has expired',
    'auth.username_required': 'Please enter a username',
    'auth.username_too_long': 'Username can be at most {max} characters',
    'auth.email_invalid': 'Invalid email format',
    'auth.phone_invalid': 'Invalid phone number format',
    'billing.insufficient_balance': 'Insufficient balance: {need} needed, {available} available. Please top up',
    'billing.insufficient_balance_pending': 'Insufficient balance: {need} needed (including {pending} queued), {available} available. Please top up',
    'billing.insufficient_balance_batch': 'Insufficient balance: {qty} items need {need} (including {pending} queued), {available} available. Please top up',
    'billing.unknown_package': 'Unknown top-up package',
    'billing.topup_unavailable': 'Top-up isn’t available yet: no receiving account is configured',
    'billing.alert_not_found': 'Alert not found',
    'billing.order_not_found': 'Order not found',
    'billing.order_paid_cannot_close': 'Paid orders can’t be cancelled',
    'billing.order_cannot_close': 'This order can’t be cancelled in its current status',
    'billing.order_closed': 'This order is cancelled and can’t be confirmed',
    'task.not_found': 'Request not found',
    'task.mock_limit': 'At most {max} test runs can run at the same time',
    'task.type_not_supported': 'This feature isn’t supported yet',
    'task.target_not_found': 'Not found, or you don’t have access',
    'task.target_mismatch': 'Data doesn’t match. Please reload the page',
    'task.invalid_payload': 'Invalid parameter: {field}',
    'task.cancel_not_supported': 'This can’t be cancelled',
    'task.already_finished': 'Already finished, can’t cancel',
    'tool.unknown': 'Unknown tool',
    'tool.missing_task': 'Missing request ID',
    'tool.run_not_found': 'Record not found',
    'tool.unsupported_file_type': 'Only png, jpg, webp, gif, mp4, mov or webm files are supported',
    'tool.prompt_required': 'Please enter a prompt',
    'tool.reference_required': 'Please upload a reference image',
    'tool.product_image_required': 'Please upload a product image',
    'tool.stitch_min_images': 'Upload at least {min} images to combine',
    'tool.video_script_required': 'Please enter a video script',
    'tool.video_source_required': 'Please upload a source video or first frame',
    'tool.first_frame_extract_failed': 'Couldn’t extract the first frame from the video',
    'tool.first_frame_required': 'A first frame image is required to generate the video',
    'tool.run_failed': 'Generation failed. Please try again later',
    'api_key.not_found': 'API key not found or already revoked',
    'template.not_found': 'Template not found',
    'project.not_found': 'Project not found',
    'project.invalid_template': 'Invalid template',
    'project.topic_required': 'Please enter a topic',
    'project.ai_generate_failed': 'AI generation failed. Please try again',
    'project.voice_preview_failed': 'Couldn’t generate the voice preview. Please try again',
    'project.full_generation_running': 'The video is being generated. Please wait',
    'project.generation_running': 'Generation in progress. Please wait',
    'project.locked_while_generating': 'Can’t edit while generating',
    'project.cover_locked': 'Can’t change the cover while generating',
    'project.download_selection_required': 'Select the videos to download',
    'project.download_limit': 'You can download up to {max} videos at once',
    'project.no_downloadable_video': 'None of the selected videos has a finished file to download',
    'project.invalid_cover_url': 'Invalid cover URL',
    'project.invalid_image_model': 'Invalid image model',
    'project.invalid_video_model': 'Invalid video model',
    'project.ready_to_compose': 'All assets are ready. Click Compose video',
    'project.cannot_cancel': 'Can’t cancel in the current status',
    'project.shot_list_incomplete': 'The scene list is incomplete',
    'project.shot_not_found': 'Scene not found',
    'project.image_text_no_video': 'Still-image videos don’t need AI video. Compose the video again instead',
    'project.shot_image_required': 'Generate the image for this scene first',
    'project.no_shots': 'No scenes yet. Generate them first',
    'project.compose_missing_media': 'Some scene images or videos are missing, so the video can’t be composed',
    'project.not_ready_to_publish': 'The video isn’t finished yet, so it can’t be published',
    'project.narration_empty': 'All scenes have empty narration, so no voice-over can be made',
    'project.shot_narration_empty': 'Narration is empty, so no voice-over can be made',
  },
}
```

- [ ] **Step 4: Tạo `frontend/src/i18n/locales/vi/errors.ts`**

```ts
/** 越南语：接口错误码文案（key 与 backend/app/errors.py 的 ERRORS 一致） */

export const viErrors = {
  errors: {
    'common.unsupported_image_type': 'Chỉ hỗ trợ ảnh JPG, PNG, WebP hoặc GIF',
    'common.empty_file': 'File trống, vui lòng chọn file khác',
    'common.file_too_large': 'File không được vượt quá {max_mb} MB',
    'common.invalid_image': 'File này không phải ảnh hợp lệ',
    'common.user_not_found': 'Không tìm thấy tài khoản',
    'auth.email_registered': 'Email này đã được đăng ký',
    'auth.invalid_credentials': 'Email hoặc mật khẩu không đúng',
    'auth.wrong_current_password': 'Mật khẩu hiện tại không đúng',
    'auth.same_password': 'Mật khẩu mới phải khác mật khẩu hiện tại',
    'auth.email_taken': 'Email này đã có người sử dụng',
    'auth.service_unavailable': 'Hệ thống đang bận, vui lòng thử lại sau',
    'auth.reset_token_invalid': 'Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn',
    'auth.username_required': 'Vui lòng nhập tên người dùng',
    'auth.username_too_long': 'Tên người dùng tối đa {max} ký tự',
    'auth.email_invalid': 'Email không đúng định dạng',
    'auth.phone_invalid': 'Số điện thoại không đúng định dạng',
    'billing.insufficient_balance': 'Số dư không đủ: cần {need}, hiện có {available}. Vui lòng nạp thêm tiền',
    'billing.insufficient_balance_pending': 'Số dư không đủ: lần này cần {need} (tính cả {pending} đang chờ), hiện có {available}. Vui lòng nạp thêm tiền',
    'billing.insufficient_balance_batch': 'Số dư không đủ: tạo {qty} mục cần {need} (tính cả {pending} đang chờ), hiện có {available}. Vui lòng nạp thêm tiền',
    'billing.unknown_package': 'Gói nạp không tồn tại',
    'billing.topup_unavailable': 'Chưa mở nạp tiền: hệ thống chưa cấu hình tài khoản nhận tiền',
    'billing.alert_not_found': 'Không tìm thấy cảnh báo',
    'billing.order_not_found': 'Không tìm thấy đơn nạp tiền',
    'billing.order_paid_cannot_close': 'Đơn đã thanh toán, không thể huỷ',
    'billing.order_cannot_close': 'Không thể huỷ đơn ở trạng thái này',
    'billing.order_closed': 'Đơn đã huỷ, không thể xác nhận đã nhận tiền',
    'task.not_found': 'Không tìm thấy yêu cầu này',
    'task.mock_limit': 'Chỉ chạy tối đa {max} lượt thử cùng lúc',
    'task.type_not_supported': 'Chức năng này chưa được hỗ trợ',
    'task.target_not_found': 'Không tìm thấy nội dung, hoặc bạn không có quyền truy cập',
    'task.target_mismatch': 'Dữ liệu không khớp, vui lòng tải lại trang',
    'task.invalid_payload': 'Tham số không hợp lệ: {field}',
    'task.cancel_not_supported': 'Không thể huỷ mục này',
    'task.already_finished': 'Đã chạy xong, không thể huỷ',
    'tool.unknown': 'Công cụ không tồn tại',
    'tool.missing_task': 'Thiếu mã yêu cầu',
    'tool.run_not_found': 'Không tìm thấy lượt tạo này',
    'tool.unsupported_file_type': 'Chỉ hỗ trợ file png, jpg, webp, gif, mp4, mov hoặc webm',
    'tool.prompt_required': 'Vui lòng nhập prompt',
    'tool.reference_required': 'Vui lòng tải lên ảnh tham chiếu',
    'tool.product_image_required': 'Vui lòng tải lên ảnh sản phẩm',
    'tool.stitch_min_images': 'Cần tải lên ít nhất {min} ảnh để ghép',
    'tool.video_script_required': 'Vui lòng nhập kịch bản video',
    'tool.video_source_required': 'Vui lòng tải lên video gốc hoặc ảnh khung hình đầu',
    'tool.first_frame_extract_failed': 'Không lấy được khung hình đầu từ video',
    'tool.first_frame_required': 'Thiếu ảnh khung hình đầu, không thể tạo video',
    'tool.run_failed': 'Tạo thất bại, vui lòng thử lại sau',
    'api_key.not_found': 'API Key không tồn tại hoặc đã bị thu hồi',
    'template.not_found': 'Không tìm thấy mẫu',
    'project.not_found': 'Không tìm thấy dự án',
    'project.invalid_template': 'Mẫu không hợp lệ',
    'project.topic_required': 'Vui lòng nhập chủ đề',
    'project.ai_generate_failed': 'AI tạo nội dung thất bại, vui lòng thử lại',
    'project.voice_preview_failed': 'Không tạo được bản nghe thử, vui lòng thử lại',
    'project.full_generation_running': 'Video đang được tạo, vui lòng đợi',
    'project.generation_running': 'Đang tạo, vui lòng đợi',
    'project.locked_while_generating': 'Đang tạo, chưa thể chỉnh sửa',
    'project.cover_locked': 'Đang tạo, chưa thể đổi ảnh bìa',
    'project.download_selection_required': 'Vui lòng chọn video cần tải',
    'project.download_limit': 'Mỗi lần tải tối đa {max} video',
    'project.no_downloadable_video': 'Các video đã chọn chưa có video hoàn chỉnh để tải',
    'project.invalid_cover_url': 'Link ảnh bìa không hợp lệ',
    'project.invalid_image_model': 'Mô hình tạo ảnh không hợp lệ',
    'project.invalid_video_model': 'Mô hình tạo video không hợp lệ',
    'project.ready_to_compose': 'Đã đủ tư liệu, hãy bấm dựng video',
    'project.cannot_cancel': 'Không thể huỷ ở trạng thái hiện tại',
    'project.shot_list_incomplete': 'Danh sách cảnh chưa đầy đủ',
    'project.shot_not_found': 'Không tìm thấy cảnh',
    'project.image_text_no_video': 'Video ảnh tĩnh không cần tạo video AI, hãy dựng lại video',
    'project.shot_image_required': 'Vui lòng tạo hình ảnh cho cảnh này trước',
    'project.no_shots': 'Chưa có phân cảnh, vui lòng tạo trước',
    'project.compose_missing_media': 'Thiếu ảnh hoặc video của cảnh, chưa thể dựng video',
    'project.not_ready_to_publish': 'Video chưa hoàn chỉnh, chưa thể đăng',
    'project.narration_empty': 'Tất cả cảnh đều chưa có lời dẫn, chưa thể tạo giọng đọc',
    'project.shot_narration_empty': 'Chưa có lời dẫn, chưa thể tạo giọng đọc',
  },
}
```

- [ ] **Step 5: Gắn vào index ngôn ngữ**

Trong `frontend/src/i18n/locales/zh.ts`: thêm `import { zhErrors } from './zh/errors'` và `...zhErrors,` cuối object `zh`. Làm tương tự với `en.ts` (`enErrors`, `./en/errors`) và `vi.ts` (`viErrors`, `./vi/errors`).

- [ ] **Step 6: Chạy test đồng bộ**

Run: `cd backend && .venv/bin/python -m pytest tests/test_app_errors.py -q -k translations`
Expected: PASS cả 3 ngôn ngữ.

- [ ] **Step 7: Viết lại `frontend/src/lib/apiError.ts`**

```ts
import { formatFenActive } from '../currency/store'
import { getActiveLocale } from '../i18n/detect'
import { interpolate, type TVars } from '../i18n/lookup'
import { messages } from '../i18n/messages'
import { markBillingMessage, notifyBillingErrorIfNeeded } from './billingError'

type CommonKey = keyof (typeof messages)['zh']['common']
type ErrorParams = Record<string, unknown>

/** 接口错误：带 HTTP 状态与后端错误码；message 已按界面语言翻译 */
export class ApiError extends Error {
  status: number
  code?: string
  params?: ErrorParams

  constructor(message: string, status: number, code?: string, params?: ErrorParams) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.params = params
  }
}

/** 按当前界面语言取通用报错兜底文案（供非 React 的 api 层使用） */
export function apiErrorText(key: CommonKey): string {
  return messages[getActiveLocale()].common[key]
}

/** 是否为余额不足类错误码（billing.insufficient_balance*） */
export function isInsufficientBalanceCode(code?: string): boolean {
  return Boolean(code && code.startsWith('billing.insufficient_balance'))
}

// 后端 params → 插值变量：*_fen 按当前展示货币格式化并去掉后缀
function toTemplateVars(params: ErrorParams): TVars {
  const vars: TVars = {}
  for (const [key, value] of Object.entries(params)) {
    if (key.endsWith('_fen') && typeof value === 'number') {
      vars[key.slice(0, -4)] = formatFenActive(value)
    } else if (typeof value === 'string' || typeof value === 'number') {
      vars[key] = value
    }
  }
  return vars
}

// detail 转可读文案：字符串原样，422 校验数组拼接 msg
function detailText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
  }
  return ''
}

/**
 * 解析接口错误响应体。
 * 文案优先级：已翻译的 code → detail → fallback → 通用「请求失败」。
 */
export function parseApiError(status: number, body: unknown, fallback?: string): ApiError {
  const data = (body && typeof body === 'object' ? body : {}) as {
    detail?: unknown
    code?: unknown
    params?: unknown
  }
  const code = typeof data.code === 'string' ? data.code : undefined
  const params =
    data.params && typeof data.params === 'object' ? (data.params as ErrorParams) : undefined
  const table = messages[getActiveLocale()].errors as Record<string, string>
  const template = code ? table[code] : undefined
  const message =
    (template ? interpolate(template, toTemplateVars(params || {})) : '') ||
    detailText(data.detail) ||
    fallback ||
    apiErrorText('requestFailed')
  if (isInsufficientBalanceCode(code)) markBillingMessage(message)
  return new ApiError(message, status, code, params)
}

/** 解析并抛出接口错误；402 / 余额不足时弹出充值引导 */
export function throwApiError(status: number, body: unknown, fallback?: string): never {
  const error = parseApiError(status, body, fallback)
  notifyBillingErrorIfNeeded(status, error.message)
  throw error
}
```

- [ ] **Step 8: Sửa `frontend/src/lib/billingError.ts`**

Thay hàm `isBillingError` bằng:

```ts
// 由错误码识别出的余额不足文案（翻译后不再含「余额不足」，靠登记识别）
const billingMessages = new Set<string>()

/** 登记一条余额不足文案，供只拿到字符串的组件识别 */
export function markBillingMessage(message: string) {
  billingMessages.add(message)
}

/** 是否为余额不足 / 计费拦截类错误（错误码登记 + 旧中文文案兜底，漫剧第二阶段前保留） */
export function isBillingError(message: string) {
  return billingMessages.has(message) || /余额不足|请先充值|402|insufficient_balance/i.test(message)
}
```

- [ ] **Step 9: Chuyển các chỗ tự đọc lỗi sang `throwApiError` / `parseApiError`**

`frontend/src/api.ts`:
- trong `request`: `throwApiError(res.status, err.detail, res.statusText)` → `throwApiError(res.status, err, res.statusText)`
- 4 khối upload/download: thay toàn bộ phần từ `const detail = err.detail` tới `throw new Error(...)` bằng một dòng, giữ nguyên fallback tương ứng:
  - `throwApiError(res.status, err, apiErrorText('avatarUploadFailed'))`
  - `throwApiError(res.status, err, apiErrorText('coverUploadFailed'))`
  - `throwApiError(res.status, err, apiErrorText('zipDownloadFailed'))`
  - `throwApiError(res.status, err, apiErrorText('frameUploadFailed'))`

`frontend/src/api/tools.ts`:
- đổi import thành `import { apiErrorText, parseApiError, throwApiError } from '../lib/apiError'`
- 4 dòng `if (res.status === 401) throw new Error(apiErrorText('loginRequired'))` → `if (res.status === 401) throw parseApiError(401, null, apiErrorText('loginRequired'))`
- `throwApiError(res.status, err.detail, apiErrorText('generateFailed'))` → `throwApiError(res.status, err, apiErrorText('generateFailed'))`
- `throw new Error(errorMessage(err.detail, apiErrorText('queryFailed')))` → `throwApiError(res.status, err, apiErrorText('queryFailed'))`
- 2 chỗ `throw new Error(errorMessage(err.detail, apiErrorText('loadFailed')))` → `throwApiError(res.status, err, apiErrorText('loadFailed'))`
- xoá hàm `errorMessage` (không còn dùng).

`frontend/src/api/tasks.ts:29`: `throwApiError(res.status, err.detail, \`HTTP ${res.status}\`)` → `throwApiError(res.status, err, \`HTTP ${res.status}\`)`

`frontend/src/api/drama.ts:62`: `throwApiError(res.status, err.detail, '请求失败')` → `throwApiError(res.status, err, '请求失败')` (giữ câu dự phòng — drama làm ở giai đoạn 2).

`frontend/src/api/apiKeys.ts`: đổi import thành `import { apiErrorText, throwApiError } from '../lib/apiError'`; thay phần từ `const detail = err.detail` tới `throw new Error(message || apiErrorText('requestFailed'))` bằng `throwApiError(res.status, err, apiErrorText('requestFailed'))`.

`frontend/src/api/agentSkills.ts`: đổi import thành `import { apiErrorText, throwApiError } from '../lib/apiError'`;
- trong `request`: thay `const detail = err.detail` + `throw new Error(typeof detail === 'string' ? detail : apiErrorText('requestFailed'))` bằng `throwApiError(res.status, err, apiErrorText('requestFailed'))`
- trong hàm upload: `throw new Error(typeof err.detail === 'string' ? err.detail : apiErrorText('uploadFailed'))` → `throwApiError(res.status, err, apiErrorText('uploadFailed'))`

Kiểm tra không còn chỗ nào truyền `err.detail`:

Run: `cd frontend && grep -rn "throwApiError(res.status, err.detail\|errorMessage(err.detail" src`
Expected: không có kết quả.

- [ ] **Step 10: Typecheck, lint, build**

Run: `cd frontend && npx tsc -b && npm run lint && npm run build`
Expected: `tsc` không lỗi; lint exit 0 và không có cảnh báo mới ở các file vừa sửa; build `✓ built`.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/i18n/locales frontend/src/lib/apiError.ts frontend/src/lib/billingError.ts frontend/src/api.ts frontend/src/api backend/tests/test_app_errors.py
git commit -m "feat: frontend dịch lỗi API theo mã lỗi

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Frontend — bỏ so câu chữ trong trang

**Files:**
- Modify: `frontend/src/pages/studio/StoryboardPage.tsx:322-324`
- Modify: `frontend/src/pages/studio/StyleConfigPage.tsx:217-219`
- Modify: `frontend/src/pages/ToolDetailPage.tsx:191-193`

**Interfaces:**
- Consumes: `ApiError` từ `frontend/src/lib/apiError.ts` (Task 7).

- [ ] **Step 1: `StoryboardPage.tsx`**

Thêm import `import { ApiError } from '../../lib/apiError'`. Trong `continueGenerate`, thay:

```tsx
      if (msg.includes('合成成片')) {
```

bằng:

```tsx
      if (err instanceof ApiError && err.code === 'project.ready_to_compose') {
```

Nếu biến `msg` chỉ còn dùng ở nhánh `else` thì giữ nguyên dòng khai báo `msg`.

- [ ] **Step 2: `StyleConfigPage.tsx`**

Thêm import `import { ApiError } from '../../lib/apiError'`. Thay `if (msg.includes('合成成片')) {` bằng `if (err instanceof ApiError && err.code === 'project.ready_to_compose') {`.

- [ ] **Step 3: `ToolDetailPage.tsx`**

Thêm import `import { ApiError } from '../lib/apiError'`. Thay:

```tsx
      if (message === t('common.loginRequired')) {
```

bằng:

```tsx
      if (err instanceof ApiError && err.status === 401) {
```

- [ ] **Step 4: Kiểm tra không còn so câu tiếng Trung ngoài drama**

Run: `cd frontend/src && grep -rn "includes('合成成片')\|=== '未登录'" . | grep -v drama`
Expected: không có kết quả.

- [ ] **Step 5: Typecheck, lint, build**

Run: `cd frontend && npx tsc -b && npm run lint && npm run build`
Expected: như Task 7 Step 10.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/studio/StoryboardPage.tsx frontend/src/pages/studio/StyleConfigPage.tsx frontend/src/pages/ToolDetailPage.tsx
git commit -m "refactor: nhận biết lỗi bằng mã lỗi thay vì so câu chữ

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Tài liệu và kiểm tra cuối

**Files:**
- Modify: `docs/I18N.md` (thêm mục "Mã lỗi API", cập nhật "分阶段进度")

- [ ] **Step 1: Cập nhật `docs/I18N.md`**

Thêm trước mục `## 分阶段进度`:

```markdown
## 接口错误码

后端业务错误统一用 `app/errors.py` 的 `AppError(code, **params)`，响应体为 `{detail, code, params}`：`detail` 保持中文（兼容管理端、漫剧与开放 API），前端 `lib/apiError.ts` 的 `parseApiError()` 按 `code` 查 `i18n/locales/{zh,en,vi}/errors.ts` 翻译，查不到才显示 `detail`。

- 新增错误码：在 `ERRORS` 登记 `(状态码, 中文模板)`，并在三份 `errors.ts` 各加一行；`tests/test_app_errors.py` 会校验三份文案与目录一致。
- `params` 只放原始数据；金额用 `*_fen`（分），模板占位符去掉后缀（`need_fen` → `{need}`），前后端各自按展示货币格式化。
- 不要把上游 / 第三方报错原文放进 `detail` 或 `params`，记日志即可。
- 组件按 `err instanceof ApiError && err.code === '…'`（或 `err.status`）判断，不要比对文案。
```

Và trong `## 分阶段进度`, dòng "已完成" thêm `、接口错误码（科普 / 工具 / 账号 / 计费 / 任务）`; dòng "待办" thêm `；漫剧与管理端接口仍返回中文 detail，任务落库的 error_message 未做错误码`.

- [ ] **Step 2: Rà lại tiếng Trung còn sót trong phạm vi**

Run: `cd backend/app && grep -nP 'detail=.*[\x{4e00}-\x{9fff}]' api/auth.py api/billing.py api/tasks.py api/tools.py api/api_keys.py api/templates.py api/projects.py`
Expected: không có kết quả.

Run: `cd backend/app && grep -nP 'raise ValueError\(.*[\x{4e00}-\x{9fff}]' services/tasks/service.py services/tasks/handlers.py services/studio_tools.py services/billing/settlement.py services/billing/topup.py`
Expected: không có kết quả.

Run: `cd backend/app && grep -n "detail=str(exc)" api/auth.py api/billing.py api/tasks.py api/tools.py api/projects.py`
Expected: không có kết quả.

- [ ] **Step 3: Chạy toàn bộ test backend**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: không có FAIL. Nếu Postgres không bật, test dùng `db_session` sẽ ERROR vì kết nối — ghi số lượng và báo rõ là chưa chạy được, không coi là đạt.

- [ ] **Step 4: Chạy app và kiểm tra thực tế**

Khởi động backend (`cd backend && .venv/bin/uvicorn app.main:app --port 8000`) và frontend (`cd frontend && npm run dev`). Với giao diện **tiếng Việt** rồi **tiếng Anh**, kiểm tra:
1. Đăng nhập sai mật khẩu → thấy "Email hoặc mật khẩu không đúng" / "Incorrect email or password".
2. Đăng xuất, vào `/tools/t2i` bấm tạo → được chuyển sang trang đăng nhập.
3. Với `BILLING_ENABLED=true` và tài khoản số dư 0, tạo ảnh ở trang công cụ → thấy câu "Số dư không đủ: cần … ₫, hiện có 0 ₫…" và hộp nhắc nạp tiền hiện ra.
4. Kiểm tra response trong DevTools có `code` và `params`.

Ghi lại kết quả từng mục (đạt / không đạt / không kiểm được vì sao).

- [ ] **Step 5: Commit**

```bash
git add docs/I18N.md
git commit -m "docs: hướng dẫn thêm mã lỗi API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
