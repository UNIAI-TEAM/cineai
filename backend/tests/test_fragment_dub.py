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
    monkeypatch.setattr(fragment_dub.storage, "STATIC_ROOT", tmp_path)

    async def fake_reload(db, fragment):
        # Session giả không có DB: "đọc lại có khoá" trả chính object (test tự đổi nó để giả lập ghi đồng thời)
        return fragment

    monkeypatch.setattr(fragment_dub, "_reload_locked", fake_reload)
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


async def test_redub_uses_raw_source_not_dubbed_video(wired, monkeypatch):
    # dub trước từng lỗi (error_code còn sót lại) — ghi "running" của lần chạy này không được mang lỗi cũ theo
    frag = _frag("【对白】Lan：Lần hai.", video="/static/generated/p1/shot_9_old_dub.mp4",
                 params={"voice_mode": "dub", "dub": {"status": "done", "url": "/static/generated/p1/shot_9_old_dub.mp4",
                                                      "sourceVideo": "/static/generated/p1/shot_9_raw.mp4",
                                                      "error": "boom cũ", "error_code": "drama.dub_failed",
                                                      "error_params": {"x": 1}}})
    write_calls: list[dict] = []
    orig_write_dub = fragment_dub._write_dub

    def spy_write_dub(fragment, dub):
        write_calls.append(dict(dub))
        return orig_write_dub(fragment, dub)

    monkeypatch.setattr(fragment_dub, "_write_dub", spy_write_dub)
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert dub["sourceVideo"] == "/static/generated/p1/shot_9_raw.mp4"
    running_writes = [w for w in write_calls if w.get("status") == "running"]
    assert len(running_writes) == 1
    assert "error" not in running_writes[0]
    assert "error_code" not in running_writes[0]
    assert "error_params" not in running_writes[0]


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


async def test_dub_mid_flow_error_rolls_back_and_marks_failed(wired, monkeypatch):
    """Lỗi giữa chừng (vd. transaction DB aborted khi load_dub_voices) phải rollback trước khi ghi lại failed,
    không được để commit tiếp raise che mất lỗi gốc hoặc âm thầm bỏ qua."""

    class _Boom(RuntimeError):
        pass

    async def boom_voices(db, project, lang):
        raise _Boom("db aborted")

    monkeypatch.setattr(fragment_dub, "load_dub_voices", boom_voices)
    frag = _frag("【对白】Lan：Xin chào.")
    db = _Db()
    with pytest.raises(_Boom):
        await fragment_dub.dub_fragment(db, USER, PROJECT, frag)
    assert db.rollbacks == 1
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"
    assert frag.video == "/static/generated/p1/shot_9.mp4"


async def test_dub_billing_failure_keeps_source_and_marks_failed(wired, monkeypatch):
    """record_line lỗi (sau khi TTS/mix đã xong) vẫn phải rơi về failed + giữ video gốc, không chốt "done" nửa vời."""

    async def boom_record(db, **kw):
        raise RuntimeError("billing down")

    monkeypatch.setattr(fragment_dub, "record_line", boom_record)
    frag = _frag("【对白】Lan：Xin chào.")
    db = _Db()
    with pytest.raises(RuntimeError):
        await fragment_dub.dub_fragment(db, USER, PROJECT, frag)
    assert db.rollbacks == 1
    assert frag.params["dub"]["status"] == "failed"
    assert frag.video == "/static/generated/p1/shot_9.mp4"


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


def test_activate_replaced_entry_carries_raw_video(monkeypatch):
    """Đang xem bản đã lồng tiếng, chuyển sang bản cũ khác: bản bị thay (đẩy vào video_versions) phải giữ rawVideo."""
    monkeypatch.setattr(generation, "_snapshot_version_media_url", lambda url, label: f"{url}#{label}" if url else "")
    frag = _frag(
        "",
        video="/v/dubbed_now.mp4",
        params={
            "dub": {"status": "done", "url": "/v/dubbed_now.mp4", "sourceVideo": "/v/raw_now.mp4"},
            "video_versions": [{"id": "v_old", "video": "/v/old.mp4", "cover": "", "lastFrameUrl": None}],
        },
    )
    out = generation.activate_fragment_video_version(frag, "v_old")
    assert frag.video == "/v/old.mp4"
    replaced = [v for v in out["video_versions"] if str(v.get("id") or "").endswith("_replaced")]
    assert len(replaced) == 1
    assert replaced[0]["rawVideo"].startswith("/v/raw_now.mp4#")


def test_activate_without_raw_video_clears_dub(monkeypatch):
    """Bản được khôi phục chưa từng lồng tiếng (không có rawVideo) → params.dub phải bị xoá, không kế thừa bản cũ."""
    monkeypatch.setattr(generation, "_snapshot_version_media_url", lambda url, label: f"{url}#{label}" if url else "")
    frag = _frag(
        "",
        video="/v/current.mp4",
        params={
            "dub": {"status": "done", "url": "/v/current.mp4", "sourceVideo": "/v/current_raw.mp4"},
            "video_versions": [{"id": "v_plain", "video": "/v/plain.mp4", "cover": "", "lastFrameUrl": None}],
        },
    )
    generation.activate_fragment_video_version(frag, "v_plain")
    assert frag.video == "/v/plain.mp4"
    assert "dub" not in frag.params


async def test_dub_discards_result_when_video_regenerated_during_dub(wired, monkeypatch, tmp_path):
    """C1: trong lúc TTS người dùng tạo lại video (video mới + generation running) → không ghi đè video/generation,
    params mới giữ nguyên, dub đánh dấu skipped/stale, không tính tiền, dọn file tạm."""
    frag = _frag("【对白】Lan：Xin chào.", params={"voice_mode": "dub", "dub": {"status": "running"}})
    wired_tts = fragment_dub.get_ark().tts

    async def tts_then_regenerate(text, voice, **kw):
        url = await wired_tts(text, voice, **kw)
        frag.video = "/static/generated/p1/shot_9_v2.mp4"
        frag.params = {**frag.params, "generation": {"status": "running"}, "video_versions": [{"id": "v1"}]}
        return url

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=tts_then_regenerate))
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert dub["status"] == "skipped" and dub["reason"] == "stale"
    assert frag.video == "/static/generated/p1/shot_9_v2.mp4"
    assert frag.params["generation"] == {"status": "running"}
    assert frag.params["video_versions"] == [{"id": "v1"}]
    assert frag.params["dub"]["status"] == "skipped"
    assert wired["usage"] == []
    assert not list(tmp_path.glob("*.mp3")) and not list(tmp_path.glob("*_dub.mp4"))


async def test_dub_failure_after_regeneration_does_not_reset_video(wired, monkeypatch):
    """C1: lỗi xảy ra sau khi video đã được thay bằng bản mới → nhánh failed không trả video về nguồn cũ."""
    frag = _frag("【对白】Lan：Xin chào.")

    async def regenerate_then_fail(text, voice, **kw):
        frag.video = "/static/generated/p1/shot_9_v2.mp4"
        raise RuntimeError("tts down")

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=regenerate_then_fail))
    with pytest.raises(RuntimeError):
        await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert frag.video == "/static/generated/p1/shot_9_v2.mp4"
    assert frag.params["dub"]["status"] == "skipped"


async def test_dub_success_merges_only_dub_key_and_cleans_clips(wired, tmp_path):
    """Thành công: chỉ trộn khoá dub vào params mới nhất (giữ khoá khác), xoá mp3 từng câu sau khi trộn."""
    frag = _frag("【对白】Lan：Xin chào.", params={"voice_mode": "dub", "video_versions": [{"id": "v0"}]})
    dub = await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert dub["status"] == "done"
    assert frag.params["video_versions"] == [{"id": "v0"}] and frag.params["voice_mode"] == "dub"
    assert not list(tmp_path.glob("*.mp3"))
    assert list(tmp_path.glob("*_dub.mp4"))


async def test_ensure_local_video_rejects_path_outside_static(monkeypatch, tmp_path):
    """I4: URL /static/../../etc/passwd không được đọc/tải ra ngoài STATIC_ROOT."""
    from app.errors import AppError

    static_root = tmp_path / "static"
    static_root.mkdir()
    monkeypatch.setattr(fragment_dub.storage, "STATIC_ROOT", static_root)
    monkeypatch.setattr(fragment_dub.storage, "local_path_from_url",
                        lambda url: static_root / url.removeprefix("/static/"))

    async def no_download(url, local):
        raise AssertionError("không được tải file ra ngoài STATIC_ROOT")

    monkeypatch.setattr(fragment_dub.storage, "ensure_local_media", no_download)
    with pytest.raises(AppError) as exc_info:
        await fragment_dub._ensure_local_video("/static/../../etc/passwd")
    assert exc_info.value.code == "drama.dub_no_video"
    assert fragment_dub._confined_local_path("/static/../../etc/passwd") is None
    inside = static_root / "generated" / "a.mp4"
    inside.parent.mkdir()
    inside.write_bytes(b"x")
    assert await fragment_dub._ensure_local_video("/static/generated/a.mp4") == inside


async def test_dub_rejects_tts_clip_outside_static(wired, monkeypatch, tmp_path):
    """I4: file TTS trả về ngoài STATIC_ROOT → lỗi dub_failed, không trộn."""
    inner = tmp_path / "static"
    inner.mkdir()
    monkeypatch.setattr(fragment_dub.storage, "STATIC_ROOT", inner)
    frag = _frag("【对白】Lan：Xin chào.")
    with pytest.raises(Exception):
        await fragment_dub.dub_fragment(_Db(), USER, PROJECT, frag)
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"
    assert frag.video == "/static/generated/p1/shot_9.mp4"


def test_versions_record_and_restore_voice_mode(monkeypatch):
    """I3: mỗi phiên bản lưu voiceMode; kích hoạt bản native trả params.voice_mode về native (không lồng đè giọng gốc)."""
    monkeypatch.setattr(generation, "_snapshot_version_media_url", lambda url, label: f"{url}#{label}" if url else "")
    frag = _frag("", video="/v/native.mp4", params={"voice_mode": "native"})
    native_entry = generation.archive_fragment_video_version(frag)
    assert native_entry["voiceMode"] == "native"
    # Tạo lại ở chế độ dub
    frag.video = "/v/dub_raw.mp4"
    frag.params["voice_mode"] = "dub"
    out = generation.activate_fragment_video_version(frag, native_entry["id"])
    assert frag.params["voice_mode"] == "native"
    replaced = [v for v in out["video_versions"] if str(v.get("id") or "").endswith("_replaced")]
    assert replaced[0]["voiceMode"] == "dub"
    generation.activate_fragment_video_version(frag, replaced[0]["id"])
    assert frag.params["voice_mode"] == "dub"


def test_activate_legacy_version_without_voice_mode(monkeypatch):
    """I3: bản cũ chưa có voiceMode → native; nếu có rawVideo (từng lồng tiếng) → dub."""
    monkeypatch.setattr(generation, "_snapshot_version_media_url", lambda url, label: f"{url}#{label}" if url else "")
    frag = _frag("", video="/v/cur.mp4", params={
        "voice_mode": "dub",
        "video_versions": [
            {"id": "plain", "video": "/v/plain.mp4", "cover": ""},
            {"id": "dubbed", "video": "/v/d.mp4", "cover": "", "rawVideo": "/v/raw.mp4"},
        ],
    })
    generation.activate_fragment_video_version(frag, "plain")
    assert frag.params["voice_mode"] == "native"
    generation.activate_fragment_video_version(frag, "dubbed")
    assert frag.params["voice_mode"] == "dub"


def test_keep_server_owned_params_ignores_stale_client_values():
    """I2: lưu phân cảnh giữ dub/voice_mode/generation/video_versions theo DB, khoá khác theo client."""
    db_params = {"dub": {"status": "done"}, "voice_mode": "dub", "generation": {"status": "done"}, "video_versions": [1]}
    client = {"dub": {"status": "running"}, "voice_mode": "native", "generation": {"status": "queued"},
              "video_versions": [], "user_edited": True}
    merged = fragment_dub.keep_server_owned_params(db_params, client)
    assert merged == {**db_params, "user_edited": True}
    # DB không có khoá → bỏ luôn giá trị client
    assert fragment_dub.keep_server_owned_params({}, {"dub": {"status": "running"}, "x": 1}) == {"x": 1}
    assert fragment_dub.keep_server_owned_params(None, None) == {}
