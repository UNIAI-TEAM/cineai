"""Resolve route theo chức năng: override → slot, lọc provider hỏng, chọn theo weight, failover."""

from __future__ import annotations

import random
from typing import Any

from app.schemas_routing import ModelBinding, ResolvedModelRoute, SystemModelChannel
from app.services.function_bindings import effective_bindings
from app.services.functions import function_capability
from app.services.model_routing_config import channel_connection_ready, normalize_model_name


class ModelNotAllowed(ValueError):
    """Model user chọn không nằm trong danh sách admin đã gán cho chức năng."""


def _snapshot(snapshot: Any | None):
    """Trả về snapshot đã truyền vào, hoặc lấy snapshot routing hiện hành nếu không có."""
    if snapshot is not None:
        return snapshot
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def _channel_ok(ch: SystemModelChannel) -> bool:
    """Provider có bật và có đủ thông tin kết nối (hoặc key thô) không."""
    return ch.enabled and (channel_connection_ready(ch) or bool((ch.api_key or "").strip()))


def _protocol(ch: SystemModelChannel) -> str:
    """Chuẩn hoá protocol của provider (rỗng/auto → openai)."""
    proto = (ch.protocol or "openai").lower()
    return "openai" if proto in ("", "auto") else proto


def _build_route(ch: SystemModelChannel, model: str, capability: str, function_id: str) -> ResolvedModelRoute:
    """Dựng ResolvedModelRoute từ một provider + model cụ thể."""
    proto = _protocol(ch)
    return ResolvedModelRoute(
        capability=capability, logical_model_id=function_id, upstream_model=model,
        channel_id=ch.id, channel_name=ch.name, base_url=(ch.base_url or "").rstrip("/"),
        api_key=(ch.api_key or "").strip(), protocol=proto, api_format="ark" if proto == "ark" else "openai",
    )


def allowed_bindings(function_id: str, *, snapshot: Any | None = None) -> list[ModelBinding]:
    """Binding hiệu lực đã loại provider tắt/thiếu key/model không còn bật."""
    snap = _snapshot(snapshot)
    by_id = {c.id: c for c in snap.channels}
    out: list[ModelBinding] = []
    for b in effective_bindings(snap.function_bindings, function_id):
        ch = by_id.get(b.channel_id)
        if ch is None or not _channel_ok(ch):
            continue
        if not any(normalize_model_name(m) == normalize_model_name(b.model) for m in ch.models):
            continue
        out.append(b)
    return out


def is_model_allowed(function_id: str, model_id: str | None, *, snapshot: Any | None = None) -> bool:
    """User chọn model này cho chức năng được không (rỗng = tự động → True)."""
    mid = normalize_model_name(model_id or "")
    if not mid:
        return True
    return any(normalize_model_name(b.model) == mid for b in allowed_bindings(function_id, snapshot=snapshot))


def _weighted_order(items: list[ModelBinding], rng: random.Random) -> list[ModelBinding]:
    """Xáo trộn danh sách binding theo weight (weight cao có xác suất đứng trước cao hơn)."""
    pool = list(items)
    out: list[ModelBinding] = []
    while pool:
        pick = rng.choices(pool, weights=[max(1, b.weight) for b in pool], k=1)[0]
        out.append(pick)
        pool.remove(pick)
    return out


def resolve_function_candidates(function_id: str, requested_model: str | None = None, *, snapshot: Any | None = None,
                                rng: random.Random | None = None) -> list[ResolvedModelRoute]:
    """Thứ tự thử: model user chọn trước, còn lại xáo trộn theo weight (failover)."""
    snap = _snapshot(snapshot)
    by_id = {c.id: c for c in snap.channels}
    capability = function_capability(function_id)
    allowed = allowed_bindings(function_id, snapshot=snap)
    mid = normalize_model_name(requested_model or "")
    head: list[ModelBinding] = []
    if mid:
        head = [b for b in allowed if normalize_model_name(b.model) == mid]
        if not head:
            raise ModelNotAllowed(requested_model or "")
    rest = [b for b in allowed if b not in head]
    ordered = head + _weighted_order(rest, rng or random)
    return [_build_route(by_id[b.channel_id], b.model, capability, function_id) for b in ordered]


def resolve_function_route(function_id: str, requested_model: str | None = None, *, snapshot: Any | None = None,
                           rng: random.Random | None = None) -> ResolvedModelRoute | None:
    """Route đầu tiên hoặc None khi chưa gán."""
    cands = resolve_function_candidates(function_id, requested_model, snapshot=snapshot, rng=rng)
    return cands[0] if cands else None


def route_for_channel(channel_id: str, model: str, capability: str, *, snapshot: Any | None = None) -> ResolvedModelRoute | None:
    """Route cố định theo kênh (poll tác vụ đã tạo), không qua bindings."""
    snap = _snapshot(snapshot)
    ch = next((c for c in snap.channels if c.id == channel_id), None)
    if ch is None:
        return None
    return _build_route(ch, model, capability, f"{capability}.poll")
