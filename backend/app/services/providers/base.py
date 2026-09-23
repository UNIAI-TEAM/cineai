"""Base types, Protocol, và HTTP helpers cho provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NoReturn, Protocol

import httpx

from app.schemas_routing import ResolvedModelRoute

# Timeout constants cho các hành động khác nhau
IMAGE_GEN_READ_SEC = 1200.0
VIDEO_CREATE_READ_SEC = 180.0
VIDEO_POLL_READ_SEC = 60.0
VIDEO_FETCH_READ_SEC = 30.0


def upstream_timeout(read_sec: float, *, connect: float = 30.0) -> httpx.Timeout:
    """Upstream HTTP timeout: connect short, read long, to avoid ReadTimeout misidentification."""
    return httpx.Timeout(connect=connect, read=float(read_sec), write=60.0, pool=30.0)


def reraise_upstream_timeout(exc: BaseException, *, kind: str, read_sec: float) -> NoReturn:
    """Convert httpx timeout to readable RuntimeError; ReadTimeout means connected but timeout on result."""
    if isinstance(exc, httpx.ReadTimeout):
        raise RuntimeError(
            f"{kind}等待上游超时（ReadTimeout）：已连通上游，但 {read_sec:.0f} 秒内未返回结果，请稍后重试"
        ) from exc
    if isinstance(exc, httpx.WriteTimeout):
        raise RuntimeError(
            f"{kind}发送请求超时（WriteTimeout）：已连通上游，但 {read_sec:.0f} 秒内未能发完请求，请稍后重试"
        ) from exc
    name = type(exc).__name__
    # Connect/Pool timeout: request chưa tới upstream → đánh dấu tạm thời để gateway failover
    raise TransientUpstreamError(
        f"{kind}无法连接上游（{name}）：请检查网络、代理或上游是否可达"
    ) from exc


def is_transient_http_status(status_code: int) -> bool:
    """Check if HTTP status is transient (429 rate limit or 5xx gateway/upstream error)."""
    return status_code == 429 or status_code >= 500


def retry_after_seconds(resp: httpx.Response, default: float) -> float:
    """Respect Retry-After header (delta-seconds); missing or HTTP-date form uses default, max 60s."""
    raw = resp.headers.get("Retry-After")
    if raw:
        try:
            return max(0.0, min(60.0, float(raw.strip())))
        except ValueError:
            pass
    return default


class ProviderNotSupported(RuntimeError):
    """Provider/protocol không được hỗ trợ hoặc không có năng lực này."""


class TransientUpstreamError(RuntimeError):
    """Lỗi tạm thời lúc tạo tác vụ (429/5xx/mạng) — được phép failover sang model kế tiếp."""


# Lỗi mạng xảy ra trước khi request tới upstream: failover không sợ tạo trùng tác vụ bị tính tiền.
# ReadError/RemoteProtocolError/WriteError có thể xảy ra sau khi upstream đã nhận request → không failover.
PRE_SEND_ERRORS: tuple[type[BaseException], ...] = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def is_failover_safe_error(exc: BaseException) -> bool:
    """Lỗi tạm thời được phép chuyển model kế tiếp: 429/5xx đã đánh dấu, hoặc lỗi mạng trước khi gửi."""
    return isinstance(exc, (TransientUpstreamError, *PRE_SEND_ERRORS))


@dataclass
class TaskResult:
    """Result từ fetch_video hoặc create_video status query."""
    status: str  # pending | running | succeeded | failed
    url: str | None = None
    last_frame_url: str | None = None
    error: str | None = None
    total_tokens: int = 0
    completion_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    provider_task_id: str | None = None
    upstream_cost_fen: int | None = None
    channel_id: str = ""
    model: str = ""  # model upstream báo trong payload tác vụ (route poll không biết model)


@dataclass
class ImageRequest:
    """Request để gen_image."""
    prompt: str
    size: str = ""
    aspect_ratio: str = ""
    refs: list[str] = field(default_factory=list)
    style_refs: list[str] = field(default_factory=list)
    output_format: str = "png"


@dataclass
class ImageOutput:
    """Output từ gen_image."""
    url: str | None = None
    data: bytes | None = None
    size: str = ""
    raw_usage: dict[str, Any] | None = None
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class VideoRequest:
    """Request để create_video."""
    body: dict[str, Any]
    plain_text: str | None = None
    target_ratio: str | None = None
    allow_structure_fallback: bool = False
    content_labels: list[str] | None = None


@dataclass
class TtsRequest:
    """Request để tts."""
    text: str
    voice: str
    emotion_hint: str | None = None


class ProviderAdapter(Protocol):
    """Hợp đồng một provider: mỗi protocol một file, facade chỉ gọi qua đây."""

    protocol: str

    async def list_models(self, route: ResolvedModelRoute, capability: str = "all") -> list[dict[str, str]]:
        """Danh sách model khả dụng cho capability này."""
        ...

    async def gen_image(self, route: ResolvedModelRoute, req: ImageRequest) -> ImageOutput:
        """Generate ảnh từ prompt."""
        ...

    async def create_video(self, route: ResolvedModelRoute, req: VideoRequest) -> str:
        """Create video task, return task_id."""
        ...

    async def fetch_video(self, route: ResolvedModelRoute, task_id: str) -> TaskResult:
        """Query video task status."""
        ...

    async def tts(self, route: ResolvedModelRoute, req: TtsRequest) -> bytes:
        """Text to speech, return audio bytes."""
        ...

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Calculate cost in fen (cents); None means no cost estimation."""
        ...

    def url_needs_auth(self, url: str) -> bool:
        """Whether URL needs Bearer auth when fetching."""
        ...

    def is_transient_error(self, exc: BaseException) -> bool:
        """Check if error is transient (can failover to next model)."""
        ...


def bearer_headers(api_key: str) -> dict[str, str]:
    """Header Bearer + JSON dùng chung cho OpenAI/Ark."""
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def join_url(base_url: str, path: str) -> str:
    """Ghép base + path, tránh `//`."""
    return f"{(base_url or '').rstrip('/')}/{(path or '').lstrip('/')}"
