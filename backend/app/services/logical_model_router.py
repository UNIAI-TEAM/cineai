"""Lớp tương thích tạm thời cho các gọi "logical model" cũ, dựng trên function_router mới.

Chỉ còn 4 hàm mà ark.py / llm_client.py / drama/seedream_options.py /
drama/build_seedance_generate_body.py / drama/voice_synthesis.py / media_catalog.py
còn import. Task 10 sẽ xoá file này khi các call site chuyển hẳn sang function_router.
"""

from __future__ import annotations

from app.schemas_routing import LogicalModelCapability, ResolvedModelRoute
from app.services.function_router import ModelNotAllowed, resolve_function_candidates, resolve_function_route

# Chức năng mặc định đại diện cho mỗi năng lực (dùng khi call site chỉ biết capability, không biết function_id)
_DEFAULT_FUNCTION_BY_CAPABILITY: dict[LogicalModelCapability, str] = {
    "text": "kepu.script",
    "image": "kepu.image",
    "video": "kepu.video",
    "audio": "kepu.tts",
}


def resolve_logical_model_id(capability: LogicalModelCapability, model_id: str | None) -> str:
    """Tương thích cũ: không còn alias, chỉ trả lại model_id đã strip (rỗng nếu không truyền)."""
    return (model_id or "").strip()


def resolve_upstream_model(capability: LogicalModelCapability, model_id: str | None) -> str:
    """Giải ra model upstream thực tế; không bao giờ raise — lỗi/rỗng thì rơi về settings.model_*."""
    function_id = _DEFAULT_FUNCTION_BY_CAPABILITY[capability]
    try:
        route = resolve_function_route(function_id, model_id or None)
    except ModelNotAllowed:
        route = None
    if route:
        return route.upstream_model
    from app.config import get_settings

    settings = get_settings()
    fallback = {
        "text": settings.model_llm,
        "image": settings.model_image,
        "video": settings.model_video,
        "audio": settings.model_audio,
    }
    return fallback[capability]


def resolve_logical_model(
    capability: LogicalModelCapability,
    model_id: str | None,
    *,
    preferred_channel_id: str = "",
) -> ResolvedModelRoute | None:
    """Giải ra route đầu tiên khớp chức năng mặc định của capability, hoặc None nếu chưa gán/không hợp lệ."""
    function_id = _DEFAULT_FUNCTION_BY_CAPABILITY[capability]
    try:
        return resolve_function_route(function_id, model_id or None)
    except ModelNotAllowed:
        return None


def resolve_logical_model_candidates(
    capability: LogicalModelCapability,
    model_id: str | None,
    *,
    preferred_channel_id: str = "",
) -> list[ResolvedModelRoute]:
    """Danh sách route ứng viên (failover); rỗng nếu chưa gán/không hợp lệ."""
    function_id = _DEFAULT_FUNCTION_BY_CAPABILITY[capability]
    try:
        return resolve_function_candidates(function_id, model_id or None)
    except ModelNotAllowed:
        return []
