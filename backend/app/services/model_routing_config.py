"""Model name normalization and capability inference shared across provider routing."""

from __future__ import annotations

import re

from app.schemas_routing import LogicalModelCapability, SystemModelChannel


# 规范化模型名用于比较
def normalize_model_name(value: str) -> str:
    """Lowercase + bỏ khoảng trắng để so khớp tên model không phân biệt định dạng."""
    return re.sub(r"\s+", "", (value or "").strip()).lower()


# 从模型名推断能力类型
def infer_model_capability(model: str) -> LogicalModelCapability:
    """Suy đoán năng lực (text/image/video/audio) từ tên model theo các từ khoá quen thuộc."""
    mid = normalize_model_name(model)
    if not mid:
        return "text"
    if (
        "tts" in mid
        or "text-to-speech" in mid
        or "text-to-dialogue" in mid
        or "elevenlabs" in mid
        or mid.startswith("zh_")
        or "speaker" in mid
        or mid.startswith("s_")
    ):
        return "audio"
    if (
        "seedance" in mid
        or "veo" in mid
        or "video" in mid
        or "i2v" in mid
        or "sora" in mid
        or mid.startswith("kie-veo")
        or mid.startswith("kie-seedance")
    ):
        return "video"
    if (
        "seedream" in mid
        or "nano-banana" in mid
        or "banana" in mid
        or "dream" in mid
        or mid.startswith("gpt-image")
        or "grok-imagine" in mid
        or "image" in mid
        or mid.startswith("kie-")
    ):
        return "image"
    return "text"


# 判断渠道是否具备连接信息
def channel_connection_ready(channel: SystemModelChannel) -> bool:
    """Kiểm tra provider đã bật và có đủ thông tin kết nối (base URL + key, hoặc key thô)."""
    if not channel.enabled:
        return False
    if channel.protocol == "volc_tts":
        return bool(channel.has_api_key or channel.base_url)
    return bool(channel.base_url and (channel.has_api_key or (channel.api_key or "").strip()))


# 判断渠道是否包含指定上游模型
def channel_supports_model(channel: SystemModelChannel, upstream_model: str) -> bool:
    """Kiểm tra provider có bật model này trong danh sách `models` (so khớp đã chuẩn hoá)."""
    target = normalize_model_name(upstream_model)
    if not target:
        return False
    return any(normalize_model_name(item) == target for item in channel.models)
