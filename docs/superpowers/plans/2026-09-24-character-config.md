# Cấu hình nhân vật (ngoại hình theo trường + chọn giọng) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho người dùng sửa ngoại hình nhân vật theo từng trường (backend tự ghép prompt ảnh) và chọn thẳng giọng TTS BytePlus cho nhân vật (nghe thử file mẫu, giọng đã chọn được khóa khi lồng tiếng).

**Architecture:** Ngoại hình lưu ở `DramaAsset.params.appearance`; hàm thuần `appearance_prompt.py` ghép prompt, được gọi khi seed từ kịch bản và khi PATCH asset. Danh mục giọng vi/en chuyển sang file JSON dữ liệu, các giọng mới gắn `auto_pool: false` để không làm đổi giọng tự động hiện có; endpoint catalog + tab "Chọn giọng" tạo tư liệu giọng có `speakerLocked`, và một hàm dùng chung `resolve_bound_speaker` tôn trọng khóa ở cả lúc tổng hợp mẫu lẫn lúc lồng tiếng.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / pytest (asyncio_mode=auto); React 19 / TS / Vite; node:test cho helper frontend.

**Spec:** `docs/superpowers/specs/2026-09-24-character-config-design.md`

## Global Constraints

- Không thêm cột DB; mọi dữ liệu mới nằm trong `DramaAsset.params` (JSON).
- 8 khóa ngoại hình, đúng thứ tự: `gender, age, face, hair, build, outfit, signature, style_note`.
- Cờ khóa giọng trên tư liệu giọng: `params.speakerLocked` (bool). Cờ chỉnh tay prompt trên nhân vật: `params.promptManual` (bool).
- Giọng mới trong danh mục: `auto_pool: false`; `list_voices()` (API `/api/voices` của 科普 studio), `default_voice_for_lang`, `lang_voice_pool` bỏ qua chúng. `tests/fixtures/voice_lang_vectors.json` **không được sửa** và phải tiếp tục pass.
- Commit message tiếng Việt, kết thúc bằng dòng `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Chuỗi giao diện mới có đủ 3 locale `vi`/`en`/`zh` trong `frontend/src/i18n/locales/*/dramaAssets.ts`; tiếng Việt tự nhiên theo `docs/I18N_GLOSSARY_VI.md` ("tư liệu", "giọng", "nhân vật"; không dịch word-by-word).
- Mỗi hàm / component / hook mới có comment chức năng ở đầu (theo `docs/STANDARDS.md`); file mới ≤ 500 dòng.
- Người dùng frontend: dùng class `pf-*` / `drama-*` có sẵn, **không** dùng Tailwind.
- Lệnh chạy test backend từ `backend/`: `pytest tests/<file> -q`. Frontend từ `frontend/`: `npm test`, `npm run lint`, `npm run build`.

## Rulings (quyết định khi lập kế hoạch, lệch/bổ sung so với spec)

1. **Ngôn ngữ giá trị `appearance`:** dự án vi/en → AI viết bằng tiếng Anh (giống tiền lệ `visualImage` ở `agents.run_script_summary`, vì model ảnh hiểu tiếng Anh tốt hơn); dự án zh → tiếng Trung. Người dùng gõ ngôn ngữ nào cũng được.
2. **Catalog endpoint nhận `project_id` thay vì `lang`:** `GET /api/drama/voices/catalog?project_id=` tự suy ngôn ngữ nội dung dự án, trả `{lang, voices}`. Frontend không phải tự đoán ngôn ngữ.
3. **Mô tả giọng giữ tiếng Anh gốc BytePlus;** không dịch 62 mô tả. Giao diện dịch nhãn giới tính và nhóm (`scenario`). `label_i18n` của 13 giọng cũ giữ nguyên; giọng mới `label_i18n` = tên giọng cho cả 3 ngôn ngữ.
4. **`list_voices()` bỏ giọng `auto_pool: false`** để trang chọn giọng科普 studio và `voiceKeyForLang` ở frontend không đổi hành vi.
5. **Dữ liệu 7+68 giọng vi/en chuyển vào `backend/app/services/data/byteplus_tts_voices.json`**, sinh từ Phụ lục A của spec bằng script ở Task 4; `voices.py` đọc file này thay cho tuple khai báo tay.
6. **Giọng đã khóa bỏ qua "voice design"** (thiết kế giọng Volc) khi tổng hợp mẫu, vì người dùng đã chọn giọng cụ thể.
7. **Tổng hợp lại (resynth) tư liệu giọng đã khóa giữ khóa** nếu `speaker` gửi lên trùng `params.speaker` hiện có.

## Review Focus

1. Dự án đổi ngôn ngữ sau khi đã khóa giọng (giọng `en_*` khóa, dự án thành `vi`) → lồng tiếng không được gọi TTS với giọng sai ngôn ngữ; rơi về luồng tự đoán + log cảnh báo. Test ở Task 5.
2. Người dùng sửa tay prompt rồi sửa tiếp một trường ngoại hình → prompt tay không bị ghi đè cho tới khi bấm "Tạo lại prompt từ các trường". Test ở Task 3 (backend) và Task 6 (helper frontend).
3. LLM tách trường trả JSON thiếu khóa / sai kiểu / có khóa lạ → vẫn lưu 8 khóa chuỗi, không crash; trả toàn rỗng → lỗi `drama.appearance_extract_failed`, không ghi params. Test ở Task 3.
4. PATCH asset không phải nhân vật (cảnh, đạo cụ) có `params.appearance` → không động vào prompt. Test ở Task 3.
5. Kịch bản cũ không có `appearance` (hoặc `appearance` không phải dict) → `build_character_params` giữ nguyên hành vi cũ, byte-for-byte. Test ở Task 2.

---

## File Structure

Backend (tạo mới):
- `backend/app/services/drama/appearance_prompt.py` — hàm thuần: chuẩn hóa, ghép prompt ngoại hình, áp vào params.
- `backend/app/services/drama/appearance_extract.py` — một lượt LLM tách prompt cũ thành 8 trường.
- `backend/app/services/data/byteplus_tts_voices.json` — dữ liệu giọng vi/en (sinh từ spec).
- `backend/app/api/drama/voices.py` — router `GET /drama/voices/catalog`.
- `backend/scripts/gen_byteplus_voices.py` — script sinh file JSON từ Phụ lục A (chạy một lần, commit cả script).
- Tests: `backend/tests/test_drama_appearance.py`, `backend/tests/test_voice_catalog.py`, `backend/tests/test_drama_speaker_lock.py`.

Backend (sửa):
- `backend/app/services/drama/seed_asset_params.py` — `build_character_params` dùng `appearance`.
- `backend/app/services/drama/script_summary_prompt.py` — schema thêm `appearance`.
- `backend/app/api/drama/assets.py` — PATCH gọi `apply_appearance_to_params`; endpoint tách trường.
- `backend/app/services/tasks/handlers.py` — đăng ký `("drama", "appearance_extract")`.
- `backend/app/errors.py` — mã `drama.appearance_extract_failed`.
- `backend/app/services/voices.py`, `backend/app/services/voice_lang.py` — đọc JSON, cờ `auto_pool`.
- `backend/app/api/drama/__init__.py` — include router voices.
- `backend/app/schemas_drama.py` — `DramaVoiceGenerateRequest.speaker_locked`.
- `backend/app/api/drama/generation.py`, `backend/app/services/drama/generation.py`, `backend/app/services/drama/voice_synthesis.py`, `backend/app/services/drama/fragment_dub.py` — khóa giọng.

Frontend (tạo mới):
- `frontend/src/lib/dramaAppearance.ts` + `frontend/tests/dramaAppearance.test.ts` — helper thuần.
- `frontend/src/pages/drama/CharacterAppearanceForm.tsx` — form 8 trường.
- `frontend/src/pages/drama/VoiceCatalogPicker.tsx` — danh sách giọng + nghe thử.

Frontend (sửa):
- `frontend/src/api/drama.ts` — `extractAppearance`, `voiceCatalog`, `generateVoice.speaker_locked`.
- `frontend/src/pages/drama/DramaAssetDetailModal.tsx`, `frontend/src/pages/drama/CharacterVoiceBindModal.tsx`.
- `frontend/src/i18n/locales/{vi,en,zh}/dramaAssets.ts`, `frontend/src/i18n/locales/{vi,en,zh}/errors.ts`.
- `frontend/src/pages/drama/drama.css` — style tối thiểu cho form/danh sách.

Docs: `docs/PROVIDERS.md`.

---

### Task 1: Hàm thuần ghép prompt ngoại hình

**Files:**
- Create: `backend/app/services/drama/appearance_prompt.py`
- Test: `backend/tests/test_drama_appearance.py`

**Interfaces:**
- Consumes: `manju_join_character_prompt(character: dict, lang: str | None) -> str`, `use_zh_prompt_labels(lang, sample) -> bool` từ `app.services.drama.seed_asset_params`.
- Produces:
  - `APPEARANCE_KEYS: tuple[str, ...]`
  - `normalize_appearance(raw: Any) -> dict[str, str]` — luôn đủ 8 khóa.
  - `appearance_is_empty(appearance: dict[str, str]) -> bool`
  - `compose_appearance_prompt(appearance: dict[str, str], lang: str | None) -> str`
  - `apply_appearance_to_params(params: dict[str, Any], lang: str | None) -> dict[str, Any]` — trả params mới (không sửa input).

- [ ] **Step 1: Viết test fail**

`backend/tests/test_drama_appearance.py`:

```python
"""Ngoại hình nhân vật theo trường: chuẩn hóa, ghép prompt, áp vào params."""

from app.services.drama.appearance_prompt import (
    APPEARANCE_KEYS,
    appearance_is_empty,
    apply_appearance_to_params,
    compose_appearance_prompt,
    normalize_appearance,
)


def test_normalize_keeps_eight_keys_and_strips():
    out = normalize_appearance({"hair": "  long black hair ", "age": 25, "bogus": "x"})
    assert tuple(out.keys()) == APPEARANCE_KEYS
    assert out["hair"] == "long black hair"
    assert out["age"] == "25"
    assert "bogus" not in out
    assert out["gender"] == ""


def test_normalize_non_dict_gives_all_empty():
    for raw in (None, "text", ["a"], 3):
        out = normalize_appearance(raw)
        assert appearance_is_empty(out)
        assert tuple(out.keys()) == APPEARANCE_KEYS


def test_compose_english_labels_for_vi_and_en_skips_empty():
    ap = normalize_appearance({"gender": "female", "age": "25", "outfit": "white ao dai"})
    for lang in ("vi", "en"):
        assert compose_appearance_prompt(ap, lang) == "Gender: female. Age: 25. Outfit: white ao dai"


def test_compose_chinese_labels_for_zh():
    ap = normalize_appearance({"gender": "女", "hair": "黑色长发"})
    assert compose_appearance_prompt(ap, "zh") == "性别：女。发型：黑色长发"


def test_compose_all_empty_returns_empty_string():
    assert compose_appearance_prompt(normalize_appearance({}), "vi") == ""


def test_apply_writes_three_prompt_slots_with_role_labels():
    params = {
        "appearance": {"gender": "female", "hair": "ponytail"},
        "roleType": "lead",
        "canvas": {"generation": {"prompt": "old", "ratio": "9:16"}},
    }
    out = apply_appearance_to_params(params, "en")
    expected = "Gender: female. Hair: ponytail. Role: lead"
    assert out["visualPrompt"] == expected
    assert out["visualImage"] == expected
    assert out["canvas"]["generation"] == {"prompt": expected, "ratio": "9:16"}
    assert out["appearance"]["hair"] == "ponytail"
    assert params["canvas"]["generation"]["prompt"] == "old"  # không sửa input


def test_apply_respects_prompt_manual():
    params = {"appearance": {"gender": "male"}, "promptManual": True, "visualPrompt": "hand written"}
    out = apply_appearance_to_params(params, "vi")
    assert out["visualPrompt"] == "hand written"


def test_apply_noop_when_appearance_empty():
    params = {"appearance": {}, "visualPrompt": "keep me"}
    out = apply_appearance_to_params(params, "vi")
    assert out["visualPrompt"] == "keep me"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_drama_appearance.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.drama.appearance_prompt'`

- [ ] **Step 3: Viết code**

`backend/app/services/drama/appearance_prompt.py`:

```python
"""Ngoại hình nhân vật theo trường (params.appearance) → prompt ảnh định trang.

Chỉ ghép ở backend để không có hai bản code ghép prompt lệch nhau giữa frontend và backend.
"""

from __future__ import annotations

from typing import Any

from app.services.drama.seed_asset_params import manju_join_character_prompt, use_zh_prompt_labels

# Thứ tự cố định của các trường ngoại hình (cũng là thứ tự ghép prompt)
APPEARANCE_KEYS: tuple[str, ...] = (
    "gender",
    "age",
    "face",
    "hair",
    "build",
    "outfit",
    "signature",
    "style_note",
)

_EN_LABELS = {
    "gender": "Gender",
    "age": "Age",
    "face": "Face",
    "hair": "Hair",
    "build": "Build",
    "outfit": "Outfit",
    "signature": "Signature details",
    "style_note": "Presence",
}
_ZH_LABELS = {
    "gender": "性别",
    "age": "年龄",
    "face": "五官",
    "hair": "发型",
    "build": "体型",
    "outfit": "服饰",
    "signature": "标志细节",
    "style_note": "气质",
}


def normalize_appearance(raw: Any) -> dict[str, str]:
    """Giữ đúng 8 khóa theo thứ tự, ép chuỗi và strip; bỏ khóa lạ; input không phải dict → toàn rỗng."""
    data = raw if isinstance(raw, dict) else {}
    out: dict[str, str] = {}
    for key in APPEARANCE_KEYS:
        value = data.get(key)
        out[key] = "" if value is None else str(value).strip()
    return out


def appearance_is_empty(appearance: dict[str, str]) -> bool:
    """Mọi trường đều rỗng."""
    return not any((appearance.get(k) or "").strip() for k in APPEARANCE_KEYS)


def compose_appearance_prompt(appearance: dict[str, str], lang: str | None) -> str:
    """Ghép các trường không rỗng: dự án zh dùng nhãn Trung, còn lại nhãn Anh; toàn rỗng → ""."""
    zh = use_zh_prompt_labels(lang, " ".join(appearance.values()))
    labels, pair_sep, join_sep = (_ZH_LABELS, "：", "。") if zh else (_EN_LABELS, ": ", ". ")
    parts = [
        f"{labels[k]}{pair_sep}{appearance[k]}" for k in APPEARANCE_KEYS if (appearance.get(k) or "").strip()
    ]
    return join_sep.join(parts)


def apply_appearance_to_params(params: dict[str, Any], lang: str | None) -> dict[str, Any]:
    """Trả params mới: nếu có ngoại hình và không ở chế độ chỉnh tay thì ghi prompt ghép vào
    visualPrompt / visualImage / canvas.generation.prompt (kèm nhãn title/roleType/coreTags/personality)."""
    out = dict(params or {})
    appearance = normalize_appearance(out.get("appearance"))
    out["appearance"] = appearance
    if out.get("promptManual") is True or appearance_is_empty(appearance):
        return out
    body = compose_appearance_prompt(appearance, lang)
    prompt = manju_join_character_prompt({**out, "visualImage": body}, lang)
    out["visualPrompt"] = prompt
    out["visualImage"] = prompt
    canvas = dict(out["canvas"]) if isinstance(out.get("canvas"), dict) else {}
    gen = dict(canvas["generation"]) if isinstance(canvas.get("generation"), dict) else {}
    gen["prompt"] = prompt
    canvas["generation"] = gen
    out["canvas"] = canvas
    return out
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd backend && pytest tests/test_drama_appearance.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/drama/appearance_prompt.py backend/tests/test_drama_appearance.py
git commit -m "feat(phim truyện): hàm ghép prompt ảnh từ ngoại hình nhân vật theo trường

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: AI sinh sẵn `appearance` khi sinh kịch bản + seed dùng các trường

**Files:**
- Modify: `backend/app/services/drama/script_summary_prompt.py` (quy tắc 12 và schema JSON `characters[]`)
- Modify: `backend/app/services/drama/seed_asset_params.py:101-123` (`build_character_params`)
- Test: `backend/tests/test_drama_appearance.py` (thêm test)

**Interfaces:**
- Consumes: `normalize_appearance`, `appearance_is_empty`, `compose_appearance_prompt` (Task 1).
- Produces: `build_character_params(character, lang)` trả thêm `"appearance": dict[str, str]` (8 khóa) và `"promptManual": False` khi kịch bản có `appearance` không rỗng.

- [ ] **Step 1: Viết test fail** (thêm vào cuối `backend/tests/test_drama_appearance.py`)

```python
from app.services.drama.script_summary_prompt import SCRIPT_SUMMARY_SYSTEM_PROMPT
from app.services.drama.seed_asset_params import build_character_params


def test_summary_prompt_asks_for_appearance_fields():
    assert '"appearance"' in SCRIPT_SUMMARY_SYSTEM_PROMPT
    for key in APPEARANCE_KEYS:
        assert f'"{key}"' in SCRIPT_SUMMARY_SYSTEM_PROMPT


def test_build_character_params_uses_appearance_when_present():
    ch = {
        "name": "Lan",
        "roleType": "lead",
        "visualImage": "long paragraph that should be replaced",
        "appearance": {"gender": "female", "age": "25", "hair": "ponytail"},
    }
    params = build_character_params(ch, "vi")
    expected = "Gender: female. Age: 25. Hair: ponytail. Role: lead"
    assert params["visualPrompt"] == expected
    assert params["visualImage"] == expected
    assert params["canvas"]["generation"]["prompt"] == expected
    assert params["appearance"]["hair"] == "ponytail"
    assert params["promptManual"] is False


def test_build_character_params_unchanged_without_appearance():
    ch = {"name": "Lan", "roleType": "lead", "visualImage": "A young woman in a white ao dai"}
    for extra in ({}, {"appearance": None}, {"appearance": "text"}, {"appearance": {}}):
        params = build_character_params({**ch, **extra}, "vi")
        assert params["visualPrompt"] == "A young woman in a white ao dai. Role: lead"
        assert params["visualImage"] == "A young woman in a white ao dai"
        assert "appearance" not in params
        assert "promptManual" not in params
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_drama_appearance.py -q`
Expected: FAIL ở 2 test mới đầu (`'"appearance"' in ...` sai; `visualPrompt` còn là đoạn văn cũ).

- [ ] **Step 3a: Sửa prompt kịch bản**

Trong `SCRIPT_SUMMARY_SYSTEM_PROMPT` (`script_summary_prompt.py`), ngay sau dòng quy tắc 12 (`12. 每人 visualImage 须 100–200 字...`) thêm dòng:

```text
12b. 每人另给 appearance 对象，把 visualImage 拆成 8 个短字段（每个 ≤ 30 字，具体可拍摄，与 visualImage 一致，不适用可为空字符串）：gender 性别、age 年龄感、face 脸型五官、hair 发型发色、build 体型身高、outfit 服饰材质与配色、signature 标志性道具或细节、style_note 气质神态
```

Trong schema JSON, sau dòng `"visualImage": string,` thêm:

```text
      "appearance": {
        "gender": string,
        "age": string,
        "face": string,
        "hair": string,
        "build": string,
        "outfit": string,
        "signature": string,
        "style_note": string
      },
```

Trong `backend/app/services/drama/agents.py` hàm `run_script_summary`, chuỗi bổ sung cho dự án không phải zh hiện là `"\n14. characters[].visualImage 是定妆照生图提示词，用英文（English）书写；"` — đổi thành:

```python
            "\n14. characters[].visualImage 与 characters[].appearance 的各字段是定妆照生图提示词，用英文（English）书写；"
```

- [ ] **Step 3b: Sửa `build_character_params`**

Trong `seed_asset_params.py`, thay thân `build_character_params` bằng:

```python
def build_character_params(character: dict[str, Any], lang: str | None = None) -> dict[str, Any]:
    # 有 appearance（按字段的外形）时由字段拼 visualImage 正文；否则沿用旧逻辑
    from app.services.drama.appearance_prompt import (
        appearance_is_empty,
        compose_appearance_prompt,
        normalize_appearance,
    )

    appearance = normalize_appearance(character.get("appearance"))
    has_appearance = not appearance_is_empty(appearance)
    if has_appearance:
        character = {**character, "visualImage": compose_appearance_prompt(appearance, lang)}
    prompt = manju_join_character_prompt(character, lang)
    visual = prompt if has_appearance else (str(character.get("visualImage") or "").strip() or prompt)
    params: dict[str, Any] = {
        "visualImage": visual,
        "visualPrompt": prompt,
        "roleType": character.get("roleType"),
        "title": character.get("title"),
        "coreTags": character.get("coreTags"),
        "identityBackground": character.get("identityBackground"),
        "growthExperience": character.get("growthExperience"),
        "personality": character.get("personality"),
        "relationships": character.get("relationships"),
        "growthArc": character.get("growthArc"),
        "canvas": {
            "appearanceName": DEFAULT_APPEARANCE_NAME,
            "generation": {
                "prompt": prompt,
                **DEFAULT_IMAGE_GENERATION,
            },
            "seededFromScript": True,
        },
    }
    if has_appearance:
        params["appearance"] = appearance
        params["promptManual"] = False
    return params
```

(Import cục bộ để tránh vòng import: `appearance_prompt` import `seed_asset_params`.)

- [ ] **Step 4: Chạy test**

Run: `cd backend && pytest tests/test_drama_appearance.py tests/test_content_lang.py -q`
Expected: tất cả pass (test_content_lang có dùng `build_character_params`, phải không đổi).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/drama/script_summary_prompt.py backend/app/services/drama/agents.py backend/app/services/drama/seed_asset_params.py backend/tests/test_drama_appearance.py
git commit -m "feat(phim truyện): kịch bản sinh sẵn ngoại hình nhân vật theo trường

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Lưu ngoại hình qua PATCH + endpoint "AI tách trường"

**Files:**
- Create: `backend/app/services/drama/appearance_extract.py`
- Modify: `backend/app/api/drama/assets.py` (`update_asset` + endpoint mới)
- Modify: `backend/app/services/tasks/handlers.py:287` (thêm dòng đăng ký)
- Modify: `backend/app/errors.py` (sau `"drama.character_asset_only"`)
- Modify: `frontend/src/i18n/locales/{vi,en,zh}/errors.ts`
- Test: `backend/tests/test_drama_appearance.py`

**Interfaces:**
- Consumes: `normalize_appearance`, `appearance_is_empty`, `apply_appearance_to_params` (Task 1); `drama_chat_json` (`app.services.drama.llm`); `run_billed_ephemeral`, `record_llm_chat_line` (`app.services.billing`); `project_content_lang`.
- Produces:
  - `should_recompose_prompt(asset_type: str | None, patch: dict | None) -> bool` (trong `appearance_prompt.py`)
  - `async extract_appearance_fields(asset: DramaAsset, lang: str) -> dict[str, str]` — raise `AppError("drama.appearance_extract_failed")` khi kết quả toàn rỗng.
  - `POST /api/drama/assets/{asset_id}/appearance/extract` → `{"ok": true, "appearance": {...8 khóa}, "task_id": int}` (không đổi params nào khác ngoài `appearance`).
  - Mã lỗi `drama.appearance_extract_failed` (HTTP 502, "外形字段拆分失败").

- [ ] **Step 1: Viết test fail** (thêm vào `backend/tests/test_drama_appearance.py`)

```python
import pytest

from app.errors import AppError
from app.services.drama import appearance_extract
from app.services.drama.appearance_prompt import should_recompose_prompt


def test_should_recompose_only_for_character_with_appearance_keys():
    assert should_recompose_prompt("character", {"appearance": {"hair": "x"}})
    assert should_recompose_prompt("Character", {"promptManual": False})
    assert not should_recompose_prompt("scene", {"appearance": {"hair": "x"}})
    assert not should_recompose_prompt("character", {"visualPrompt": "x"})
    assert not should_recompose_prompt("character", None)


def test_manual_prompt_survives_later_appearance_edit():
    params = {"appearance": {"hair": "short"}, "promptManual": True, "visualPrompt": "my own prompt"}
    params = apply_appearance_to_params({**params, "appearance": {"hair": "long"}}, "vi")
    assert params["visualPrompt"] == "my own prompt"
    params = apply_appearance_to_params({**params, "promptManual": False}, "vi")
    assert params["visualPrompt"] == "Hair: long"


class _Asset:
    id = 7
    name = "Lan"
    type = "character"
    params = {"visualPrompt": "A young woman, 25, long black ponytail, white ao dai"}


async def test_extract_normalizes_llm_output(monkeypatch):
    async def fake_json(system, user, **kwargs):
        assert "A young woman" in user
        return {"hair": "long black ponytail", "age": 25, "junk": "x"}

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    out = await appearance_extract.extract_appearance_fields(_Asset(), "vi")
    assert tuple(out.keys()) == APPEARANCE_KEYS
    assert out["hair"] == "long black ponytail"
    assert out["age"] == "25"


async def test_extract_all_empty_raises(monkeypatch):
    async def fake_json(system, user, **kwargs):
        return ["not", "a", "dict"]

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    with pytest.raises(AppError) as err:
        await appearance_extract.extract_appearance_fields(_Asset(), "vi")
    assert err.value.code == "drama.appearance_extract_failed"


async def test_extract_without_source_text_raises(monkeypatch):
    class _Empty(_Asset):
        params = {}

    async def fake_json(*a, **k):
        raise AssertionError("không được gọi LLM khi không có mô tả")

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    with pytest.raises(AppError) as err:
        await appearance_extract.extract_appearance_fields(_Empty(), "vi")
    assert err.value.code == "drama.appearance_extract_failed"
```

Kiểm tra `AppError` có thuộc tính `.code`: chạy `grep -n "class AppError" -A15 backend/app/errors.py`; nếu tên thuộc tính khác (ví dụ `error_code`), dùng đúng tên đó trong 2 assert.

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_drama_appearance.py -q`
Expected: FAIL — `ImportError: cannot import name 'should_recompose_prompt'` / module `appearance_extract` không tồn tại.

- [ ] **Step 3a: `should_recompose_prompt`** — thêm vào cuối `appearance_prompt.py`:

```python
def should_recompose_prompt(asset_type: str | None, patch: dict[str, Any] | None) -> bool:
    """PATCH tư liệu có cần ghép lại prompt: chỉ nhân vật, và body có appearance hoặc promptManual."""
    if (asset_type or "").lower() != "character" or not isinstance(patch, dict):
        return False
    return "appearance" in patch or "promptManual" in patch
```

- [ ] **Step 3b: Mã lỗi.** Trong `backend/app/errors.py`, sau dòng `"drama.character_asset_only": (400, "仅支持角色资产"),` thêm:

```python
    "drama.appearance_extract_failed": (502, "外形字段拆分失败"),
```

Trong `frontend/src/i18n/locales/vi/errors.ts` sau `'drama.character_asset_only': ...` thêm `'drama.appearance_extract_failed': 'Không tách được các trường ngoại hình, vui lòng thử lại',`; `en/errors.ts`: `'drama.appearance_extract_failed': 'Could not split the appearance into fields, please try again',`; `zh/errors.ts`: `'drama.appearance_extract_failed': '外形字段拆分失败，请重试',`.

Nếu có test kiểm tra đồng bộ mã lỗi backend ↔ frontend (`grep -rn "errors.ts" backend/tests frontend/tests`), chạy nó ở Step 4.

- [ ] **Step 3c: `appearance_extract.py`**

```python
"""AI tách mô tả ngoại hình cũ (visualPrompt / visualImage) của nhân vật thành 8 trường appearance."""

from __future__ import annotations

import json
import logging

from app.errors import AppError
from app.models_drama import DramaAsset
from app.services.content_lang import is_zh
from app.services.drama.appearance_prompt import APPEARANCE_KEYS, appearance_is_empty, normalize_appearance
from app.services.drama.llm import drama_chat_json

logger = logging.getLogger(__name__)

APPEARANCE_EXTRACT_SYSTEM = """你是影视定妆设计师。把给定的角色外形描述拆成 8 个短字段，输出严格 JSON 对象（不要 markdown）：
{"gender": string, "age": string, "face": string, "hair": string, "build": string, "outfit": string, "signature": string, "style_note": string}
要求：
1. 只根据描述拆分，不要编造描述里没有的信息；描述未提及的字段给空字符串
2. 每个字段 ≤ 30 字，具体、可拍摄
3. gender 性别；age 年龄感；face 脸型五官；hair 发型发色；build 体型身高；outfit 服饰材质与配色；signature 标志性道具或细节；style_note 气质神态"""


def _source_text(asset: DramaAsset) -> str:
    """待拆分的外形描述：优先 visualPrompt，其次 visualImage。"""
    params = asset.params if isinstance(asset.params, dict) else {}
    for key in ("visualPrompt", "visualImage"):
        text = str(params.get(key) or "").strip()
        if text:
            return text
    return ""


async def extract_appearance_fields(asset: DramaAsset, lang: str) -> dict[str, str]:
    """一次 LLM 调用把外形描述拆成 8 字段；无描述或结果全空 → AppError(drama.appearance_extract_failed)。"""
    source = _source_text(asset)
    if not source:
        raise AppError("drama.appearance_extract_failed")
    system = APPEARANCE_EXTRACT_SYSTEM
    if not is_zh(lang):
        system += "\n4. 各字段值用英文（English）书写"
    user = f"角色名：{asset.name or ''}\n外形描述：\n{source}"
    try:
        data = await drama_chat_json(system, user, temperature=0.2, max_tokens=1024, lang=lang)
    except (RuntimeError, json.JSONDecodeError) as exc:
        logger.warning("外形字段拆分 LLM 失败 asset_id=%s err=%s", asset.id, exc)
        raise AppError("drama.appearance_extract_failed") from exc
    appearance = normalize_appearance(data)
    if appearance_is_empty(appearance):
        raise AppError("drama.appearance_extract_failed")
    return {k: appearance[k] for k in APPEARANCE_KEYS}
```

Kiểm tra `is_zh` tồn tại trong `app.services.content_lang` (`grep -n "def is_zh" backend/app/services/content_lang.py`); `voice_prompt.py` đã import nó từ đó.

- [ ] **Step 3d: Đăng ký task type.** Trong `backend/app/services/tasks/handlers.py`, ngay dưới dòng `("drama", "voice_prompt"): TaskHandler("drama", "voice_prompt", _noop_ephemeral),` thêm:

```python
    ("drama", "appearance_extract"): TaskHandler("drama", "appearance_extract", _noop_ephemeral),
```

Kiểm tra giá ước tính cho task type ephemeral: `grep -rn "\"voice_prompt\"" backend/app/services/billing` — nếu `voice_prompt` có mục riêng trong bảng giá/estimate, thêm mục `appearance_extract` y hệt ngay dưới.

- [ ] **Step 3e: PATCH gọi ghép lại prompt.** Trong `backend/app/api/drama/assets.py` hàm `update_asset`, thay vòng `for field in (...)` bằng:

```python
    for field in ("type", "asset_type", "name", "cover", "url", "params"):
        val = getattr(body, field)
        if val is None:
            continue
        if field == "params" and isinstance(val, dict):
            asset.params = _merge_asset_params(
                asset.params if isinstance(asset.params, dict) else {},
                val,
            )
            if should_recompose_prompt(asset.type, val):
                project = await db.get(DramaProject, asset.project_id)
                asset.params = apply_appearance_to_params(asset.params, project_content_lang(project))
        else:
            setattr(asset, field, val)
```

Import ở đầu file (khối import app.services): 

```python
from app.services.content_lang import project_content_lang
from app.services.drama.appearance_extract import extract_appearance_fields
from app.services.drama.appearance_prompt import apply_appearance_to_params, should_recompose_prompt
from app.services.billing import record_llm_chat_line, run_billed_ephemeral
```

(`run_billed_ephemeral` đã được import; gộp `record_llm_chat_line` vào cùng dòng. Bỏ dòng `from app.models_drama import DramaProject` cục bộ trong `update_asset` vì `DramaProject` đã import ở đầu file.)

- [ ] **Step 3f: Endpoint tách trường.** Thêm vào `assets.py`, ngay sau `update_asset`:

```python
@router.post("/assets/{asset_id}/appearance/extract")
async def extract_asset_appearance(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """AI 把角色旧的外形描述拆成 8 个字段并写入 params.appearance（不改 visualPrompt）。"""
    asset = await db.get(DramaAsset, asset_id)
    if not asset:
        raise AppError("drama.asset_not_found")
    project = await get_owned_drama_project(db, asset.project_id, user)
    if (asset.type or "").lower() != "character":
        raise AppError("drama.character_asset_only")
    lang = project_content_lang(project)

    async def _do_extract() -> dict[str, str]:
        appearance = await extract_appearance_fields(asset, lang)
        await record_llm_chat_line(db, user_id=user.id, domain="drama", drama_project_id=project.id)
        return appearance

    try:
        task, appearance = await run_billed_ephemeral(
            db,
            user,
            domain="drama",
            task_type="appearance_extract",
            executor=_do_extract,
            payload={"asset_id": asset.id},
            drama_project_id=project.id,
            asset_id=asset.id,
            commit=True,
        )
    except ValueError as exc:
        raise http_exception_for_value_error(exc) from exc

    asset.params = {**(asset.params or {}), "appearance": appearance}
    await db.commit()
    logger.info("外形字段已拆分 project_id=%s asset_id=%s task_id=%s", project.id, asset.id, task.id)
    return {"ok": True, "appearance": appearance, "task_id": task.id}
```

Kiểm tra `get_owned_drama_project(db, project_id, user)` chấp nhận gọi không có `with_script` (xem `app/services/drama/access.py`); nó raise khi user không sở hữu dự án.

- [ ] **Step 4: Chạy test**

Run: `cd backend && pytest tests/test_drama_appearance.py tests/test_app_errors.py -q`
Expected: tất cả pass.

Run thêm smoke import: `cd backend && python -c "import app.main"` — Expected: không lỗi.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/drama/appearance_prompt.py backend/app/services/drama/appearance_extract.py backend/app/api/drama/assets.py backend/app/services/tasks/handlers.py backend/app/errors.py frontend/src/i18n/locales/*/errors.ts backend/tests/test_drama_appearance.py
git commit -m "feat(phim truyện): lưu ngoại hình tự ghép lại prompt và AI tách trường cho nhân vật cũ

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Danh mục giọng vi/en đầy đủ + endpoint catalog

**Files:**
- Create: `backend/scripts/gen_byteplus_voices.py`
- Create: `backend/app/services/data/byteplus_tts_voices.json` (sinh bằng script)
- Create: `backend/app/api/drama/voices.py`
- Modify: `backend/app/services/voices.py:95-124` (khối tuple vi/en → đọc JSON), `list_voices()`
- Modify: `backend/app/services/voice_lang.py` (`default_voice_for_lang`, `lang_voice_pool`)
- Modify: `backend/app/api/drama/__init__.py`
- Test: `backend/tests/test_voice_catalog.py`

**Interfaces:**
- Produces:
  - Mỗi preset vi/en trong `VOICE_PRESETS` có thêm khóa `name: str`, `scenario: str`, `description: str`, `sample_url: str`, `auto_pool: bool`.
  - `catalog_voices(lang: str | None) -> list[dict]` trong `voices.py`: phần tử `{id, speaker, name, gender, scenario, description, sample_url}` theo thứ tự danh mục.
  - `GET /api/drama/voices/catalog?project_id=<int>` → `{"lang": "vi"|"en"|"zh", "voices": [...]}`.

- [ ] **Step 1: Script sinh dữ liệu**

`backend/scripts/gen_byteplus_voices.py`:

```python
"""Sinh app/services/data/byteplus_tts_voices.json từ Phụ lục A của spec cấu hình nhân vật.

Chạy từ backend/: python scripts/gen_byteplus_voices.py
Nguồn: https://docs.byteplus.com/en/docs/byteplusvoice/tts-voice-list (lấy ngày 2026-09-24).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/superpowers/specs/2026-09-24-character-config-design.md"
OUT = ROOT / "backend/app/services/data/byteplus_tts_voices.json"

# 13 giọng đã có trước đây: giữ thứ tự cũ ở đầu mỗi ngôn ngữ và vẫn vào pool tự động
LEGACY_ORDER = [
    "vi_female_ruan_uranus_bigtts",
    "vi_male_wumg_uranus_bigtts",
    "vi_female_ling_uranus_bigtts",
    "vi_female_linh_uranus_bigtts",
    "vi_female_wu_uranus_bigtts",
    "vi_female_hong_uranus_bigtts",
    "vi_female_partner_uranus_bigtts",
    "en_female_hayley_uranus_bigtts",
    "en_male_tim_uranus_bigtts",
    "en_female_skye_uranus_bigtts",
    "en_female_jenny_uranus_bigtts",
    "en_male_kevin_uranus_bigtts",
    "en_male_marcus_uranus_bigtts",
]
ROW_RE = re.compile(r"^\| `([^`]+)` \| ([^|]*) \| (female|male) \| ([^|]*) \| [^|]* \| ([^|]*) \| (\S*) \|$")


def main() -> None:
    text = SPEC.read_text(encoding="utf-8")
    appendix = text.split("## Phụ lục A", 1)[1]
    rows = {}
    for line in appendix.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        speaker, name, gender, scenario, desc, sample = (g.strip() for g in m.groups())
        rows[speaker] = {
            "speaker": speaker,
            "name": name,
            "gender": gender,
            "languages": [speaker.split("_", 1)[0]],
            "scenario": scenario,
            "description": desc,
            "sample_url": sample,
        }
    missing = [s for s in LEGACY_ORDER if s not in rows]
    assert not missing, f"thiếu giọng cũ trong phụ lục: {missing}"
    ordered = []
    for lang in ("vi", "en"):
        legacy = [s for s in LEGACY_ORDER if s.startswith(f"{lang}_")]
        rest = [s for s in rows if s.startswith(f"{lang}_") and s not in legacy]
        ordered += [{**rows[s], "auto_pool": True} for s in legacy]
        ordered += [{**rows[s], "auto_pool": False} for s in rest]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(ordered)} voices → {OUT}")


if __name__ == "__main__":
    main()
```

Run: `cd backend && python scripts/gen_byteplus_voices.py`
Expected: `wrote 75 voices → .../byteplus_tts_voices.json`. Kiểm tra: `python -c "import json;d=json.load(open('app/services/data/byteplus_tts_voices.json'));print(sum(v['auto_pool'] for v in d), len(d))"` → `13 75`.

Nếu `app/services/data/` chưa phải package và các file dữ liệu khác được đọc theo đường dẫn file (không qua importlib.resources) thì không cần `__init__.py`. Kiểm tra Dockerfile backend có copy toàn bộ `app/` (`grep -n "COPY" backend/Dockerfile`) để file JSON có trong image.

- [ ] **Step 2: Viết test fail**

`backend/tests/test_voice_catalog.py`:

```python
"""Danh mục giọng BytePlus vi/en: đủ dữ liệu, giọng mới không vào pool tự động, catalog theo ngôn ngữ."""

from app.services import voices
from app.services.voice_lang import default_voice_for_lang, lang_voice_pool, voice_supports_lang


def _by_lang(lang):
    return [p for p in voices.VOICE_PRESETS if lang in p["languages"]]


def test_catalog_counts():
    assert len(voices.catalog_voices("vi")) == 7
    assert len(voices.catalog_voices("en")) == 68
    assert voices.catalog_voices("fr") == []
    assert voices.catalog_voices(None) == []


def test_catalog_item_shape_and_order():
    first = voices.catalog_voices("vi")[0]
    assert first == {
        "id": "vi_female_ruan_uranus_bigtts",
        "speaker": "vi_female_ruan_uranus_bigtts",
        "name": "Ruan",
        "gender": "female",
        "scenario": "General",
        "description": first["description"],
        "sample_url": first["sample_url"],
    }
    assert first["description"] and first["sample_url"].startswith("https://")


def test_new_voices_excluded_from_auto_pool_and_list_voices():
    assert lang_voice_pool("en") == [
        "en_female_hayley_uranus_bigtts",
        "en_male_tim_uranus_bigtts",
        "en_female_skye_uranus_bigtts",
        "en_female_jenny_uranus_bigtts",
        "en_male_kevin_uranus_bigtts",
        "en_male_marcus_uranus_bigtts",
    ]
    assert default_voice_for_lang("en", "male") == "en_male_tim_uranus_bigtts"
    listed = {v["id"] for v in voices.list_voices()}
    assert "en_male_bruce_uranus_bigtts" not in listed
    assert "en_male_tim_uranus_bigtts" in listed


def test_new_voices_still_known_for_language_checks():
    assert voice_supports_lang("en_male_bruce_uranus_bigtts", "en")
    assert not voice_supports_lang("en_male_bruce_uranus_bigtts", "vi")


def test_all_vi_en_presets_have_catalog_fields():
    for p in _by_lang("vi") + _by_lang("en"):
        for key in ("name", "scenario", "description", "sample_url", "auto_pool", "label_i18n"):
            assert key in p, (p["id"], key)
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_voice_catalog.py -q`
Expected: FAIL — `AttributeError: module 'app.services.voices' has no attribute 'catalog_voices'`.

- [ ] **Step 4a: `voices.py` đọc JSON.** Thay toàn bộ khối `*[ {...} for speaker, lang, gender, zh, en, vi in (...) ]` (dòng ~95–124, phần "越南语 / 英语") bằng `*_byteplus_presets(),` và thêm phía trên `VOICE_PRESETS`:

```python
import json
from pathlib import Path

# 13 giọng vi/en cũ: giữ nhãn i18n đã dịch; giọng mới dùng tên giọng cho mọi ngôn ngữ
_LEGACY_LABELS: dict[str, tuple[str, str, str]] = {
    "vi_female_ruan_uranus_bigtts": ("Ruan · 越南语沉稳女声", "Ruan · Steady, poised female", "Ruan · giọng nữ điềm đạm, rõ ràng"),
    "vi_male_wumg_uranus_bigtts": ("Wumg · 越南语稳重男声", "Wumg · Patient, measured male", "Wumg · giọng nam trẻ, từ tốn"),
    "vi_female_ling_uranus_bigtts": ("Ling · 越南语温柔女声", "Ling · Gentle, kind female", "Ling · giọng nữ dịu dàng"),
    "vi_female_linh_uranus_bigtts": ("Linh · 越南语爽利女声", "Linh · Crisp, energetic female", "Linh · giọng nữ trẻ, dứt khoát"),
    "vi_female_wu_uranus_bigtts": ("Wu · 越南语开朗女声", "Wu · Outgoing, level-headed female", "Wu · giọng nữ cởi mở, mạch lạc"),
    "vi_female_hong_uranus_bigtts": ("Hong · 越南语直爽女声", "Hong · Down-to-earth, frank female", "Hong · giọng nữ mộc mạc, thẳng thắn"),
    "vi_female_partner_uranus_bigtts": ("Partner · 越南语饱满情绪女声", "Partner · Youthful, emotive female", "Partner · giọng nữ trẻ, giàu cảm xúc"),
    "en_female_hayley_uranus_bigtts": ("Hayley · 英语女声 · 故事", "Hayley · Lively female storyteller", "Hayley · giọng nữ kể chuyện sinh động"),
    "en_male_tim_uranus_bigtts": ("Tim · 英语清晰男声", "Tim · Clear, friendly male", "Tim · giọng nam rõ ràng, thân thiện"),
    "en_female_skye_uranus_bigtts": ("Skye · 英语真诚女声", "Skye · Clear, sincere female", "Skye · giọng nữ trong trẻo, chân thành"),
    "en_female_jenny_uranus_bigtts": ("Jenny · 英语温暖女声", "Jenny · Warm, cheerful female", "Jenny · giọng nữ ấm áp, vui tươi"),
    "en_male_kevin_uranus_bigtts": ("Kevin · 英语年轻男声", "Kevin · Young, articulate male", "Kevin · giọng nam trẻ, mạch lạc"),
    "en_male_marcus_uranus_bigtts": ("Marcus · 英语醇厚男声 · 故事", "Marcus · Deep, mellow storyteller", "Marcus · giọng nam trầm ấm, kể chuyện"),
}
_BYTEPLUS_VOICES_FILE = Path(__file__).resolve().parent / "data" / "byteplus_tts_voices.json"


def _byteplus_presets() -> list[dict[str, Any]]:
    """Giọng BytePlus TTS 2.0 vi/en từ file dữ liệu (sinh bởi scripts/gen_byteplus_voices.py).

    Thứ tự: 13 giọng cũ trước (auto_pool=true, giữ giọng mặc định / pool tự động như trước), giọng mới sau (auto_pool=false).
    """
    rows = json.loads(_BYTEPLUS_VOICES_FILE.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for row in rows:
        speaker = row["speaker"]
        zh, en, vi = _LEGACY_LABELS.get(speaker, (row["name"], row["name"], row["name"]))
        out.append(
            {
                "id": speaker,
                "label": zh,
                "label_i18n": {"zh": zh, "en": en, "vi": vi},
                "languages": list(row["languages"]),
                "gender": row["gender"],
                "speaker": speaker,
                "name": row["name"],
                "scenario": row["scenario"],
                "description": row["description"],
                "sample_url": row["sample_url"],
                "auto_pool": bool(row["auto_pool"]),
            }
        )
    return out
```

Sửa `list_voices` và thêm `catalog_voices`:

```python
def list_voices() -> list[dict[str, Any]]:
    """Danh mục cho /api/voices (科普 studio): bỏ giọng chỉ-chọn-tay (auto_pool=false) để không đổi hành vi cũ."""
    return [p for p in VOICE_PRESETS if p.get("auto_pool", True)]


def catalog_voices(lang: str | None) -> list[dict[str, Any]]:
    """Giọng chọn tay cho nhân vật phim truyện: mọi preset đọc được `lang`, theo thứ tự danh mục."""
    if not lang:
        return []
    return [
        {
            "id": p["id"],
            "speaker": p["speaker"],
            "name": p.get("name") or p["id"],
            "gender": p.get("gender") or "",
            "scenario": p.get("scenario") or "",
            "description": p.get("description") or "",
            "sample_url": p.get("sample_url") or "",
        }
        for p in VOICE_PRESETS
        if lang in (p.get("languages") or [])
    ]
```

- [ ] **Step 4b: `voice_lang.py` bỏ qua giọng chỉ-chọn-tay.** Trong `default_voice_for_lang` và `lang_voice_pool`, đổi dòng lọc thành:

```python
    candidates = [p for p in VOICE_PRESETS if lang in (p.get("languages") or []) and p.get("auto_pool", True)]
```

Cập nhật docstring module (dòng 3–8) thêm một gạch đầu dòng: `- Preset auto_pool=false (giọng chỉ chọn tay trong phim truyện) không tham gia giọng mặc định / pool tự động, nhưng vẫn được nhận diện ngôn ngữ / giới tính.`

- [ ] **Step 4c: Giữ fixture chung không đổi.** `tests/test_voice_lang.py::test_voice_for_lang_matches_shared_vectors` so `catalog` với toàn bộ `VOICE_PRESETS`. Sửa **test** (không sửa fixture) để so với phần tham gia pool:

```python
    catalog = [
        {"id": p["id"], "speaker": p["speaker"], "gender": p["gender"], "languages": p["languages"]}
        for p in VOICE_PRESETS
        if p.get("auto_pool", True)
    ]
```

và thêm vào docstring của test: `catalog chỉ gồm preset auto_pool (giọng chỉ-chọn-tay không ảnh hưởng thay thế tự động).`

- [ ] **Step 4d: Router catalog.** `backend/app/api/drama/voices.py`:

```python
"""Danh mục giọng TTS để chọn tay cho nhân vật phim truyện."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.content_lang import project_content_lang
from app.services.drama.access import get_owned_drama_project
from app.services.voices import catalog_voices

router = APIRouter()


@router.get("/voices/catalog")
async def voice_catalog(
    project_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """按项目内容语言返回可手选的 TTS 音色（含试听样音 URL）。"""
    project = await get_owned_drama_project(db, project_id, user)
    lang = project_content_lang(project)
    return {"lang": lang, "voices": catalog_voices(lang)}
```

Trong `backend/app/api/drama/__init__.py`: thêm `voices` vào dòng import các module router và `router.include_router(voices.router)` sau `skills.router`. Kiểm tra prefix: `grep -n "prefix" backend/app/api/drama/__init__.py backend/app/main.py | grep -i drama` để URL cuối cùng là `/api/drama/voices/catalog`.

- [ ] **Step 5: Chạy test**

Run: `cd backend && pytest tests/test_voice_catalog.py tests/test_voice_lang.py -q && python -c "import app.main"`
Expected: tất cả pass; `git diff --stat tests/fixtures/voice_lang_vectors.json` trống.

Run frontend fixture test: `cd frontend && npm test` — Expected: pass (fixture không đổi).

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/gen_byteplus_voices.py backend/app/services/data/byteplus_tts_voices.json backend/app/services/voices.py backend/app/services/voice_lang.py backend/app/api/drama/voices.py backend/app/api/drama/__init__.py backend/tests/test_voice_catalog.py backend/tests/test_voice_lang.py
git commit -m "feat(giọng): đủ danh mục giọng BytePlus vi/en và API chọn giọng cho nhân vật

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Khóa giọng khi tổng hợp mẫu và khi lồng tiếng

**Files:**
- Modify: `backend/app/schemas_drama.py:253` (`DramaVoiceGenerateRequest`)
- Modify: `backend/app/api/drama/generation.py` (`generate_voice`)
- Modify: `backend/app/services/drama/generation.py:1457` (`generate_voice_asset_audio`)
- Modify: `backend/app/services/drama/voice_synthesis.py` (`resolve_bound_speaker` mới; `synthesize_voice_asset`)
- Modify: `backend/app/services/drama/fragment_dub.py:92-121` (`load_dub_voices`)
- Test: `backend/tests/test_drama_speaker_lock.py`

**Interfaces:**
- Consumes: `usable_speaker`, `infer_character_speaker` (đã có trong `voice_synthesis.py`); `voice_supports_lang` (`app.services.voice_lang`); `VOICE_PRESETS`.
- Produces:
  - `resolve_bound_speaker(speaker: str | None, lang: str, *, locked: bool, voice_prompt: str, character_name: str | None, key_asset_id: int) -> str`
  - `lockable_speaker(speaker: str | None) -> bool` — có trong `VOICE_PRESETS` hoặc bắt đầu `S_`.
  - `DramaVoiceGenerateRequest.speaker_locked: bool = False`
  - `synthesize_voice_asset(..., speaker_locked: bool = False)` và `generate_voice_asset_audio(..., speaker_locked: bool = False)`; khi khóa ghi `params["speakerLocked"] = True`, ngược lại `params.pop("speakerLocked", None)`.

- [ ] **Step 1: Viết test fail**

`backend/tests/test_drama_speaker_lock.py`:

```python
"""Khóa giọng người dùng đã chọn: không bị đổi theo giới tính mô tả; sai ngôn ngữ thì rơi về luồng cũ."""

import logging

from app.services.drama import fragment_dub, voice_synthesis
from app.services.drama.voice_synthesis import lockable_speaker, resolve_bound_speaker


def _resolve(speaker, lang, locked, prompt="giọng nữ trẻ"):
    return resolve_bound_speaker(
        speaker, lang, locked=locked, voice_prompt=prompt, character_name="Lan", key_asset_id=5
    )


def test_locked_keeps_speaker_even_if_gender_mismatch():
    assert _resolve("vi_male_wumg_uranus_bigtts", "vi", True) == "vi_male_wumg_uranus_bigtts"


def test_unlocked_gender_mismatch_is_reinferred():
    assert _resolve("vi_male_wumg_uranus_bigtts", "vi", False) != "vi_male_wumg_uranus_bigtts"


def test_locked_wrong_language_falls_back_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        out = _resolve("en_male_bruce_uranus_bigtts", "vi", True, prompt="giọng nam trầm")
    assert out.startswith("vi_")
    assert "en_male_bruce_uranus_bigtts" in caplog.text


def test_locked_empty_speaker_falls_back():
    assert _resolve("", "vi", True).startswith("vi_")


def test_lockable_speaker():
    assert lockable_speaker("en_male_bruce_uranus_bigtts")
    assert lockable_speaker("S_abc123")
    assert not lockable_speaker("made_up_voice")
    assert not lockable_speaker("")


class _A:
    def __init__(self, id, type, name, params):
        self.id, self.type, self.name, self.params = id, type, name, params


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Db:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _Result(self._rows)


class _Project:
    id = 1


async def test_load_dub_voices_honours_lock(monkeypatch):
    voice = _A(20, "voice", "Lan · Wumg", {"speaker": "vi_male_wumg_uranus_bigtts", "speakerLocked": True,
                                            "voicePrompt": "giọng nữ trẻ"})
    char = _A(10, "character", "Lan", {"voiceAudio": {"sourceAssetId": 20, "url": "/static/x.mp3"}})
    monkeypatch.setattr(fragment_dub, "resolve_character_prompt_name", lambda d: d["name"], raising=False)
    characters, _narrator = await fragment_dub.load_dub_voices(_Db([char, voice]), _Project(), "vi")
    assert characters[0].speaker == "vi_male_wumg_uranus_bigtts"


async def test_load_dub_voices_unlocked_reinfers(monkeypatch):
    voice = _A(20, "voice", "Lan · Wumg", {"speaker": "vi_male_wumg_uranus_bigtts", "voicePrompt": "giọng nữ trẻ"})
    char = _A(10, "character", "Lan", {"voiceAudio": {"sourceAssetId": 20, "url": "/static/x.mp3"}})
    monkeypatch.setattr(fragment_dub, "resolve_character_prompt_name", lambda d: d["name"], raising=False)
    characters, _ = await fragment_dub.load_dub_voices(_Db([char, voice]), _Project(), "vi")
    assert characters[0].speaker != "vi_male_wumg_uranus_bigtts"
```

Nếu `resolve_character_prompt_name` được import trong `fragment_dub.py` dưới tên khác, sửa tên monkeypatch cho đúng (`grep -n "resolve_character_prompt_name" backend/app/services/drama/fragment_dub.py`); nếu hàm thật chạy được với dict `{"name","params"}` thì bỏ hẳn dòng monkeypatch.

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_drama_speaker_lock.py -q`
Expected: FAIL — `ImportError: cannot import name 'lockable_speaker'`.

- [ ] **Step 3a: Helper trong `voice_synthesis.py`** — đặt ngay sau `usable_speaker`:

```python
def lockable_speaker(speaker: str | None) -> bool:
    """speaker có được phép khóa không: giọng trong danh mục hoặc giọng nhân bản S_*."""
    from app.services.voices import VOICE_PRESETS

    sp = (speaker or "").strip()
    if not sp:
        return False
    return sp.startswith("S_") or any(p["speaker"] == sp for p in VOICE_PRESETS)


def resolve_bound_speaker(
    speaker: str | None,
    lang: str,
    *,
    locked: bool,
    voice_prompt: str,
    character_name: str | None,
    key_asset_id: int,
) -> str:
    """speaker thực dùng cho nhân vật: đã khóa và đọc được ngôn ngữ dự án → dùng nguyên;
    còn lại theo luồng cũ (usable_speaker → infer_character_speaker)."""
    from app.services.voice_lang import voice_supports_lang

    sp = (speaker or "").strip()
    if locked and sp:
        if voice_supports_lang(sp, lang):
            return sp
        logger.warning("Giọng đã khóa không đọc được ngôn ngữ dự án, tự chọn lại speaker=%s lang=%s", sp, lang)
    if usable_speaker(sp, lang, voice_prompt=voice_prompt, character_name=character_name):
        return sp
    return infer_character_speaker(voice_prompt, character_name, key_asset_id=key_asset_id, lang=lang)
```

Kiểm tra `voice_synthesis.py` có `logger = logging.getLogger(__name__)` (nếu chưa, thêm).

- [ ] **Step 3b: `synthesize_voice_asset`** — thêm tham số keyword `speaker_locked: bool = False` vào chữ ký. Đổi điều kiện voice design:

```python
    if voice_design_enabled(settings) and not settings.ark_mock and not speaker_locked:
```

Thay khối `if not usable_speaker(resolved_speaker, ...): resolved_speaker = infer_character_speaker(...)` (dòng ~264–270) bằng:

```python
        resolved_speaker = resolve_bound_speaker(
            resolved_speaker,
            lang,
            locked=speaker_locked,
            voice_prompt=prompt,
            character_name=character_label,
            key_asset_id=character_asset.id if character_asset is not None else asset.id,
        )
```

Trong khối ghi params (sau `params["speaker"] = resolved_speaker`) thêm:

```python
    if speaker_locked and resolved_speaker == (speaker or "").strip():
        params["speakerLocked"] = True
    else:
        params.pop("speakerLocked", None)
```

- [ ] **Step 3c: `generate_voice_asset_audio`** (`services/drama/generation.py`) — thêm `speaker_locked: bool = False` vào chữ ký và truyền `speaker_locked=speaker_locked` vào `synthesize_voice_asset`.

- [ ] **Step 3d: Schema + API.** Trong `DramaVoiceGenerateRequest` thêm:

```python
    speaker_locked: bool = Field(default=False, description="用户手选音色：锁定 speaker，配音时不按描述性别改换")
```

Trong `generate_voice` (`api/drama/generation.py`), ngay trước `try: updated = await generate_voice_asset_audio(`:

```python
    prev_params = asset.params if isinstance(asset.params, dict) else {}
    requested = (body.speaker or "").strip()
    # 手选音色，或对已锁定音色用同一 speaker 重新合成 → 保持锁定
    speaker_locked = lockable_speaker(requested) and (
        body.speaker_locked or (prev_params.get("speakerLocked") is True and prev_params.get("speaker") == requested)
    )
```

Lưu ý: `prev_params` phải đọc **trước** đoạn code hiện có ghi đè `params["generation"]`/`voicePrompt` — di chuyển 3 dòng trên lên ngay sau khối `if body.asset_id: ... else: ...` tạo/tìm asset. Truyền `speaker_locked=speaker_locked` vào `generate_voice_asset_audio(...)`. Import `lockable_speaker` từ `app.services.drama.voice_synthesis`.

- [ ] **Step 3e: `load_dub_voices`** (`fragment_dub.py`) — thay 2 dòng:

```python
        if not usable_speaker(speaker, lang, voice_prompt=prompt, character_name=asset.name):
            speaker = infer_character_speaker(prompt, asset.name, key_asset_id=asset.id, lang=lang)
```

bằng:

```python
        speaker = resolve_bound_speaker(
            speaker,
            lang,
            locked=vparams.get("speakerLocked") is True,
            voice_prompt=prompt,
            character_name=asset.name,
            key_asset_id=asset.id,
        )
```

Cập nhật import dòng 31: `from app.services.drama.voice_synthesis import _drama_tts_model, resolve_bound_speaker` (bỏ `infer_character_speaker`, `usable_speaker` nếu không còn dùng trong file — kiểm tra bằng grep).

- [ ] **Step 4: Chạy test**

Run: `cd backend && pytest tests/test_drama_speaker_lock.py tests/test_fragment_dub.py tests/test_drama_dub_lines.py tests/test_voice_lang.py -q && python -c "import app.main"`
Expected: tất cả pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas_drama.py backend/app/api/drama/generation.py backend/app/services/drama/generation.py backend/app/services/drama/voice_synthesis.py backend/app/services/drama/fragment_dub.py backend/tests/test_drama_speaker_lock.py
git commit -m "feat(phim truyện): khóa giọng người dùng đã chọn khi tổng hợp mẫu và lồng tiếng

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Frontend — form ngoại hình trong hộp thoại tư liệu

**Files:**
- Create: `frontend/src/lib/dramaAppearance.ts`, `frontend/tests/dramaAppearance.test.ts`
- Create: `frontend/src/pages/drama/CharacterAppearanceForm.tsx`
- Modify: `frontend/src/api/drama.ts` (thêm `extractAppearance`)
- Modify: `frontend/src/pages/drama/DramaAssetDetailModal.tsx`
- Modify: `frontend/src/i18n/locales/{vi,en,zh}/dramaAssets.ts`
- Modify: `frontend/src/pages/drama/drama.css`

**Interfaces:**
- Consumes: `POST /api/drama/assets/{id}/appearance/extract` → `{ok, appearance, task_id}`; `PATCH /api/drama/assets/{id}` với `params.appearance` / `params.promptManual` (backend tự ghép lại `visualPrompt`).
- Produces (`lib/dramaAppearance.ts`):
  - `APPEARANCE_KEYS` (8 khóa, cùng thứ tự backend), `type AppearanceKey`, `type Appearance = Record<AppearanceKey, string>`
  - `emptyAppearance(): Appearance`, `readAppearance(asset: {params?: unknown}): Appearance`, `appearanceIsEmpty(a: Appearance): boolean`, `appearanceEqual(a: Appearance, b: Appearance): boolean`, `readPromptManual(asset): boolean`
  - `buildAppearanceSave(opts: {appearance: Appearance; appearanceDirty: boolean; promptText: string; promptDirty: boolean; wasManual: boolean}): Record<string, unknown> | null` — body `params` cho PATCH; `null` khi không có gì thay đổi.

- [ ] **Step 1: Test helper fail**

`frontend/tests/dramaAppearance.test.ts`:

```ts
/** Ngoại hình nhân vật theo trường: đọc params, so sánh, dựng body lưu (chế độ tự ghép / chỉnh tay) */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  APPEARANCE_KEYS,
  appearanceEqual,
  appearanceIsEmpty,
  buildAppearanceSave,
  emptyAppearance,
  readAppearance,
  readPromptManual,
} from '../src/lib/dramaAppearance.ts'

test('readAppearance fills all 8 keys and ignores junk', () => {
  const a = readAppearance({ params: { appearance: { hair: ' ponytail ', age: 25, junk: 'x' } } })
  assert.deepEqual(Object.keys(a), [...APPEARANCE_KEYS])
  assert.equal(a.hair, 'ponytail')
  assert.equal(a.age, '25')
  assert.ok(appearanceIsEmpty(readAppearance({ params: { appearance: 'text' } })))
  assert.ok(appearanceIsEmpty(readAppearance({})))
})

test('appearanceEqual compares trimmed values', () => {
  const a = { ...emptyAppearance(), hair: 'x' }
  assert.ok(appearanceEqual(a, { ...emptyAppearance(), hair: ' x ' }))
  assert.ok(!appearanceEqual(a, emptyAppearance()))
})

test('readPromptManual only true for literal true', () => {
  assert.equal(readPromptManual({ params: { promptManual: true } }), true)
  assert.equal(readPromptManual({ params: { promptManual: 'yes' } }), false)
})

test('buildAppearanceSave: field edit in auto mode asks backend to recompose', () => {
  const appearance = { ...emptyAppearance(), hair: 'long' }
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: true, promptText: 'p', promptDirty: false, wasManual: false }),
    { appearance, promptManual: false },
  )
})

test('buildAppearanceSave: typed prompt switches to manual and keeps text', () => {
  const appearance = emptyAppearance()
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: false, promptText: ' mine ', promptDirty: true, wasManual: false }),
    { promptManual: true, visualPrompt: 'mine', visualImage: 'mine' },
  )
})

test('buildAppearanceSave: field edit while manual keeps manual prompt', () => {
  const appearance = { ...emptyAppearance(), hair: 'long' }
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: true, promptText: 'mine', promptDirty: false, wasManual: true }),
    { appearance },
  )
})

test('buildAppearanceSave: nothing changed → null', () => {
  assert.equal(
    buildAppearanceSave({ appearance: emptyAppearance(), appearanceDirty: false, promptText: 'x', promptDirty: false, wasManual: false }),
    null,
  )
})
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd frontend && node --test tests/dramaAppearance.test.ts`
Expected: FAIL — không tìm thấy module `../src/lib/dramaAppearance.ts`.

- [ ] **Step 3: Helper** — `frontend/src/lib/dramaAppearance.ts`:

```ts
/** Ngoại hình nhân vật theo trường (params.appearance) — cùng 8 khóa / thứ tự với backend appearance_prompt.py */

export const APPEARANCE_KEYS = [
  'gender',
  'age',
  'face',
  'hair',
  'build',
  'outfit',
  'signature',
  'style_note',
] as const

export type AppearanceKey = (typeof APPEARANCE_KEYS)[number]
export type Appearance = Record<AppearanceKey, string>

// Ngoại hình rỗng (đủ 8 khóa)
export function emptyAppearance(): Appearance {
  return Object.fromEntries(APPEARANCE_KEYS.map((k) => [k, ''])) as Appearance
}

// Đọc params.appearance: đủ 8 khóa, ép chuỗi + trim; kiểu sai → rỗng
export function readAppearance(asset: { params?: unknown }): Appearance {
  const params = (asset.params && typeof asset.params === 'object' ? asset.params : {}) as Record<string, unknown>
  const raw = params.appearance && typeof params.appearance === 'object' ? (params.appearance as Record<string, unknown>) : {}
  const out = emptyAppearance()
  for (const k of APPEARANCE_KEYS) {
    const v = raw[k]
    out[k] = v === null || v === undefined ? '' : String(v).trim()
  }
  return out
}

// Mọi trường đều rỗng
export function appearanceIsEmpty(a: Appearance): boolean {
  return APPEARANCE_KEYS.every((k) => !a[k].trim())
}

// So sánh hai bộ ngoại hình (bỏ khoảng trắng đầu/cuối)
export function appearanceEqual(a: Appearance, b: Appearance): boolean {
  return APPEARANCE_KEYS.every((k) => a[k].trim() === b[k].trim())
}

// Prompt đang ở chế độ chỉnh tay (backend không tự ghép đè)
export function readPromptManual(asset: { params?: unknown }): boolean {
  const params = (asset.params && typeof asset.params === 'object' ? asset.params : {}) as Record<string, unknown>
  return params.promptManual === true
}

/**
 * Dựng params cho PATCH khi lưu:
 * - sửa ô prompt → chuyển chỉnh tay, gửi nguyên văn prompt;
 * - chỉ sửa trường khi đang tự ghép → gửi appearance + promptManual:false (backend ghép lại);
 * - sửa trường khi đang chỉnh tay → chỉ gửi appearance (prompt tay giữ nguyên);
 * - không đổi gì → null.
 */
export function buildAppearanceSave(opts: {
  appearance: Appearance
  appearanceDirty: boolean
  promptText: string
  promptDirty: boolean
  wasManual: boolean
}): Record<string, unknown> | null {
  const { appearance, appearanceDirty, promptDirty, wasManual } = opts
  const prompt = opts.promptText.trim()
  if (!appearanceDirty && !promptDirty) return null
  const out: Record<string, unknown> = {}
  if (appearanceDirty) out.appearance = appearance
  if (promptDirty) {
    out.promptManual = true
    out.visualPrompt = prompt
    out.visualImage = prompt
  } else if (!wasManual) {
    out.promptManual = false
  }
  return out
}
```

Run: `cd frontend && node --test tests/dramaAppearance.test.ts` — Expected: 7 pass.

- [ ] **Step 4: API.** Trong `dramaApi` (`frontend/src/api/drama.ts`), sau `suggestVoicePrompt`:

```ts
  extractAppearance: (assetId: number) =>
    request<{ ok: boolean; appearance: Record<string, string>; task_id: number }>(
      `/api/drama/assets/${assetId}/appearance/extract`,
      { method: 'POST' },
    ),
```

- [ ] **Step 5: i18n.** Trong `frontend/src/i18n/locales/vi/dramaAssets.ts`, thêm nhóm `appearance` cạnh nhóm `detail` (cùng cấp, đúng cấu trúc object hiện có của file):

```ts
  appearance: {
    title: 'Ngoại hình',
    fields: {
      gender: 'Giới tính',
      age: 'Tuổi',
      face: 'Khuôn mặt',
      hair: 'Tóc',
      build: 'Vóc dáng',
      outfit: 'Trang phục',
      signature: 'Điểm nhận diện',
      style_note: 'Thần thái',
    },
    extract: 'AI tách trường',
    extracting: 'Đang tách…',
    emptyHint: 'Nhân vật này chưa có ngoại hình theo trường. Bấm "AI tách trường" để AI chia mô tả hiện có thành từng mục.',
    manualBadge: 'Đang chỉnh tay',
    manualHint: 'Prompt đang được chỉnh tay nên sửa các trường sẽ không tự cập nhật prompt.',
    recompose: 'Tạo lại prompt từ các trường',
    extractFailed: 'Không tách được các trường ngoại hình',
  },
```

`en/dramaAssets.ts`:

```ts
  appearance: {
    title: 'Appearance',
    fields: {
      gender: 'Gender',
      age: 'Age',
      face: 'Face',
      hair: 'Hair',
      build: 'Build',
      outfit: 'Outfit',
      signature: 'Signature details',
      style_note: 'Presence',
    },
    extract: 'Split with AI',
    extracting: 'Splitting…',
    emptyHint: 'This character has no appearance fields yet. Click "Split with AI" to break the current description into fields.',
    manualBadge: 'Edited by hand',
    manualHint: 'The prompt was edited by hand, so field changes will not update it.',
    recompose: 'Rebuild prompt from fields',
    extractFailed: 'Could not split the appearance into fields',
  },
```

`zh/dramaAssets.ts`:

```ts
  appearance: {
    title: '外形',
    fields: {
      gender: '性别',
      age: '年龄',
      face: '五官',
      hair: '发型',
      build: '体型',
      outfit: '服饰',
      signature: '标志细节',
      style_note: '气质',
    },
    extract: 'AI 拆分字段',
    extracting: '拆分中…',
    emptyHint: '该角色还没有分字段外形。点击「AI 拆分字段」把现有描述拆成各项。',
    manualBadge: '手动编辑中',
    manualHint: '提示词为手动编辑，修改字段不会自动更新提示词。',
    recompose: '按字段重新生成提示词',
    extractFailed: '外形字段拆分失败',
  },
```

Nếu có test/tsc kiểm tra các locale cùng cấu trúc (`grep -rn "dramaAssets" frontend/tests frontend/src/i18n/messages.ts`), đảm bảo 3 file khớp khóa.

- [ ] **Step 6: Component form** — `frontend/src/pages/drama/CharacterAppearanceForm.tsx`:

```tsx
/** Form 8 trường ngoại hình nhân vật + nút AI tách trường; chỉ hiển thị/sửa, việc lưu do DramaAssetDetailModal làm */
import { APPEARANCE_KEYS, appearanceIsEmpty, type Appearance, type AppearanceKey } from '../../lib/dramaAppearance'
import { useI18n } from '../../i18n/context'

type Props = {
  value: Appearance
  onChange: (next: Appearance) => void
  onExtract: () => void
  extracting: boolean
  disabled: boolean
}

// Trường dài hiển thị bằng textarea 2 dòng
const MULTILINE: ReadonlySet<AppearanceKey> = new Set(['outfit', 'style_note'])

// Render form ngoại hình
export function CharacterAppearanceForm({ value, onChange, onExtract, extracting, disabled }: Props) {
  const { t } = useI18n()
  const empty = appearanceIsEmpty(value)
  return (
    <section className="drama-appearance-form" aria-label={t('dramaAssets.appearance.title')}>
      <header className="drama-appearance-head">
        <strong>{t('dramaAssets.appearance.title')}</strong>
        <button type="button" className="pf-btn pf-btn-sm" disabled={disabled || extracting} onClick={onExtract}>
          {extracting ? t('dramaAssets.appearance.extracting') : t('dramaAssets.appearance.extract')}
        </button>
      </header>
      {empty ? <p className="drama-muted">{t('dramaAssets.appearance.emptyHint')}</p> : null}
      <div className="drama-appearance-grid">
        {APPEARANCE_KEYS.map((key) => (
          <label key={key} className={`drama-field${MULTILINE.has(key) ? ' drama-appearance-wide' : ''}`}>
            <span>{t(`dramaAssets.appearance.fields.${key}`)}</span>
            {MULTILINE.has(key) ? (
              <textarea
                rows={2}
                value={value[key]}
                disabled={disabled}
                onChange={(e) => onChange({ ...value, [key]: e.target.value })}
              />
            ) : (
              <input
                type="text"
                value={value[key]}
                disabled={disabled}
                onChange={(e) => onChange({ ...value, [key]: e.target.value })}
              />
            )}
          </label>
        ))}
      </div>
    </section>
  )
}
```

CSS thêm vào cuối `frontend/src/pages/drama/drama.css`:

```css
/* Form ngoại hình nhân vật (CharacterAppearanceForm) */
.drama-appearance-form { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.drama-appearance-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.drama-appearance-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; }
.drama-appearance-wide { grid-column: 1 / -1; }
@media (max-width: 640px) { .drama-appearance-grid { grid-template-columns: 1fr; } }
.drama-prompt-manual { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
```

- [ ] **Step 7: Nối vào `DramaAssetDetailModal.tsx`**

1. Import:
```tsx
import { CharacterAppearanceForm } from './CharacterAppearanceForm'
import {
  appearanceEqual,
  buildAppearanceSave,
  readAppearance,
  readPromptManual,
  type Appearance,
} from '../../lib/dramaAppearance'
```
2. State (trong khối comment state hiện có, thêm dòng mô tả `appearanceDraft 外形字段草稿 / extracting AI 拆分中`):
```tsx
  const [appearanceDraft, setAppearanceDraft] = useState<Appearance>(() => readAppearance(asset))
  const [extracting, setExtracting] = useState(false)
```
3. Trong `useEffect` đang reset `setPromptDraft(readVisualPrompt(asset))` (dòng ~95), thêm `setAppearanceDraft(readAppearance(asset))`.
4. Tính dirty (thay dòng `const dirty = ...`):
```tsx
  const isCharacter = (asset.type || '').toLowerCase() === 'character'
  const promptDirty = promptDraft.trim() !== readVisualPrompt(asset).trim()
  const appearanceDirty = isCharacter && !appearanceEqual(appearanceDraft, readAppearance(asset))
  const wasManual = readPromptManual(asset)
  const dirty = promptDirty || appearanceDirty
```
Nếu file đã có biến `isCharacter`, dùng lại, không khai báo trùng.
5. Hàm dựng params — thay chỗ dùng `buildPromptParams(asset, text)` trong `savePrompt` và `handleGenerate` bằng `buildSaveParams()`:
```tsx
  // Params gửi PATCH khi lưu: nhân vật đi qua buildAppearanceSave, tư liệu khác giữ buildPromptParams cũ
  function buildSaveParams(): Record<string, unknown> {
    if (!isCharacter) return buildPromptParams(asset, promptDraft.trim())
    return (
      buildAppearanceSave({
        appearance: appearanceDraft,
        appearanceDirty,
        promptText: promptDraft,
        promptDirty,
        wasManual,
      }) || {}
    )
  }
```
Giữ nguyên kiểm tra `promptRequired` hiện có chỉ khi `!isCharacter || promptDirty` (nhân vật chỉ sửa trường thì prompt do backend ghép, không bắt buộc ô prompt).
Sau khi PATCH thành công trong `savePrompt`/`handleGenerate`, gọi `setPromptDraft(readVisualPrompt(updated))` để ô prompt hiển thị prompt backend vừa ghép.
6. Hành động:
```tsx
  // AI tách mô tả hiện có thành 8 trường (chỉ điền form, người dùng xem rồi mới lưu)
  async function handleExtract() {
    setExtracting(true)
    try {
      const result = await dramaApi.extractAppearance(asset.id)
      setAppearanceDraft(readAppearance({ params: { appearance: result.appearance } }))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.appearance.extractFailed'))
    } finally {
      setExtracting(false)
    }
  }

  // Bỏ chế độ chỉnh tay: backend ghép lại prompt từ các trường
  async function handleRecompose() {
    setSaving(true)
    try {
      const updated = await dramaApi.updateAsset(asset.id, {
        params: { appearance: appearanceDraft, promptManual: false },
      })
      onUpdated(updated)
      setPromptDraft(readVisualPrompt(updated))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.detail.savePromptFailed'))
    } finally {
      setSaving(false)
    }
  }
```
7. Render — ngay trước `<label className="drama-field">` của ô prompt:
```tsx
          {isCharacter ? (
            <CharacterAppearanceForm
              value={appearanceDraft}
              onChange={setAppearanceDraft}
              onExtract={() => void handleExtract()}
              extracting={extracting}
              disabled={actionBusy || saving}
            />
          ) : null}
          {isCharacter && wasManual ? (
            <div className="drama-prompt-manual">
              <span className="pf-badge">{t('dramaAssets.appearance.manualBadge')}</span>
              <span className="drama-muted">{t('dramaAssets.appearance.manualHint')}</span>
              <button type="button" className="pf-btn pf-btn-sm" disabled={saving || actionBusy} onClick={() => void handleRecompose()}>
                {t('dramaAssets.appearance.recompose')}
              </button>
            </div>
          ) : null}
```
Kiểm tra class `pf-badge` có trong `frontend/src/styles/printfilm.css` (`grep -n "\.pf-badge" frontend/src/styles/printfilm.css`); nếu không có, dùng `<strong>` thay cho `<span className="pf-badge">`.
8. Nếu file vượt 500 dòng sau khi sửa, chuyển `handleExtract`/`handleRecompose`/`buildSaveParams` sang hook `useCharacterAppearance.ts` cùng thư mục.

- [ ] **Step 8: Kiểm tra**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: test pass, lint không lỗi mới, build thành công.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/dramaAppearance.ts frontend/tests/dramaAppearance.test.ts frontend/src/pages/drama/CharacterAppearanceForm.tsx frontend/src/pages/drama/DramaAssetDetailModal.tsx frontend/src/api/drama.ts frontend/src/i18n/locales/*/dramaAssets.ts frontend/src/pages/drama/drama.css
git commit -m "feat(phim truyện): form ngoại hình nhân vật theo trường trong hộp thoại tư liệu

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Frontend — tab "Chọn giọng" trong hộp thoại gắn giọng

**Files:**
- Create: `frontend/src/pages/drama/VoiceCatalogPicker.tsx`
- Modify: `frontend/src/api/drama.ts` (`voiceCatalog`, `generateVoice.speaker_locked`)
- Modify: `frontend/src/pages/drama/CharacterVoiceBindModal.tsx`
- Modify: `frontend/src/i18n/locales/{vi,en,zh}/dramaAssets.ts`
- Modify: `frontend/src/pages/drama/drama.css`

**Interfaces:**
- Consumes: `GET /api/drama/voices/catalog?project_id=` → `{lang, voices: CatalogVoice[]}`; `POST /api/drama/generation/voice` với `speaker_locked: true`; `buildBoundParams(asset, voice)` và `dramaApi.updateAsset` (đã có trong `CharacterVoiceBindModal.tsx`).
- Produces: `type CatalogVoice = {id: string; speaker: string; name: string; gender: string; scenario: string; description: string; sample_url: string}` export từ `api/drama.ts`; component `VoiceCatalogPicker({ voices, lang, busySpeaker, onPick })`.

- [ ] **Step 1: API** — trong `frontend/src/api/drama.ts`:

```ts
/** Giọng TTS chọn tay cho nhân vật (GET /api/drama/voices/catalog) */
export type CatalogVoice = {
  id: string
  speaker: string
  name: string
  gender: string
  scenario: string
  description: string
  sample_url: string
}
```

Trong `dramaApi`: thêm `speaker_locked?: boolean` vào kiểu body của `generateVoice`, và thêm:

```ts
  voiceCatalog: (projectId: number) =>
    request<{ lang: string; voices: CatalogVoice[] }>(`/api/drama/voices/catalog?project_id=${projectId}`),
```

- [ ] **Step 2: i18n** — trong nhóm `voiceBind` của mỗi `dramaAssets.ts` thêm các khóa.

vi:
```ts
    catalogTab: 'Chọn giọng',
    catalogLoading: 'Đang tải danh sách giọng…',
    catalogEmpty: 'Chưa có giọng nào cho ngôn ngữ của dự án này.',
    catalogLoadFailed: 'Không tải được danh sách giọng',
    filterAll: 'Tất cả',
    filterMale: 'Nam',
    filterFemale: 'Nữ',
    filterScenarioAll: 'Mọi nhóm',
    play: 'Nghe thử',
    stop: 'Dừng',
    useVoice: 'Dùng giọng này',
    usingVoice: 'Đang tạo giọng…',
    viMaleNote: 'Tiếng Việt hiện chỉ có 1 giọng nam; các nhân vật nam sẽ dùng chung giọng này.',
    lockedHint: 'Giọng bạn chọn sẽ được giữ nguyên khi lồng tiếng.',
    scenario: {
      General: 'Đa dụng',
      Entertainment: 'Giải trí',
      Education: 'Giáo dục',
      AudioBook: 'Sách nói',
      Dubbing: 'Lồng tiếng',
      CustomerService: 'Chăm sóc khách hàng',
      RolePlay: 'Nhập vai',
    },
```

en:
```ts
    catalogTab: 'Pick a voice',
    catalogLoading: 'Loading voices…',
    catalogEmpty: 'No voices for this project language yet.',
    catalogLoadFailed: 'Could not load voices',
    filterAll: 'All',
    filterMale: 'Male',
    filterFemale: 'Female',
    filterScenarioAll: 'All styles',
    play: 'Play',
    stop: 'Stop',
    useVoice: 'Use this voice',
    usingVoice: 'Creating voice…',
    viMaleNote: 'Vietnamese has only 1 male voice for now; all male characters will share it.',
    lockedHint: 'The voice you pick is kept as-is when dubbing.',
    scenario: {
      General: 'General',
      Entertainment: 'Entertainment',
      Education: 'Education',
      AudioBook: 'Audiobook',
      Dubbing: 'Dubbing',
      CustomerService: 'Customer service',
      RolePlay: 'Role play',
    },
```

zh:
```ts
    catalogTab: '选择音色',
    catalogLoading: '音色加载中…',
    catalogEmpty: '当前项目语言暂无可选音色。',
    catalogLoadFailed: '音色列表加载失败',
    filterAll: '全部',
    filterMale: '男声',
    filterFemale: '女声',
    filterScenarioAll: '全部类型',
    play: '试听',
    stop: '停止',
    useVoice: '使用此音色',
    usingVoice: '音色生成中…',
    viMaleNote: '越南语目前只有 1 个男声，所有男性角色将共用该音色。',
    lockedHint: '手选的音色在配音时保持不变。',
    scenario: {
      General: '通用',
      Entertainment: '娱乐',
      Education: '教育',
      AudioBook: '有声书',
      Dubbing: '配音',
      CustomerService: '客服',
      RolePlay: '角色扮演',
    },
```

- [ ] **Step 3: Component** — `frontend/src/pages/drama/VoiceCatalogPicker.tsx`:

```tsx
/** Danh sách giọng TTS chọn tay: lọc giới tính / nhóm, nghe thử file mẫu (không tốn phí), bấm dùng giọng */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CatalogVoice } from '../../api/drama'
import { useI18n } from '../../i18n/context'

type Props = {
  voices: CatalogVoice[]
  lang: string
  busySpeaker: string | null
  onPick: (voice: CatalogVoice) => void
}

type GenderFilter = 'all' | 'male' | 'female'

// Render danh sách giọng
export function VoiceCatalogPicker({ voices, lang, busySpeaker, onPick }: Props) {
  /*
   * gender lọc giới tính
   * scenario lọc nhóm ('' = tất cả)
   * playing speaker đang phát mẫu
   */
  const { t } = useI18n()
  const [gender, setGender] = useState<GenderFilter>('all')
  const [scenario, setScenario] = useState('')
  const [playing, setPlaying] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const scenarios = useMemo(() => [...new Set(voices.map((v) => v.scenario).filter(Boolean))], [voices])
  const shown = voices.filter(
    (v) => (gender === 'all' || v.gender === gender) && (!scenario || v.scenario === scenario),
  )

  // Dừng phát khi unmount
  useEffect(() => () => audioRef.current?.pause(), [])

  // Phát / dừng file mẫu; bấm giọng khác thì dừng giọng cũ
  function togglePlay(voice: CatalogVoice) {
    const audio = audioRef.current
    if (!audio) return
    if (playing === voice.speaker) {
      audio.pause()
      setPlaying(null)
      return
    }
    audio.src = voice.sample_url
    void audio.play().catch(() => setPlaying(null))
    setPlaying(voice.speaker)
  }

  // Nhãn nhóm đã dịch (nhóm lạ hiển thị nguyên văn)
  const scenarioLabel = (s: string) => {
    const key = `dramaAssets.voiceBind.scenario.${s}`
    const label = t(key)
    return label === key ? s : label
  }

  return (
    <div className="drama-voice-catalog">
      {lang === 'vi' ? <p className="drama-muted">{t('dramaAssets.voiceBind.viMaleNote')}</p> : null}
      <p className="drama-muted">{t('dramaAssets.voiceBind.lockedHint')}</p>
      <div className="drama-voice-catalog-filters">
        {(['all', 'male', 'female'] as const).map((g) => (
          <button
            key={g}
            type="button"
            className={`pf-btn pf-btn-sm${gender === g ? ' active' : ''}`}
            onClick={() => setGender(g)}
          >
            {t(g === 'all' ? 'dramaAssets.voiceBind.filterAll' : g === 'male' ? 'dramaAssets.voiceBind.filterMale' : 'dramaAssets.voiceBind.filterFemale')}
          </button>
        ))}
        {scenarios.length > 1 ? (
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="">{t('dramaAssets.voiceBind.filterScenarioAll')}</option>
            {scenarios.map((s) => (
              <option key={s} value={s}>
                {scenarioLabel(s)}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <ul className="drama-voice-catalog-list">
        {shown.map((voice) => (
          <li key={voice.speaker} className="drama-voice-catalog-item">
            <div className="drama-voice-catalog-meta">
              <strong>{voice.name}</strong>
              <small className="drama-muted">
                {t(voice.gender === 'male' ? 'dramaAssets.voiceBind.filterMale' : 'dramaAssets.voiceBind.filterFemale')}
                {voice.scenario ? ` · ${scenarioLabel(voice.scenario)}` : ''}
              </small>
              {voice.description ? <span className="drama-muted">{voice.description}</span> : null}
            </div>
            <div className="drama-voice-catalog-actions">
              {voice.sample_url ? (
                <button type="button" className="pf-btn pf-btn-sm" onClick={() => togglePlay(voice)}>
                  {playing === voice.speaker ? t('dramaAssets.voiceBind.stop') : t('dramaAssets.voiceBind.play')}
                </button>
              ) : null}
              <button
                type="button"
                className="pf-btn pf-btn-sm pf-btn-lime"
                disabled={busySpeaker !== null}
                onClick={() => onPick(voice)}
              >
                {busySpeaker === voice.speaker ? t('dramaAssets.voiceBind.usingVoice') : t('dramaAssets.voiceBind.useVoice')}
              </button>
            </div>
          </li>
        ))}
      </ul>
      <audio ref={audioRef} onEnded={() => setPlaying(null)} hidden />
    </div>
  )
}
```

Kiểm tra `t()` trả về chính key khi thiếu bản dịch (`grep -n "return" frontend/src/i18n/lookup.ts | head`); nếu hành vi khác (ví dụ trả rỗng), sửa `scenarioLabel` cho phù hợp: `label && label !== key ? label : s`.

CSS thêm vào cuối `drama.css`:

```css
/* Danh sách chọn giọng (VoiceCatalogPicker) */
.drama-voice-catalog { display: flex; flex-direction: column; gap: 8px; }
.drama-voice-catalog-filters { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.drama-voice-catalog-list { list-style: none; margin: 0; padding: 0; max-height: 360px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.drama-voice-catalog-item { display: flex; justify-content: space-between; gap: 12px; padding: 8px; border: 1px solid var(--pf-border, rgba(255,255,255,0.12)); border-radius: 8px; }
.drama-voice-catalog-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.drama-voice-catalog-actions { display: flex; gap: 6px; align-items: flex-start; flex-shrink: 0; }
@media (max-width: 640px) { .drama-voice-catalog-item { flex-direction: column; } }
```

Kiểm tra tên biến màu viền thật trong `printfilm.css` (`grep -n "\-\-pf-border\|--pf-line" frontend/src/styles/printfilm.css | head -3`) và dùng biến đó.

- [ ] **Step 4: Nối vào `CharacterVoiceBindModal.tsx`**

1. Import `VoiceCatalogPicker` và kiểu `CatalogVoice`.
2. `mode` đổi kiểu thành `'catalog' | 'pick' | 'create'`; thêm state (ghi vào khối comment state):
```tsx
  const [catalog, setCatalog] = useState<CatalogVoice[] | null>(null)
  const [catalogLang, setCatalogLang] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const [pickingSpeaker, setPickingSpeaker] = useState<string | null>(null)
```
3. Trong `useEffect` mở modal: đặt `setMode('catalog')` thay cho `setMode('pick')`; **bỏ** nhánh `if (voices.length === 0) setMode('create')` (tab mặc định giờ là catalog). Thêm tải catalog:
```tsx
    setCatalog(null)
    setCatalogError('')
    dramaApi
      .voiceCatalog(projectId)
      .then((res) => {
        setCatalog(res.voices)
        setCatalogLang(res.lang)
      })
      .catch((err) => setCatalogError(err instanceof Error ? err.message : translate('dramaAssets.voiceBind.catalogLoadFailed')))
```
4. Hàm chọn giọng:
```tsx
  // Chọn giọng trong danh mục: tạo tư liệu giọng khóa speaker (TTS câu mẫu) rồi gắn ngay cho nhân vật
  async function handlePickCatalog(voice: CatalogVoice) {
    if (pickingSpeaker) return
    setPickingSpeaker(voice.speaker)
    try {
      const result = await dramaApi.generateVoice({
        project_id: projectId,
        name: `${asset.name || t('dramaAssets.voiceBind.characterFallback')} · ${voice.name}`,
        voice_prompt: voice.description || voice.name,
        speaker: voice.speaker,
        speaker_locked: true,
        character_asset_id: asset.id,
      })
      const created = result.asset
      if (!created) throw new Error(t('dramaAssets.voiceBind.synthFailed'))
      setVoiceAssets((prev) => [...prev, created])
      const updated = await dramaApi.updateAsset(asset.id, { params: buildBoundParams(asset, created) })
      onBound(updated)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.voiceSynthFailed'))
    } finally {
      setPickingSpeaker(null)
    }
  }
```
Kiểm tra `handleConfirm` hiện có gắn giọng bằng cách nào (`grep -n "async function handleConfirm" -A20`); nếu nó gọi thêm bước khác ngoài `updateAsset(... buildBoundParams ...)` (ví dụ đóng modal / cập nhật canvas), lặp lại đúng các bước đó ở đây.
5. Tab — thêm nút đầu tiên trong `.drama-voice-mode-tabs`:
```tsx
        <button type="button" className={mode === 'catalog' ? 'active' : ''} onClick={() => setMode('catalog')}>
          {t('dramaAssets.voiceBind.catalogTab')}
        </button>
```
6. Nội dung — đổi `{mode === 'pick' ? (...) : (...)}` thành ba nhánh, nhánh catalog đứng đầu:
```tsx
      {mode === 'catalog' ? (
        catalogError ? (
          <p className="drama-muted">{catalogError}</p>
        ) : catalog === null ? (
          <p className="drama-muted">{t('dramaAssets.voiceBind.catalogLoading')}</p>
        ) : catalog.length === 0 ? (
          <p className="drama-muted">{t('dramaAssets.voiceBind.catalogEmpty')}</p>
        ) : (
          <VoiceCatalogPicker
            voices={catalog}
            lang={catalogLang}
            busySpeaker={pickingSpeaker}
            onPick={(v) => void handlePickCatalog(v)}
          />
        )
      ) : mode === 'pick' ? (
        /* giữ nguyên JSX danh sách tư liệu giọng hiện có */
      ) : (
        /* giữ nguyên JSX form tạo và tổng hợp hiện có */
      )}
```
7. Footer: nút "Xác nhận gắn" chỉ có ý nghĩa ở tab `pick`; thêm điều kiện ẩn nó khi `mode !== 'pick'`. `dismissible` của Modal: `!busy && !pickingSpeaker`.
8. Nếu file vượt 500 dòng, tách `handlePickCatalog` + state catalog sang hook `useVoiceCatalog.ts` cùng thư mục.

- [ ] **Step 5: Kiểm tra**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: pass / không lỗi mới / build thành công.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/drama/VoiceCatalogPicker.tsx frontend/src/pages/drama/CharacterVoiceBindModal.tsx frontend/src/api/drama.ts frontend/src/i18n/locales/*/dramaAssets.ts frontend/src/pages/drama/drama.css
git commit -m "feat(phim truyện): tab chọn giọng có nghe thử, giọng đã chọn được khóa khi lồng tiếng

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Tài liệu + kiểm tra toàn bộ

**Files:**
- Modify: `docs/PROVIDERS.md` (phần TTS / giọng)
- Modify: `docs/superpowers/specs/2026-09-24-character-config-design.md` (mục "Rulings khi lập kế hoạch")

- [ ] **Step 1: `docs/PROVIDERS.md`** — trong phần nói về TTS / danh mục giọng (tìm bằng `grep -n "uranus_bigtts\|VOICE_PRESETS\|音色" docs/PROVIDERS.md`), thêm mục:

```markdown
### Danh mục giọng BytePlus vi/en và khóa giọng

- Nguồn: https://docs.byteplus.com/en/docs/byteplusvoice/tts-voice-list (lấy 2026-09-24). Dữ liệu nằm ở `backend/app/services/data/byteplus_tts_voices.json`, sinh bằng `backend/scripts/gen_byteplus_voices.py` từ Phụ lục A của `docs/superpowers/specs/2026-09-24-character-config-design.md`. Mỗi giọng có `name / gender / scenario / description / sample_url` (file mẫu trên CDN BytePlus, nghe thử không tốn phí).
- Mỗi giọng chỉ đọc một ngôn ngữ. Tiếng Việt có 7 giọng (6 nữ, 1 nam), tiếng Anh 68.
- `auto_pool`: 13 giọng cũ = `true` (tham gia giọng mặc định và pool thay thế tự động, `/api/voices`); giọng thêm sau = `false` (chỉ xuất hiện ở `GET /api/drama/voices/catalog` để chọn tay). Không đưa giọng mới vào pool vì `stable_pick` theo hash sẽ đổi giọng của nhân vật đang lồng tiếng tự động.
- Khóa giọng: tư liệu giọng tạo từ tab "Chọn giọng" có `params.speakerLocked = true`. Khi tổng hợp mẫu và khi lồng tiếng (`resolve_bound_speaker`), giọng khóa được dùng nguyên nếu đọc được ngôn ngữ dự án (bỏ qua so khớp giới tính với mô tả, bỏ qua voice design); nếu dự án đã đổi ngôn ngữ thì rơi về luồng tự đoán và ghi log cảnh báo.
```

- [ ] **Step 2: Spec** — thêm vào cuối mục 3 (trước "## 4. Kiểm thử") một mục `### 3.4 Quyết định khi lập kế hoạch` liệt kê nguyên văn 7 mục trong phần "Rulings" của plan này.

- [ ] **Step 3: Kiểm tra toàn bộ**

Run: `cd backend && pytest -q -p no:cacheprovider tests/test_drama_appearance.py tests/test_voice_catalog.py tests/test_drama_speaker_lock.py tests/test_voice_lang.py tests/test_fragment_dub.py tests/test_drama_dub_lines.py tests/test_content_lang.py tests/test_app_errors.py`
Expected: tất cả pass.

Run: `cd backend && pytest -q` (toàn bộ; test cần Postgres sẽ lỗi kết nối nếu DB không chạy — ghi rõ số test lỗi do thiếu DB, không coi là pass).

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add docs/PROVIDERS.md docs/superpowers/specs/2026-09-24-character-config-design.md
git commit -m "docs(giọng): danh mục giọng BytePlus vi/en, cờ auto_pool và khóa giọng

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
