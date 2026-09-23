"""Tên mặc định phim ngắn theo ngôn ngữ nội dung dự án; dữ liệu tiếng Trung cũ vẫn được nhận là tên giữ chỗ."""
from app.services.drama.agents import _titles_ready, append_manual_episode, merge_episode_bodies
from app.services.drama.fragment_plan import _build_opening_cue_lines
from app.services.drama.naming import (
    default_asset_name,
    default_canvas_node_name,
    default_episode_title,
    default_voice_name,
    is_default_episode_title,
)


def test_default_names_follow_content_lang():
    assert default_episode_title(3) == "第 3 集"
    assert default_episode_title(3, "zh", compact=True) == "第3集"
    assert default_episode_title(3, "vi") == "Tập 3"
    assert default_episode_title(3, "en-US") == "Episode 3"
    assert default_asset_name() == "未命名资产"
    assert default_asset_name("vi") == "Chưa đặt tên"
    assert default_voice_name("en") == "Untitled voice"
    assert default_canvas_node_name("n1", "vi") == "Nút n1"
    assert default_canvas_node_name("n1") == "节点 n1"


def test_placeholder_titles_in_any_language():
    for title in ("第 3 集", "第3集", "Tập 3", "episode 3"):
        assert is_default_episode_title(title, 3)
    assert not is_default_episode_title("Tập 3", 4)
    assert not is_default_episode_title("Bến sông lúc bình minh")


def test_titles_ready_treats_vi_placeholders_as_missing():
    placeholders = [{"episodeNumber": n, "title": f"Tập {n}"} for n in (1, 2)]
    assert _titles_ready(placeholders, 2) is False
    real = [{"episodeNumber": 1, "title": "Gặp gỡ"}, {"episodeNumber": 2, "title": "Chia ly"}]
    assert _titles_ready(real, 2) is True


def test_merge_keeps_real_title_over_vi_placeholder():
    merged = merge_episode_bodies(
        [{"episodeNumber": 1, "title": "Gặp gỡ", "body": ""}],
        [{"episodeNumber": 1, "title": "Tập 1", "body": "nội dung"}],
        prefer_incoming=True,
    )
    assert merged[0]["title"] == "Gặp gỡ"


def test_manual_episode_default_title_uses_lang():
    episodes, number = append_manual_episode([], lang="vi")
    assert number == 1 and episodes[0]["title"] == "Tập 1"
    episodes, _ = append_manual_episode([])
    assert episodes[0]["title"] == "第 1 集"


def test_opening_cue_episode_number_follows_lang():
    kwargs = dict(project_title="", story_type="", one_line_story="", background_blurb="")
    zh = _build_opening_cue_lines(episode_number=2, episode_name="重逢", **kwargs)
    assert zh[0] == "【片头·集号叠字】第2集｜重逢"
    vi = _build_opening_cue_lines(episode_number=2, episode_name="第2集", lang="vi", **kwargs)
    assert vi[0] == "【片头·集号叠字】Tập 2"
