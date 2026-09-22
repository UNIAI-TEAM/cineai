"""OpenAIAdapter: map size/quality, generations vs edits, base64, TTS, /models."""
from __future__ import annotations

import base64

import httpx
import pytest

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import base, openai_adapter
from app.services.providers.openai_adapter import OpenAIAdapter, openai_image_size, openai_voice_for_speaker


def _route(model="gpt-image-2.5-sunburst", capability="image", base_url="https://api.openai.com/v1"):
    return ResolvedModelRoute(capability=capability, logical_model_id="tools.image", upstream_model=model,
                              channel_id="openai", channel_name="OpenAI", base_url=base_url, api_key="sk",
                              protocol="openai", api_format="openai")


class _Recorder:
    def __init__(self, script):
        self.script = list(script); self.calls = []
    def client(self):
        rec = self
        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append(("POST", url, json)); return rec.script.pop(0)
            async def get(self, url, headers=None):
                rec.calls.append(("GET", url, None)); return rec.script.pop(0)
        return _C


@pytest.mark.parametrize("size,ratio,model,expect", [
    ("1K", "", "gpt-image-1", ("1024x1024", "low")),
    ("2K", "9:16", "gpt-image-1", ("1024x1536", "medium")),
    ("2K", "16:9", "gpt-image-1", ("1536x1024", "medium")),
    ("4K", "1:1", "gpt-image-1", ("1024x1024", "high")),
    ("2816x1584", "", "gpt-image-2.5-sunburst", ("2816x1584", "medium")),   # 2.x: WxH giữ, chia hết 16
    ("2816x1584", "", "gpt-image-1", ("1536x1024", "medium")),              # 1.x: WxH không hỗ trợ → tier
    ("5000x1000", "", "gpt-image-2", ("3840x1280", "medium")),              # kẹp cạnh dài 3840, tỉ lệ ≤ 3:1
])
def test_openai_image_size(size, ratio, model, expect):
    assert openai_image_size(size, ratio, model) == expect


def test_voice_map():
    assert openai_voice_for_speaker("zh_female_cancan_uranus_bigtts") == "marin"
    assert openai_voice_for_speaker("zh_male_shaonianzixin_uranus_bigtts") == "cedar"
    assert openai_voice_for_speaker("") == "alloy"


async def test_gen_image_without_refs_uses_generations(monkeypatch):
    png = base64.b64encode(b"\x89PNG-fake").decode()
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": png}], "usage": {"input_tokens": 10, "output_tokens": 1000, "total_tokens": 1010}})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    out = await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="mèo", size="2K", aspect_ratio="9:16"))
    _, url, body = rec.calls[0]
    assert url.endswith("/images/generations")
    assert body == {"model": "gpt-image-2.5-sunburst", "prompt": "mèo", "n": 1, "size": "1024x1536", "quality": "medium", "output_format": "png"}
    assert out.data == b"\x89PNG-fake" and out.url is None
    assert out.total_tokens == 1010 and out.completion_tokens == 1000 and out.prompt_tokens == 10
    assert out.raw_usage["output_tokens"] == 1000


async def test_gen_image_with_refs_uses_edits(monkeypatch):
    png = base64.b64encode(b"x").decode()
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": png}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p", size="1K", refs=["https://a/1.png"], style_refs=["data:image/png;base64,AAA"]))
    _, url, body = rec.calls[0]
    assert url.endswith("/images/edits")
    assert body["images"] == [{"image_url": "https://a/1.png"}, {"image_url": "data:image/png;base64,AAA"}]
    assert "n" in body and body["size"] == "1024x1024"


async def test_gen_image_caps_refs_at_16(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"x").decode()}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p", refs=[f"https://a/{i}.png" for i in range(20)]))
    assert len(rec.calls[0][2]["images"]) == 16


async def test_gen_image_http_error_readable(monkeypatch):
    rec = _Recorder([httpx.Response(400, json={"error": {"message": "safety system rejected"}})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError) as exc:
        await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p"))
    assert "safety system rejected" in str(exc.value)


async def test_gen_image_transient(monkeypatch):
    rec = _Recorder([httpx.Response(429, json={})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(base.TransientUpstreamError):
        await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p"))


async def test_tts_body(monkeypatch):
    rec = _Recorder([httpx.Response(200, content=b"ID3" + b"\x00" * 2000)])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    audio = await OpenAIAdapter().tts(_route("gpt-4o-mini-tts", "audio"), base.TtsRequest(text="xin chào", voice="zh_female_cancan_uranus_bigtts", emotion_hint="vui vẻ"))
    _, url, body = rec.calls[0]
    assert url.endswith("/audio/speech")
    assert body["model"] == "gpt-4o-mini-tts" and body["voice"] == "marin" and body["response_format"] == "mp3"
    assert body["instructions"] == "vui vẻ"
    assert audio.startswith(b"ID3")


async def test_tts_no_instructions_for_tts1(monkeypatch):
    rec = _Recorder([httpx.Response(200, content=b"\xff\xfb" + b"\x00" * 2000)])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().tts(_route("tts-1", "audio"), base.TtsRequest(text="a", voice="v", emotion_hint="x"))
    assert "instructions" not in rec.calls[0][2]


async def test_list_models_infers_capability(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"id": "gpt-5.6-sol"}, {"id": "gpt-image-2"}, {"id": "gpt-4o-mini-tts"}, {"id": "sora-2"}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    out = await OpenAIAdapter().list_models(_route(), "all")
    caps = {m["id"]: m["capability"] for m in out}
    assert caps["gpt-5.6-sol"] == "text" and caps["gpt-image-2"] == "image" and caps["gpt-4o-mini-tts"] == "audio"
    assert "sora-2" not in caps                      # video OpenAI bị loại (đã gỡ 2026-09-24)


async def test_create_video_not_supported():
    with pytest.raises(base.ProviderNotSupported):
        await OpenAIAdapter().create_video(_route(), base.VideoRequest(body={}))


def test_infer_model_capability_recognizes_sora_as_video():
    from app.services.model_routing_config import infer_model_capability

    assert infer_model_capability("sora-2") == "video"
    assert infer_model_capability("sora-2-pro") == "video"
