"""Chặn dùng lại API key đã lưu khi admin đổi sang host khác (tránh gửi key tới máy chủ lạ)."""
from __future__ import annotations

from urllib.parse import urlsplit

# Thông báo 400 cho admin khi đổi host mà không nhập lại key
HOST_CHANGED_MESSAGE = "Đổi địa chỉ máy chủ thì phải nhập lại API key"

_DEFAULT_PORTS = {"http": 80, "https": 443}


class ProviderHostChangedError(ValueError):
    """Base URL gửi lên khác host đã lưu mà không kèm key mới."""

    def __init__(self) -> None:
        """Luôn mang thông báo tiếng Việt chuẩn cho admin."""
        super().__init__(HOST_CHANGED_MESSAGE)


def _origin(url: str) -> tuple[str, str, int | None]:
    """Chuẩn hoá (scheme, host, port) của URL; port mặc định theo scheme."""
    parts = urlsplit((url or "").strip())
    scheme = (parts.scheme or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    return scheme, (parts.hostname or "").lower(), port or _DEFAULT_PORTS.get(scheme)


def same_host(a: str, b: str) -> bool:
    """Hai URL có cùng scheme + host + port không."""
    return _origin(a) == _origin(b)
