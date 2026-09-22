"""Danh mục model ảnh/video hiển thị ở frontend: suy ra từ function_bindings hiện hành (kepu.image/kepu.video).

Task 10 sẽ viết lại đầy đủ theo `scope` (kepu/drama/tools) khi tách bindings theo domain;
bản này chỉ đủ để `/api/media-models` và validate project image_model/video_model hoạt động.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.schemas_routing import LogicalModelCapability, ModelBinding
from app.services.model_routing_config import infer_model_capability, normalize_model_name


def _row(*, model_id: str, label: str, recommended: bool, provider: str = "", description: str = "") -> dict[str, Any]:
    """Đóng gói một dòng model cho danh mục frontend."""
    return {
        "id": model_id,
        "label": (label or model_id).strip() or model_id,
        "description": description,
        "provider": provider,
        "recommended": recommended,
    }


def _bindings_to_rows(bindings: list[ModelBinding]) -> list[dict[str, Any]]:
    """Chuyển binding (channel, model) hiệu lực thành danh sách dòng, loại trùng theo tên model chuẩn hoá."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for b in bindings:
        key = normalize_model_name(b.model)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(_row(model_id=b.model, label=b.model, recommended=not rows, provider=b.channel_id))
    return rows


def build_media_catalog(
    *,
    image_bindings: list[ModelBinding],
    video_bindings: list[ModelBinding],
    fallback_image: str = "",
    fallback_video: str = "",
) -> dict[str, Any]:
    """Dựng danh mục image/video từ binding hiệu lực của kepu.image/kepu.video."""
    images = _bindings_to_rows(image_bindings)
    videos = _bindings_to_rows(video_bindings)
    default_image = images[0]["id"] if images else (fallback_image or "").strip()
    default_video = videos[0]["id"] if videos else (fallback_video or "").strip()
    if not images and default_image:
        images.append(_row(model_id=default_image, label=default_image, recommended=True))
    if not videos and default_video:
        videos.append(_row(model_id=default_video, label=default_video, recommended=True))
    return {
        "image_models": images,
        "video_models": videos,
        "defaults": {"image_model": default_image, "video_model": default_video},
    }


def catalog_payload() -> dict[str, Any]:
    """Danh mục công khai cho /api/media-models (dùng bởi frontend)."""
    from app.services.function_router import allowed_bindings
    from app.services.model_settings import get_routing_snapshot

    snap = get_routing_snapshot()
    settings = get_settings()
    return build_media_catalog(
        image_bindings=allowed_bindings("kepu.image", snapshot=snap),
        video_bindings=allowed_bindings("kepu.video", snapshot=snap),
        fallback_image=settings.model_image,
        fallback_video=settings.model_video,
    )


def is_valid_project_media_model(model_id: str | None, capability: LogicalModelCapability) -> bool:
    """Kiểm tra project.image_model/video_model hợp lệ: khớp binding đang gán hoặc rơi vào fallback khoan dung cũ."""
    mid = (model_id or "").strip()
    if not mid:
        return True
    from app.services.function_router import is_model_allowed

    function_id = "kepu.image" if capability == "image" else "kepu.video"
    if is_model_allowed(function_id, mid):
        return True
    cat = catalog_payload()
    list_key = "image_models" if capability == "image" else "video_models"
    norm_mid = normalize_model_name(mid)
    for row in cat.get(list_key) or []:
        if normalize_model_name(str(row.get("id") or "")) == norm_mid:
            return True
    defaults = cat.get("defaults") if isinstance(cat.get("defaults"), dict) else {}
    def_key = "image_model" if capability == "image" else "video_model"
    if normalize_model_name(str(defaults.get(def_key) or "")) == norm_mid:
        return True
    # 与前台 /api/media-models 同源；能力推断一致即允许保存，具体路由在生成阶段解析
    if infer_model_capability(mid) == capability:
        return True
    settings = get_settings()
    fallback = (settings.model_image if capability == "image" else settings.model_video) or ""
    if normalize_model_name(fallback) == norm_mid:
        return True
    return False
