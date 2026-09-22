"""ArkAdapter: body ảnh/video đúng shape Ark, retry tạo task, parse GET task."""
from __future__ import annotations

import json

import httpx
import pytest

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import ark_adapter, base
from app.services.providers.ark_adapter import ArkAdapter


def _route(model="dreamina-seedance-2-5-260628", base_url="https://ark.ap-southeast.bytepluses.com/api/v3"):
    return ResolvedModelRoute(
        capability="video", logical_model_id="drama.video", upstream_model=model,
        channel_id="byteplus", channel_name="BytePlus", base_url=base_url,
        api_key="k", protocol="ark", api_format="ark",
    )


class _Recorder:
    """Ghi lại từng POST/GET và trả về câu trả lời theo kịch bản."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[tuple[str, str, dict | None]] = []

    def client(self):
        rec = self

        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append(("POST", url, json))
                return rec.script.pop(0)
            async def get(self, url, headers=None):
                rec.calls.append(("GET", url, None))
                return rec.script.pop(0)
        return _C


async def test_gen_image_body_and_url(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"url": "https://cdn/x.jpg"}], "usage": {"output_tokens": 4096, "total_tokens": 4096, "generated_images": 1}})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    out = await ArkAdapter().gen_image(
        _route("dola-seedream-5-0-pro-260628"),
        base.ImageRequest(prompt="một chú mèo", size="4K", refs=["https://a/1.png"], style_refs=["https://a/s.png"]),
    )
    method, url, body = rec.calls[0]
    assert url.endswith("/images/generations")
    assert body["model"] == "dola-seedream-5-0-pro-260628"
    assert body["size"] == "2K"                      # pro: 4K bị kẹp về 2K
    assert body["image"] == ["https://a/1.png", "https://a/s.png"]
    assert body["watermark"] is False and body["response_format"] == "url"
    assert out.url == "https://cdn/x.jpg"
    assert out.total_tokens == 4096
    assert out.raw_usage["generated_images"] == 1


async def test_gen_image_single_ref_is_scalar(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"url": "https://cdn/x.jpg"}]})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    await ArkAdapter().gen_image(_route("seedream-4-5-251128"), base.ImageRequest(prompt="p", size="2K", refs=["https://a/1.png"]))
    assert rec.calls[0][2]["image"] == "https://a/1.png"


async def test_gen_image_text_sensitive_raises_readable(monkeypatch):
    rec = _Recorder([httpx.Response(400, text='{"error":{"code":"InputTextSensitiveContentDetected"}}')])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError) as exc:
        await ArkAdapter().gen_image(_route("seedream-4-5-251128"), base.ImageRequest(prompt="p"))
    assert "内容审核" in str(exc.value)


async def test_create_video_first_frame_no_ratio(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"id": "cgt-1"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "t"}, {"type": "image_url", "image_url": {"url": "https://a/f.png"}, "role": "first_frame"}], "duration": 8, "resolution": "720p"}
    task_id = await ArkAdapter().create_video(_route(), base.VideoRequest(body=body))
    assert task_id == "cgt-1"
    assert rec.calls[0][1].endswith("/contents/generations/tasks")
    assert rec.calls[0][2]["model"] == "dreamina-seedance-2-5-260628"   # model lấy từ route
    assert "ratio" not in rec.calls[0][2]


async def test_create_video_json_prompt_falls_back_to_plain(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="BodyFormat"), httpx.Response(200, json={"id": "cgt-2"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": '{"summary_caption":"x"}'}, {"type": "image_url", "image_url": {"url": "u"}, "role": "first_frame"}], "duration": 5}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body, plain_text="x thuần", allow_structure_fallback=True))
    assert rec.calls[1][2]["content"][0]["text"] == "x thuần"


async def test_create_video_policy_hit_retries_with_cg(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="InputTextSensitive"), httpx.Response(200, json={"id": "cgt-3"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "cảnh"}], "duration": 5}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body))
    assert ark_adapter.SEEDREAM_CG_STYLE.strip() in rec.calls[1][2]["content"][0]["text"]


async def test_create_video_privacy_error_no_retry(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="InputImageSensitive")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError):
        await ArkAdapter().create_video(_route(), base.VideoRequest(body={"model": "m", "content": [{"type": "text", "text": "x"}]}))
    assert len(rec.calls) == 1


async def test_create_video_structure_fallback_drops_ratio_then_adaptive(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="ratio invalid"), httpx.Response(400, text="ratio invalid"), httpx.Response(200, json={"id": "cgt-4"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "x"}, {"type": "image_url", "image_url": {"url": "u"}, "role": "first_frame"}], "ratio": "9:16"}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body, allow_structure_fallback=True))
    assert "ratio" not in rec.calls[1][2]
    assert rec.calls[2][2]["ratio"] == "adaptive" and "role" not in rec.calls[2][2]["content"][1]


async def test_create_video_transient_5xx_raises_transient(monkeypatch):
    rec = _Recorder([httpx.Response(503, text="busy")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(base.TransientUpstreamError):
        await ArkAdapter().create_video(_route(), base.VideoRequest(body={"model": "m", "content": [{"type": "text", "text": "x"}]}))


async def test_fetch_video_succeeded_parses_ark_shape(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"id": "cgt-1", "status": "succeeded", "content": {"video_url": "https://v/1.mp4", "last_frame_url": "https://v/l.jpg"}, "usage": {"completion_tokens": 123, "total_tokens": 123}})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    out = await ArkAdapter().fetch_video(_route(), "cgt-1")
    assert rec.calls[0][1].endswith("/contents/generations/tasks/cgt-1")
    assert out.status == "succeeded" and out.url == "https://v/1.mp4" and out.last_frame_url == "https://v/l.jpg"
    assert out.completion_tokens == 123 and out.provider_task_id == "cgt-1" and out.channel_id == "byteplus"


@pytest.mark.parametrize("code", [429, 502])
async def test_fetch_video_transient_is_running(monkeypatch, code):
    rec = _Recorder([httpx.Response(code, text="x")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "running"


async def test_fetch_video_404_failed(monkeypatch):
    rec = _Recorder([httpx.Response(404, text="nope")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "failed"


async def test_fetch_video_network_error_is_running(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): raise httpx.ConnectError("x")
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", _Boom)
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "running"


def test_static_models_have_capabilities():
    caps = {m["capability"] for m in ark_adapter.ARK_STATIC_MODELS}
    assert caps == {"text", "image", "video"}
    assert any(m["id"] == "dreamina-seedance-2-5-260628" for m in ark_adapter.ARK_STATIC_MODELS)


async def test_list_models_filters_by_capability():
    out = await ArkAdapter().list_models(_route(), "video")
    assert out and all(m["capability"] == "video" for m in out)


def test_is_ark_host():
    assert ark_adapter.is_ark_host("https://ark.ap-southeast.bytepluses.com/api/v3")
    assert ark_adapter.is_ark_host("https://ark.cn-beijing.volces.com/api/v3")
    assert not ark_adapter.is_ark_host("https://api.openai.com/v1")


async def test_tts_not_supported():
    with pytest.raises(base.ProviderNotSupported):
        await ArkAdapter().tts(_route(), base.TtsRequest(text="a", voice="v"))


def test_i2v_role_rule():
    assert ark_adapter.resolve_seedance_i2v_image_role("9:16") == ("reference_image", "9:16")
    assert ark_adapter.resolve_seedance_i2v_image_role(None) == ("first_frame", None)
