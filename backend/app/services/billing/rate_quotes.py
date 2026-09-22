# backend/app/services/billing/rate_quotes.py
"""Đơn giá ước tính theo chức năng: model hiệu lực của slot × provider_rates, lấy mức đắt nhất (chưa buffer)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from app.config import get_settings
from app.services.billing.money import usd_to_fen
from app.services.billing.pricing import charge_fen_for_tokens
from app.services.billing.provider_rates import EST_IMAGE_OUTPUT_TOKENS, match_rate, rate_cost_usd

VIDEO_FPS = 24
# Diện tích khung 16:9 theo độ phân giải Seedance (tỉ lệ khác có diện tích xấp xỉ, đủ cho ước tính).
# Công thức token = ceil(giây × rộng × cao × fps / 1024): BytePlus Seedance pricing docs (chưa xác minh URL).
VIDEO_PIXELS: dict[str, int] = {"480p": 864 * 480, "720p": 1280 * 720, "1080p": 1920 * 1080}
_CAP_LABEL_FIELD = {"text": "model_llm", "image": "model_image", "video": "model_video", "audio": "model_audio"}


def _snapshot(snapshot: Any | None) -> Any:
    """Snapshot truyền vào, hoặc snapshot routing hiện hành."""
    if snapshot is not None:
        return snapshot
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def function_models(function_id: str, *, settings: Any | None = None, snapshot: Any | None = None) -> list[str]:
    """Model hiệu lực (đã loại provider tắt/thiếu key) của chức năng; slot chưa gán → nhãn settings.model_*."""
    from app.services.function_router import allowed_bindings
    from app.services.functions import function_capability

    s = settings or get_settings()
    models = list(dict.fromkeys(b.model for b in allowed_bindings(function_id, snapshot=_snapshot(snapshot))))
    if models:
        return models
    label = str(getattr(s, _CAP_LABEL_FIELD[function_capability(function_id)], "") or "").strip()
    return [label] if label else []


def _rate_fen(model: str, fallback_tokens: int, settings: Any) -> int | None:
    """Giá fen theo provider_rates với số lượng ước tính; model không có giá → None."""
    rate = match_rate(model)
    if rate is None:
        return None
    usd = rate_cost_usd(rate, {}, fallback_tokens=fallback_tokens)
    return usd_to_fen(usd, settings) if usd else None


def _max_fen(models: list[str], price: Callable[[str], int]) -> int:
    """Giá cao nhất trong danh sách model (rỗng → giá của model rỗng = dự phòng), tối thiểu 1 fen."""
    return max(1, max((price(m) for m in models), default=price("")))


def normalize_video_resolution(resolution: str | None, settings: Any) -> str:
    """Chỉ nhận 480p/720p/1080p; giá trị lạ → ark_video_resolution → 480p."""
    raw = (resolution or "").strip().lower()
    if raw in VIDEO_PIXELS:
        return raw
    fallback = str(getattr(settings, "ark_video_resolution", "") or "480p").strip().lower()
    return fallback if fallback in VIDEO_PIXELS else "480p"


def video_tokens(seconds: float, resolution: str) -> int:
    """Token Seedance ước tính: ceil(max(giây, 2) × rộng × cao × 24 / 1024)."""
    secs = max(float(seconds or 0), 2.0)
    return int(math.ceil(secs * VIDEO_PIXELS[resolution] * VIDEO_FPS / 1024))


def _token_price(model: str, tokens: int, billing_key: str, settings: Any) -> int:
    """Giá fen cho `tokens` theo provider_rates, không có giá → đơn giá token dự phòng của billing_key."""
    hit = _rate_fen(model, tokens, settings)
    if hit is not None:
        return hit
    cost, _ = charge_fen_for_tokens(tokens, billing_key, settings=settings)
    return cost


def image_fallback_fen(model: str, settings: Any) -> int:
    """Giá 1 ảnh khi không có usage thật: tra provider_rates với trần EST_IMAGE_OUTPUT_TOKENS, không có giá thì
    dùng token dự phòng seedream (billing_est_seedream_tokens). Task 6 gọi lại đúng hàm này khi quyết toán,
    để đóng băng và quyết toán không bao giờ lệch nhau trên model ảnh chưa có giá.
    """
    hit = _rate_fen(model, EST_IMAGE_OUTPUT_TOKENS, settings)
    if hit is not None:
        return hit
    cost, _ = charge_fen_for_tokens(int(settings.billing_est_seedream_tokens), "seedream", settings=settings)
    return cost


def image_unit_fen(function_id: str, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá một ảnh (đắt nhất trong slot); model tính theo token dùng trần EST_IMAGE_OUTPUT_TOKENS."""
    s = settings or get_settings()
    return _max_fen(
        function_models(function_id, settings=s, snapshot=snapshot),
        lambda m: image_fallback_fen(m, s),
    )


def video_fen(
    function_id: str,
    seconds: float,
    *,
    resolution: str = "",
    settings: Any | None = None,
    snapshot: Any | None = None,
) -> int:
    """Giá một video: token theo thời lượng × độ phân giải × giá/M của model đắt nhất trong slot."""
    s = settings or get_settings()
    tokens = video_tokens(seconds, normalize_video_resolution(resolution, s))
    return _max_fen(
        function_models(function_id, settings=s, snapshot=snapshot),
        lambda m: _token_price(m, tokens, "seedance2:video0", s),
    )


def text_fen(function_id: str, tokens: int, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá LLM cho số token ước tính (tách 70/30 vào/ra) theo model đắt nhất của chức năng văn bản."""
    s = settings or get_settings()
    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot),
                    lambda m: _token_price(m, int(tokens), "llm_chat", s))


def tts_fen(function_id: str, tokens: int, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá giọng đọc cho số token/ký tự ước tính theo model đắt nhất của chức năng giọng đọc."""
    s = settings or get_settings()
    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot),
                    lambda m: _token_price(m, int(tokens), "tts", s))
