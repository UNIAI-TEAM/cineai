"""VolcTtsAdapter: header theo kiểu key, body openspeech, NDJSON → bytes."""
from __future__ import annotations

import base64
import json

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import base, volc_tts_adapter
from app.services.providers.volc_tts_adapter import VolcTtsAdapter


def _route(api_key="vk", base_url=""):
    return ResolvedModelRoute(capability="audio", logical_model_id="kepu.tts", upstream_model="seed-tts-2.0",
                              channel_id="volc", channel_name="Volc", base_url=base_url, api_key=api_key,
                              protocol="volc_tts", api_format="openai")


def _ndjson(chunks):
    lines = [json.dumps({"code": 0, "data": base64.b64encode(c).decode()}) for c in chunks]
    lines.append(json.dumps({"code": 20000000}))
    return ("\n".join(lines)).encode()


class _Recorder:
    def __init__(self, resp): self.resp = resp; self.calls = []
    def client(self):
        rec = self
        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append((url, headers, json)); return rec.resp
        return _C


def test_parse_ndjson_concatenates():
    assert volc_tts_adapter.parse_openspeech_ndjson(_ndjson([b"ab", b"cd"])) == b"abcd"


def test_speaker_alias_and_resource():
    assert volc_tts_adapter.resolve_volc_speaker("narrator_calm", "x") == "zh_female_cancan_uranus_bigtts"
    assert volc_tts_adapter.resolve_volc_speaker("", "zh_x") == "zh_x"
    assert volc_tts_adapter.resource_id_for_speaker("S_abc", "seed-tts-2.0") == "seed-icl-2.0"
    assert volc_tts_adapter.resource_id_for_speaker("zh_female_cancan_uranus_bigtts", "seed-tts-2.0") == "seed-tts-2.0"


async def test_tts_uses_api_key_header_and_default_url(monkeypatch):
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\xff" * 1500])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    audio = await VolcTtsAdapter().tts(_route(), base.TtsRequest(text="xin chào", voice="narrator_calm", emotion_hint="ấm áp"))
    url, headers, body = rec.calls[0]
    assert url == volc_tts_adapter.VOLC_TTS_DEFAULT_URL
    assert headers["X-Api-Key"] == "vk" and headers["X-Api-Resource-Id"] == "seed-tts-2.0"
    assert body["req_params"]["speaker"] == "zh_female_cancan_uranus_bigtts"
    assert body["req_params"]["audio_params"] == {"format": "mp3", "sample_rate": 24000}
    assert "additions" in body["req_params"]
    assert len(audio) == 1500


async def test_tts_legacy_app_id_headers(monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "volc_tts_app_id", "app"); monkeypatch.setattr(s, "volc_tts_access_key", "ak")
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\x00" * 1200])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    await VolcTtsAdapter().tts(_route(api_key=""), base.TtsRequest(text="a", voice="v"))
    _, headers, _ = rec.calls[0]
    assert headers["X-Api-App-Id"] == "app" and headers["X-Api-Access-Key"] == "ak" and "X-Api-Key" not in headers
