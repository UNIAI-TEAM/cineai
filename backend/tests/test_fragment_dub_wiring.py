"""Nối lồng tiếng (bản 3 — guard theo task thật + executor tự dọn params.dub treo):
handler đăng ký + chạy phiên riêng, guard 4 tra TaskRun đang hoạt động (không khoá cứng vĩnh viễn),
executor._fail_task/_fail_task_before_start/_mark_cancelled tự đóng params.dub khi treo "running",
_fail_task không còn đụng params.generation của fragment_dub, enqueue bỏ qua khi đã có task đang chạy
và luôn ghi params.dub failed best-effort khi enqueue lỗi, ước tính phí tách khỏi fragment_video,
mã lỗi có trong danh mục.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.errors import ERRORS, AppError
from app.models_drama import DramaEpisode, DramaEpisodeFragment, DramaProject
from app.models import User
from app.services.billing import estimates
from app.services.drama import fragment_dub
from app.services.tasks import executor as tasks_executor
from app.services.tasks.handlers import get_task_handler


def _frag(video="/static/generated/p1/shot_9.mp4", params=None, content="【对白】Lan：Xin chào."):
    return SimpleNamespace(id=9, episode_id=1, content=content, video=video, cover="",
                            params=params if params is not None else {"voice_mode": "dub"})


async def _always_inactive(db, fragment_id):
    return False


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


# ---- has_active_fragment_dub_task: bọc db.execute(...).scalar_one_or_none() ----


class _FakeQueryResult:
    def __init__(self, found: bool):
        self._found = found

    def scalar_one_or_none(self):
        return 123 if self._found else None


class _FakeQueryDb:
    def __init__(self, found: bool):
        self._found = found

    async def execute(self, stmt):
        return _FakeQueryResult(self._found)


async def test_has_active_fragment_dub_task_true_when_row_found():
    assert await fragment_dub.has_active_fragment_dub_task(_FakeQueryDb(True), 9) is True


async def test_has_active_fragment_dub_task_false_when_no_row():
    assert await fragment_dub.has_active_fragment_dub_task(_FakeQueryDb(False), 9) is False


# ---- assert_fragment_dubbable: 4 guard (guard 4 giờ nhận dub_task_active từ ngoài) ----


def test_assert_dubbable_rejects_video_still_generating():
    frag = _frag(params={"voice_mode": "dub", "generation": {"status": "running"}})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag, dub_task_active=False)
    assert exc_info.value.code == "drama.dub_fragment_generating"


def test_assert_dubbable_rejects_non_dub_voice_mode():
    frag = _frag(params={"voice_mode": "native"})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag, dub_task_active=False)
    assert exc_info.value.code == "drama.dub_not_enabled"


def test_assert_dubbable_rejects_missing_video():
    frag = _frag(video="", params={"voice_mode": "dub"})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag, dub_task_active=False)
    assert exc_info.value.code == "drama.dub_no_video"


def test_assert_dubbable_rejects_active_dub_task():
    frag = _frag(params={"voice_mode": "dub"})
    with pytest.raises(AppError) as exc_info:
        fragment_dub.assert_fragment_dubbable(frag, dub_task_active=True)
    assert exc_info.value.code == "drama.dub_fragment_generating"


def test_assert_dubbable_allows_redub_when_stale_running_flag_but_no_active_task():
    """Ruling 11 / N2: params.dub.status vẫn "running" (task cũ kết thúc bất thường, chưa kịp dọn)
    nhưng KHÔNG có task đang hoạt động → vẫn cho lồng lại, guard không được khoá cứng vĩnh viễn."""
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    fragment_dub.assert_fragment_dubbable(frag, dub_task_active=False)  # không raise


def test_assert_dubbable_passes_when_all_conditions_met():
    frag = _frag(params={"voice_mode": "dub"})
    fragment_dub.assert_fragment_dubbable(frag, dub_task_active=False)  # không raise


# ---- enqueue_fragment_dub: ghi running, bỏ lỗi cũ, tạo task với dedupe_key + line_count ----


class _FakeDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def _no_lock_no_active(monkeypatch, *, active=False):
    """Session giả không có DB: "khoá dòng" trả chính object, has_active_fragment_dub_task theo tham số."""

    async def fake_reload(db, fragment):
        return fragment

    async def fake_active(db, fragment_id):
        return active

    monkeypatch.setattr(fragment_dub, "_reload_locked", fake_reload)
    monkeypatch.setattr(fragment_dub, "has_active_fragment_dub_task", fake_active)


async def test_enqueue_fragment_dub_rechecks_active_task_under_lock(monkeypatch):
    """M6: sau khi khoá dòng mà đã có task đang chạy (bấm đúp) → từ chối, không tạo task thứ hai."""
    _no_lock_no_active(monkeypatch, active=True)

    async def should_not_create(*a, **kw):
        raise AssertionError("không được tạo task trùng")

    monkeypatch.setattr(fragment_dub, "create_task", should_not_create)
    frag = _frag(content="【对白】Lan：Câu một.", params={"voice_mode": "dub"})
    with pytest.raises(AppError) as exc_info:
        await fragment_dub.enqueue_fragment_dub(_FakeDb(), SimpleNamespace(id=1), frag, drama_project_id=1,
                                                episode_id=1)
    assert exc_info.value.code == "drama.dub_fragment_generating"
    assert "dub" not in frag.params


async def test_enqueue_fragment_dub_writes_running_drops_stale_error_and_creates_task(monkeypatch):
    async def fake_names(db, fragment):
        return {}

    monkeypatch.setattr(fragment_dub, "_fragment_asset_names", fake_names)
    _no_lock_no_active(monkeypatch)

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
    assert body.payload == {"fragment_id": 9, "line_count": 2,
                            "char_count": len("Câu một.") + len("Câu hai.")}
    assert body.drama_project_id == 1 and body.episode_id == 2 and body.fragment_id == 9
    assert created["commit"] is False
    assert db.commits == 1


async def test_enqueue_fragment_dub_line_count_at_least_one_when_no_dialogue(monkeypatch):
    async def fake_names(db, fragment):
        return {}

    monkeypatch.setattr(fragment_dub, "_fragment_asset_names", fake_names)
    _no_lock_no_active(monkeypatch)

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
    episode = SimpleNamespace(id=2, project_id=3, params={})
    project = SimpleNamespace(id=3)
    user = SimpleNamespace(id=4)
    gets = {
        (DramaEpisodeFragment, 9): frag,
        (DramaEpisode, 2): episode,
        (DramaProject, 3): project,
        (User, 4): user,
    }
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory(gets))

    async def boom(db, u, p, f, *, task_run_id=None, burn_subtitles=False):
        raise RuntimeError("dub lỗi")

    monkeypatch.setattr(fragment_dub, "dub_fragment", boom)

    with pytest.raises(RuntimeError):
        await fragment_dub.run_fragment_dub_job(99, 9, 4)


async def test_run_fragment_dub_job_returns_status_on_success(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2)
    episode = SimpleNamespace(id=2, project_id=3, params={"subtitleMode": "model"})
    project = SimpleNamespace(id=3)
    user = SimpleNamespace(id=4)
    gets = {
        (DramaEpisodeFragment, 9): frag,
        (DramaEpisode, 2): episode,
        (DramaProject, 3): project,
        (User, 4): user,
    }
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory(gets))

    seen = {}

    async def ok(db, u, p, f, *, task_run_id=None, burn_subtitles=False):
        seen["burn_subtitles"] = burn_subtitles
        return {"status": "done"}

    monkeypatch.setattr(fragment_dub, "dub_fragment", ok)

    result = await fragment_dub.run_fragment_dub_job(99, 9, 4)
    assert result == {"ok": True, "status": "done"}
    # Tập bật "phụ đề do mô hình" → lồng tiếng tự đốt phụ đề khớp giọng TTS
    assert seen["burn_subtitles"] is True


async def test_run_fragment_dub_job_raises_when_fragment_missing(monkeypatch):
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", _fake_session_factory({}))
    with pytest.raises(RuntimeError):
        await fragment_dub.run_fragment_dub_job(99, 404, 4)


# ---- enqueue_fragment_dub_after_video: bỏ qua khi đã có task đang chạy (N3), luôn ghi failed
#      best-effort khi lỗi (N4), không phá task video ----


class _FakeAfterVideoSession:
    def __init__(self, fragment, user):
        self._fragment = fragment
        self._user = user
        self.rollbacks = 0
        self.commits = 0

    async def get(self, model, ident):
        if model is DramaEpisodeFragment:
            return self._fragment
        if model is User:
            return self._user
        return None

    async def rollback(self):
        self.rollbacks += 1

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_enqueue_fragment_dub_after_video_skips_when_active_task_exists(monkeypatch):
    """N3: đã có task fragment_dub đang chạy cho phân cảnh này → không tạo thêm task trùng."""
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub"})
    user = SimpleNamespace(id=4)
    session = _FakeAfterVideoSession(frag, user)
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)

    async def active_true(db, fragment_id):
        return True

    monkeypatch.setattr(fragment_dub, "has_active_fragment_dub_task", active_true)

    calls = {"n": 0}

    async def should_not_run(*a, **k):
        calls["n"] += 1

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", should_not_run)

    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert calls["n"] == 0
    assert session.rollbacks == 0


async def test_enqueue_fragment_dub_after_video_marks_failed_on_generic_error(monkeypatch):
    """N4: lỗi enqueue bất kỳ (không phải billing.*) vẫn phải ghi params.dub failed best-effort."""
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub"})
    user = SimpleNamespace(id=4)
    session = _FakeAfterVideoSession(frag, user)
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(fragment_dub, "has_active_fragment_dub_task", _always_inactive)

    async def boom_enqueue(db, u, f, *, drama_project_id, episode_id):
        raise RuntimeError("hàng đợi lỗi bất kỳ")

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", boom_enqueue)

    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert session.rollbacks == 1
    assert session.commits == 1
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"
    assert frag.params["dub"]["sourceVideo"] == "/v.mp4"


async def test_enqueue_fragment_dub_after_video_marks_failed_on_insufficient_balance(monkeypatch):
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub"})
    user = SimpleNamespace(id=4)
    session = _FakeAfterVideoSession(frag, user)
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(fragment_dub, "has_active_fragment_dub_task", _always_inactive)

    async def boom_enqueue(db, u, f, *, drama_project_id, episode_id):
        raise AppError("billing.insufficient_balance", need_fen=100, available_fen=0)

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", boom_enqueue)

    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert session.rollbacks == 1
    assert session.commits == 1
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "billing.insufficient_balance"
    assert frag.params["dub"]["sourceVideo"] == "/v.mp4"


# ---- mark_fragment_dub_ended + executor hooks: N1 (không đụng params.generation của fragment_dub)
#      và N2 (params.dub không treo "running" mãi khi task fail/cancel bất thường) ----


def _executor_task(*, task_type: str, task_id: int = 99, fragment_id: int = 9, **extra) -> SimpleNamespace:
    base = dict(
        id=task_id, domain="drama", task_type=task_type, fragment_id=fragment_id, asset_id=None,
        project_id=None, payload={}, batch_key=None, steps=[], current_step_key=task_type,
        error_code=None, error_params=None, error_message=None, finished_at=None, status="running",
        billing_status="frozen",
    )
    base.update(extra)
    return SimpleNamespace(**base)


def _executor_db(fragment) -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=fragment)
    return db


async def test_mark_fragment_dub_ended_noop_for_other_task_types():
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_video")
    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")
    assert frag.params["dub"]["status"] == "running"  # không đụng vào


async def test_mark_fragment_dub_ended_noop_when_not_running():
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "done"}})
    task = _executor_task(task_type="fragment_dub")
    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")
    assert frag.params["dub"]["status"] == "done"  # đã kết thúc rồi thì không viết đè


async def test_mark_fragment_dub_ended_uses_registered_task_error_code():
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", error_code="billing.insufficient_balance")
    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "billing.insufficient_balance"


async def test_mark_fragment_dub_ended_falls_back_to_dub_failed_for_unregistered_code():
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", error_code="RuntimeError")  # không đăng ký trong ERRORS
    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"


async def test_mark_fragment_dub_ended_cancel_path_has_no_registered_cancel_code():
    """task.cancelled chưa được đăng ký trong ERRORS → nhánh huỷ cũng rơi về drama.dub_failed."""
    assert "task.cancelled" not in ERRORS
    frag = _frag(params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", error_code=None)
    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "cancelled")
    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"


async def test_mark_fragment_dub_ended_keeps_prior_url_and_source_video_on_redub_failure():
    """Hồi quy round 3: phân cảnh đã lồng tiếng trước đó (video=D, dub={done,url:D,sourceVideo:R}),
    người dùng bấm lồng lại → enqueue chuyển "running" nhưng vẫn giữ url/sourceVideo cũ; task fail
    trước khi dub_fragment kịp chạy (freeze lỗi / huỷ / lỗi đầu run_fragment_dub_job) → hook KHÔNG
    được suy sourceVideo từ fragment.video (lúc này vẫn là D, bản đã lồng), nếu không lần lồng tiếp
    theo sẽ trộn TTS đè lên chính audio đã lồng thay vì video gốc R."""
    frag = SimpleNamespace(
        id=9,
        video="/D_dub.mp4",  # đang xem bản đã lồng tiếng trước đó
        params={
            "voice_mode": "dub",
            "dub": {
                "status": "running",  # enqueue_fragment_dub vừa chuyển sang running cho lượt lồng lại
                "url": "/D_dub.mp4",
                "sourceVideo": "/R_raw.mp4",
            },
        },
    )
    task = _executor_task(task_type="fragment_dub", error_code=None)

    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")

    dub = frag.params["dub"]
    assert dub["status"] == "failed"
    assert dub["url"] == "/D_dub.mp4"
    assert dub["sourceVideo"] == "/R_raw.mp4"
    # Hệ quả đúng: lần lồng tiếp theo vẫn lấy video GỐC làm nguồn, không lồng chồng lên bản đã lồng
    assert fragment_dub.dub_source_video(frag) == "/R_raw.mp4"


async def test_mark_fragment_dub_ended_leaves_no_source_video_when_never_dubbed_before():
    """Chưa từng lồng tiếng thành công lần nào (dub={status:running} không có url/sourceVideo) →
    hook không tự bịa sourceVideo; dub_source_video tự rơi về fragment.video là đúng."""
    frag = SimpleNamespace(id=9, video="/raw.mp4", params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", error_code=None)

    await fragment_dub.mark_fragment_dub_ended(_executor_db(frag), task, "failed")

    dub = frag.params["dub"]
    assert dub["status"] == "failed"
    assert "sourceVideo" not in dub
    assert "url" not in dub
    assert fragment_dub.dub_source_video(frag) == "/raw.mp4"


async def test_fail_task_fragment_dub_leaves_generation_untouched_and_marks_dub_failed(monkeypatch):
    """N1 + N2: _fail_task trên task fragment_dub không đụng params.generation (video vẫn còn),
    nhưng dọn params.dub khỏi trạng thái "running" treo mãi."""
    frag = SimpleNamespace(
        id=9, video="/v.mp4",
        params={
            "voice_mode": "dub",
            "generation": {"status": "done", "video": "/v.mp4"},
            "dub": {"status": "running"},
        },
    )
    task = _executor_task(task_type="fragment_dub")
    db = _executor_db(frag)
    monkeypatch.setattr(tasks_executor, "settle_task", AsyncMock())
    monkeypatch.setattr(tasks_executor, "append_task_event", AsyncMock())

    await tasks_executor._fail_task(db, task, RuntimeError("dub lỗi"))

    assert frag.params["generation"] == {"status": "done", "video": "/v.mp4"}  # N1
    assert frag.params["dub"]["status"] == "failed"  # N2
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"
    assert db.commit.await_count == 1


async def test_fail_task_non_fragment_dub_still_writes_generation_failed(monkeypatch):
    """Kiểm chứng N1 không phá hành vi cũ của các task type khác (vd. fragment_video)."""
    frag = SimpleNamespace(id=9, video="/v.mp4", params={"generation": {"status": "running"}})
    task = _executor_task(task_type="fragment_video")
    db = _executor_db(frag)
    monkeypatch.setattr(tasks_executor, "settle_task", AsyncMock())
    monkeypatch.setattr(tasks_executor, "append_task_event", AsyncMock())

    await tasks_executor._fail_task(db, task, RuntimeError("video lỗi"))

    assert frag.params["generation"]["status"] == "failed"


async def test_fail_task_before_start_marks_dub_failed_when_running(monkeypatch):
    frag = SimpleNamespace(id=9, video="/v.mp4", params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", billing_status="none")
    db = _executor_db(frag)
    monkeypatch.setattr(tasks_executor, "settle_task", AsyncMock())
    monkeypatch.setattr(tasks_executor, "append_task_event", AsyncMock())

    await tasks_executor._fail_task_before_start(
        db, task, None, error_code="billing.insufficient_balance", message="không đủ số dư",
    )

    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "billing.insufficient_balance"


async def test_mark_cancelled_marks_dub_failed_when_running(monkeypatch):
    frag = SimpleNamespace(id=9, video="/v.mp4", params={"voice_mode": "dub", "dub": {"status": "running"}})
    task = _executor_task(task_type="fragment_dub", status="cancel_requested",
                          next_action_at=None, lease_until=None)
    db = _executor_db(frag)
    monkeypatch.setattr(tasks_executor, "settle_task", AsyncMock())
    monkeypatch.setattr(tasks_executor, "append_task_event", AsyncMock())

    await tasks_executor._mark_cancelled(db, task)

    assert frag.params["dub"]["status"] == "failed"
    assert frag.params["dub"]["error_code"] == "drama.dub_failed"  # không có mã task.cancelled đăng ký


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


async def test_fragment_dub_estimate_uses_char_count(priced_routing):
    """M5: có char_count → ước theo số ký tự (cùng đơn vị quyết toán), thấp hơn hẳn ước theo câu × hằng số token."""
    from app.config import get_settings
    from app.services.billing.rate_quotes import tts_fen

    by_chars = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 2, "char_count": 40},
                               fragment_id=None, project_id=None)
    by_lines = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 2},
                               fragment_id=None, project_id=None)
    fen_chars = await estimates.estimate_task_fen(None, by_chars)
    fen_lines = await estimates.estimate_task_fen(None, by_lines)
    s = get_settings()
    assert fen_chars == estimates._buffered_fen(tts_fen("drama.tts", 40, settings=s), s)
    assert 0 < fen_chars <= fen_lines


async def test_fragment_dub_estimate_defaults_to_one_line(priced_routing):
    task_default = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={},
                                    fragment_id=None, project_id=None)
    task_one = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={"line_count": 1},
                                fragment_id=None, project_id=None)
    fen_default = await estimates.estimate_task_fen(None, task_default)
    fen_one = await estimates.estimate_task_fen(None, task_one)
    assert fen_default == fen_one


async def test_enqueue_fragment_dub_after_video_race_lost_does_not_mark_failed(monkeypatch):
    """M6: enqueue phát hiện (dưới khoá) đã có task khác → im lặng rollback, không ghi đè "running" thành failed."""
    frag = SimpleNamespace(id=9, episode_id=2, video="/v.mp4", params={"voice_mode": "dub", "dub": {"status": "running"}})
    session = _FakeAfterVideoSession(frag, SimpleNamespace(id=4))
    monkeypatch.setattr(fragment_dub, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(fragment_dub, "has_active_fragment_dub_task", _always_inactive)

    async def lost_race(*a, **k):
        raise AppError("drama.dub_fragment_generating")

    monkeypatch.setattr(fragment_dub, "enqueue_fragment_dub", lost_race)
    await fragment_dub.enqueue_fragment_dub_after_video(9, 4, drama_project_id=1, episode_id=1)
    assert frag.params["dub"] == {"status": "running"}
    assert session.rollbacks == 1 and session.commits == 0
