"""providers/base: helper chung + registry theo protocol."""
import httpx
import pytest

from app.services.providers import base, registry


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_status(code):
    assert base.is_transient_http_status(code)


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_terminal_status(code):
    assert not base.is_transient_http_status(code)


def test_retry_after_caps_at_60():
    resp = httpx.Response(429, headers={"Retry-After": "600"})
    assert base.retry_after_seconds(resp, 8.0) == 60.0
    assert base.retry_after_seconds(httpx.Response(429), 8.0) == 8.0


def test_join_url_strips_slashes():
    assert base.join_url("https://x/api/v3/", "/images/generations") == "https://x/api/v3/images/generations"
    assert base.join_url("https://x/api/v3", "images/generations") == "https://x/api/v3/images/generations"


def test_reraise_read_timeout_mentions_upstream():
    with pytest.raises(RuntimeError) as exc:
        base.reraise_upstream_timeout(httpx.ReadTimeout("t"), kind="生图", read_sec=12)
    assert "ReadTimeout" in str(exc.value)
    assert "TokenFree" not in str(exc.value)


def test_registry_unknown_protocol():
    with pytest.raises(base.ProviderNotSupported):
        registry.get_adapter("kie")


def test_registry_auto_is_openai():
    assert registry.get_adapter("auto").protocol == "openai"
    assert registry.get_adapter("").protocol == "openai"
    assert registry.get_adapter("ark").protocol == "ark"
    assert registry.get_adapter("volc_tts").protocol == "volc_tts"
