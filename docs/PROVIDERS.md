# Lớp Provider (OpenAI + BytePlus ModelArk)

> Sau khi bỏ TokenFree (Plan A), backend gọi thẳng từng upstream (OpenAI, BytePlus ModelArk, BytePlus Seed
> Speech) qua một lớp adapter mỏng. Tài liệu này mô tả kiến trúc, cách thêm provider mới, danh sách model
> tĩnh, cấu hình `function_bindings`, và các giới hạn cần biết. Xem thêm lịch sử thiết kế ở
> `docs/superpowers/specs/2026-09-22-provider-migration-design.md`.

## 1. Kiến trúc adapter

Toàn bộ code gọi upstream nằm trong `backend/app/services/providers/`:

- **`base.py`** — types dùng chung (`ImageRequest/ImageOutput`, `VideoRequest`, `TtsRequest`, `TaskResult`),
  hằng số timeout, và `Protocol` `ProviderAdapter` mà mọi adapter phải hiện thực:
  - `list_models(route, capability)` — danh sách model khả dụng cho năng lực (`text|image|video|audio`)
  - `gen_image(route, req)` — sinh ảnh, trả `ImageOutput` (bytes base64 hoặc URL)
  - `create_video(route, req)` — tạo tác vụ video, trả `task_id` (async, cần poll)
  - `fetch_video(route, task_id)` — tra một lần trạng thái tác vụ, trả `TaskResult`
  - `tts(route, req)` — chuyển văn bản thành audio bytes
  - `cost_fen(model, raw_usage)` — ước tính chi phí (Plan B mới có bảng giá thật; hiện trả `None`)
  - `url_needs_auth(url)` — URL kết quả có cần Bearer khi tải lại không
  - `is_transient_error(exc)` — lỗi có tạm thời không (được phép failover sang model kế tiếp trong cùng slot)
- **`registry.py`** — `get_adapter(protocol)` trả về **adapter singleton** theo `protocol`
  (`openai|ark|volc_tts`; rỗng/`auto` coi là `openai`); import từng adapter theo kiểu lazy để tránh vòng
  import. `url_needs_auth(url)` ở module-level hỏi lượt tất cả adapter đã biết.
- **`presets.py`** — `PROVIDER_PRESETS`: danh sách preset gợi ý khi admin thêm provider mới (id, tên,
  protocol, base URL mặc định, cách lấy catalog model). Hiện có: `openai`, `byteplus` (BytePlus ModelArk),
  `openrouter`, `volc_tts` (BytePlus Seed Speech), `custom_openai`.
- **`openai_adapter.py`** — `OpenAIAdapter` (protocol `openai`): dùng cho OpenAI chính chủ, OpenRouter, hoặc
  bất kỳ endpoint tương thích OpenAI. `/images/generations` hoặc `/images/edits` (có ref ảnh) trả base64;
  `/audio/speech` cho TTS; `GET /models` cho danh sách model (tự suy luận capability, loại bỏ `video` vì
  OpenAI không còn API tạo video). **Không hỗ trợ video** (`create_video`/`fetch_video` raise
  `ProviderNotSupported`).
- **`ark_adapter.py`** — `ArkAdapter` (protocol `ark`): BytePlus ModelArk / Volcengine Ark. Seedream (ảnh,
  đồng bộ, `POST /images/generations`) + Seedance (video, `POST/GET /contents/generations/tasks`, task +
  poll). Không có `GET /models` nên dùng danh sách tĩnh `ARK_STATIC_MODELS` (xem mục 3). Không hỗ trợ TTS.
  Chứa các heuristics xử lý lỗi kiểm duyệt/chính sách của Seedream/Seedance (làm dịu prompt, thêm phong
  cách CG, bỏ tham chiếu âm thanh lỗi…) — không liên quan tới việc chọn provider, chỉ là retry nội bộ trong
  một model.
- **`volc_tts_adapter.py`** — `VolcTtsAdapter` (protocol `volc_tts`): BytePlus Seed Speech / Volcengine
  openspeech (`VOLC_TTS_*`, key khác với Ark/OpenAI). Chỉ hỗ trợ `tts`.

**Facade duy nhất mà pipeline/drama/tools gọi:** `backend/app/services/media_gateway.py`
(`MediaGateway` / `get_media_gateway()`). Facade **không chứa HTTP** — nó resolve route theo chức năng
(`function_router.resolve_function_candidates`), gọi `get_adapter(route.protocol)`, và xử lý phần
"nghiệp vụ" chung (lưu file local/OSS, mock khi không có key, retry giữa các model trong slot khi lỗi tạm
thời, ghi nhớ `channel_id` đã tạo tác vụ để poll đúng kênh). TTS còn có thêm `tts_service.py` (cascade
mock → model trong slot Giọng đọc → edge-tts) mà `MediaGateway.tts()` ủy quyền tới.

### Cách thêm provider mới

1. Tạo file `app/services/providers/<ten>_adapter.py`, hiện thực class thỏa `ProviderAdapter` (xem
   `base.py`), đặt `protocol = "<ten_protocol>"`.
2. Đăng ký trong `registry.get_adapter()`: thêm một nhánh `elif proto == "<ten_protocol>": from ... import
   ... as cls`.
3. Nếu muốn xuất hiện trong danh sách preset ở màn hình admin, thêm một `ProviderPreset` vào
   `presets.PROVIDER_PRESETS` (id, name, protocol, base_url mặc định, `catalog` là `"remote"` nếu provider
   có `GET /models`, `"static"` nếu dùng danh sách cứng, `"none"` nếu không có catalog).
4. Nếu catalog là `static`, định nghĩa danh sách `list[dict[str, str]]` (`id/label/capability`) ngay trong
   adapter (theo mẫu `ARK_STATIC_MODELS`) và truyền vào preset.
5. Không cần sửa `function_router.py`/`media_gateway.py` — chúng chỉ biết đến `protocol` string và gọi qua
   `get_adapter()`, không import trực tiếp class adapter cụ thể (trừ vài helper Seedance/TTS được
   `MediaGateway` expose lại để giữ tương thích test cũ).
6. Cập nhật `backend/.env.example` nếu provider cần biến môi trường seed lần đầu, và tài liệu này (mục 3)
   nếu có danh sách model tĩnh mới.

## 2. Danh sách model tĩnh BytePlus (Ark)

BytePlus ModelArk không có `GET /models`, nên `ArkAdapter.list_models()` trả về danh sách cứng
`ARK_STATIC_MODELS` khai báo ở đầu `backend/app/services/providers/ark_adapter.py` (cập nhật lần cuối
2026-09-22):

| id | label | capability |
|---|---|---|
| `dola-seedream-5-0-pro-260628` | Seedream 5.0 Pro | image |
| `dola-seedream-5-0-flash-260915` | Seedream 5.0 Flash | image |
| `seedream-5-0-260128` | Seedream 5.0 Lite | image |
| `seedream-4-5-251128` | Seedream 4.5 | image |
| `seedream-4-0-250828` | Seedream 4.0 | image |
| `dreamina-seedance-2-5-260628` | Seedance 2.5 | video |
| `dreamina-seedance-2-0-260128` | Seedance 2.0 | video |
| `dreamina-seedance-2-0-fast-260128` | Seedance 2.0 Fast | video |
| `dreamina-seedance-2-0-mini-260615` | Seedance 2.0 Mini | video |
| `seedance-1-0-pro-250528` | Seedance 1.0 Pro | video |
| `dola-seed-2-1-turbo-260628` | Seed 2.1 Turbo | text |
| `seed-2-0-pro-260328` | Seed 2.0 Pro | text |
| `seed-2-0-lite-260428` | Seed 2.0 Lite | text |
| `deepseek-v4-pro-ga-260813` | DeepSeek V4 Pro | text |
| `deepseek-v4-flash-ga-260731` | DeepSeek V4 Flash | text |

**Cách cập nhật:** sửa trực tiếp mảng `ARK_STATIC_MODELS` trong `ark_adapter.py` (thêm/xoá/đổi tên model
theo console BytePlus ModelArk), rồi cập nhật bảng trên cho khớp. Model mới chỉ dùng được sau khi admin
thêm nó vào `models` của provider `ark`/`byteplus` (mục "Providers" ở `/settings/routing`) **và** gán nó
vào một slot/override trong `function_bindings` (mục 4) — có trong `ARK_STATIC_MODELS` không có nghĩa là
tự động khả dụng cho một chức năng.

`VOLC_TTS_STATIC_MODELS` (BytePlus Seed Speech) cũng là danh sách tĩnh tương tự, khai báo trong
`volc_tts_adapter.py`.

## 3. `function_bindings`: gán model theo chức năng

Danh mục chức năng cố định (`backend/app/services/functions.py`, `FUNCTIONS`):

| id | capability | Mô tả |
|---|---|---|
| `kepu.script` | text | Mở rộng chủ đề + tách phân cảnh video khoa học |
| `drama.script` | text | Tóm tắt, chia tập, tách phân cảnh, viết prompt phim ngắn |
| `kepu.image` | image | Ảnh tĩnh từng phân cảnh video khoa học |
| `drama.asset_image` | image | Nhân vật, bối cảnh, đạo cụ và ảnh tĩnh phân cảnh phim ngắn |
| `tools.image` | image | Công cụ t2i/i2p và `/api/v1/images` |
| `kepu.video` | video | Video từng phân cảnh video khoa học |
| `drama.video` | video | Video phân cảnh và video tài sản phim ngắn |
| `tools.video` | video | Công cụ t2v/i2v và `/api/v1/videos` |
| `kepu.tts` | audio | Giọng đọc lời bình video khoa học |
| `drama.tts` | audio | Giọng nhân vật và mẫu giọng phim ngắn |

`FunctionBindings` (`app/schemas_routing.py`) có hai lớp, và `effective_bindings()`
(`function_bindings.py`) luôn **ưu tiên override của đúng function_id, không có mới rơi về slot theo
capability**:

- `slots: dict[capability, list[ModelBinding]]` — mặc định cho cả 4 năng lực (`text|image|video|audio`),
  áp dụng cho mọi chức năng thuộc năng lực đó nếu chức năng không có override riêng.
- `overrides: dict[function_id, list[ModelBinding]]` — gán riêng cho một chức năng cụ thể, đè lên slot.

`ModelBinding = {channel_id, model, weight}` — nhiều binding trong cùng một slot/override được chọn theo
**weight** (xác suất, không phải ưu tiên tuyệt đối) qua `_weighted_order()`, và khi một model bị lỗi tạm
thời (`is_transient_error`), `media_gateway._try_candidates()` thử model kế tiếp trong danh sách đó
(failover). Model do người dùng chỉ định (ví dụ chọn model cụ thể ở tools) luôn được thử trước, các
binding còn lại xáo trộn theo weight sau nó.

Ví dụ JSON `function_bindings` với 1 slot ảnh 2 model (weight 70/30) + 1 override video riêng cho drama:

```json
{
  "slots": {
    "text": [{"channel_id": "openai", "model": "gpt-5.6-sol", "weight": 1}],
    "image": [
      {"channel_id": "byteplus", "model": "dola-seedream-5-0-pro-260628", "weight": 70},
      {"channel_id": "openai", "model": "gpt-image-2.5", "weight": 30}
    ],
    "video": [{"channel_id": "byteplus", "model": "dreamina-seedance-2-5-260628", "weight": 1}],
    "audio": [{"channel_id": "openai", "model": "gpt-4o-mini-tts", "weight": 1}]
  },
  "overrides": {
    "drama.video": [
      {"channel_id": "byteplus", "model": "dreamina-seedance-2-0-fast-260128", "weight": 1}
    ]
  }
}
```

### Cấu hình qua curl khi chưa có UI

`GET/PATCH /api/admin/settings/routing` (`backend/app/api/admin/settings.py`) đọc/ghi toàn bộ cấu hình
provider + function_bindings, yêu cầu admin đăng nhập (Bearer token của user có quyền admin).

```bash
# 1) Đọc cấu hình hiện tại (providers + function_bindings + readiness)
curl -s http://127.0.0.1:8000/api/admin/settings/routing \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# 2) Ghi 2 provider (OpenAI + BytePlus ModelArk) và function_bindings mẫu ở trên
curl -s -X PATCH http://127.0.0.1:8000/api/admin/settings/routing \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "providers": [
      {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-...",
        "protocol": "openai",
        "models": ["gpt-5.6-sol", "gpt-image-2.5", "gpt-4o-mini-tts"],
        "enabled": true
      },
      {
        "id": "byteplus",
        "name": "BytePlus ModelArk",
        "base_url": "https://ark.ap-southeast.bytepluses.com/api/v3",
        "api_key": "ark-...",
        "protocol": "ark",
        "models": ["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"],
        "enabled": true
      }
    ],
    "function_bindings": {
      "slots": {
        "text": [{"channel_id": "openai", "model": "gpt-5.6-sol", "weight": 1}],
        "image": [{"channel_id": "byteplus", "model": "dola-seedream-5-0-pro-260628", "weight": 1}],
        "video": [{"channel_id": "byteplus", "model": "dreamina-seedance-2-5-260628", "weight": 1}],
        "audio": [{"channel_id": "openai", "model": "gpt-4o-mini-tts", "weight": 1}]
      },
      "overrides": {}
    }
  }' | jq .
```

Gửi `providers` mà không có `api_key` (hoặc bỏ trường `api_key`) giữ nguyên key đã lưu; gửi
`"clear_api_key": true` để xoá key. Response `AdminRoutingSettingsSaveOut.applied` cho biết những phần nào
đã được lưu (`providers`, `function_bindings`); lỗi validate (provider không tồn tại, model chưa bật ở
provider, model sai capability…) trả `HTTP 400` với message tiếng Việt từ
`function_bindings.validate_function_bindings()`.

`GET /api/media-models?scope=<kepu|drama|tools>` (public, không cần admin) trả danh sách model đang khả
dụng cho từng nhóm chức năng — dùng để hiển thị dropdown chọn model ở frontend, không dùng để cấu hình.

## 4. Giới hạn cần biết

- **OpenAI không có video.** `OpenAIAdapter.create_video`/`fetch_video` luôn raise
  `ProviderNotSupported`. Slot/override năng lực `video` chỉ nên gán provider `ark` (BytePlus ModelArk).
  OpenAI Videos API / Sora 2 đã bị gỡ khỏi API công khai (2026-09-24) nên sẽ không được thêm lại trong
  tương lai gần.
- **URL kết quả ảnh/video của BytePlus (Seedream/Seedance) là URL công khai nhưng hết hạn sau 24 giờ.**
  `ArkAdapter.url_needs_auth()` luôn trả `False` (không cần Bearer để tải), nhưng facade phải tải ngay về
  local/OSS sau khi tác vụ thành công — không lưu URL đó lại để tải sau. `media_gateway.py` đã làm đúng
  điều này (`save_video_assets_from_result` tải về `static/generated/...` ngay khi poll xong).
  Nếu viết thêm tính năng dùng lại URL đã trả (ví dụ hiển thị preview trước khi ghi đĩa), phải tải xong
  trong vòng 24h kể từ khi tác vụ hoàn tất.
- **Ark không có `GET /models`** nên danh sách model phụ thuộc vào việc cập nhật tay `ARK_STATIC_MODELS`
  (mục 2) — model mới ra mắt ở console BytePlus sẽ không tự xuất hiện.
- **OpenAI-compatible (OpenRouter, `custom_openai`) không tạo video** vì dùng chung `OpenAIAdapter`; nếu
  cần video từ endpoint OpenAI-compatible khác Ark, phải viết adapter riêng (mục 1).
- **`cost_fen()` của cả hai adapter hiện trả `None`** (chưa có bảng giá `provider_rates`) — chi phí ước
  tính đóng băng/quyết toán dùng hằng số cũ trong `services/billing/` cho tới khi Plan B thêm bảng giá
  thật theo provider.
- **`tokenfree_pricing.py` / `tokenfree_usage.py` vẫn còn trong repo có chủ đích** (dùng cho màn admin
  "So sánh dùng lượng upstream", Plan B sẽ xoá). Lưu ý an ninh đã biết:
  `tokenfree_usage.resolve_tokenfree_api_key()` khi không tìm được provider tên `tokenfree`/base URL chứa
  `tokenfree.com` sẽ **fallback sang dùng key OpenAI hoặc Ark hiện có** để gọi thử endpoint đối chiếu quota
  — nghĩa là màn admin-only này có thể âm thầm dùng key OpenAI/Ark của bạn cho một mục đích khác với lúc
  cấu hình. Không phải lỗi chặn release (chỉ admin truy cập được), nhưng cần Plan B xử lý khi xoá
  TokenFree hoàn toàn.
- **Mock khi chưa có key**: đặt `ARK_MOCK=true`, hoặc không cấu hình bất kỳ provider nào có `api_key` —
  `MediaGateway.mock` sẽ tự phát hiện (`get_routing_snapshot().channels` không có channel nào
  `enabled` + có key) và chuyển toàn bộ ảnh/video/TTS sang sinh dữ liệu giả cục bộ (`static/mock/...`),
  không gọi upstream.
