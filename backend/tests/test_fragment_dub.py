"""Lồng tiếng phân cảnh: skipped khi không có thoại, không lồng đè bản đã lồng, lỗi giữ video gốc, phiên bản giữ rawVideo."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.dub_mix import DubPlan
from app.services.drama import fragment_dub, generation


class _Db:
    """AsyncSession giả: ghi nhận commit/rollback, refresh không làm gì."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        return None


def _frag(content, video="/static/generated/p1/shot_9.mp4", params=None):
    return SimpleNamespace(id=9, content=content, video=video, cover="", params=params or {"voice_mode": "dub"})


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Nối giả: TTS ghi file, FFmpeg giả, lưu trữ trỏ vào tmp, không có nhân vật."""
    calls = {"tts": [], "usage": []}

    async def fake_tts(text, voice, **kw):
        calls["tts"].append((text, voice, kw))
        p = tmp_path / kw["out_name"]
        p.write_bytes(b"ID3" + b"\x00" * 3000)
        return f"/static/generated/p1/{p.name}"

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=fake_tts))
    monkeypatch.setattr(fragment_dub, "project_content_lang", lambda project: "vi")
    monkeypatch.setattr(fragment_dub, "_drama_tts_model", lambda: "seed-tts-2.0")

    async def fake_voices(db, project, lang):
        return [], "vi_female_ruan_uranus_bigtts"

    async def fake_names(db, fragment):
        return {}

    async def fake_local(url):
        return tmp_path / Path(url).name

    def fake_mix(video, clips, dest):
        dest.write_bytes(b"mp4")
        return DubPlan(starts=[0.2] * len(clips), tempo=1.0, out_duration=8.0, freeze_sec=0.0)

    async def fake_record(db, **kw):
        calls["usage"].append(kw)

    monkeypatch.setattr(fragment_dub, "load_dub_voices", fake_voices)
    monkeypatch.setattr(fragment_dub, "_fragment_asset_names", fake_names)
    monkeypatch.setattr(fragment_dub, "_ensure_local_video", fake_local)
    monkeypatch.setattr(fragment_dub, "run_dub_mix", fake_mix)
    monkeypatch.setattr(fragment_dub, "record_line", fake_record)
    monkeypatch.setattr(fragment_dub.storage, "local_path_from_url", lambda url: tmp_path / Path(url).name)
    monkeypatch.setattr(fragment_dub.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(fragment_dub.storage, "rel_static_url", lambda p: f"/static/generated/p1/{p.name}")
    monkeypatch.setattr(fragment_dub.storage, "republish_url", lambda url, sync=True: url)
    return calls


USER = SimpleNamespace(id=1)
PROJECT = SimpleNamespace(id=1, params={})


async def test_dub_done_replaces_video_and_bills_chars(wired):
    frag = _frag("【对白】Lan：Xin chào.\n【旁白】Trời mưa.")
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag, task_run_id=42)
    assert dub["status"] == "done"
    assert dub["sourceVideo"] == "/static/generated/p1/shot_9.mp4"
    assert frag.video == dub["url"] and frag.video.endswith("_dub.mp4")
    assert [c[2]["lang"] for c in wired["tts"]] == ["vi", "vi"]
    assert wired["usage"][0]["tokens"] == len("Xin chào.") + len("Trời mưa.")
    assert wired["usage"][0]["task_run_id"] == 42 and wired["usage"][0]["billing_key"] == "tts"


async def test_dub_skipped_when_no_dialogue(wired):
    frag = _frag("00:00-00:05 【画面】Toàn cảnh thành phố")
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert dub["status"] == "skipped" and wired["tts"] == [] and wired["usage"] == []
    assert frag.video == "/static/generated/p1/shot_9.mp4"


async def test_redub_uses_raw_source_not_dubbed_video(wired):
    frag = _frag("【对白】Lan：Lần hai.", video="/static/generated/p1/shot_9_old_dub.mp4",
                 params={"voice_mode": "dub", "dub": {"status": "done", "url": "/static/generated/p1/shot_9_old_dub.mp4",
                                                      "sourceVideo": "/static/generated/p1/shot_9_raw.mp4"}})
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert dub["sourceVideo"] == "/static/generated/p1/shot_9_raw.mp4"


async def test_dub_failure_keeps_source_and_records_nothing(wired, monkeypatch):
    async def boom(text, voice, **kw):
        raise RuntimeError("tts down")

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=boom))
    frag = _frag("【对白】Lan：Xin chào.")
    with pytest.raises(RuntimeError):
        await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"
    assert frag.video == "/static/generated/p1/shot_9.mp4" and wired["usage"] == []


def test_dub_source_video_rules():
    raw = _frag("", video="/v/raw.mp4", params={})
    assert fragment_dub.dub_source_video(raw) == "/v/raw.mp4"
    dubbed = _frag("", video="/v/d.mp4", params={"dub": {"url": "/v/d.mp4", "sourceVideo": "/v/raw.mp4"}})
    assert fragment_dub.dub_source_video(dubbed) == "/v/raw.mp4"
    stale = _frag("", video="/v/new.mp4", params={"dub": {"url": "/v/d.mp4", "sourceVideo": "/v/raw.mp4"}})
    assert fragment_dub.dub_source_video(stale) == "/v/new.mp4"


def test_versions_carry_raw_video(monkeypatch):
    monkeypatch.setattr(generation, "_snapshot_version_media_url", lambda url, label: f"{url}#{label}" if url else "")
    frag = _frag("", video="/v/d.mp4", params={"dub": {"status": "done", "url": "/v/d.mp4", "sourceVideo": "/v/raw.mp4"}})
    entry = generation.archive_fragment_video_version(frag)
    assert entry["rawVideo"].startswith("/v/raw.mp4#")
    frag.video = "/v/new_raw.mp4"
    frag.params.pop("dub")
    generation.activate_fragment_video_version(frag, entry["id"])
    assert frag.video == entry["video"]
    assert frag.params["dub"]["url"] == entry["video"]
    assert frag.params["dub"]["sourceVideo"] == entry["rawVideo"]
