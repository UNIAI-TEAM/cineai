"""Nối lồng tiếng (bản 2 — task thật, không còn _noop_ephemeral):
handler đăng ký + chạy phiên riêng, guard tái sử dụng được, enqueue ghi running/xoá lỗi cũ/tạo task,
executor lan lỗi để executor.py tự fail+hoàn phí, ước tính phí tách khỏi fragment_video, mã lỗi có trong danh mục.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.errors import ERRORS, AppError
from app.models_drama import DramaEpisode, DramaEpisodeFragment, DramaProject
from app.models import User
from app.services.billing import estimates
from app.services.drama import fragment_dub
from app.services.tasks.handlers import get_task_handler


def _frag(video="/static/generated/p1/shot_9.mp4", params=None, content="【对白】Lan：Xin chào."):
    return SimpleNamespace(id=9, episode_id=1, content=content, video=video, cover="",
                            params=params if params is not None else {"voice_mode": "dub"})


# ---- handler / error catalog ----


def test_fragment_dub_handler_registered():
    assert get_task_handler("drama", "fragment_dub") is not None


def test_fragment_dub_handler_is_not_noop():
    """Ruling 10.A: fragment_dub phải là handler thật (chạy phiên riêng), không còn _noop_ephemeral."""
    from app.services.tasks.handlers import _noop_ephemeral

    handler = get_task_handler("drama", "fragment_dub")
    assert handler.executor is not _noop_ephemeral


def test_dub_error_codes_registered():
    for code in ("drama.dub_no_video", "drama.dub_not_enabled", "drama.dub_failed", "drama.dub_fragment_generating"):
        assert code in ERRORS


# ---- assert_fragment_dubbable: 4 guard ----


def test_assert_dubbable_rejects_video_still_generating():
    frag = _frag(params={"voice_mode": "dub", "generation": {"status": "running"}})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag)
    assert exc_info.value.code == "drama.dub_fragment_generating"


def test_assert_dubbable_rejects_non_dub_voice_mode():
    frag = _frag(params={"voice_mode": "native"})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag)
    assert exc_info.value.code == "drama.dub_not_enabled"


def test_assert_dubbable_rejects_missing_video():
    frag = _frag(video="", params={"voice_mode": "dub"})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag)
    assert exc_info.value.code == "drama.dub_no_video"


def test_assert_dubbable_rejects_dub_already_running():
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag)
    assert exc_info.value.code == "drama.dub_fragment_generating"


def test_assert_dubbable_passes_when_all_conditions_met():
    frag = _frag(params={"voice_mode": "dub"})
    fragment_dub.assert_fragment_dubbable(frag)  # không raise


# ---- enqueue_fragment_dub: ghi running, bỏ lỗi cũ, tạo task với dedupe_key + line_count ----


class _FakeDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


async def test_enqueue_fragment_dub_writes_running_drops_stale_error_and_creates_task(monkeypatch):
    async def fake_names(db, fragment):
        return {}

    monkeypatch.setattr(fragment_dub, "_fragment_asset_names", fake_names)

    created: dict = {}

    async def fake_create_task(db, user, body, *, commit=False):
        created["db"], created["user"], created["body"], created["commit"] = db, user, body, commit
        return SimpleNamespace(id=777)

    monkeypatch.setattr(fragment_dub, "create_task", fake_create_task)

    frag = _frag(
        content="【对白】Lan：Câu một.\n【对白】Lan：Câu hai.",
        params={
            "voice_mode": "dub",
            "dub": {"status": "failed", "error": "cũ", "error_code": "drama.dub_failed", "error_params": {"x": 1}},
        },
    )
    user = SimpleNamespace(id=9)
    db = _FakeDb()

    task = await fragment_dub.enqueue_fragment_dub(db, user, frag, drama_project_id=1, episode_id=2)

    assert task.id == 777
    assert frag.params["dub"]["status"] == "running"
    assert "error" not in frag.params["dub"]
    assert "error_code" not in frag.params["dub"]
    assert "error_params" not in frag.params["dub"]
    body = created["body"]
    assert body.domain == "drama" and body.task_type == "fragment_dub"
    assert body.dedupe_key == "drama:fragment_dub:fragment:9"
    assert body.payload == {"fragment_id": 9, "line_count": 2}
    assert body.drama_project_id == 1 and body.episode_id == 2 and body.fragment_id == 9
    assert created["commit"] is False
    assert db.commits == 1


async def test_enqueue_fragment_dub_line_count_at_least_one_when_no_dialogue(monkeypatch):
    async def fake_names(db, fragment):
        return {}

    monkeypatch.setattr(fragment_dub, "_fragment_asset_names", fake_names)

    created: dict = {}

    async def fake_create_task(db, user, body, *, commit=False):
        created["body"] = body
        return SimpleNamespace(id=1)

    monkeypatch.setattr(fragment_dub, "create_task", fake_create_task)

    frag = _frag(content="00:00-00:05 【画面】Chỉ có hình ảnh")
    await fragment_dub.enqueue_fragment_dub(_FakeDb(), SimpleNamespace(id=1), frag, drama_project_id=1, episode_id=1)
    assert created["body"].payload["line_count"] == 1


# ---- run_fragment_dub_job: mở phiên riêng, lan lỗi dub_fragment ra ngoài ----


class _FakeJobSession:
    """AsyncSessionLocal() giả: chỉ hỗ trợ get(model, id) tra theo dict, không cần DB thật."""

    def __init__(self, gets: dict):
        self._gets = gets

    async def get(self, model, ident):
        return self._gets.get((model, ident))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _fake_session_factory(gets: dict):
    return lambda: _FakeJobSession(gets)


async def test_run_fragment_dub_job_propagates_dub_failure(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2)
    episode = SimpleNamespace(id=2, project_id=3)
    project = SimpleNamespace(id=3)
    user = SimpleNamespace(id=4)
    gets = {
        (DramaEpisodeFragment, 9): frag,
        (DramaEpisode, 2): episode,
        (DramaProject, 3): project,
        (User, 4): user,
    }
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory(gets))

    async def boom(db, u, p, f, *, task_run_id=None):
        raise RuntimeError("dub lỗi")

    monkeypatch.setattr(fragment_dub, "dub_fragment", boom)

    with pytest.raises(RuntimeError):
        await fragment_dub.run_fragment_dub_job(99, 9, 4)


async def test_run_fragment_dub_job_returns_status_on_success(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2)
    episode = SimpleNamespace(id=2, project_id=3)
    project = SimpleNamespace(id=3)
    user = SimpleNamespace(id=4)
    gets = {
        (DramaEpisodeFragment, 9): frag,
        (DramaEpisode, 2): episode,
        (DramaProject, 3): project,
        (User, 4): user,
    }
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory(gets))

    async def ok(db, u, p, f, *, task_run_id=None):
        return {"status": "done"}

    monkeypatch.setattr(fragment_dub, "dub_fragment", ok)

    result = await fragment_dub.run_fragment_dub_job(99, 9, 4)
    assert result == {"ok": True, "status": "done"}


async def test_run_fragment_dub_job_raises_when_fragment_missing(monkeypatch):
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory({}))
    with pytest.raises(RuntimeError):
        await fragment_dub.run_fragment_dub_job(99, 404, 4)


# ---- enqueue_fragment_dub_after_video: nuốt lỗi vào hàng đợi, không phá task video ----


async def test_enqueue_fragment_dub_after_video_swallows_enqueue_error(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub"})
    user = SimpleNamespace(id=4)

    class _Session:
        def __init__(self):
            self.rollbacks = 0
            self.commits = 0

        async def get(self, model, ident):
            if model is DramaEpisodeFragment:
                return frag
            if model is User:
                return user
            return None

        async def rollback(self):
            self.rollbacks += 1

        async def commit(self):
            self.commits += 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    session = _Session()
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)

    async def boom_enqueue(db, u, f, *, drama_project_id, episode_id):
        raise RuntimeError("hàng đợi lỗi bất kỳ")

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", boom_enqueue)

    # Không raise ra ngoài — lỗi không phải billing.* thì chỉ log, không viết lại params.dub
    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert session.rollbacks == 0


async def test_enqueue_fragment_dub_after_video_marks_failed_on_insufficient_balance(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub"})
    user = SimpleNamespace(id=4)

    class _Session:
        def __init__(self):
            self.rollbacks = 0
            self.commits = 0

        async def get(self, model, ident):
            if model is DramaEpisodeFragment:
                return frag
            if model is User:
                return user
            return None

        async def rollback(self):
            self.rollbacks += 1

        async def commit(self):
            self.commits += 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    session = _Session()
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)

    async def boom_enqueue(db, u, f, *, drama_project_id, episode_id):
        raise AppError("billing.insufficient_balance", need_fen=100, available_fen=0)

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", boom_enqueue)

    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert session.rollbacks == 1
    assert session.commits == 1
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "billing.insufficient_balance"
    assert frag.params["dub"]["sourceVideo"] == "/v.mp4"


# ---- ước tính phí: fragment_video không còn phụ thuộc voice_mode, fragment_dub theo line_count ----


async def test_fragment_video_estimate_ignores_voice_mode(monkeypatch, priced_routing):
    async def fake_dur(db, task, payload):
        return 8.0

    monkeypatch.setattr(estimates, "_drama_video_duration", fake_dur)
    base_task = dict(domain="drama", task_type="fragment_video", fragment_id=None, project_id=None)
    native = SimpleNamespace(**base_task, payload={"voice_mode": "native"})
    dub = SimpleNamespace(**base_task, payload={"voice_mode": "dub"})
    fen_native = await estimates.estimate_task_fen(None, native)
    fen_dub = await estimates.estimate_task_fen(None, dub)
    assert fen_dub == fen_native


async def test_fragment_dub_estimate_grows_with_line_count(priced_routing):
    task_one = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 1},
                                fragment_id=None, project_id=None)
    task_many = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 5},
                                 fragment_id=None, project_id=None)
    fen_one = await estimates.estimate_task_fen(None, task_one)
    fen_many = await estimates.estimate_task_fen(None, task_many)
    assert fen_one > 0
    assert fen_many > fen_one


async def test_fragment_dub_estimate_defaults_to_one_line(priced_routing):
    task_default = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={},
                                    fragment_id=None, project_id=None)
    task_one = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 1},
                                fragment_id=None, project_id=None)
    fen_default = await estimates.estimate_task_fen(None, task_default)
    fen_one = await estimates.estimate_task_fen(None, task_one)
    assert fen_default == fen_one
