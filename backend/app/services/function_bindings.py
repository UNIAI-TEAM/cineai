"""Gán model theo chức năng: parse/validate/hợp nhất override → slot (thuần, không DB)."""

from __future__ import annotations

from typing import Any

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.functions import CAPABILITIES, FUNCTION_BY_ID, function_capability
from app.services.model_routing_config import infer_model_capability, normalize_model_name

_CAP_LABEL = {"text": "Văn bản", "image": "Ảnh", "video": "Video", "audio": "Giọng đọc"}


def _parse_list(raw: Any) -> list[ModelBinding]:
    """Parse một danh sách binding thô, bỏ qua phần tử hỏng hoặc thiếu trường."""
    out: list[ModelBinding] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            b = ModelBinding.model_validate(item)
        except Exception:  # noqa: BLE001
            continue
        if b.channel_id.strip() and b.model.strip():
            out.append(b)
    return out


def parse_function_bindings(raw: Any) -> FunctionBindings:
    """Đọc từ config_json; bỏ khoá lạ và phần tử hỏng."""
    if not isinstance(raw, dict):
        return FunctionBindings()
    slots = {k: _parse_list(v) for k, v in (raw.get("slots") or {}).items() if k in CAPABILITIES}
    overrides = {k: _parse_list(v) for k, v in (raw.get("overrides") or {}).items() if k in FUNCTION_BY_ID}
    return FunctionBindings(slots=slots, overrides=overrides)


def bindings_to_dict(b: FunctionBindings) -> dict[str, Any]:
    """Dạng lưu DB."""
    return b.model_dump()


def effective_bindings(b: FunctionBindings, function_id: str) -> list[ModelBinding]:
    """Override của chức năng nếu có, không thì slot năng lực."""
    override = b.overrides.get(function_id) or []
    if override:
        return list(override)
    return list(b.slots.get(function_capability(function_id)) or [])


def slot_assigned(b: FunctionBindings, capability: str) -> bool:
    """Slot năng lực đã có ít nhất một model."""
    return bool(b.slots.get(capability))


def _check(label: str, capability: str, items: list[ModelBinding], channels: dict[str, SystemModelChannel]) -> list[str]:
    """Kiểm tra một danh sách binding: provider tồn tại, model đã bật, đúng năng lực."""
    errs: list[str] = []
    for item in items:
        ch = channels.get(item.channel_id)
        if ch is None:
            errs.append(f"{label}: provider '{item.channel_id}' không tồn tại")
            continue
        if not any(normalize_model_name(m) == normalize_model_name(item.model) for m in ch.models):
            errs.append(f"{label}: model '{item.model}' chưa được bật ở provider {ch.name}")
            continue
        if ch.protocol == "volc_tts":
            cap = "audio"
        else:
            cap = infer_model_capability(item.model)
        if cap != capability:
            errs.append(f"{label}: model '{item.model}' không phải model {_CAP_LABEL[capability].lower()}")
    return errs


def validate_function_bindings(b: FunctionBindings, channels: list[SystemModelChannel]) -> list[str]:
    """Danh sách lỗi (tiếng Việt); rỗng = hợp lệ."""
    by_id = {c.id: c for c in channels}
    errs: list[str] = []
    for cap, items in b.slots.items():
        errs.extend(_check(f"Slot {_CAP_LABEL.get(cap, cap)}", cap, items, by_id))
    for fid, items in b.overrides.items():
        fn = FUNCTION_BY_ID.get(fid)
        if fn is None:
            errs.append(f"Chức năng '{fid}' không tồn tại")
            continue
        errs.extend(_check(fn.label_vi, fn.capability, items, by_id))
    return list(dict.fromkeys(errs))
