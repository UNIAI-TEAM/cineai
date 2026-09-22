"""Danh mục chức năng AI cố định (id → năng lực) dùng cho gán model theo chức năng."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas_routing import LogicalModelCapability

CAPABILITIES: tuple[str, ...] = ("text", "image", "video", "audio")


@dataclass(frozen=True)
class AiFunction:
    """Một chức năng AI cố định trong sản phẩm (id, năng lực và nhãn hiển thị)."""

    id: str
    capability: LogicalModelCapability
    label_vi: str
    label_en: str
    description_vi: str


FUNCTIONS: tuple[AiFunction, ...] = (
    AiFunction("kepu.script", "text", "Kịch bản khoa học", "Science script", "Mở rộng chủ đề và tách phân cảnh video khoa học"),
    AiFunction("drama.script", "text", "Kịch bản phim ngắn", "Drama script", "Tóm tắt, chia tập, tách phân cảnh, viết prompt phim ngắn"),
    AiFunction("kepu.image", "image", "Ảnh phân cảnh khoa học", "Science storyboard image", "Ảnh tĩnh từng phân cảnh video khoa học"),
    AiFunction("drama.asset_image", "image", "Ảnh tài sản phim ngắn", "Drama asset image", "Nhân vật, bối cảnh, đạo cụ và ảnh tĩnh phân cảnh"),
    AiFunction("tools.image", "image", "Ảnh công cụ & Open API", "Tools & API image", "Công cụ t2i/i2p và /api/v1/images"),
    AiFunction("kepu.video", "video", "Video khoa học", "Science video", "Video từng phân cảnh video khoa học"),
    AiFunction("drama.video", "video", "Video phim ngắn", "Drama video", "Video phân cảnh và video tài sản phim ngắn"),
    AiFunction("tools.video", "video", "Video công cụ & Open API", "Tools & API video", "Công cụ t2v/i2v và /api/v1/videos"),
    AiFunction("kepu.tts", "audio", "Lời bình khoa học", "Science narration", "Giọng đọc lời bình video khoa học"),
    AiFunction("drama.tts", "audio", "Lồng tiếng phim ngắn", "Drama voice", "Giọng nhân vật và mẫu giọng phim ngắn"),
)
FUNCTION_BY_ID: dict[str, AiFunction] = {f.id: f for f in FUNCTIONS}


def function_capability(function_id: str) -> LogicalModelCapability:
    """Năng lực của chức năng; KeyError nếu id lạ."""
    return FUNCTION_BY_ID[function_id].capability


def function_catalog_payload() -> list[dict[str, str]]:
    """Danh mục cho admin API (nhãn tiếng Việt)."""
    return [{"id": f.id, "capability": f.capability, "label": f.label_vi, "description": f.description_vi} for f in FUNCTIONS]
