# Bỏ TokenFree, gọi thẳng provider: OpenAI + BytePlus ModelArk

- Ngày: 2026-09-22
- Trạng thái: đã duyệt thiết kế, chờ lập kế hoạch
- Liên quan: `docs/BILLING.md`, `docs/SEEDANCE_2_5.md`, `CLAUDE.md` mục "模型路由"

## 1. Mục tiêu

1. **Gỡ hẳn TokenFree** (New API aggregator) khỏi mã nguồn: không còn base URL bị khoá, không còn quota `500000 = 1 USD`, không còn các hack `/responses`, `/videos`, Omni SSE.
2. Gọi thẳng hãng qua **lớp adapter theo protocol**: `openai` (OpenAI, OpenRouter, OpenAI-compatible), `ark` (BytePlus ModelArk / Volcengine Ark), `volc_tts` (BytePlus Seed Speech / Volc openspeech). Thêm provider sau này = thêm một file adapter.
3. Admin cấu hình theo mô hình **"Provider ↔ Gán chức năng AI"**: cột trái là danh sách provider (key, model bật), cột phải là 4 slot năng lực (Văn bản / Ảnh / Video / Giọng đọc) + ghi đè theo từng chức năng, mỗi slot nhiều model chia luân phiên theo weight.
4. **Giữ nguyên mô hình platform-key**: chỉ admin cấu hình, user chỉ chọn trong danh sách admin đã bật, chi phí trừ ví như cũ. Không BYOK.
5. **Tiêu chí nghiệm thu cứng**: mọi chức năng phía user (khoa học, phim ngắn, công cụ, Open API, TTS, billing) chạy tốt như trước — checklist ở mục 9.

## 2. Không làm (biên giới rõ)

- Không thêm slot "Hiểu ảnh" (vision) — chưa có chức năng dùng.
- Không viết sẵn adapter cho fal.ai / Replicate / Gemini / Kling. Interface phải đủ để thêm sau.
- Không dùng OpenAI video: Videos API / Sora 2 bị gỡ ngày 2026-09-24. Video chỉ đi qua `ark`.
- Không đổi đơn vị ví (`fen`), không đổi `resolve_kepu_billing_phase()`, không đổi luồng nạp tiền chuyển khoản.
- Không Việt hoá phần admin còn lại; chỉ màn hình mới viết tiếng Việt.
- Không đổi tên field cấu hình `ARK_*` / `ark_*` (chỉ đổi nhãn hiển thị) để tránh churn ở overlay, schema và test.
- Không giữ tương thích ngược với cấu hình TokenFree cũ: kênh `tokenfree` bị xoá lúc khởi động; admin gán lại.

## 3. Hiện trạng (kết quả khảo sát, tóm tắt)

- Kiến trúc đa kênh **vẫn còn nguyên**: `system_model_channels` có `base_url / api_key / protocol ∈ {openai, ark, volc_tts, kie, auto} / models[]`; `logical_model_router.py` resolve nhiều kênh; `llm_client.py` OpenAI-compatible generic.
- Khoá TokenFree nằm ở 3 chỗ trong `model_settings.py` (`_bootstrap_channels_from_env`, `_ensure_tokenfree_channel`, `patch_admin_routing_settings`) + `tokenfree_gateway.apply_tokenfree_flat_overlay` ghi đè `ark_base_url/openai_base_url` toàn cục + `get_admin_routing_settings` lọc chỉ còn kênh tokenfree.
- `ark.py` (2 427 dòng) chứa 3 phương ngữ: Ark-native, OpenAI-shaped, TokenFree. Phương ngữ TokenFree móc vào qua `_url/_route_url` (remap path), `_video_json` (bọc body), `_finalize_video_result` + `download_result_media` (URL cần Bearer); riêng ảnh rẽ nhánh inline trong `_seedream_once`.
- **Poll bỏ qua route**: `poll_task/fetch_task_once` dùng `settings.ark_base_url` + key toàn cục; `TaskRun` không có cột provider (chỉ `TaskStep.provider_name`, chưa ai ghi).
- **Bug sẵn có**: `gen_and_wait_video(model=…)` không truyền `model` xuống `gen_video_i2v` → khoa học luôn dùng model video mặc định, bỏ qua `project.video_model`.
- Logical model **không do admin tạo** mà được tái sinh từ `channel.models[]` mỗi lần đọc/ghi; alias `{seedream-5.0, seedream-4.5, seedance-2.5, seedance-2}` hard-code ở 4 chỗ; `weight` chỉ là khoá sắp xếp, không luân phiên.
- Billing: `parse_upstream_cost_fen` gộp quota New API + yuan Volcano + credit Kie; `UsageEvent.provider` đoán bằng dò chuỗi "kie"; `upstream_usage_daily` giả định đúng 1 tài khoản upstream.
- Admin không có i18n; chuỗi tiếng Trung inline. Không có pattern master-detail sẵn.

## 4. Lớp adapter provider (backend)

### 4.1 Gói `app/services/providers/`

```
providers/
  base.py           # dataclass request/response + Protocol ProviderAdapter + registry get_adapter(protocol)
  openai_adapter.py # text quirks, /images/generations|edits, /audio/speech, GET /models
  ark_adapter.py    # /images/generations, /contents/generations/tasks[/id], danh sách model tĩnh
  volc_tts_adapter.py # openspeech / Seed Speech unidirectional (bọc _tts_openspeech hiện có)
  presets.py        # preset provider cho admin: id, tên, protocol, base_url mặc định, cách lấy catalog
```

Interface (async, nhận `ResolvedModelRoute` để biết `base_url / api_key / upstream_model`):

| Phương thức | Trả về | Ghi chú |
|---|---|---|
| `list_models(route, capability)` | `[{id, label, capability}]` | openai: `GET /models` + suy luận năng lực; ark: danh sách tĩnh có nhãn (không có `/models`) |
| `gen_image(route, ImageRequest)` | `ImageOutput(bytes | url, usage, size)` | facade lo lưu file/publish |
| `create_video(route, VideoRequest)` | `task_id: str` | openai: `NotSupported` |
| `fetch_video(route, task_id)` | `TaskResult` | status ∈ `queued/running/succeeded/failed/cancelled` |
| `tts(route, TtsRequest)` | `bytes` | mp3 |
| `cost_fen(model, raw_usage)` | `int | None` | tra bảng giá (mục 6) |
| `url_needs_auth(url)` | `bool` | thay cho `is_tokenfree_*_url` |
| `is_transient_error(exc)` | `bool` | dùng cho failover lúc tạo |

`ImageRequest`: `prompt, size (nội bộ: "1K/2K/3K/4K" hoặc "WxH"), refs[], style_refs[], output_format`. `VideoRequest`: giữ shape Ark hiện tại làm chuẩn nội bộ (`content[]` với `text / image_url{role} / audio_url`, `duration, resolution, ratio, generate_audio, return_last_frame, watermark=False`) vì đó là shape giàu nhất và toàn bộ drama/kepu đã dựng theo nó. `TaskResult` giữ dataclass hiện có, thêm `channel_id`.

### 4.2 `openai_adapter`

- Ảnh: không ref → `POST /images/generations`; có ref → `POST /images/edits` (JSON, `images[]` ≤ 16, mỗi phần tử `{image_url}` https hoặc data URI). `size` map: `1K` → `1024x1024`, `2K` + tỉ lệ → `1536x1024` / `1024x1536` / `1024x1024`; model `gpt-image-2*` / `gpt-image-2.5*` cho phép `WxH` chia hết 16 → dùng `WxH` tính từ tỉ lệ mong muốn. `quality` từ `ark_image_size` map (`1K→low, 2K→medium, ≥3K→high`). Kết quả **luôn base64** → facade ghi file.
- TTS: `POST /audio/speech` `{model, input, voice, response_format: "mp3"}`; voice map từ speaker nội bộ (`zh_female_*`, `S_*`, preset) → `marin/cedar/alloy/…` theo giới tính suy ra; `instructions` từ `emotion_hint` khi model là `gpt-4o-mini-tts`.
- Text: `llm_client.py` giữ nguyên, thêm: protocol `openai` gửi `max_completion_tokens` thay `max_tokens`; `response_format` giữ.
- `url_needs_auth` luôn `False`.

### 4.3 `ark_adapter`

- Chuyển nguyên nhánh Ark từ `ark.py`: `/images/generations` (`image` scalar-or-list, `watermark: False`, `response_format: "url"`, `size` clamp theo model: 5.0 pro/flash `1K/1.5K/2K`, lite/4.5 `2K/3K/4K`), `/contents/generations/tasks` + `GET …/{id}`.
- Rule Seedance đặt trong adapter: `resolve_seedance_i2v_image_role` (ratio chỉ đi cùng `reference_image`), 4 tầng retry tạo task (plain prompt → CG style khi policy → bỏ `ratio` → `adaptive`), phân loại lỗi privacy/policy (`_is_seedance_*`), `_format_seedance_create_error`, `MAX_REFERENCE_IMAGES` thành thuộc tính adapter (2.5: 30, 2.0: 9 → lấy 9 làm mặc định an toàn).
- Nhận diện host: `bytepluses.com`, `volces.com`, `volcengineapi.com`. Base URL mặc định `https://ark.ap-southeast.bytepluses.com/api/v3`.
- Danh sách model tĩnh (cập nhật 2026-09-22): ảnh `dola-seedream-5-0-pro-260628`, `dola-seedream-5-0-flash-260915`, `seedream-5-0-260128`, `seedream-4-5-251128`, `seedream-4-0-250828`; video `dreamina-seedance-2-5-260628`, `dreamina-seedance-2-0-260128`, `dreamina-seedance-2-0-fast-260128`, `dreamina-seedance-2-0-mini-260615`, `seedance-1-0-pro-250528`; text `seed-2-0-pro-260328`, `seed-2-0-lite-260428`, `deepseek-v4-pro-ga-260813`… Admin vẫn nhập thêm ID thủ công được (endpoint ID `ep-…`).
- `url_needs_auth` luôn `False` (URL kết quả công khai nhưng hết hạn 24 h → tải ngay như hiện nay).

### 4.4 Tách `ark.py`

| File mới | Nội dung | Nguồn |
|---|---|---|
| `media_gateway.py` | Facade mỏng, **giữ nguyên tên hàm public**: `gen_image`, `gen_video_i2v`, `gen_video_seedance_body`, `gen_and_wait_seedance_body`, `gen_and_wait_video`, `poll_task`, `fetch_task_once`, `save_video_assets_from_result`, `wait_video*`, `download_result_media`, `tts`, `mock`; resolve route → gọi adapter theo `route.protocol`; mock branches; `_resolve_image_ref`; retry ladder Seedream (`seedream_text_soften`) | `ark.py` [G] |
| `kepu_text.py` | `chat_storyboard`, `expand_content`, parser, overlay title/subtitle, `_mock_storyboard` | `ark.py` [KEPU] ~560 dòng |
| `tts_service.py` | Cascade: mock → slot Giọng đọc (adapter theo route) → edge-tts; `_accept_if_audible`, `_persist_tts_mp3` | `ark.py` [TTS] |
| `providers/ark_adapter.py` | mục 4.3 | `ark.py` [ARK] + `seedance_i2v_role.py` |
| `providers/openai_adapter.py` | mục 4.2 | `ark.py` [OAI] |

`get_ark()` / `reset_ark()` giữ làm alias của `get_media_gateway()` để call site và test hiện có không đổi; call site mới dùng tên mới. `ark.py` còn lại chỉ re-export (xoá ở đợt dọn sau).

**Xoá**: `tokenfree_gateway.py`, `tokenfree_image.py`, `tokenfree_video.py`, `tokenfree_audio.py`, `tokenfree_pricing.py`, `tokenfree_usage.py`, `admin/tokenfreeRecommendedModels.ts`, 6 test `test_tokenfree_*` + `test_tts_tokenfree_fallback.py` (viết lại thành `test_tts_fallback.py`).

### 4.5 Poll đúng kênh + sửa bug model

- `task_runs.provider_channel_id VARCHAR(64) NULL` (additive, `_apply_schema_patches` + conftest). Ghi lúc submit ở `submit_fragment_video_task` (drama), `run_billed_ephemeral_deferred` (api/studio). `payload.prepared` thêm `channel_id`.
- `fetch_task_once(task_id, *, channel_id: str | None)` / `poll_task(...)`: resolve route theo `channel_id`; không có (task cũ) → dùng slot video hiện tại và log cảnh báo.
- `gen_and_wait_video` truyền `model` xuống `gen_video_i2v(model=…)`; `gen_video_i2v` resolve theo `(function_id, model)` thay vì `settings.model_video`.
- `UsageEvent.provider = route.channel_id` ở mọi `record_*_usage`; bỏ dò chuỗi "kie".
- `FragmentVideoPrepared.submit_mode == "kie"` và `payload.video_provider == "kie"`: giữ nhánh fail-fast hiện có (task cũ), thông báo "Kênh cũ không còn, hãy tạo lại".

## 5. Mô hình cấu hình

### 5.1 Provider (bảng `system_model_channels`, gỡ khoá)

- Dùng: `id` (slug do admin đặt hoặc sinh từ preset: `openai`, `byteplus`, `openrouter`…), `name`, `protocol ∈ {openai, ark, volc_tts}`, `base_url`, `api_key_ciphertext`, `models[]`, `enabled`, `sort_order`.
- Bỏ dùng: `api_format`, `advanced_config`, protocol `kie`, `auto` (giữ cột, không đọc; `auto` cũ → coi là `openai`).
- `_bootstrap_channels_from_env`: seed từ env nếu có key — `OPENAI_API_KEY`(+`OPENAI_BASE_URL`) → provider `openai`; `ARK_API_KEY`(+`ARK_BASE_URL`, mặc định mới là BytePlus) → provider `byteplus`; `VOLC_TTS_*` → provider `volc_tts`. Không key → không seed.
- Startup patch một lần: xoá row `id = "tokenfree"`; xoá `logical_models`, `default_models` khỏi `config_json` (không còn đọc).
- `patch_admin_routing_settings`: nhận danh sách provider đầy đủ (thêm/sửa/xoá), key trống = giữ nguyên, `clear_api_key` = xoá; **không** ép base URL/protocol, **không** tắt kênh khác.

### 5.2 Gán chức năng — `config_json["function_bindings"]`

```json
{
  "slots": {
    "text":  [{"channel_id": "openai",   "model": "gpt-5.6-sol", "weight": 1}],
    "image": [{"channel_id": "byteplus", "model": "dola-seedream-5-0-pro-260628", "weight": 1}],
    "video": [{"channel_id": "byteplus", "model": "dreamina-seedance-2-5-260628", "weight": 1}],
    "audio": [{"channel_id": "openai",   "model": "gpt-4o-mini-tts", "weight": 1}]
  },
  "overrides": {
    "tools.image": [{"channel_id": "openai", "model": "gpt-image-2.5-sunburst", "weight": 1}]
  }
}
```

Danh mục chức năng cố định trong code (`services/functions.py`), mỗi mục `{id, capability, label_vi, label_en, description}`:

| id | năng lực | nhãn |
|---|---|---|
| `kepu.script` | text | Kịch bản khoa học |
| `drama.script` | text | Kịch bản phim ngắn |
| `kepu.image` | image | Ảnh phân cảnh khoa học |
| `drama.asset_image` | image | Ảnh tài sản phim ngắn |
| `tools.image` | image | Ảnh công cụ & Open API |
| `kepu.video` | video | Video khoa học |
| `drama.video` | video | Video phim ngắn |
| `tools.video` | video | Video công cụ & Open API |
| `kepu.tts` | audio | Lời bình khoa học |
| `drama.tts` | audio | Lồng tiếng phim ngắn |

Override rỗng/thiếu = kế thừa slot năng lực. Validation khi lưu: `channel_id` tồn tại; `model` nằm trong `models[]` của provider đó; năng lực của model (suy luận `infer_model_capability`, hoặc nhãn từ catalog) khớp slot; `weight ≥ 1`.

### 5.3 Resolver mới `services/function_router.py`

```
resolve_function_route(function_id, requested_model=None) -> ResolvedModelRoute
resolve_function_candidates(function_id, requested_model=None) -> list[ResolvedModelRoute]
effective_bindings(function_id) -> list[Binding]     # override → slot
```

- Danh sách hiệu lực chỉ giữ binding có provider `enabled` và có key (trừ `volc_tts` có thể dùng app id).
- `requested_model` (user chọn) phải nằm trong danh sách hiệu lực; không nằm → `AppError("model.not_available")`.
- Không chọn → **chọn ngẫu nhiên theo weight** (luân phiên thật). `candidates` trả toàn bộ theo thứ tự: mục được chọn trước, còn lại xáo trộn theo weight — dùng cho failover lúc tạo (`adapter.is_transient_error`).
- Thay thế `resolve_logical_model_id / resolve_upstream_model / resolve_logical_model` tại: `llm_client`, `media_gateway`, `drama/seedream_options.resolve_seedream_model_endpoint`, `drama/build_seedance_generate_body.resolve_seedance_model_endpoint`, `media_catalog`, `estimates`. Xoá `logical_model_router.py`; trong `model_routing_config.py` xoá `synchronize_logical_models_with_channels`, `resolve_logical_model_config`, `is_logical_model_resolvable`, `normalize_default_models`, `model_routing_validation_errors` (thay bằng validation của 5.2); **giữ** `infer_model_capability`, `normalize_model_name`, `channel_connection_ready`, `channel_supports_model`. Trong `model_settings.py` xoá `_bootstrap_logical_from_channels`, `_merge_friendly_alias_models`, `_seedance_logical_meta`, `_ensure_tokenfree_channel`.
- `Settings.model_llm / model_image / model_video / model_audio` không còn được ghi đè từ default logical id; chỉ dùng làm fallback nhãn khi chưa gán (readiness "chưa gán").

### 5.4 Phía user

- `GET /api/media-models?scope=kepu|drama|tools` → `{image_models[], video_models[], defaults}` từ `effective_bindings` của function ảnh/video tương ứng scope; mỗi dòng `{id, label, provider, recommended}` (recommended = mục đầu). Không `scope` → union (tương thích client cũ).
- Khoa học: `project.image_model / video_model` validate bằng `effective_bindings("kepu.image"/"kepu.video")`; nới cột và schema từ 64 lên 128 ký tự vì ID BytePlus dài.
- Phim ngắn: `model_id` trên canvas/episode validate bằng `drama.asset_image` / `drama.video`. `DramaImageGenOptionsBar` tự sửa `model_id` cũ về mặc định khi catalog về (đã có).
- Chuỗi i18n frontend nhắc "TokenFree" (≈41) → đổi thành "nhà cung cấp mô hình" / provider chung; `dramaGenError.ts` regex `tokenfree.com|api.kie.ai` → nhận diện lỗi kết nối theo mã lỗi thay vì host.

## 6. Billing

### 6.1 Bảng giá theo provider — `config_json["provider_rates"]`

Mảng `{pattern, unit, usd, note}`; `pattern` là glob trên model id (so khớp không phân biệt hoa thường), dòng đầu khớp thắng.

| unit | công thức chi phí (USD) |
|---|---|
| `per_image` | `usage.generated_images (mặc định 1) × usd` |
| `per_m_tokens` | `usage.total_tokens / 1e6 × usd` |
| `per_m_output_tokens` | `usage.output_tokens / 1e6 × usd` |
| `per_m_input_output` | `in/1e6 × usd_in + out/1e6 × usd_out` (text; lưu 2 giá) |
| `per_m_chars` | `len(text)/1e6 × usd` |

Seed mặc định (giá chính thức 2026-09-22): `dola-seedream-5-0-pro*` 0.045/ảnh; `dola-seedream-5-0-flash*` 0.018; `seedream-5-0*` 0.035; `seedream-4-5*` 0.04; `seedream-4-0*` 0.03; `dreamina-seedance-2-5*` 10.70/M token; `dreamina-seedance-2-0-fast*` 5.6; `dreamina-seedance-2-0-mini*` 3.5; `dreamina-seedance-2-0*` 7.0; `seedance-1-0-pro*` 2.5; `gpt-image-2*` (gồm 2.5) 30/M output token; `gpt-4o-mini-tts*` 12/M audio out (ước 0.015 USD/phút); `tts-1` 15/M ký tự; `gpt-5.6-sol` 4/20; `gpt-5.6-terra` 2/12; `seed-2-0-*` theo docs BytePlus. Không khớp dòng nào → về `charge_fen_for_tokens` với `BILLING_*_PER_M` hiện có (đơn vị yuan/M, giữ nguyên).

USD → fen: `usd × BILLING_USD_CNY × 100` (làm tròn lên). Hiển thị VND/USD qua `money.py` không đổi.

### 6.2 Luồng

- `adapter.cost_fen(model, raw_usage)` → gán `upstream_cost_fen` vào `ImageResult` / `TaskResult` ngay khi có usage.
- `parse_upstream_cost_fen(raw)` rút còn: `cost_fen` / `cost_cents` → dùng; **xoá** nhánh quota New API, yuan, Kie credits. `charge_fen_for_usage`: `upstream_cost` → dùng; không → `provider_rates` theo `model` trong raw; không nữa → token fallback (`estimated=True`).
- Không usage (mock, lỗi) → như hiện nay (`record_line` fallback token). `record_seedance_video_usage` vẫn re-fetch task một lần khi token = 0 (giờ có `channel_id`).
- **Ước tính đóng băng** (`estimates.py`): dùng `provider_rates` + `effective_bindings(function)`; ảnh = max giá per-image trong slot (không buffer); video = `duration × w × h × 24 / 1024` token × giá/M theo model (lấy max trong slot) × buffer; LLM/TTS giữ hằng số ước tính hiện có × giá text/tts của slot. `resolve_kepu_billing_phase()` không đổi.
- **Bỏ** đối chiếu dùng upstream theo ngày: `services/admin/upstream_usage.py`, endpoint `/api/admin/stats/upstream-usage*`, `/finance/daily/sync`, `/settings/tokenfree/quota`, card Dashboard, nút sync Finance. `finance.py` dùng `cost_fen` local làm chi phí thật (`actual_cost_fen = cost_fen`). Bảng `upstream_usage_daily` giữ, không đọc.
- `/api/admin/settings/billing/model-rates` → `GET/PUT` bảng `provider_rates`.

## 7. Admin UI (`admin/`)

### 7.1 Tab "Mô hình" → màn hình 2 cột

CSS mới `settings-providers-layout` (grid 280px + 1fr; dưới 900px xếp dọc), theo pf-style hiện có của admin (`settings-*`), Tailwind v4 + shadcn. Thêm shadcn `checkbox`, `tooltip`, `separator` nếu cần.

**Cột trái — Provider** (`ProviderSidebar.tsx`)
- Mỗi dòng: icon theo preset, tên, phụ đề "1 key" / "Chưa có key", chấm trạng thái (xanh: bật + có key; xám: thiếu key; đỏ: tắt). Click → mở `ProviderDialog`.
- Nút **+ Thêm provider** → `ProviderDialog` chế độ tạo: chọn preset (OpenAI / BytePlus ModelArk / OpenRouter / BytePlus Seed Speech / OpenAI-compatible tuỳ chỉnh) → điền sẵn tên, protocol, base URL; ô API key (password); nút **Kiểm tra kết nối** (`POST /api/admin/settings/providers/test`); phần **Model bật**: protocol `openai` → nút "Tải danh sách" (`POST /settings/upstream/models`) + lọc theo năng lực + tìm; protocol `ark` → checklist tĩnh từ preset; luôn có ô "Thêm ID thủ công". Nút Lưu / Xoá provider (xác nhận; chặn xoá nếu đang được gán, báo rõ chức năng nào).

**Cột phải — Gán chức năng AI** (`FunctionBindingsPanel.tsx`)
- Header: tiêu đề, phụ đề "Mỗi chức năng chạy bằng model bạn chọn ở đây. Chọn nhiều model thì các yêu cầu được chia luân phiên.", đếm "N/4 slot đã gán" + thanh tiến độ.
- 4 hàng slot năng lực: icon, tên, mô tả, chip `icon provider · model id · ×` (kèm weight khi > 1), badge cam **Chưa gán** khi rỗng, badge xám **N tạm không dùng được** khi có binding hỏng (provider tắt/thiếu key/model bị bỏ tick). Nút **Chọn model** / **Đổi model** → `ModelPickerDialog`: liệt kê model đã bật ở mọi provider đúng năng lực, tick nhiều, ô weight, tìm.
- Nhóm thu gọn **Ghi đè theo chức năng**: 10 hàng theo bảng 5.2; trống hiển thị "Dùng slot Ảnh" (mờ); có nút Chọn/Đổi/Bỏ ghi đè.
- Lưu qua nút chung của trang (`SettingsTabShell`); `PATCH /api/admin/settings/routing` body `{providers?, function_bindings?}`. Lỗi validation trả tiếng Việt, hiển thị dưới header.

### 7.2 API admin

- `GET /api/admin/settings/routing` → `{providers[] (key che), function_bindings, readiness[4], function_catalog[10], presets[], validation_errors[], updated_at}`.
- `PATCH /api/admin/settings/routing` như trên.
- `POST /api/admin/settings/providers/test` `{protocol, base_url, api_key?, channel_id?}` → `{ok, message, models_count?}`.
- `POST /api/admin/settings/upstream/models` giữ, bỏ mọi rewrite sang TokenFree; `ark` trả danh sách tĩnh.
- Xoá `/settings/tokenfree/quota`; `/settings/billing/model-rates` thành `GET/PUT provider_rates`.
- `AdminModelSettingsOut.readiness` tính từ `function_bindings` (4 slot), thông điệp tiếng Việt.

### 7.3 Chỗ khác trong admin

- `PaymentSettingsPanel`: bỏ nút số dư TokenFree, bỏ link "去 TokenFree 核对", bảng giá thành bảng `provider_rates` sửa được (pattern / đơn vị / USD).
- `RuntimeSettingsPanel`: nhãn `ark_*` đổi thành trung tính ("Kích thước ảnh mặc định", "Độ phân giải video"…), field giữ nguyên; readiness dùng nguồn backend.
- `DashboardPage`, `FinanceListPage`: bỏ card/nút đối chiếu upstream.
- Task center (`/queues`, chi tiết task): thêm cột/field `provider_channel_id`.
- Xoá `lib/tokenfreeRecommendedModels.ts`, `RoutingSettingsPanel.tsx` cũ.

## 8. Khởi động & chuyển đổi

1. `_apply_schema_patches`: `ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS provider_channel_id VARCHAR(64)`; `ALTER TABLE projects ALTER COLUMN image_model TYPE VARCHAR(128)` (và `video_model`) — additive/nới rộng, hợp quy ước.
2. `load_model_settings_cache`: xoá row `tokenfree`; bỏ khoá `logical_models/default_models`; seed provider từ env nếu chưa có provider nào; `function_bindings` thiếu → `{}`; `provider_rates` thiếu → seed mặc định.
3. `.env.example`: `ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3`, `OPENAI_BASE_URL=https://api.openai.com/v1`, ghi chú đây chỉ là seed lần đầu.
4. Readiness lúc chưa gán: `/api/health` báo `models: not_configured`; tạo tác vụ trả `AppError("model.slot_not_configured")` tiếng Việt thay vì lỗi 500.
5. `ARK_MOCK=true` hoặc không provider nào có key → mock như hiện nay (mock ở facade, không cần adapter).

## 9. Kiểm thử & nghiệm thu

### 9.1 Test tự động (`backend/`, `pytest`; TDD theo từng task)

Unit (không DB):
- `test_openai_adapter.py`: body `/images/generations` vs `/images/edits`, map size/quality, ghi base64 → file, usage → `cost_fen`, TTS body + voice map, `max_completion_tokens`.
- `test_ark_adapter.py`: body ảnh (clamp size theo model, refs), body video (role/ratio), 4 tầng retry, phân loại lỗi, parse `GET task` (status, `video_url`, `last_frame_url`, `usage`), host detection.
- `test_function_router.py`: override kế thừa, chọn theo weight (seed RNG), validate lựa chọn user, candidates/failover, provider tắt/thiếu key bị loại.
- `test_function_bindings_config.py`: validation khi lưu, migration xoá tokenfree/logical_models, seed từ env.
- `test_provider_rates.py`: khớp pattern, từng `unit`, USD→fen, fallback.
- `test_media_catalog.py` (sửa): `scope`, union, validate `project.image_model`.
- `test_kepu_continuity.py` (sửa): `url_needs_auth`.
- `test_tts_fallback.py` (viết lại): slot audio lỗi → edge-tts, không ghi im lặng.
- `test_media_gateway_poll.py`: `fetch_task_once(channel_id)` dùng đúng route; task cũ không channel → slot hiện tại.
- `test_kepu_video_model_passthrough.py`: `gen_and_wait_video(model=…)` tới adapter đúng model (bug fix).
- Sửa: `test_seedance_model_routing`, `test_logical_image_route`, `test_model_settings_overlay`, `test_generic_text_model_routing` sang resolver mới; giữ xanh nguyên trạng: `test_seedance_*`, `test_seedream_*`, `test_ark_poll_resilience` (chuyển sang adapter), `test_ark_upstream_timeout`, `test_billing_settlement`, `test_kepu_phase_billing`, `test_fragment_video_estimate`.

Integration (PostgreSQL, `db_session`):
- Poller drama/ephemeral đọc `provider_channel_id`; chuỗi freeze → usage → settle với `provider_rates`; `PATCH routing` lưu provider + bindings + lỗi validation; `test_task_poller_dispatch`, `test_finalizing_cancel_race`, `test_billing_integration` giữ xanh.

Frontend/admin: `npm run lint`, `npm run build` cả hai app; test thuần cho `lib` mới nếu có.

### 9.2 Checklist hồi quy thủ công (điều kiện nghiệm thu)

Chạy 2 vòng: `ARK_MOCK=true` (không key) rồi key thật OpenAI + BytePlus.

1. **Khoa học**: tạo dự án từ chủ đề → kịch bản → ảnh phân cảnh → video → lời bình → ghép (mode `full`); mode `image_text`; tạo lại ảnh / video / audio một phân cảnh; đổi `image_model` / `video_model` trong dự án và xác nhận (qua task center / log) model đó thật sự được dùng.
2. **Phim ngắn**: tạo project → tóm tắt / chia tập → seed tài sản → tạo ảnh nhân vật / cảnh / đạo cụ (có style board) → video tài sản → tách phân cảnh → tạo video phân cảnh trên canvas (hàng đợi, huỷ, thử lại, first/last frame nối tiếp) → lồng tiếng.
3. **Công cụ**: t2i, i2p (ảnh tham chiếu), t2v / i2v; lịch sử công cụ.
4. **Open API** `/api/v1` images / videos / seedance với API key.
5. **Billing**: số dư đóng băng → trừ thật → hoàn dư; số tiền khớp bảng giá; hiển thị VND; đơn nạp tiền vẫn xác nhận được.
6. **Admin**: thêm 2 provider, kiểm tra kết nối, gán 4 slot + 1 override, readiness đúng; tắt provider → badge "tạm không dùng được", task mới không đi vào kênh đó; task center hiện provider.
7. **Không key**: toàn bộ luồng 1–4 chạy hết trạng thái ở chế độ mock.

### 9.3 Tài liệu

`CLAUDE.md` (mục "模型路由" → mô tả adapter + function slots), `README.md`, `docs/BILLING.md` (bỏ quota, thêm `provider_rates`), mới `docs/PROVIDERS.md` (interface adapter, cách thêm provider, danh sách model tĩnh BytePlus), `docs/releases/` sau khi phát hành.

## 10. Thứ tự triển khai (gợi ý cho kế hoạch)

1. Tách `kepu_text.py`, `tts_service.py` khỏi `ark.py` (không đổi hành vi) — test hiện có xanh.
2. `providers/base.py` + `ark_adapter.py` chuyển nguyên nhánh Ark; `media_gateway.py` gọi adapter; xoá phương ngữ TokenFree.
3. `function_router.py` + `function_bindings` + migration; thay resolver ở call site; gỡ khoá `model_settings.py`; `media-models?scope`.
4. `openai_adapter.py` (ảnh, TTS, text quirk).
5. `provider_channel_id` + poll theo kênh + bug `model`.
6. `provider_rates` + billing/estimates; bỏ upstream usage compare.
7. Admin UI mới + API; dọn Payment/Runtime/Dashboard/Finance; frontend i18n.
8. Docs, checklist hồi quy, release note.
