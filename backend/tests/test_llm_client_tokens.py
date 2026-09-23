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


async def test_failover_to_next_model_on_transient_status(monkeypatch):
    """Model đầu trả 503 → thử model kế tiếp; 400 thì dừng luôn, không failover."""
    from types import SimpleNamespace

    a = SimpleNamespace(channel_id="a", api_key="k", upstream_model="m-a", base_url="https://a.example/v1")
    b = SimpleNamespace(channel_id="b", api_key="k", upstream_model="m-b", base_url="https://b.example/v1")
    monkeypatch.setattr(llm_client, "resolve_function_candidates", lambda _fid: [a, b])
    status = {"a": 503}
    calls: list[str] = []

    class _C:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            ch = "a" if "a.example" in url else "b"
            calls.append(ch)
            if ch in status:
                return httpx.Response(status[ch], text="err")
            return httpx.Response(200, json={"choices": [{"message": {"content": json["model"]}}]})

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", _C)
    assert await llm_client.chat_completions("s", "u", function_id="kepu.script") == "m-b"
    assert calls == ["a", "b"]

    status["a"] = 400; calls.clear()
    with pytest.raises(RuntimeError, match="LLM error 400"):
        await llm_client.chat_completions("s", "u", function_id="kepu.script")
    assert calls == ["a"]


@pytest.mark.parametrize("base,model,has_temp", [
    ("https://api.openai.com/v1", "gpt-5-mini", False),
    ("https://api.openai.com/v1", "o4-mini", False),
    ("https://api.openai.com/v1", "gpt-4.1", True),
    ("https://ark.ap-southeast.bytepluses.com/api/v3", "gpt-5-mini", True),
])
async def test_temperature_omitted_for_openai_reasoning_models(monkeypatch, base, model, has_temp):
    prev = get_routing_snapshot()
    ch = SystemModelChannel(id="c", name="c", base_url=base, api_key="k", has_api_key=True, protocol="openai", models=[model], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"text": [ModelBinding(channel_id="c", model=model)]}))
    try:
        rec = _Rec(); monkeypatch.setattr(llm_client.httpx, "AsyncClient", rec.client())
        await llm_client.chat_completions("s", "u", function_id="kepu.script")
        assert ("temperature" in rec.body) is has_temp
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
