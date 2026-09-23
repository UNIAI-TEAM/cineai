"""Lỗi job phim ngắn hiện cho người dùng: câu ngắn, không lộ request id / JSON thô của nhà cung cấp."""
import httpx

from app.errors import AppError
from app.services.drama.job_errors import user_job_error
from app.services.llm_client import LlmUnavailableError

_RAW_401 = (
    'LLM error 401: {"error":{"code":"AuthenticationError","message":"The API key format is incorrect. '
    'Request id: 021790123456789abcdef","param":"","type":"Unauthorized"}}'
)


def test_upstream_auth_error_is_short_without_request_id():
    msg = user_job_error(RuntimeError(_RAW_401))
    assert msg == "Nhà cung cấp mô hình từ chối API key, hãy liên hệ với chúng tôi"
    assert "Request id" not in msg and "0217901" not in msg and "{" not in msg


def test_upstream_rate_limit_and_server_errors():
    assert user_job_error(RuntimeError("LLM error 429: too many")) == (
        "Nhà cung cấp mô hình đang quá tải, vui lòng thử lại sau"
    )
    assert user_job_error(RuntimeError('LLM error 502: {"x":1}')) == (
        "Nhà cung cấp mô hình đang gặp sự cố, vui lòng thử lại sau"
    )


def test_network_error_is_short():
    msg = user_job_error(httpx.ConnectError("boom"))
    assert msg == "Không kết nối được nhà cung cấp mô hình, vui lòng thử lại sau"


def test_user_facing_errors_are_kept():
    unavailable = LlmUnavailableError("Chưa gán model văn bản. Vào Admin → Cài đặt → Mô hình để cấu hình.")
    assert user_job_error(unavailable) == str(unavailable)
    app_err = AppError("model.slot_not_configured")
    assert user_job_error(app_err) == str(app_err)


def test_other_errors_drop_request_id_and_are_capped():
    msg = user_job_error(RuntimeError("分集生成无进度 request_id=abc-123 " + "x" * 400))
    assert "abc-123" not in msg and "request_id" not in msg
    assert msg.startswith("分集生成无进度") and len(msg) <= 200
