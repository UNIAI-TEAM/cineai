# -*- coding: utf-8 -*-
"""Danh sách model khả dụng của một provider: openai → GET /models qua adapter; ark/volc_tts → tĩnh."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas_routing import ResolvedModelRoute
from app.services.providers.registry import get_adapter


async def _resolve_channel_credentials(
    db: AsyncSession | None,
    *,
    channel_id: str | None,
    protocol: str,
    base_url: str,
    api_key_override: str | None,
) -> tuple[str, str, str]:
    """Trả (protocol, base_url, api_key); bù dữ liệu còn thiếu từ kênh đã lưu nếu có channel_id."""
    proto = (protocol or "auto").strip().lower() or "auto"
    base = (base_url or "").strip().rstrip("/")
    key = (api_key_override or "").strip()

    if db is not None and channel_id:
        from app.services.model_settings import _load_channels

        channels = await _load_channels(db, runtime=True)
        channel = next((item for item in channels if item.id == channel_id), None)
        if channel is not None:
            if not key:
                key = (channel.api_key or "").strip()
            if not base:
                base = (channel.base_url or "").strip().rstrip("/")
            if proto in {"", "auto"}:
                proto = (channel.protocol or "auto").strip().lower() or "auto"

    if proto in {"", "auto"}:
        proto = "openai"
    return proto, base, key


def _volc_tts_key_acceptable(key: str) -> bool:
    """volc_tts không bắt buộc `key` nếu đã cấu hình cặp app_id/access_key kiểu cũ."""
    if key:
        return True
    from app.config import get_settings

    settings = get_settings()
    return bool(settings.volc_tts_app_id and settings.volc_tts_access_key)


async def list_upstream_models(
    db: AsyncSession | None = None,
    *,
    channel_id: str | None = None,
    protocol: str = "auto",
    base_url: str = "",
    api_key_override: str | None = None,
    capability: str = "all",
) -> list[dict[str, str]]:
    """Tra danh mục model của một provider (đã lưu theo channel_id, hoặc form đang nhập)."""
    proto, base, key = await _resolve_channel_credentials(
        db,
        channel_id=channel_id,
        protocol=protocol,
        base_url=base_url,
        api_key_override=api_key_override,
    )
    if proto == "openai":
        if not base:
            raise RuntimeError("Cần Base URL")
        if not key:
            raise RuntimeError("Cần API key")
    elif proto == "ark":
        if not key:
            raise RuntimeError("Cần API key")
    elif proto == "volc_tts":
        if not _volc_tts_key_acceptable(key):
            raise RuntimeError("Cần API key")
    route = ResolvedModelRoute(
        capability="text",
        logical_model_id="catalog",
        upstream_model="",
        channel_id=channel_id or "",
        channel_name="",
        base_url=base,
        api_key=key,
        protocol=proto,
        api_format="ark" if proto == "ark" else "openai",
    )
    try:
        return await get_adapter(proto).list_models(route, capability)
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Không kết nối được provider: {type(exc).__name__}: {str(exc)[:200]}") from exc
