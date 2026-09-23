"""OpenAI (và OpenAI-compatible: OpenRouter, tuỳ chỉnh): ảnh base64, TTS, danh sách model."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.billing.pricing import parse_usage_dict
from app.services.providers.base import (
    IMAGE_GEN_READ_SEC, ImageOutput, ImageRequest, ProviderNotSupported, TaskResult,
    TransientUpstreamError, TtsRequest, UpstreamError, VideoRequest, bearer_headers, is_failover_safe_error, is_transient_http_status,
    join_url, reraise_upstream_timeout, upstream_timeout,
)

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_EDIT_REFS = 16
# gpt-image-2 / 2.5: WxH tuỳ ý chia hết 16, cạnh ≤ 3840x2160, tỉ lệ trong [1:3, 3:1]
_ARBITRARY_SIZE_MODELS = re.compile(r"^gpt-image-2(\.|-|$)")
_TIER_QUALITY = {"1K": "low", "2K": "medium", "3K": "high", "4K": "high"}


def is_official_openai(base_url: str) -> bool:
    """Base URL là api.openai.com (dùng để chọn max_completion_tokens)."""
    return (urlparse(base_url or "").hostname or "").lower() == "api.openai.com"


def _ratio_of(aspect_ratio: str) -> float | None:
    """Parse chuỗi "W:H" thành tỉ lệ số thực; không khớp hoặc H=0 thì trả None."""
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", aspect_ratio or "")
    return (int(m.group(1)) / int(m.group(2))) if m and int(m.group(2)) else None


def openai_image_size(size: str, aspect_ratio: str, model: str) -> tuple[str, str]:
    """Map size nội bộ (1K/2K/3K/4K hoặc WxH) + tỉ lệ sang (size, quality) của OpenAI."""
    raw = (size or "2K").strip()
    tier = raw.upper()
    ratio = _ratio_of(aspect_ratio)
    m = re.match(r"^(\d+)\s*[xX×]\s*(\d+)$", raw)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        ratio = w / h if h else ratio
        if _ARBITRARY_SIZE_MODELS.match((model or "").lower()):
            scale = min(1.0, 3840 / max(w, 1), 2160 / max(h, 1))
            w, h = int(w * scale), int(h * scale)
            r = w / max(h, 1)
            if r > 3:
                h = w // 3
            elif r < 1 / 3:
                w = h // 3
            w, h = max(16, w - w % 16), max(16, h - h % 16)
            return f"{w}x{h}", "medium"
        tier = "2K"
    quality = _TIER_QUALITY.get(tier, "medium")
    if ratio is None or abs(ratio - 1) < 0.15:
        return "1024x1024", quality
    return ("1536x1024", quality) if ratio > 1 else ("1024x1536", quality)


def openai_voice_for_speaker(speaker: str) -> str:
    """Speaker nội bộ (zh_female_*, S_*, preset) → voice OpenAI theo giới tính suy ra."""
    from app.services.voices import infer_speaker_gender

    g = infer_speaker_gender(speaker or "")
    if g == "female":
        return "marin"
    if g == "male":
        return "cedar"
    return "alloy"


def _error_text(resp: httpx.Response) -> str:
    """Rút gọn thông báo lỗi upstream: ưu tiên error.message JSON, không có thì lấy text thô."""
    try:
        err = resp.json().get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
    except Exception:  # noqa: BLE001
        pass
    return (resp.text or "")[:300]


class OpenAIAdapter:
    """OpenAI-compatible: /images/generations|edits (base64), /audio/speech, GET /models."""

    protocol = "openai"

    async def list_models(self, route: ResolvedModelRoute, capability: str = "all") -> list[dict[str, str]]:
        """GET /models rồi suy luận capability từng model, loại video (OpenAI/OpenRouter chưa hỗ trợ)."""
        from app.services.model_routing_config import infer_model_capability

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(join_url(route.base_url, "/models"), headers=bearer_headers(route.api_key))
        if resp.status_code >= 400:
            raise UpstreamError(f"Không tải được danh sách model (HTTP {resp.status_code}): {_error_text(resp)}")
        out: list[dict[str, str]] = []
        for item in resp.json().get("data") or []:
            mid = str(item.get("id") or "").strip()
            if not mid:
                continue
            cap = infer_model_capability(mid)
            if cap == "video":
                continue  # OpenAI không còn video; OpenRouter chưa có
            if capability in ("all", cap):
                out.append({"id": mid, "label": mid, "capability": cap})
        return sorted(out, key=lambda m: m["id"])

    async def gen_image(self, route: ResolvedModelRoute, req: ImageRequest) -> ImageOutput:
        """Sinh ảnh: có ref/style_ref thì gọi /images/edits, không thì /images/generations; trả base64."""
        model = route.upstream_model
        size, quality = openai_image_size(req.size, req.aspect_ratio, model)
        refs = [*req.refs, *req.style_refs][:MAX_EDIT_REFS]
        body: dict[str, Any] = {"model": model, "prompt": req.prompt, "n": 1, "size": size, "quality": quality, "output_format": req.output_format or "png"}
        path = "/images/generations"
        if refs:
            path = "/images/edits"
            body["images"] = [{"image_url": u} for u in refs]
        try:
            async with httpx.AsyncClient(timeout=upstream_timeout(IMAGE_GEN_READ_SEC)) as client:
                resp = await client.post(join_url(route.base_url, path), headers=bearer_headers(route.api_key), json=body)
        except httpx.TimeoutException as exc:
            reraise_upstream_timeout(exc, kind="生图", read_sec=IMAGE_GEN_READ_SEC)
        if resp.status_code >= 400:
            if is_transient_http_status(resp.status_code):
                raise TransientUpstreamError(f"OpenAI image HTTP {resp.status_code}")
            raise UpstreamError(f"生图失败（{resp.status_code}）：{_error_text(resp)}")
        data = resp.json()
        first = (data.get("data") or [{}])[0]
        usage = parse_usage_dict(data)
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        b64 = first.get("b64_json")
        if not b64 and not first.get("url"):
            raise UpstreamError("出图未返回图片数据，请稍后重试")
        return ImageOutput(url=first.get("url"), data=base64.b64decode(b64) if b64 else None, size=size, raw_usage=raw_usage,
                           total_tokens=int(usage.get("total_tokens") or 0), prompt_tokens=int(usage.get("prompt_tokens") or 0),
                           completion_tokens=int(usage.get("completion_tokens") or 0))

    async def create_video(self, route: ResolvedModelRoute, req: VideoRequest) -> str:
        """OpenAI không có API tạo video (Sora đã gỡ khỏi API)."""
        raise ProviderNotSupported("OpenAI không hỗ trợ tạo video")

    async def fetch_video(self, route: ResolvedModelRoute, task_id: str) -> TaskResult:
        """OpenAI không có API tạo video nên cũng không có tác vụ để tra."""
        raise ProviderNotSupported("OpenAI không hỗ trợ tạo video")

    async def tts(self, route: ResolvedModelRoute, req: TtsRequest) -> bytes:
        """Chuyển văn bản thành giọng nói qua /audio/speech, trả mp3 bytes."""
        model = route.upstream_model or "gpt-4o-mini-tts"
        body: dict[str, Any] = {"model": model, "input": req.text, "voice": openai_voice_for_speaker(req.voice), "response_format": "mp3"}
        if req.emotion_hint and not model.startswith("tts-1"):
            body["instructions"] = req.emotion_hint[:400]
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(join_url(route.base_url, "/audio/speech"), headers=bearer_headers(route.api_key), json=body)
        if resp.status_code >= 400:
            raise UpstreamError(f"TTS HTTP {resp.status_code}: {_error_text(resp)}")
        if len(resp.content) < 1000:
            raise UpstreamError("TTS trả về âm thanh rỗng")
        return resp.content

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates từ usage thật (gpt-image: output_tokens)."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)

    def url_needs_auth(self, url: str) -> bool:
        """URL ảnh/audio OpenAI trả về (hoặc base64) không cần Bearer khi tải lại."""
        return False

    def is_transient_error(self, exc: BaseException) -> bool:
        """Lỗi tạm thời (429/5xx/mạng) có thể failover sang model kế tiếp."""
        return is_failover_safe_error(exc)
