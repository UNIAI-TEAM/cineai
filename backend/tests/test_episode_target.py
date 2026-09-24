"""单集目标时长：解析优先级、分镜预算、剧本篇幅与提示词注入。"""

import json
from pathlib import Path

from app.services.drama.build_fragments import EPISODE_DURATION_BUDGET_SEC, EPISODE_FRAGMENT_MAX
from app.services.drama.episode_target import (
    EPISODE_FRAGMENT_MAX_AUTO,
    EPISODE_TARGET_DEFAULT,
    EPISODE_TARGET_OPTIONS,
    episode_content_length,
    episode_fragment_budget,
    episode_min_content_chars,
    fragment_count_range,
    normalize_episode_target_sec,
    resolve_episode_target_sec,
)
from app.services.drama.fragment_budget import FRAGMENT_TOTAL_MAX
from app.services.drama.fragment_plan_prompt import build_fragment_plan_user_prompt

_TABLE = Path(__file__).parent / "fixtures" / "episode_target_table.json"


def test_resolve_prefers_episode_then_project_then_default():
    assert resolve_episode_target_sec({"episodeTargetSec": 30}, {"episodeTargetSec": 120}) == 30
    assert resolve_episode_target_sec({}, {"episodeTargetSec": 120}) == 120
    assert resolve_episode_target_sec(None, None) == EPISODE_DURATION_BUDGET_SEC
    # 0 = 自动，是合法值，不能被当成缺省
    assert resolve_episode_target_sec({"episodeTargetSec": 0}, {"episodeTargetSec": 120}) == 0
    # 非法值跳过
    assert resolve_episode_target_sec({"episodeTargetSec": 45}, {"episodeTargetSec": "60"}) == 60


def test_normalize_rejects_unknown_values():
    assert normalize_episode_target_sec(True) is None
    assert normalize_episode_target_sec("abc") is None
    assert normalize_episode_target_sec(75) is None
    assert normalize_episode_target_sec("180") == 180


def test_fragment_budget_keeps_legacy_default_and_auto_unbounded_total():
    assert episode_fragment_budget(EPISODE_DURATION_BUDGET_SEC) == (EPISODE_FRAGMENT_MAX, EPISODE_DURATION_BUDGET_SEC)
    assert episode_fragment_budget(0) == (EPISODE_FRAGMENT_MAX_AUTO, None)
    count_30, total_30 = episode_fragment_budget(30)
    assert total_30 == 30 and 3 <= count_30 <= 5
    count_180, _ = episode_fragment_budget(180)
    assert count_180 > EPISODE_FRAGMENT_MAX


def test_content_length_scales_and_min_gate_relaxes_for_short_targets():
    short_target, short_min, _ = episode_content_length(30)
    long_target, long_min, _ = episode_content_length(180)
    assert short_target < long_target
    assert short_min < 450
    assert long_min == 450
    assert episode_min_content_chars({"episodeTargetSec": 30}) == short_min
    assert episode_min_content_chars(None) == 450


def _prompt(target_sec: int) -> str:
    return build_fragment_plan_user_prompt(
        episode_name="第一集",
        episode_body="### 场1-1\n日 外 街道\n△ 画面。",
        asset_catalog=[],
        episode_number=1,
        target_sec=target_sec,
    )


def test_fragment_plan_prompt_uses_target():
    assert "30 秒" in _prompt(30)
    assert "2 分钟" in _prompt(120)
    assert "自动" in _prompt(0)
    assert "60–90 秒" not in _prompt(180)


def test_min_chars_prefers_episode_override():
    # 单集操作：分集覆盖优先于项目设置
    assert episode_min_content_chars({"episodeTargetSec": 90}, {"episodeTargetSec": 30}) == 150
    assert episode_min_content_chars({"episodeTargetSec": 30}, {}) == 150
    assert episode_min_content_chars({"episodeTargetSec": 30}, None) == 150


def test_shared_table_matches_backend():
    """与前端 lib/dramaEpisodeTarget.ts 共用的预算表（tests/fixtures/episode_target_table.json），防止两边公式漂移。"""
    table = json.loads(_TABLE.read_text(encoding="utf-8"))
    assert table["default_target_sec"] == EPISODE_TARGET_DEFAULT
    assert table["fragment_max_sec"] == FRAGMENT_TOTAL_MAX
    assert [row["target_sec"] for row in table["rows"]] == list(EPISODE_TARGET_OPTIONS)
    for row in table["rows"]:
        target = row["target_sec"]
        assert list(episode_fragment_budget(target)) == [row["max_fragments"], row["max_total_sec"]], target
        rng = fragment_count_range(target)
        assert (list(rng) if rng else None) == row["shot_range"], target
        assert episode_content_length(target)[1] == row["min_body_chars"], target
