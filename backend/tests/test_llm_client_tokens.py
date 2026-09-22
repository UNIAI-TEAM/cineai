"""llm_client: OpenAI chính thức dùng max_completion_tokens; provider khác dùng max_tokens; route theo function."""
import httpx
import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import llm_client
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot


def _snap(base_url):
    """Gán slot văn bản về một provider có base_url cho trước."""
    ch = SystemModelChannel(id="c", name="c", base_url=base_url, api_key="k", has_api_key=True, protocol="openai", models=["m"], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"text": [ModelBinding(channel_id="c", model="m")]}))


class _Rec:
    """Ghi lại body JSON mà llm_client gửi lên upstream."""

    def __init__(self):
        self.body = None

    def client(self):
        """Trả về lớp AsyncClient giả ghi body và luôn đáp 200."""
        rec = self

        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.body = json
                return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        return _C


@pytest.mark.parametrize("base,key", [("https://api.openai.com/v1", "max_completion_tokens"), ("https://ark.ap-southeast.bytepluses.com/api/v3", "max_tokens")])
async def test_token_param_by_host(monkeypatch, base, key):
    prev = get_routing_snapshot(); _snap(base)
    try:
        rec = _Rec(); monkeypatch.setattr(llm_client.httpx, "AsyncClient", rec.client())
        assert await llm_client.chat_completions("s", "u", function_id="kepu.script", max_tokens=100) == "ok"
        assert rec.body[key] == 100 and ("max_tokens" in rec.body) != ("max_completion_tokens" in rec.body)
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_unconfigured_text_slot_raises(monkeypatch):
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        with pytest.raises(llm_client.LlmUnavailableError):
            await llm_client.chat_completions("s", "u", function_id="drama.script")
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
