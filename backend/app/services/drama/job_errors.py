"""Câu lỗi ngắn cho job phim ngắn hiện ra giao diện: không lộ request id, JSON thô hay stack của nhà cung cấp.

Lỗi đầy đủ vẫn ghi log phía server (logger.exception ở nơi gọi).
"""

from __future__ import annotations

import re

from app.errors import AppError
from app.services.exc_format import (
    _CONNECT_EXC_NAMES,
    _READ_TIMEOUT_EXC_NAMES,
    _WRITE_TIMEOUT_EXC_NAMES,
)
from app.services.llm_client import LlmUnavailableError

# USER_ERROR_LIMIT: độ dài tối đa câu lỗi lưu cho người dùng
USER_ERROR_LIMIT = 200

_MSG_AUTH = "Nhà cung cấp mô hình từ chối API key, hãy liên hệ với chúng tôi"
_MSG_RATE_LIMIT = "Nhà cung cấp mô hình đang quá tải, vui lòng thử lại sau"
_MSG_SERVER = "Nhà cung cấp mô hình đang gặp sự cố, vui lòng thử lại sau"
_MSG_REJECTED = "Nhà cung cấp mô hình từ chối yêu cầu, vui lòng thử lại sau"
_MSG_NETWORK = "Không kết nối được nhà cung cấp mô hình, vui lòng thử lại sau"

# "LLM error 401: {...}" (llm_client) và các dạng "HTTP 401" / "status 401"
_STATUS_RE = re.compile(r"(?:LLM error|HTTP|status(?:_code)?)[\s:=]*([1-5]\d\d)\b", re.IGNORECASE)
# "Request id: xxx" / "request_id=xxx" / "x-request-id: xxx"
_REQUEST_ID_RE = re.compile(r"\(?\b(?:x-)?request[\s_-]?id\b[\s:=]*[\w.-]*\)?\.?", re.IGNORECASE)


def _upstream_status(exc: BaseException) -> int | None:
    """Mã HTTP của lỗi nhà cung cấp: thuộc tính status_code / response.status_code, hoặc đọc từ câu lỗi."""
    for obj in (exc, getattr(exc, "response", None)):
        code = getattr(obj, "status_code", None)
        if isinstance(code, int) and 100 <= code <= 599:
            return code
    m = _STATUS_RE.search(str(exc))
    return int(m.group(1)) if m else None


def user_job_error(exc: BaseException) -> str:
    """Đổi exception của job thành câu ngắn cho người dùng.

    - Lỗi nghiệp vụ đã viết cho người dùng (AppError, chưa gán model) giữ nguyên
    - Lỗi HTTP / mạng của nhà cung cấp → câu tiếng Việt theo loại lỗi
    - Còn lại: bỏ request id và phần JSON thô, cắt còn USER_ERROR_LIMIT ký tự
    """
    if isinstance(exc, (AppError, LlmUnavailableError)):
        return str(exc).strip()[:USER_ERROR_LIMIT]
    name = type(exc).__name__
    if name in _CONNECT_EXC_NAMES or name in _READ_TIMEOUT_EXC_NAMES or name in _WRITE_TIMEOUT_EXC_NAMES:
        return _MSG_NETWORK
    status = _upstream_status(exc)
    if status in (401, 403):
        return _MSG_AUTH
    if status == 429:
        return _MSG_RATE_LIMIT
    if status is not None and status >= 500:
        return _MSG_SERVER
    if status is not None and status >= 400:
        return _MSG_REJECTED
    text = str(exc).split("{", 1)[0]
    text = _REQUEST_ID_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" :;,-")
    return (text or "Tạo thất bại, vui lòng thử lại sau")[:USER_ERROR_LIMIT]
