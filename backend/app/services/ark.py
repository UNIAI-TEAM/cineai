"""Shim tương thích: mọi tên `ark.*` cũ nay trỏ sang MediaGateway + provider adapters.

Không còn logic HTTP ở đây. Sinh ảnh/video/giọng đọc nằm ở `media_gateway.py`, giao thức
nằm ở `providers/*`, tách phân cảnh nằm ở `kepu_text.py`. Giữ file này để call site và test
cũ (`get_ark()`, `ArkGateway`, `TaskResult`, các helper `_*`) không phải đổi trong một lượt.
"""

from __future__ import annotations

from app.services.kepu_text import ShotPlan, StoryboardResult, storyboard_name_policy
from app.services.media_gateway import ImageResult, MediaGateway, get_media_gateway, reset_media_gateway
from app.services.providers import ark_adapter, base

TaskResult = base.TaskResult
IMAGE_GEN_READ_SEC = base.IMAGE_GEN_READ_SEC
VIDEO_CREATE_READ_SEC = base.VIDEO_CREATE_READ_SEC
reraise_upstream_timeout = base.reraise_upstream_timeout
_upstream_timeout = base.upstream_timeout
_is_transient_http_status = base.is_transient_http_status
_retry_after_seconds = base.retry_after_seconds

_SEEDREAM_CG_STYLE = ark_adapter.SEEDREAM_CG_STYLE
_build_task_result_from_payload = ark_adapter.build_task_result_from_payload
_format_seedance_create_error = ark_adapter.format_seedance_create_error
_raise_seedream_http_error = ark_adapter.raise_seedream_http_error

# Tên cũ mà pipeline/drama/tools và test vẫn dùng
ArkGateway = MediaGateway
get_ark = get_media_gateway
reset_ark = reset_media_gateway

__all__ = [
    "IMAGE_GEN_READ_SEC",
    "VIDEO_CREATE_READ_SEC",
    "ArkGateway",
    "ImageResult",
    "MediaGateway",
    "ShotPlan",
    "StoryboardResult",
    "TaskResult",
    "get_ark",
    "get_media_gateway",
    "reraise_upstream_timeout",
    "reset_ark",
    "reset_media_gateway",
    "storyboard_name_policy",
]
