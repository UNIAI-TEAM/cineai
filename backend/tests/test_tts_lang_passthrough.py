"""TtsService truyền lang / speech_rate vào adapter và ghi file theo out_name."""
from __future__ import annotations

from types import SimpleNamespace

from app.services import tts_service
from app.services.tts_service import TtsService


class _FakeAdapter:
    def __init__(self):
        self.reqs = []

    async def tts(self, route, req):
        self.reqs.append(req)
        return b"ID3" + b"\x00" * 3000


async def test_synthesize_passes_lang_rate_and_out_name(monkeypatch, tmp_path):
    fake = _FakeAdapter()
    route = SimpleNamespace(protocol="volc_tts", channel_id="volc", upstream_model="seed-tts-2.0")
    monkeypatch.setattr(tts_service, "resolve_function_candidates", lambda fid: [route])
    monkeypatch.setattr(tts_service, "get_adapter", lambda protocol: fake)
    monkeypatch.setattr(tts_service.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(tts_service.storage, "publish_local", lambda p: f"/static/x/{p.name}")

    async def _audible(self, dest, label):
        return f"/static/x/{dest.name}"

    monkeypatch.setattr(TtsService, "_accept_if_audible", _audible)
    from app.config import get_settings

    url = await TtsService(get_settings(), mock=False).synthesize(
        "Xin chào", "vi_female_ruan_uranus_bigtts", function_id="drama.tts", project_id=7,
        lang="vi", speech_rate=15, out_name="dub_f1_00.mp3",
    )
    assert url == "/static/x/dub_f1_00.mp3"
    assert (tmp_path / "dub_f1_00.mp3").exists()
    assert fake.reqs[0].lang == "vi" and fake.reqs[0].speech_rate == 15
