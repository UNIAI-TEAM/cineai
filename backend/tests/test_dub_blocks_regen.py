"""C1(b): đang có task lồng tiếng thì không cho tạo lại video hay đổi phiên bản video của phân cảnh."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.drama import episodes
from app.errors import AppError
from app.schemas_drama import DramaActivateVideoVersionRequest, DramaGenerateRequest


def _frag(fid=9):
    return SimpleNamespace(id=fid, episode_id=1, sort_order=0, video="/v/d.mp4", cover="", content="",
                           duration_sec=8, params={"voice_mode": "dub", "video_versions": [{"id": "v1", "video": "/v/1.mp4"}]})


@pytest.fixture
def patched(monkeypatch):
    """Nối giả quyền sở hữu tập/dự án và danh sách phân cảnh; task lồng tiếng đang chạy cho fragment 9."""
    frag = _frag()

    async def owned_episode(db, episode_id, user):
        return SimpleNamespace(id=episode_id, project_id=1)

    async def owned_project(db, project_id, user):
        return SimpleNamespace(id=project_id, params={})

    async def load_frags(db, episode_id):
        return [frag]

    async def dub_active(db, fragment_id):
        return fragment_id == 9

    monkeypatch.setattr(episodes, "get_owned_episode", owned_episode)
    monkeypatch.setattr(episodes, "get_owned_drama_project", owned_project)
    monkeypatch.setattr(episodes, "load_episode_fragments", load_frags)
    monkeypatch.setattr(episodes, "has_active_fragment_dub_task", dub_active)
    return frag


async def test_generate_rejected_while_dub_task_active(patched):
    with pytest.raises(AppError) as exc_info:
        await episodes.generate_episode(1, DramaGenerateRequest(fragment_ids=[9]), db=SimpleNamespace(),
                                        user=SimpleNamespace(id=1))
    assert exc_info.value.code == "drama.dub_fragment_generating"
    assert "generation" not in patched.params


async def test_activate_version_rejected_while_dub_task_active(patched):
    class _Db:
        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: patched)

    with pytest.raises(AppError) as exc_info:
        await episodes.activate_video_version(9, DramaActivateVideoVersionRequest(version_id="v1"), db=_Db(),
                                              user=SimpleNamespace(id=1))
    assert exc_info.value.code == "drama.dub_fragment_generating"
    assert patched.video == "/v/d.mp4"
