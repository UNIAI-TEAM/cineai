"""单集目标成片时长：分集 params 优先，回退项目 params；决定分镜条数/总时长预算与剧本篇幅提示。"""

from __future__ import annotations

import math
from typing import Any

from app.services.drama.build_fragments import (
    EPISODE_DURATION_BUDGET_SEC,
    EPISODE_FRAGMENT_MAX,
)

# 0 = 自动（按剧本内容，不压缩）
EPISODE_TARGET_AUTO = 0
EPISODE_TARGET_OPTIONS = (0, 30, 60, 90, 120, 180)
EPISODE_TARGET_DEFAULT = EPISODE_DURATION_BUDGET_SEC
# 自动模式下的条数安全上限（防止异常长剧本一次排出过多视频任务）
EPISODE_FRAGMENT_MAX_AUTO = 30
# 平均单镜秒数：用于由目标时长推算条数上限（90s → 10 条，与旧默认一致）
_AVG_FRAGMENT_SEC = 9


def normalize_episode_target_sec(raw: Any) -> int | None:
    # 合法选项返回秒数，非法/缺省返回 None
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value in EPISODE_TARGET_OPTIONS else None


def resolve_episode_target_sec(
    episode_params: dict | None,
    project_params: dict | None,
) -> int:
    # 分集 → 项目 → 默认 90s
    ep = episode_params if isinstance(episode_params, dict) else {}
    proj = project_params if isinstance(project_params, dict) else {}
    for value in (ep.get("episodeTargetSec"), proj.get("episodeTargetSec")):
        picked = normalize_episode_target_sec(value)
        if picked is not None:
            return picked
    return EPISODE_TARGET_DEFAULT


def episode_fragment_budget(target_sec: int) -> tuple[int, int | None]:
    """
    目标时长 → (最多条数, 总时长上限)。
    自动模式返回 (EPISODE_FRAGMENT_MAX_AUTO, None)：不按总时长压缩。
    """
    if not target_sec:
        return EPISODE_FRAGMENT_MAX_AUTO, None
    if target_sec == EPISODE_DURATION_BUDGET_SEC:
        return EPISODE_FRAGMENT_MAX, target_sec
    max_count = max(3, min(EPISODE_FRAGMENT_MAX_AUTO, math.ceil(target_sec / _AVG_FRAGMENT_SEC)))
    return max_count, target_sec


def format_target_label_zh(target_sec: int) -> str:
    # 提示词里的中文时长描述
    if target_sec % 60 == 0 and target_sec >= 60:
        return f"{target_sec // 60} 分钟"
    return f"{target_sec} 秒"


def fragment_plan_budget_lines(target_sec: int) -> list[str]:
    # 分镜提示词：条数与成片时长约束
    max_count, max_total = episode_fragment_budget(target_sec)
    if max_total is None:
        return [
            f"- 本集目标时长：自动（按场记内容完整拆分，不刻意压缩）；fragments 数组长度 ≤ {max_count}（含开幕镜）。",
        ]
    low = max(15, int(max_total * 0.7))
    return [
        f"- fragments 数组长度 ≤ {max_count}（含开幕镜）；整集成片目标 {low}–{max_total} 秒"
        f"（用户选择约 {format_target_label_zh(max_total)}）。",
        "- 场记内容超出目标时长时：保留主线冲突与反转，合并同场对白，删次要铺垫；不要把多场戏硬塞进一镜。",
    ]


# 默认单集篇幅（与 agents.TARGET/MIN_EPISODE_CONTENT_CHARS 一致，约 1–1.5 分钟成片）
_DEFAULT_CONTENT_CHARS = 550
_DEFAULT_MIN_CONTENT_CHARS = 450
_DEFAULT_SCENE_HINT = "2-3 场"


def episode_content_length(target_sec: int) -> tuple[int, int, str]:
    """
    目标时长 → (正文目标字数, 正文最少字数, 场次提示)。
    字数按中文口径（vi/en 由 localize_length_units 换算）；自动模式沿用默认篇幅。
    最少字数同时用于「正文是否完成 / 可否进入分镜」判定，短时长时按比例放宽。
    """
    if not target_sec:
        return _DEFAULT_CONTENT_CHARS, _DEFAULT_MIN_CONTENT_CHARS, _DEFAULT_SCENE_HINT
    target_chars = max(150, round(target_sec * 6.1))
    min_chars = min(_DEFAULT_MIN_CONTENT_CHARS, max(120, round(target_sec * 5)))
    if target_sec <= 30:
        scenes = "1 场"
    elif target_sec <= 60:
        scenes = "1-2 场"
    elif target_sec <= 120:
        scenes = "2-3 场"
    else:
        scenes = "3-4 场"
    return target_chars, min_chars, scenes


def episode_min_content_chars(project_params: dict | None) -> int:
    # 项目目标时长对应的正文最少字数（完成判定 / 进入分镜门槛）
    return episode_content_length(resolve_episode_target_sec(None, project_params))[1]
