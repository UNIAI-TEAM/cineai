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
  - `cost_fen(model, raw_usage)` — chi phí fen tính từ usage thật theo bảng `provider_rates`
    (`services/billing/provider_rates.py`); không usage / model chưa có giá → `None`
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

### Cấu hình qua trang quản trị

Admin → **系统设置** → tab **"Mô hình"** là màn hình 2 cột (`ModelsSettingsPanel`):

- **Cột trái — Nhà cung cấp** (`ProviderSidebar` + `ProviderDialog`): "+ Thêm nhà cung cấp" mở hộp thoại,
  chọn mẫu (OpenAI, BytePlus ModelArk, OpenRouter, BytePlus Seed Speech, hoặc tự nhập cho endpoint tương
  thích OpenAI khác) → nhập Base URL / API key → **Kiểm tra kết nối** → tick model ở phần "Model bật" →
  **Lưu**. Nhà cung cấp lưu ngay từ hộp thoại (PATCH riêng), không phụ thuộc nút Lưu của trang. Với
  protocol `ark` và `volc_tts`, nút "Kiểm tra kết nối" chỉ xác nhận đã nhập key (hai upstream này không có
  endpoint kiểm tra miễn phí) chứ chưa thật sự gọi thử nhà cung cấp; chỉ `openai` gọi `GET /models` thật.
  Đổi Base URL sang host khác (khác scheme/host/port) thì phải nhập lại API key — key cũ không được dùng
  lại cho host mới, hộp thoại nhắc ngay trong ô key. Không xoá được nhà cung cấp, và không bỏ tick được
  một model, nếu nó đang được gán ở cột phải (bản đã lưu hoặc bản nháp chưa lưu) — thông báo lỗi liệt kê
  đích danh chức năng nào đang dùng.
- **Cột phải — Gán chức năng AI** (`FunctionBindingsPanel`): 4 slot năng lực Văn bản / Ảnh / Video / Giọng
  đọc, mỗi slot chọn một hoặc nhiều model kèm tỉ lệ (weight) để luân phiên. Nhóm "Ghi đè theo chức năng" cho
  từng chức năng cụ thể (mục 3), để trống thì dùng slot mặc định. Thay đổi ở cột này chỉ lưu khi bấm
  **Lưu gán chức năng** ở đầu trang (khác với cột trái, lưu ngay trong hộp thoại); nút bị chặn nếu bản nháp
  còn lỗi (model/nhà cung cấp không tồn tại hoặc sai năng lực). Binding trỏ vào nhà cung cấp đang tắt hoặc
  thiếu key vẫn được giữ nguyên, chỉ hiện badge "tạm không dùng được" và không nhận yêu cầu mới.
- Bảng giá USD theo model (đổi được, dùng để dự tính phí và quyết toán) nằm ở tab **支付与汇率 → mục "5.
  Bảng giá model (USD)"** (`ProviderRatesEditor`, xem `docs/BILLING.md`), không nằm trong tab Mô hình.

### Cấu hình qua curl (tự động hoá)

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
`"clear_api_key": true` để xoá key. Riêng khi `base_url` đổi sang host khác (so scheme + host + port) thì
**bắt buộc nhập lại `api_key`**, nếu không sẽ nhận `HTTP 400` "Đổi địa chỉ máy chủ thì phải nhập lại API
key" — key đã lưu không bao giờ được gửi tới host mới. Quy tắc này cũng áp dụng cho
`POST /settings/providers/test` và `POST /settings/upstream/models` khi truyền `channel_id` kèm `base_url`
khác host đã lưu.

### Seed provider từ `.env` (chỉ một lần)

Lúc nạp cấu hình (`model_settings._ensure_bootstrapped_channels`):

- Kênh cũ `tokenfree` (hoặc bất kỳ provider nào có base URL chứa `tokenfree.com`) luôn bị xoá.
- Provider chỉ được seed từ `.env` (`OPENAI_*`, `ARK_*`, `VOLC_TTS_*`) **đúng một lần** trên DB mới: sau khi
  seed, `app_settings.config_json["providers_seeded"] = true` và các lần nạp sau không seed lại — kể cả khi
  admin xoá hết provider (`providers: []`).
- DB đã có provider (dù chưa có cờ) được coi là đã seed. DB nâng cấp từ bản TokenFree (vừa xoá kênh
  `tokenfree`) **không seed** từ `.env` cũ vì `ARK_API_KEY`/`OPENAI_API_KEY` khi đó là key TokenFree —
  admin phải tự thêm provider ở trang cài đặt.
- Provider mà base URL suy ra từ env vẫn trỏ `tokenfree.com` thì bị bỏ qua. Key giữ chỗ
  (`replace-me`, `changeme`, `your-*`, `sk-xxx*`, `<...>`) được coi như rỗng. `.env` không có key nào thì
  chưa tính là đã seed (điền key rồi khởi động lại vẫn seed được).
- Có cấu hình Volc TTS trong env thì slot `audio` được seed với binding Volc đứng đầu.

Response `AdminRoutingSettingsSaveOut.applied` cho biết những phần nào đã được lưu (`providers`,
`function_bindings`); lỗi validate ("nhà cung cấp … không tồn tại", "chưa được bật ở nhà cung cấp …", model sai
capability…) trả `HTTP 400` với message tiếng Việt từ `function_bindings.validate_function_bindings()`.

`GET /api/media-models?scope=<kepu|drama|tools>` (public, không cần admin) trả danh sách model đang khả
dụng cho từng nhóm chức năng — dùng để hiển thị dropdown chọn model ở frontend, không dùng để cấu hình.

### Giọng đọc theo ngôn ngữ (TTS)

Danh mục giọng `services/voices.py` (`VOICE_PRESETS`, trả qua `GET /api/voices`) có trường `languages`
(`zh`/`vi`/`en`) cho mỗi giọng. Tài liệu BytePlus ghi rõ mỗi giọng chỉ đọc được một số ngôn ngữ, dùng sai
ngôn ngữ có thể **tổng hợp lỗi** — nên hệ thống tự đổi giọng theo ngôn ngữ nội dung:

- Giọng mặc định của mỗi ngôn ngữ = giọng **đứng đầu** ngôn ngữ đó trong danh mục (cùng giới tính nếu có):
  zh `zh_female_cancan_uranus_bigtts` / `zh_male_shaonianzixin_uranus_bigtts`,
  vi `vi_female_ruan_uranus_bigtts` / `vi_male_wumg_uranus_bigtts`,
  en `en_female_hayley_uranus_bigtts` / `en_male_tim_uranus_bigtts`.
- `services/voice_lang.py`: `voice_for_lang()` đổi giọng không đọc được ngôn ngữ sang giọng mặc định (giữ
  giới tính, có log). `TtsService.synthesize(lang=…)` luôn gọi hàm này (không truyền `lang` thì đoán theo văn
  bản); video ngắn dùng `project_kepu_lang(project)`. Giọng clone `S_*` / id tự nhập không rõ ngôn ngữ → giữ nguyên.
- Nghe thử: giọng không đọc được ngôn ngữ giao diện thì nghe câu mẫu bằng ngôn ngữ của giọng.
- Frontend `StyleConfigPage` chỉ liệt kê giọng đọc được `project.effective_content_lang`
  (`lib/voiceLang.ts`, cùng quy tắc).
- Dự phòng edge-tts: zh → giọng `zh-CN-*` theo speaker; vi → `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural`;
  en → `en-US-JennyNeural` / `en-US-GuyNeural` (theo giới tính). Truyền thẳng tên giọng edge
  (`vi-VN-HoaiMyNeural`…) cũng được dùng nguyên.
- OpenAI TTS: giọng dựng sẵn (`marin`/`cedar`/`alloy`…) đọc được nhiều ngôn ngữ (theo danh sách ngôn ngữ của
  Whisper, có tiếng Việt); adapter chọn `marin`/`cedar` theo giới tính suy ra từ speaker (`vi_female_*`,
  `en_male_*`… đều suy ra được).

Giọng vi/en đã thêm — đều là giọng Seed Speech **TTS 2.0** (`*_uranus_bigtts`, resource `seed-tts-2.0`), chỉ
có ở BytePlus (quốc tế); nếu nhà cung cấp `volc_tts` trỏ Volcengine Trung Quốc mà không có giọng này thì
cascade rơi xuống OpenAI / edge-tts như trên:

| Ngôn ngữ | Voice id |
|---|---|
| vi | `vi_female_ruan_uranus_bigtts`, `vi_male_wumg_uranus_bigtts`, `vi_female_ling_uranus_bigtts`, `vi_female_linh_uranus_bigtts`, `vi_female_wu_uranus_bigtts`, `vi_female_hong_uranus_bigtts`, `vi_female_partner_uranus_bigtts` |
| en | `en_female_hayley_uranus_bigtts`, `en_male_tim_uranus_bigtts`, `en_female_skye_uranus_bigtts`, `en_female_jenny_uranus_bigtts`, `en_male_kevin_uranus_bigtts`, `en_male_marcus_uranus_bigtts` |

Nguồn (kiểm tra 2026-09-23):

- BytePlus Seed Speech — Voice List (TTS 2.0, cột Speaker ID / Language / Gender):
  https://docs.byteplus.com/en/docs/byteplusvoice/tts-voice-list
- OpenAI Text to speech (giọng dựng sẵn, ngôn ngữ hỗ trợ): https://developers.openai.com/api/docs/guides/text-to-speech
- Giọng edge-tts = giọng neural của Azure Speech: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
  (`en-US-JennyNeural`, `en-US-GuyNeural` có trong bảng; cả 4 giọng vi-VN / en-US đều có trong
  `edge_tts.list_voices()` chạy ngày 2026-09-23).

Lời thoại do Seedance tự đọc (phim ngắn, `generate_audio=true`) không dùng danh mục này: dự án vi/en được
khai báo ngôn ngữ trước lời thoại theo `docs/SEEDANCE_2_5.md` §4.3 (`seedance_segments.declare_spoken_language`,
chỉ ở bước gửi, dữ liệu phân cảnh không đổi).

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
- **Model chưa có dòng giá** (vd. endpoint `ep-…` tự đặt) được tính theo giá token dự phòng `BILLING_*_PER_M`
  và hiện trong `unpriced_models` của `GET /api/admin/settings/billing/model-rates` — thêm dòng giá cho chúng.
- **Nhãn model của dòng usage TTS phim ngắn không chắc khớp model thực chạy.** `voice_synthesis.py`
  (`_drama_tts_model()`) lấy model theo lượt chọn ngẫu nhiên (weight) của slot `drama.tts` để ghi vào
  `usage_events.model`, không phải model mà `TtsService` thực tế đã dùng (cascade mock → slot → edge-tts
  có thể rơi vào một nhánh khác). Số tiền vẫn bị chặn trên bởi giá ước tính nên không bị tính quá, nhưng
  tên model trên dòng usage có thể sai — hạn chế đã biết, chưa khắc phục.
- **Mock khi chưa có key**: đặt `ARK_MOCK=true`, hoặc không cấu hình bất kỳ provider nào có `api_key` —
  `MediaGateway.mock` sẽ tự phát hiện (`get_routing_snapshot().channels` không có channel nào
  `enabled` + có key) và chuyển toàn bộ ảnh/video/TTS sang sinh dữ liệu giả cục bộ (`static/mock/...`),
  không gọi upstream. **Mock không bao gồm văn bản của phim ngắn**: `llm_client.chat_completions` không có
  nhánh mock, nên các luồng văn bản drama (tóm tắt kịch bản, viết tập, tách phân cảnh…) vẫn gọi nhà cung
  cấp văn bản thật kể cả khi `ARK_MOCK=true` — chưa gán slot `text` thì báo "Chưa gán model văn bản", key
  sai thì báo lỗi xác thực của nhà cung cấp.

## 5. Nâng cấp từ bản TokenFree

Checklist cho người vận hành nâng cấp một bản cài đã chạy TokenFree lên bản gọi thẳng provider (không có
đường tương thích ngược tự động — admin phải cấu hình lại provider và gán chức năng sau khi deploy).

- **Kênh `tokenfree` bị xoá ở lần khởi động đầu tiên** (mục "Seed provider từ `.env`" ở trên), cùng với
  mọi provider có base URL chứa `tokenfree.com`. Cấu hình `logical_models` / `default_models` kiểu cũ
  không còn được đọc.
- **Tác vụ còn đang chạy lúc deploy sẽ thất bại và được hoàn tiền tạm giữ**, theo luồng quyết toán
  thường (không mất tiền, nhưng tác vụ phải tạo lại). Hai trường hợp, hai thông báo khác nhau: task drama
  cũ có `submit_mode == "kie"` báo `"Kênh video cũ không còn, hãy tạo lại phân cảnh này"` (`drama/jobs.py:1410`,
  `drama/generation.py:1665`); một tác vụ video mà `provider_channel_id` trỏ vào kênh đã bị xoá (ví dụ
  `tokenfree`) thì poll báo `"Không tìm thấy provider của tác vụ"` (`media_gateway.py::fetch_task_once`).
  Nên deploy lúc ít tác vụ, hoặc chờ hàng đợi video trống.
- **Bản cài nâng cấp không seed provider từ env.** Vì lần khởi động đầu vừa xoá kênh `tokenfree`,
  `_ensure_bootstrapped_channels` đánh dấu đã seed mà không đọc `OPENAI_API_KEY` / `ARK_API_KEY` /
  `VOLC_TTS_*` trong env (env cũ chứa key TokenFree). Sửa env trước hay sau khi deploy đều không có tác
  dụng: sau deploy, admin thêm từng provider (OpenAI, BytePlus ModelArk, Seed Speech — kể cả Base URL của
  Seed Speech) ở admin → **系统设置** → tab **"Mô hình"**, rồi gán chức năng.
- **Bản cài mới** (DB chưa có provider, chưa có cờ `app_settings.config_json["providers_seeded"]`) thì seed
  từ env **đúng một lần**, xem mục "Seed provider từ `.env`": `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, mặc
  định `https://api.openai.com/v1`), `ARK_API_KEY` (+ `ARK_BASE_URL`, mặc định mới
  `https://ark.ap-southeast.bytepluses.com/api/v3`), `VOLC_TTS_*` nếu dùng Seed Speech. Sau đó sửa env không
  còn tác dụng với provider; env còn trỏ `tokenfree.com` không được seed, key giữ chỗ cũng bị bỏ qua.
- **URL Seed Speech lấy theo thứ tự**: Base URL của provider Seed Speech ở admin → `volc_tts_url` trong cấu
  hình phẳng đã lưu DB (`app_settings.config_json["flat"]`, phủ lên env qua overlay) → mặc định mới
  `https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/unidirectional` (`volc_tts_adapter.py`). Cấu hình
  phẳng chỉ được chụp từ env ở lần khởi động đầu của DB, nên:
  - Bản cài nâng cấp giữ `volc_tts_url` đã lưu từ trước (thường là địa chỉ openspeech Trung Quốc
    `https://openspeech.bytedance.com/api/v3/tts/unidirectional`, mặc định cũ); đổi `VOLC_TTS_URL` trong
    env không có tác dụng. Hãy điền Base URL đúng cho provider Seed Speech ở tab "Mô hình": key BytePlus
    quốc tế dùng địa chỉ `voice.ap-southeast-1.bytepluses.com` ở trên, key openspeech Trung Quốc
    (Volcengine) dùng `openspeech.bytedance.com`.
  - Bản cài mới lấy `VOLC_TTS_URL` trong env lúc khởi động đầu (không đặt thì là mặc định quốc tế mới), vừa
    làm Base URL của provider Seed Speech được seed, vừa lưu vào cấu hình phẳng. Bộ key Trung Quốc phải đặt
    tường minh `VOLC_TTS_URL=https://openspeech.bytedance.com/api/v3/tts/unidirectional` trước lần khởi động
    đầu, hoặc sửa Base URL ở admin sau đó.
- **Key đã lưu không được dùng lại khi đổi host của Base URL** (đổi scheme/host/port): xem mục "Cấu hình
  qua trang quản trị" và "Cấu hình qua curl" ở trên — backend luôn yêu cầu nhập lại API key trong trường
  hợp này, kể cả qua API.
- **`GET /api/health` đổi shape của `models`**: từ chuỗi LLM/ảnh/video đơn sang
  `{slot: {status, model}}` theo 4 năng lực (`text|image|video|audio`), `status` là `ready` / `unavailable`
  / `not_configured` / `unknown`. Script/monitoring nào đọc field cũ phải cập nhật.
- **Giới hạn tính phí đã biết (kế thừa từ Plan B, chưa khắc phục)**:
  - `gpt-image` chỉ tính phí theo token đầu ra (`per_m_output_tokens`); token đầu vào (ảnh tham chiếu,
    prompt dài) không được tính vào chi phí.
  - Seedream trả nhiều ảnh trong một lần gọi: tiền tạm giữ ước tính lúc tạo tác vụ không biết trước số
    ảnh, nên phần chênh giữa số ảnh thật và ước tính được quyết toán qua nhánh "vượt mức tạm giữ" (xem
    ngay dưới), không có bước ước tính riêng cho nhiều ảnh.
  - Số tiền quyết toán có thể **vượt mức tạm giữ** (không có trần): `settlement.py::settle_task` trừ
    thẳng phần vượt từ số dư khi usage thật cao hơn ước tính lúc freeze — hành vi đã có từ trước, không
    phải lỗi mới.
  - Nhãn model trên dòng usage TTS phim ngắn có thể không khớp model thực chạy (xem mục 4 ở trên,
    `_drama_tts_model()`).
  - Bảng giá `provider_rates` là **cache trong tiến trình** (`get_provider_rates()`/`set_provider_rates()`
    ở `services/billing/provider_rates.py`), không có pub/sub giữa các process — chạy nhiều worker
    uvicorn thì admin sửa giá ở worker này sẽ không tới được worker khác cho tới khi restart. Giữ
    `--workers 1`.
- **Đối chiếu dùng lượng upstream (upstream-usage reconciliation) và đồng bộ tài chính (finance sync) kiểu
  TokenFree đã bị gỡ bỏ** — không còn job định kỳ gọi API "dùng lượng" của TokenFree hay endpoint đồng bộ
  tài chính cũ; số liệu tài chính giờ tính hoàn toàn từ `usage_events` nội bộ theo `provider_rates`.
