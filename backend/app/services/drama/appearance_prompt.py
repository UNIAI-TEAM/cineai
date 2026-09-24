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


def has_field_composed_prompt(asset_type: str | None, params: Any) -> bool:
    """Nhân vật có ngoại hình theo trường và đang tự ghép: prompt hiện tại chính là bản ghép từ trường,
    các luồng LLM viết lại prompt (làm mới từ kịch bản, bù prompt yếu) phải bỏ qua."""
    if (asset_type or "").lower() != "character" or not isinstance(params, dict):
        return False
    if params.get("promptManual") is True:
        return False
    return not appearance_is_empty(normalize_appearance(params.get("appearance")))


def compose_appearance_prompt(appearance: dict[str, str], lang: str | None) -> str:
    """Ghép các trường không rỗng: dự án zh dùng nhãn Trung, còn lại nhãn Anh; toàn rỗng → ""."""
    zh = use_zh_prompt_labels(lang, " ".join(appearance.values()))
    labels, pair_sep, join_sep = (_ZH_LABELS, "：", "。") if zh else (_EN_LABELS, ": ", ". ")
    parts = [
        f"{labels[k]}{pair_sep}{appearance[k]}" for k in APPEARANCE_KEYS if (appearance.get(k) or "").strip()
    ]
    return join_sep.join(parts)


def apply_appearance_to_params(
    params: dict[str, Any], lang: str | None, *, body: str | None = None
) -> dict[str, Any]:
    """Trả params mới: nếu có ngoại hình và không ở chế độ chỉnh tay thì ghi prompt vào
    visualPrompt / visualImage / canvas.generation.prompt (kèm nhãn title/roleType/coreTags/personality).
    body: đoạn mô tả AI viết từ các trường; không có thì ghép thẳng 8 trường."""
    out = dict(params or {})
    appearance = normalize_appearance(out.get("appearance"))
    out["appearance"] = appearance
    if out.get("promptManual") is True or appearance_is_empty(appearance):
        return out
    body = (body or "").strip() or compose_appearance_prompt(appearance, lang)
    prompt = manju_join_character_prompt({**out, "visualImage": body}, lang)
    out["visualPrompt"] = prompt
    out["visualImage"] = prompt
    canvas = dict(out["canvas"]) if isinstance(out.get("canvas"), dict) else {}
    gen = dict(canvas["generation"]) if isinstance(canvas.get("generation"), dict) else {}
    gen["prompt"] = prompt
    canvas["generation"] = gen
    out["canvas"] = canvas
    return out


def should_recompose_prompt(
    asset_type: str | None,
    patch: dict[str, Any] | None,
    prev_params: dict[str, Any] | None,
) -> bool:
    """PATCH tư liệu có cần ghép lại prompt: chỉ nhân vật, và chỉ khi có ý định thật —
    bật lại chế độ tự ghép (promptManual=False) hoặc appearance thực sự đổi so với trước.
    PATCH gửi lại nguyên params cũ (gắn giọng, nhập từ thư viện…) không được ghi đè prompt."""
    if (asset_type or "").lower() != "character" or not isinstance(patch, dict):
        return False
    prev = prev_params if isinstance(prev_params, dict) else {}
    # Chỉ tính là "bật lại tự ghép" khi trước đó chưa ở chế độ tự ghép (tránh echo cờ đã lưu)
    if patch.get("promptManual") is False and prev.get("promptManual") is not False:
        return True
    if "appearance" not in patch:
        return False
    prev_appearance = prev.get("appearance")
    return normalize_appearance(patch["appearance"]) != normalize_appearance(prev_appearance)
