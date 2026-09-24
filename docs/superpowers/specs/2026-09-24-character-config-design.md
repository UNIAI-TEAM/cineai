# Cấu hình nhân vật: ngoại hình theo trường + chọn giọng

- Ngày: 2026-09-24
- Trạng thái: đã duyệt thiết kế, chờ lập kế hoạch
- Thuộc: phim truyện (drama) — tư liệu nhân vật, lồng tiếng

## 1. Vấn đề

**Ngoại hình:** khi sinh kịch bản, AI viết cho mỗi nhân vật một đoạn văn `visualImage` 100–200 chữ (giới tính, tuổi, khuôn mặt, tóc, vóc dáng, trang phục…). `build_character_params` ghép đoạn này cùng `title/roleType/coreTags/personality` thành `visualPrompt`. Người dùng chỉ sửa được bằng một ô văn bản tự do trong `DramaAssetDetailModal`. Muốn đổi một chi tiết (ví dụ màu tóc) phải tự tìm trong đoạn văn dài rồi sửa tay.

**Giọng:** người dùng không chọn được giọng TTS cụ thể. Hộp thoại gắn giọng chỉ cho viết mô tả; AI gợi ý `speaker` rồi hệ thống tự đoán lại. Khi lồng tiếng, `usable_speaker` có thể lặng lẽ đổi giọng nếu giới tính trong mô tả khác với giới tính của giọng. Ngoài ra danh mục giọng tiếng Anh trong repo mới có 6/68 giọng BytePlus.

**Ràng buộc từ BytePlus** ([TTS voice list](https://docs.byteplus.com/en/docs/byteplusvoice/tts-voice-list)):

- Mỗi giọng chỉ đọc một ngôn ngữ; dùng sai ngôn ngữ có thể tổng hợp lỗi.
- Tiếng Việt: 7 giọng (6 nữ, **1 nam** `vi_male_wumg_uranus_bigtts`). Repo đã có đủ.
- Tiếng Anh (American English): 68 giọng (41 nam, 27 nữ), repo có 6.
- Mỗi giọng có file mẫu `.wav` trên CDN BytePlus — nghe thử không tốn phí TTS.

## 2. Phạm vi

**Làm:**

- Trường ngoại hình có cấu trúc trên tư liệu nhân vật; AI sinh sẵn khi sinh kịch bản; nhân vật cũ có nút "AI tách trường".
- Backend ghép `visualPrompt` từ các trường; người dùng vẫn sửa tay được (chế độ thủ công).
- Nhập đủ 68 giọng tiếng Anh + `sample_url` cho mọi giọng vi/en vào danh mục.
- API danh mục giọng theo ngôn ngữ dự án; tab "Chọn giọng" trong hộp thoại gắn giọng, nghe thử bằng file mẫu.
- Khóa giọng người dùng đã chọn: lồng tiếng không tự đổi theo giới tính.

**Không làm (để sau):**

- Làm cho nhiều nhân vật nam tiếng Việt có giọng khác nhau (chỉnh tốc độ/cao độ, nhân bản giọng `S_*`). Lần này chỉ hiện ghi chú.
- Cấu hình nhân vật ngay lúc bấm "Thêm nhân vật" (vẫn tạo trước, sửa sau).
- Đổi giọng theo từng câu thoại / cảnh.
- Danh mục giọng cho các ngôn ngữ khác vi/en/zh.

## 3. Thiết kế

### 3.1 Ngoại hình theo trường

**Dữ liệu** — `DramaAsset.params` của nhân vật (không thêm cột, không cần `_apply_schema_patches`):

```jsonc
{
  "appearance": {
    "gender": "nữ",
    "age": "khoảng 25 tuổi",
    "face": "mặt trái xoan, mắt một mí sắc",
    "hair": "tóc đen dài buộc đuôi ngựa",
    "build": "dáng mảnh, cao",
    "outfit": "áo dài lụa trắng, quần đen",
    "signature": "vòng bạc cổ tay trái",
    "style_note": "khí chất lạnh lùng, ánh mắt kiên định"
  },
  "promptManual": false
}
```

- Mọi trường là chuỗi, có thể rỗng. Ngôn ngữ giá trị theo ngôn ngữ nội dung dự án (AI viết), không ép.
- `promptManual`: `true` khi người dùng đã sửa tay ô prompt → backend không ghi đè `visualPrompt` nữa.

**Sinh sẵn khi sinh kịch bản** — `script_summary_prompt.py`:

- Schema `characters[]` thêm object `appearance` với 8 khóa trên; quy tắc: mỗi trường ngắn gọn, cụ thể, có thể quay/chụp; nhất quán với `visualImage`.
- `visualImage` vẫn giữ (tương thích ngược, và là nguồn cho nhân vật không có `appearance`).
- `build_character_params` lưu `appearance` (đã chuẩn hóa: chỉ 8 khóa, giá trị chuỗi đã `strip`) vào params. Khi có `appearance` không rỗng, `visualPrompt` được ghép bằng `compose_appearance_prompt` (mục dưới) thay cho `visualImage`, rồi nối tiếp nhãn `title/roleType/coreTags/personality` như `manju_join_character_prompt` hiện tại.

**Nhân vật cũ — "AI tách trường"**:

- `POST /api/drama/assets/{id}/appearance/extract` (chỉ nhân vật, chủ sở hữu dự án).
- Một lượt LLM tách `visualPrompt` (hoặc `visualImage`) hiện có thành 8 trường, trả JSON; lưu vào `params.appearance`, **không** đổi `visualPrompt` (người dùng xem form rồi mới lưu).
- Tính phí qua `run_billed_ephemeral(domain="drama", task_type="appearance_extract")`; đăng ký `("drama", "appearance_extract")` là `_noop_ephemeral` trong `tasks/handlers.py`; function id dùng slot text của drama giống `voice_prompt`.

**Ghép prompt — chỉ ở backend** (`services/drama/appearance_prompt.py`, file mới):

- `normalize_appearance(raw) -> dict[str, str]`: giữ đúng 8 khóa, ép chuỗi, `strip`, bỏ khóa lạ.
- `compose_appearance_prompt(appearance, lang) -> str`: hàm thuần, ghép theo thứ tự cố định `gender, age, face, hair, build, outfit, signature, style_note`, bỏ trường rỗng. Nhãn tiếng Anh cho dự án vi/en (`Gender: …. Age: …`), nhãn Trung cho dự án zh (theo `use_zh_prompt_labels`). Trả chuỗi rỗng nếu mọi trường rỗng.
- `apply_appearance_update(asset, lang)`: nếu nhân vật có `appearance` không rỗng và `promptManual` không `true` → ghi `visualPrompt`, `visualImage` và `canvas.generation.prompt` bằng prompt đã ghép (cộng nhãn `title/roleType/coreTags/personality`).

**Lưu** — `PATCH /api/drama/assets/{id}` hiện merge `params` chung. Sau merge, nếu asset là `character` và body có `params.appearance` hoặc `params.promptManual` → gọi `apply_appearance_update`. Logic nằm trong service, API chỉ gọi.

**Giao diện** — `DramaAssetDetailModal.tsx`, chỉ với nhân vật:

- Form 8 trường (input một dòng; `outfit`, `style_note` là textarea 2 dòng) đặt trên ô prompt. Tách thành component riêng `CharacterAppearanceForm.tsx` để modal không vượt 500 dòng.
- Nhân vật chưa có `appearance` → form trống + nút "AI tách trường" (gọi endpoint trên, điền form).
- "Lưu" gửi `params.appearance` (+ `promptManual: false` nếu đang ở chế độ tự ghép); ô prompt hiển thị `visualPrompt` backend trả về.
- Người dùng gõ vào ô prompt → khi lưu gửi kèm `promptManual: true`; hiện nhãn "Đang chỉnh tay" và nút "Tạo lại prompt từ các trường" (gửi `promptManual: false` → backend ghép lại).
- "Tạo ảnh" giữ luồng hiện có (lưu nếu có thay đổi rồi gọi `onGenerate`).

### 3.2 Chọn giọng

**Danh mục** — `services/voices.py` `VOICE_PRESETS`:

- Thêm 62 giọng tiếng Anh còn thiếu (Phụ lục A). Mỗi preset vi/en thêm các khóa: `sample_url`, `scenario`, `description` (tiếng Anh, lấy nguyên từ BytePlus), giữ `label_i18n` cho 13 giọng đã có; giọng mới dùng `"<Tên> · <mô tả ngắn>"` cho `en`, và bản dịch tiếng Việt tự nhiên cho `vi` (theo `docs/I18N_GLOSSARY_VI.md`).
- **Cờ `auto_pool`** (mặc định `true`): 62 giọng mới đặt `auto_pool: false`. `default_voice_for_lang`, `lang_voice_pool` (backend) và phần tương ứng trong `frontend/src/lib/voiceLang.ts` **bỏ qua** preset `auto_pool: false`. Lý do: `stable_pick` chọn theo hash trên pool; thêm giọng vào pool sẽ đổi giọng của nhân vật đang lồng tiếng tự động. `tests/fixtures/voice_lang_vectors.json` hiện có phải tiếp tục pass không sửa.
- `voice_languages` / `voice_gender` / `voice_supports_lang` vẫn nhận mọi preset (kể cả `auto_pool: false`).

**API** — `GET /api/drama/voices/catalog?lang=vi|en|zh`:

- Trả `[{id, speaker, name, gender, scenario, description, label, sample_url}]` các preset có `lang` trong `languages`, theo thứ tự danh mục; `label` theo ngôn ngữ giao diện (`label_i18n`).
- Không cần dự án; chỉ cần đăng nhập. `lang` ngoài vi/en/zh → mảng rỗng.

**Giao diện** — `CharacterVoiceBindModal.tsx` thêm tab thứ ba **"Chọn giọng"** (đặt đầu tiên); tách danh sách thành component `VoiceCatalogPicker.tsx`:

- Lấy catalog theo ngôn ngữ nội dung dự án. Lọc giới tính (Tất cả/Nam/Nữ) và nhóm (`scenario`).
- Mỗi dòng: tên, giới tính, nhóm, mô tả, nút ▶ phát `sample_url` (một `<audio>` dùng chung, bấm dòng khác thì dừng dòng cũ).
- Bấm "Dùng giọng này" → `dramaApi.generateVoice({project_id, name: "<nhân vật> · <tên giọng>", voice_prompt: description, speaker, character_asset_id, speaker_locked: true})` → nhận tư liệu giọng (có câu mẫu đọc bằng giọng đó, tốn một lượt TTS — cần vì Seedance dùng file này làm `reference_audio`) → tự gắn cho nhân vật bằng `buildBoundParams` hiện có → `onBound`.
- Dự án tiếng Việt: hiện ghi chú "Tiếng Việt hiện chỉ có 1 giọng nam; các nhân vật nam sẽ dùng chung giọng này."
- Ba trạng thái tải/trống/lỗi; lỗi dùng `onError` như các tab khác.

**Khóa giọng**:

- `DramaVoiceGenerateRequest` thêm `speaker_locked: bool = False`; `generate_voice` ghi `params.speakerLocked = true` vào tư liệu giọng khi có cờ và `speaker` hợp lệ (có trong `VOICE_PRESETS`, hoặc `S_*`).
- Kiểm tra bỏ qua khi khóa: tạo hàm `speaker_for_voice_asset(vparams, lang, *, prompt, character_name)` (trong `voice_synthesis.py`) dùng chung cho `fragment_dub.load_dub_voices` và chỗ gọi ở `voice_synthesis.py:264`:
  - `speakerLocked` và `voice_supports_lang(speaker, lang)` → dùng nguyên `speaker` (không xét giới tính mô tả).
  - `speakerLocked` nhưng không hỗ trợ ngôn ngữ (dự án đổi ngôn ngữ sau khi chọn) → rơi về luồng cũ (`usable_speaker` → `infer_character_speaker`) và log cảnh báo.
  - Không khóa → luồng cũ không đổi.
- Tab "Tạo và tổng hợp" / "Chọn có sẵn" hiện tại giữ nguyên hành vi (không khóa).

### 3.3 Xử lý lỗi

- Endpoint tách trường: LLM trả JSON hỏng → `AppError("drama.appearance_extract_failed")`, không ghi params. Asset không phải nhân vật → `drama.character_asset_only` (đã có).
- Catalog: không có lỗi nghiệp vụ; `sample_url` rỗng → ẩn nút ▶.
- `generateVoice` lỗi khi chọn giọng → giữ nguyên binding cũ, báo lỗi qua `onError`.
- Mã lỗi mới thêm vào bảng mã lỗi API (vi/en) theo `docs/superpowers/specs/2026-09-22-api-error-codes-design.md`.

## 4. Kiểm thử

Backend (pytest, phần lớn là unit):

- `compose_appearance_prompt`: vi/en dùng nhãn Anh, zh dùng nhãn Trung, bỏ trường rỗng, tất cả rỗng → `""`.
- `normalize_appearance`: bỏ khóa lạ, ép chuỗi, strip.
- `apply_appearance_update`: ghi đè 3 chỗ prompt khi `promptManual` false; không động khi `promptManual` true.
- `build_character_params` với `appearance` từ kịch bản → `visualPrompt` được ghép từ trường; không có `appearance` → như cũ.
- `lang_voice_pool` / `default_voice_for_lang` bỏ qua `auto_pool: false`; `voice_lang_vectors.json` vẫn pass; `voice_supports_lang` nhận giọng mới.
- `speaker_for_voice_asset`: khóa + khác giới tính mô tả → giữ speaker; khóa + sai ngôn ngữ → luồng cũ; không khóa → luồng cũ.
- `load_dub_voices` (tích hợp, cần Postgres): nhân vật gắn giọng đã khóa giữ đúng speaker.
- Catalog endpoint: lọc đúng ngôn ngữ, 7 vi / 68 en.
- `test_drama_*` hiện có tiếp tục pass.

Frontend: test vector `voiceLang` hiện có pass; `npm run lint` và `npm run build` ở `frontend/`.

## 5. Tài liệu

- `docs/PROVIDERS.md` (phần TTS): nguồn danh mục giọng BytePlus, cờ `auto_pool`, `sample_url`, và quy tắc khóa giọng (`speakerLocked`) khi lồng tiếng.

## Phụ lục A — Danh mục giọng BytePlus TTS 2.0 (vi / en)

Lấy từ trang voice list ngày 2026-09-24. Cột "Đã có" = đã nằm trong `VOICE_PRESETS`.

### Tiếng Việt (7)

| Speaker ID | Tên | Giới tính | Nhóm | Đã có | Mô tả | Mẫu |
|---|---|---|---|---|---|---|
| `vi_female_partner_uranus_bigtts` | Partner | female | Dubbing | ✓ | A young woman with intense, full emotion—brimming with youthful vitality. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812144504-442015548259.wav |
| `vi_female_ruan_uranus_bigtts` | Ruan | female | General | ✓ | A steady, well-measured young woman—clear-minded, dignified, and poised. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114548-959421129182.wav |
| `vi_female_ling_uranus_bigtts` | Ling | female | General | ✓ | A tender, kind young woman—earnest and dependable in her work. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114600-319719388711.wav |
| `vi_female_linh_uranus_bigtts` | Linh | female | Dubbing | ✓ | A straightforward, candid young woman full of energy—crisp and decisive in expression. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114608-323718302955.wav |
| `vi_female_wu_uranus_bigtts` | Wu | female | General | ✓ | A straightforward, outgoing young woman with a steady, rational mindset. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114638-1050422919510.wav |
| `vi_female_hong_uranus_bigtts` | Hong | female | General | ✓ | An out-of-town young woman with a Vietnamese accent—straightforward, with frank emotional expression. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114648-1720038904310.wav |
| `vi_male_wumg_uranus_bigtts` | Wumg | male | General | ✓ | A modest, patient young man—rigorous and meticulous. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902114656-960419004557.wav |

### Tiếng Anh (68)

| Speaker ID | Tên | Giới tính | Nhóm | Đã có | Mô tả | Mẫu |
|---|---|---|---|---|---|---|
| `en_female_stokie_uranus_bigtts` | Stokie | female | General |  | A trendy, casual, and expressive young female voice | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112114-1086068446089.wav |
| `en_female_dacey_uranus_bigtts` | Dacey | female | General |  | A crisp, confident, and engaging young female voice | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812134954-1569519467022.wav |
| `en_male_tim_uranus_bigtts` | Tim | male | General | ✓ | A clear, versatile, and friendly mid-range male voice | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112151-479148939756.wav |
| `en_female_nadia_uranus_bigtts` | Blair | female | General |  | A young American female voice—clean and clear, with a gentle, relaxed way of speaking | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135157-566436208791.wav |
| `en_male_kevin_uranus_bigtts` | Kevin | male | Education | ✓ | A young, clear, and friendly American male voice with fluent, articulate delivery | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135225-335389250698.wav |
| `en_male_jamie_uranus_bigtts` | Jamie | male | General |  | A hearty male voice—sincere and candid, witty and full of energy | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135408-719229071308.wav |
| `en_female_hayley_uranus_bigtts` | Hayley | female | Education | ✓ | A lively female voice with strong emotional tension, skilled at storytelling | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135425-1467433606159.wav |
| `en_female_skye_uranus_bigtts` | Skye | female | General | ✓ | A clear, candid older sister who speaks sincerely and from the heart | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135541-1555904357610.wav |
| `en_male_bruce_uranus_bigtts` | Adrian | male | General |  | A composed, level-headed gentleman with rational restraint | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135611-484512265785.wav |
| `en_male_alex_uranus_bigtts` | Alex | male | General |  | A young man who is objective and composed, with a warm, clear voice | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135639-840828958085.wav |
| `en_male_yangguangjieshuonan_uranus_bigtts` | Dylan | male | General |  | A witty, humorous uncle with American pronunciation and a vivid, expressive narrative style. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135654-493733909658.wav |
| `en_male_ronald_uranus_bigtts` | Ronald | male | AudioBook |  | A British gentleman with a deep, resonant, dignified voice | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135907-1636867644896.wav |
| `en_male_diyuwenrounan_uranus_bigtts` | Julian | male | AudioBook |  | A refined, gentle man who is sincere and friendly, with a relaxed, easygoing way of speaking | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112218-1683295024357.wav |
| `en_male_knightley_uranus_bigtts` | Knightley | male | AudioBook |  | A deep, magnetic American middle-aged male voice with a steady, dignified manner | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812135952-1390971360481.wav |
| `en_male_fernando-martinez_uranus_bigtts` | Felix | male | General |  | A cheerful male voice—lively in conversation and highly contagious in emotion | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140013-190273807530.wav |
| `en_male_michael_uranus_bigtts` | Hank | male | General |  | A laid-back man with a deep, magnetic voice and a relaxed, easygoing manner | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112245-602144329640.wav |
| `en_male_josh_uranus_bigtts` | Josh | male | Dubbing |  | A clear, bright young man—cheerful, energetic, and easygoing | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140130-1278375401109.wav |
| `en_male_simba_p1_uranus_bigtts` | Simba | male | General |  | A mature American male voice—deep and reserved, with a steady, composed tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140143-681607778263.wav |
| `en_male_motivational-coach_uranus_bigtts` | Rory | male | Entertainment |  | An energetic college-aged man—full of emotion and super dynamic | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140157-684020766269.wav |
| `en_male_marcus_uranus_bigtts` | Marcus | male | General | ✓ | A mature American male voice—mellow and deep, skilled at gentle, unhurried storytelling | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140220-573753353646.wav |
| `en_male_michael_kevin_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Michael_Kevin | male | General |  | A steady, mellow mid-range male voice with a calm, professional narration style | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140239-552835515742.wav |
| `en_male_valentino_uranus_bigtts` | Valentino | male | General |  | A calm, gentle, and approachable young male voice with a mellow tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140256-153881849623.wav |
| `en_male_josh_coery_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Josiah | male | Education |  | A businesslike young man with a deep, magnetic voice and a dignified, steady tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140308-89032612307.wav |
| `en_male_david_uranus_bigtts` | David | male | General |  | A middle-aged man with a deep, weighty voice, an unhurried pace, and natural pauses | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140320-119333422466.wav |
| `en_female_allison_uranus_bigtts` | Allison | female | Dubbing |  | An upbeat, enthusiastic college-aged woman, full of energy and warmth | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140355-1235416731399.wav |
| `en_male_godfather_uranus_bigtts` | Godfather | male | AudioBook |  | A mature man with sincere emotion who tells his story in a gentle, unhurried way | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140410-466341655815.wav |
| `en_male_evil-guy-oxley_uranus_bigtts` | Harrison | male | Dubbing |  | An industry heavyweight—rigorous and professional, with a steady, commanding presence | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140432-252324088452.wav |
| `en_male_joker_uranus_bigtts` | Joker | male | Entertainment |  | An American middle-aged male voice with a slow pace and a warm, magnetic tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112328-356713551851.wav |
| `en_female_wenrouzhishijieshuonv_uranus_bigtts` | Megan | female | CustomerService |  | A gentle, fun older sister with American pronunciation who shares interesting knowledge in a relaxed way. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140457-1206978628584.wav |
| `en_female_lana_del_rey_parky_s_p1_uranus_bigtts` | Ivy | female | CustomerService |  | A gentle, soft female voice with a warm, natural tone that is soothing to the ear | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140515-1459670874119.wav |
| `en_female_jane_uranus_bigtts` | Jane | female | Dubbing |  | An energetic young girl with outwardly vivid, expressive emotion | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112404-1011524852973.wav |
| `en_female_rachel_p1_uranus_bigtts` | Rachel | female | Entertainment |  | An outwardly expressive young female voice—bright and clear, with strong dramatic flair | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140755-832871475982.wav |
| `en_male_cowboy-bob_uranus_bigtts` | Bob | male | General |  | A mature man with a deep, resonant, slightly raspy voice and a relaxed, calm demeanor | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812140958-253982741782.wav |
| `en_female_brittney_pimintel_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Zoe | female | AudioBook |  | A calm, gentle young female voice with a steady, understated storytelling tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112428-1405161473843.wav |
| `en_female_female_tutor_ms-jenny_uranus_bigtts` | Holly | female | Education |  | An enthusiastic, energetic female host with a vivid, standout style | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141330-1561908753001.wav |
| `en_female_joanne_uranus_bigtts` | Joanne | female | General |  | A crisp, lively American young female voice with a light tone and a relaxed, natural conversational feel | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141425-1585940149486.wav |
| `en_male_bill_jones_corey_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Bill | male | General |  | A steady, self-assured male professional with poise and composure | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141433-477062632595.wav |
| `en_male_adam-imitation_uranus_bigtts` | Rowan | male | General |  | An easygoing, natural young man with a subtly cool, aloof edge | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141441-1231703896081.wav |
| `en_male_brad_pitt_p1_uranus_bigtts` | Brad_Pitt | male | General |  | A laid-back man with a low, husky voice and a relaxed, easygoing manner | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141452-101140770855.wav |
| `en_male_father-christmas_uranus_bigtts` | Alfred | male | General |  | An elder with a deep, resonant voice and clear, unhurried articulation | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112516-62711392310.wav |
| `en_male_hades_uranus_bigtts` | Beau | male | General |  | A free-spirited mature man with a relaxed, easygoing way of speaking | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141532-696880694219.wav |
| `en_male_alberto_uranus_bigtts` | Alberto | male | General |  | A gentle, approachable man with a low, soothing tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112532-257169121658.wav |
| `en_female_jenny_uranus_bigtts` | Jenny | female | General | ✓ | A naturally cheerful, smiling, warm and talkative personality | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141557-1287841536184.wav |
| `en_male_valentino_corey_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Clark | male | Dubbing |  | A mature, dignified uncle with American pronunciation and a steady, powerful professional narration style | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112641-895533999334.wav |
| `en_male_russell_uranus_bigtts` | Russell | male | General |  | An easygoing American male voice—sincere and friendly, with a natural, approachable tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141629-1440123010330.wav |
| `en_male_tom_hiddleston_p1_uranus_bigtts` | Tom | male | General |  | A deep, reserved uncle whose reciting style is full of narrative feeling. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112658-602064658913.wav |
| `en_female_authoritative-informative_uranus_bigtts` | Margaret | female | General |  | A gentle, sincere big sister who tells her story in a soft, unhurried way | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141647-1030207862432.wav |
| `en_male_jidongchuanjiaoshi_uranus_bigtts` | Blaze | male | Entertainment |  | An immersive, passionate performance with high-spirited, fervent intonation | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141653-1594833122100.wav |
| `en_female_myra_uranus_bigtts` | Myra | female | Education |  | A sweet, lively young-girl voice that tells stories in a gentle, moving way | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141701-23813566020.wav |
| `en_male_bill-jones_uranus_bigtts` | Jones | male | Entertainment |  | A humorous uncle with a thick Southern American rural accent | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812141954-1286656740372.wav |
| `en_female_pleasant-female_uranus_bigtts` | Elaine | female | AudioBook |  | A gentle, lovely young lady who tells you the little joys of life with heartfelt warmth | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142001-376515827960.wav |
| `en_female_scarlet_p1_uranus_bigtts` | Scarlet | female | CustomerService |  | A gentle, deeply affectionate older sister whose eyes always hold a spark of light | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142010-1104040283124.wav |
| `en_female_brittney_uranus_bigtts` | Brittney | female | General |  | A warm, intelligent older sister with a tender heart | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142018-1175394545635.wav |
| `en_female_lana_del_rey_kelley_d_p1_uranus_bigtts` | Lynn | female | RolePlay |  | An American young female voice—soft, slow and slightly husky | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112718-1084167131772.wav |
| `en_female_mel_uranus_bigtts` | Mel | female | Education |  | A lively, dynamic American female voice with vivid ups and downs, skilled at performing animated dialogue | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142031-990478358205.wav |
| `en_male_chandler_p1_uranus_bigtts` | Leo | male | Entertainment |  | A theatrical man with exaggerated, dramatic intonation and rich expressiveness | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142132-936396896366.wav |
| `en_female_natasha_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Natasha | female | General |  | A conversational female voice—bright and vivid, warm and approachable | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142138-1234309873658.wav |
| `en_male_cowboy_john_b_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | John | male | Entertainment |  | An energetic, flamboyant uncle with a Southern American accent | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142146-250936435204.wav |
| `en_male_deep-voice_uranus_bigtts` | Orion | male | Entertainment |  | A solid, textured voice with a slow pace and full dramatic expressiveness. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142152-337745107764.wav |
| `en_male_jimmy_uranus_bigtts` | Jimmy | male | General |  | A natural, clear American young male voice with smooth, fluent delivery and an easygoing tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142158-658844092062.wav |
| `en_male_excited-male-voice_uranus_bigtts` | Jasper | male | Entertainment |  | A passionate young male voice—high-spirited and impassioned, with exaggerated, sweeping intonation | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142218-770612490823.wav |
| `en_female_xinwenjieshuonv_uranus_bigtts` | Kayla | female | RolePlay |  | An enthusiastic, outgoing female college student with American pronunciation, full of emotion and expressiveness. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142224-478329543480.wav |
| `en_female_authoritative-british_uranus_bigtts` | Charlotte | female | Education |  | A bright, crisp older sister with plenty of tension and drive | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142230-282129010135.wav |
| `en_female_myra_cmb_uranus_bigtts （Note：TTS Unidirectional Streaming Only — Not Supported for Bidirectional Streaming API）` | Sunny | female | Education |  | A crisp, lively American young female voice—full of enthusiasm and outstanding expressiveness | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142242-539072841077.wav |
| `en_female_zendaya_p1_uranus_bigtts` | Zendaya | female | Education |  | An easygoing, approachable older sister—relaxed and unpretentious, yet full of energy. | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142328-806946409618.wav |
| `en_male_michael-mouse_uranus_bigtts` | Chip | male | Entertainment |  | A cartoonish male voice with a lively, high-pitched tone and an exaggerated, comical style | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260812142336-390497613572.wav |
| `en_male_gollum_uranus_bigtts` | Gollum | male | RolePlay |  | A wacky, over-the-top male voice, skilled at creating playful characters | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112823-1251247677009.wav |
| `en_female_sharron_uranus_bigtts` | Sharron | female | Entertainment |  | A soft-spoken young woman with a gentle, breathy whisper voice—slightly husky, intimate, and soothing, with a leisurely, easygoing tone | https://sf-bpcms.bytepluscdn.com/obj/byteplus-public-aiso/cloud-universal-doc/20260902112858-1036113408199.wav |

