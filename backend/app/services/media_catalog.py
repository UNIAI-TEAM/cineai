"""Catalog ảnh/video phía user: lấy từ slot/override đã gán, theo scope sản phẩm."""

from __future__ import annotations

from typing import Any

from app.schemas_routing import LogicalModelCapability
from app.services.model_routing_config import normalize_model_name

# Mỗi scope sản phẩm tương ứng một cặp chức năng (ảnh, video)
_SCOPE_FUNCTIONS: dict[str, tuple[str, str]] = {
    "kepu": ("kepu.image", "kepu.video"),
    "drama": ("drama.asset_image", "drama.video"),
    "tools": ("tools.image", "tools.video"),
}


def _rows(function_id: str, snapshot: Any | None = None) -> list[dict[str, Any]]:
    """Binding hiệu lực của một chức năng → danh sách dòng model, loại trùng theo tên chuẩn hoá."""
    from app.services.function_router import allowed_bindings

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for b in allowed_bindings(function_id, snapshot=snapshot):
        key = normalize_model_name(b.model)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": b.model,
                "label": b.model,
                "description": "",
                "provider": b.channel_id,
                "recommended": not out,
            }
        )
    return out


def build_media_catalog(
    *,
    image_function: str,
    video_function: str,
    snapshot: Any | None = None,
) -> dict[str, Any]:
    """Danh mục ảnh/video của một cặp chức năng; model đầu tiên là gợi ý mặc định."""
    images = _rows(image_function, snapshot)
    videos = _rows(video_function, snapshot)
    return {
        "image_models": images,
        "video_models": videos,
        "defaults": {
            "image_model": images[0]["id"] if images else "",
            "video_model": videos[0]["id"] if videos else "",
        },
    }


def catalog_payload(scope: str | None = None) -> dict[str, Any]:
    """Danh mục cho /api/media-models; không truyền scope thì hợp nhất kepu → drama → tools."""
    if scope in _SCOPE_FUNCTIONS:
        image_function, video_function = _SCOPE_FUNCTIONS[scope]
        return build_media_catalog(image_function=image_function, video_function=video_function)
    from app.services.model_settings import get_routing_snapshot

    # Một snapshot dùng chung cho cả 3 scope: tránh đọc cấu hình đổi giữa chừng
    snapshot = get_routing_snapshot()
    merged: dict[str, Any] = {"image_models": [], "video_models": []}
    seen: dict[str, set[str]] = {"image_models": set(), "video_models": set()}
    for key in ("kepu", "drama", "tools"):
        image_function, video_function = _SCOPE_FUNCTIONS[key]
        part = build_media_catalog(
            image_function=image_function, video_function=video_function, snapshot=snapshot
        )
        for bucket in ("image_models", "video_models"):
            for row in part[bucket]:
                norm = normalize_model_name(row["id"])
                if norm in seen[bucket]:
                    continue
                seen[bucket].add(norm)
                merged[bucket].append({**row, "recommended": not merged[bucket]})
    merged["defaults"] = {
        "image_model": merged["image_models"][0]["id"] if merged["image_models"] else "",
        "video_model": merged["video_models"][0]["id"] if merged["video_models"] else "",
    }
    return merged


def is_valid_project_media_model(model_id: str | None, capability: LogicalModelCapability) -> bool:
    """project.image_model / video_model phải nằm trong model admin đã gán cho chức năng khoa học."""
    from app.services.function_router import is_model_allowed

    return is_model_allowed("kepu.image" if capability == "image" else "kepu.video", model_id)
