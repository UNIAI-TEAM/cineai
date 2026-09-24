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
    # route.base_url rỗng → rơi về settings.volc_tts_url (mặc định BytePlus Seed Speech, không phải openspeech cũ)
    assert url == volc_tts_adapter.BYTEPLUS_TTS_URL
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


async def test_tts_legacy_credentials_not_sent_to_foreign_host(monkeypatch):
    """Provider không có key + base URL lạ → không gửi cặp app-id/access-key toàn cục."""
    import pytest
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "volc_tts_app_id", "app"); monkeypatch.setattr(s, "volc_tts_access_key", "ak")
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\x00" * 1200])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(base.UpstreamError):
        await VolcTtsAdapter().tts(_route(api_key="", base_url="https://evil.example/tts"), base.TtsRequest(text="a", voice="v"))
    assert rec.calls == []


def test_additions_explicit_language_for_vietnamese():
    raw = volc_tts_adapter.build_tts_additions("vi_female_ruan_uranus_bigtts", "vui vẻ", lang="vi")
    data = json.loads(raw)
    assert data["explicit_language"] == "vi"
    assert data["context_texts"] == ["Hãy đọc với giọng vui vẻ"]


def test_additions_lang_inferred_from_speaker_prefix():
    data = json.loads(volc_tts_adapter.build_tts_additions("vi_male_wumg_uranus_bigtts", None))
    assert data == {"explicit_language": "vi"}


def test_additions_chinese_unchanged():
    data = json.loads(volc_tts_adapter.build_tts_additions("zh_female_vv_uranus_bigtts", "清亮少女音"))
    assert "explicit_language" not in data
    assert data["context_texts"] == ["用「清亮少女音」的语气朗读"]


def test_split_tts_text_packs_sentences_under_limit():
    text = "Câu một. Câu hai dài hơn chút! Câu ba?"
    assert volc_tts_adapter.split_tts_text(text, max_chars=21) == ["Câu một.", "Câu hai dài hơn chút!", "Câu ba?"]
    assert volc_tts_adapter.split_tts_text("ngắn", max_chars=20) == ["ngắn"]


def test_split_tts_text_hard_splits_overlong_sentence_on_spaces():
    parts = volc_tts_adapter.split_tts_text("a " * 30, max_chars=10)
    assert all(len(p) <= 10 for p in parts) and "".join(parts).replace(" ", "") == "a" * 30


def test_parse_ndjson_raises_on_error_code():
    import pytest
    raw = json.dumps({"code": 45000000, "message": "speaker permission denied"}).encode()
    with pytest.raises(volc_tts_adapter.OpenspeechError) as ei:
        volc_tts_adapter.parse_openspeech_ndjson(raw)
    assert ei.value.code == 45000000


def test_transient_error_classification():
    a = VolcTtsAdapter()
    assert a.is_transient_error(volc_tts_adapter.OpenspeechError("x", code=55000000))
    assert a.is_transient_error(volc_tts_adapter.OpenspeechError("quota exceeded for types: concurrency", code=None))
    assert a.is_transient_error(volc_tts_adapter.OpenspeechError("HTTP 503", status=503))
    assert not a.is_transient_error(volc_tts_adapter.OpenspeechError("denied", code=45000000))


async def test_tts_sends_app_key_speech_rate_and_chunks(monkeypatch):
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\xff" * 1100])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    monkeypatch.setattr(volc_tts_adapter, "MAX_TTS_CHUNK_CHARS", 20)
    req = base.TtsRequest(text="Xin chào bạn. Hôm nay trời đẹp.", voice="vi_female_ruan_uranus_bigtts",
                          lang="vi", speech_rate=20)
    audio = await VolcTtsAdapter().tts(_route(), req)
    assert len(rec.calls) == 2 and len(audio) == 2200
    _, headers, body = rec.calls[0]
    assert headers["X-Api-App-Key"] == "aGjiRDfUWi"
    assert body["req_params"]["audio_params"]["speech_rate"] == 20
    assert json.loads(body["req_params"]["additions"])["explicit_language"] == "vi"
