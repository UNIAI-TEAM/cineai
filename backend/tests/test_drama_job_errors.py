"""Lỗi job phim ngắn: lưu kèm mã lỗi (frontend dịch theo ngôn ngữ), không lộ request id / JSON thô của nhà cung cấp."""
from types import SimpleNamespace

import httpx

from app.errors import AppError
from app.services.drama.generation import (
    build_failed_generation_params,
    overlay_fragment_status_with_active_task,
)
from app.services.drama.job_errors import (
    clear_job_error,
    gen_error_fields,
    gen_progress,
    set_job_error,
    set_job_error_code,
    user_job_error,
)
from app.services.llm_client import LlmUnavailableError

_RAW_401 = (
    'LLM error 401: {"error":{"code":"AuthenticationError","message":"The API key format is incorrect. '
    'Request id: 021790123456789abcdef","param":"","type":"Unauthorized"}}'
)


def test_upstream_auth_error_has_code_and_no_request_id():
    text, code, params = user_job_error(RuntimeError(_RAW_401))
    assert code == "drama.upstream_auth"
    assert params is None
    assert "Request id" not in text and "0217901" not in text and "{" not in text


def test_upstream_rate_limit_and_server_errors():
    assert user_job_error(RuntimeError("LLM error 429: too many"))[1] == "drama.upstream_rate_limit"
    assert user_job_error(RuntimeError('LLM error 502: {"x":1}'))[1] == "drama.upstream_server"
    assert user_job_error(RuntimeError("LLM error 400: bad"))[1] == "drama.upstream_rejected"


def test_network_error_has_code():
    assert user_job_error(httpx.ConnectError("boom"))[1] == "drama.upstream_network"
    assert user_job_error(httpx.ReadTimeout("slow"))[1] == "drama.upstream_network"


def test_app_error_and_unavailable_keep_meaning():
    unavailable = LlmUnavailableError("Chưa gán model văn bản.")
    assert user_job_error(unavailable)[1] == "model.slot_not_configured"
    app_err = AppError("drama.episode_gen_incomplete", done=3, total=10)
    text, code, params = user_job_error(app_err)
    assert (text, code, params) == (str(app_err), "drama.episode_gen_incomplete", {"done": 3, "total": 10})


def test_other_errors_fall_back_to_generic_code():
    text, code, _ = user_job_error(RuntimeError("分集生成无进度 request_id=abc-123 " + "x" * 400))
    assert code == "drama.gen_failed"
    assert "abc-123" not in text and len(text) <= 200


def test_set_and_clear_job_error_fields():
    params: dict = {}
    text = set_job_error(params, "summary_error", AppError("drama.creative_too_short", min=10))
    assert params["summary_error"] == text
    assert params["summary_error_code"] == "drama.creative_too_short"
    assert params["summary_error_params"] == {"min": 10}
    # 无参数的新错误会清掉旧 params
    set_job_error(params, "summary_error", RuntimeError("LLM error 429"))
    assert params["summary_error_code"] == "drama.upstream_rate_limit"
    assert "summary_error_params" not in params
    clear_job_error(params, "summary_error", keep_key=True)
    assert params == {"summary_error": None}
    set_job_error_code(params, "fragment_plan_error", "drama.episode_body_empty")
    assert params["fragment_plan_error_code"] == "drama.episode_body_empty"
    assert params["fragment_plan_error"]
    clear_job_error(params, "fragment_plan_error")
    assert "fragment_plan_error" not in params and "fragment_plan_error_code" not in params


def test_gen_error_fields_only_classifies_known_errors():
    assert gen_error_fields(httpx.ReadTimeout("x")) == ("drama.gen_timeout", None)
    assert gen_error_fields(httpx.ConnectError("x")) == ("drama.gen_network", None)
    assert gen_error_fields(AppError("drama.gen_no_image_url")) == ("drama.gen_no_image_url", None)
    # 其余交给前端按原文细分（审核、音频过短等）
    assert gen_error_fields(RuntimeError("Seedance create error 400 PrivacyInformation")) == (None, None)


def test_failed_generation_params_carry_error_code():
    gen = build_failed_generation_params(None, "上一镜失败", error_code="drama.prev_shot_failed")
    assert gen["error_code"] == "drama.prev_shot_failed"
    assert "error_params" not in gen
    plain = build_failed_generation_params(None, "Seedance create error 400")
    assert "error_code" not in plain


def test_gen_progress_has_message_key_and_params():
    out = gen_progress("generatingRefsItem", "正在生成参考图 1/2：阿明", done=1, total=2, name="阿明")
    assert out == {
        "message": "正在生成参考图 1/2：阿明",
        "message_key": "generatingRefsItem",
        "message_params": {"done": 1, "total": 2, "name": "阿明"},
    }
    assert "message_params" not in gen_progress("queued", "已入队")


def test_status_overlay_adds_message_key_only_when_missing():
    running = overlay_fragment_status_with_active_task({"status": "queued"}, "awaiting_poll")
    assert running["status"] == "running"
    assert running["message_key"] == "upstreamRunning"
    queued = overlay_fragment_status_with_active_task({"status": "queued"}, "pending")
    assert queued["message_key"] == "queued"
    kept = overlay_fragment_status_with_active_task(
        {"status": "running", **gen_progress("refsReady", "参考图已就绪，开始生成视频")}, "running"
    )
    assert kept["message_key"] == "refsReady"


def test_fragment_generation_status_passes_message_key():
    from app.services.drama.generation import fragment_generation_status

    frag = SimpleNamespace(
        params={"generation": {"status": "queued", **gen_progress("queued", "已入队")}},
        video=None,
        cover=None,
    )
    out = fragment_generation_status(frag)
    assert out["message_key"] == "queued"
    failed = SimpleNamespace(
        params={"generation": {"status": "failed", "error": "x", "error_code": "drama.gen_timeout"}},
        video=None,
        cover=None,
    )
    assert fragment_generation_status(failed)["error_code"] == "drama.gen_timeout"
