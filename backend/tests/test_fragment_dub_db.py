"""C1 trên PostgreSQL thật: dub_fragment đọc lại dòng phân cảnh có khoá, không ghi đè thay đổi đồng thời."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_drama import DramaEpisode, DramaEpisodeFragment, DramaProject
from app.services.drama import fragment_dub
from tests.conftest import make_user
from tests.test_fragment_dub import wired  # noqa: F401  (fixture nối giả TTS/FFmpeg/lưu trữ)

_REAL_RELOAD = fragment_dub._reload_locked


async def _make_fragment(db: AsyncSession, user) -> tuple[DramaProject, DramaEpisodeFragment]:
    """Tạo user → dự án → tập → một phân cảnh dub đã có video thô."""
    project = DramaProject(user_id=user.id, title="Dub C1")
    db.add(project)
    await db.flush()
    episode = DramaEpisode(project_id=project.id, name="Tập 1")
    db.add(episode)
    await db.flush()
    fragment = DramaEpisodeFragment(
        episode_id=episode.id,
        sort_order=1,
        content="【对白】Lan：Xin chào.",
        video="/static/generated/p1/shot_9.mp4",
        params={"voice_mode": "dub", "dub": {"status": "running"}},
    )
    db.add(fragment)
    await db.flush()
    await db.commit()
    return project, fragment


async def _row(db: AsyncSession, fragment_id: int) -> tuple[str, dict]:
    """Đọc thẳng cột video/params từ DB (không qua identity map)."""
    row = (
        await db.execute(
            select(DramaEpisodeFragment.video, DramaEpisodeFragment.params).where(DramaEpisodeFragment.id == fragment_id)
        )
    ).one()
    return row[0], row[1]


async def test_dub_keeps_concurrent_regeneration_on_real_db(db_session: AsyncSession, wired, monkeypatch):  # noqa: F811
    """Ghi đồng thời (UPDATE ngoài ORM) giữa lúc TTS: bản lồng bị bỏ, video/generation mới giữ nguyên."""
    monkeypatch.setattr(fragment_dub, "_reload_locked", _REAL_RELOAD)
    user = await make_user(db_session)
    project, fragment = await _make_fragment(db_session, user)
    fid = fragment.id
    base_tts = fragment_dub.get_ark().tts

    async def tts_then_regenerate(text, voice, **kw):
        url = await base_tts(text, voice, **kw)
        await db_session.execute(
            update(DramaEpisodeFragment)
            .where(DramaEpisodeFragment.id == fid)
            .values(
                video="/static/generated/p1/shot_9_v2.mp4",
                params={"voice_mode": "dub", "dub": {"status": "running"}, "generation": {"status": "running"}},
            )
            .execution_options(synchronize_session=False)
        )
        return url

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=tts_then_regenerate))
    dub = await fragment_dub.dub_fragment(db_session, user, project, fragment)
    assert dub["status"] == "skipped" and dub["reason"] == "stale"
    video, params = await _row(db_session, fid)
    assert video == "/static/generated/p1/shot_9_v2.mp4"
    assert params["generation"] == {"status": "running"}
    assert params["dub"]["status"] == "skipped"
    assert wired["usage"] == []


async def test_dub_done_on_real_db_merges_fresh_params(db_session: AsyncSession, wired, monkeypatch):  # noqa: F811
    """Không có thay đổi video nhưng có khoá params khác được ghi đồng thời → bản lồng vào, khoá mới được giữ."""
    monkeypatch.setattr(fragment_dub, "_reload_locked", _REAL_RELOAD)
    user = await make_user(db_session)
    project, fragment = await _make_fragment(db_session, user)
    fid = fragment.id
    base_tts = fragment_dub.get_ark().tts

    async def tts_then_touch_params(text, voice, **kw):
        url = await base_tts(text, voice, **kw)
        await db_session.execute(
            update(DramaEpisodeFragment)
            .where(DramaEpisodeFragment.id == fid)
            .values(params={"voice_mode": "dub", "dub": {"status": "running"}, "user_edited": True})
            .execution_options(synchronize_session=False)
        )
        return url

    monkeypatch.setattr(fragment_dub, "get_ark", lambda: SimpleNamespace(tts=tts_then_touch_params))
    dub = await fragment_dub.dub_fragment(db_session, user, project, fragment)
    assert dub["status"] == "done"
    video, params = await _row(db_session, fid)
    assert video == dub["url"] and video.endswith("_dub.mp4")
    assert params["user_edited"] is True
    assert params["dub"]["sourceVideo"] == "/static/generated/p1/shot_9.mp4"
