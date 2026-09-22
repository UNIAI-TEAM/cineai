# -*- coding: utf-8 -*-
"""按 TaskRun 估算预扣金额：provider_rates × 功能 slot 内最贵模型（mục 6.2 spec）。"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.models import Project
from app.models_tasks import TaskRun
from app.services.billing.rate_quotes import image_unit_fen, text_fen, tts_fen, video_fen
from app.services.kepu_stages import (
    normalize_kepu_pipeline_phase,
    project_audio_ready,
    resolve_kepu_billing_phase,
    shot_image_ready,
    shot_video_ready,
)

__all__ = [
    "estimate_phase_fen",
    "estimate_task_fen",
    "resolve_kepu_billing_phase",
]


def _kepu_video_resolution(project: Project | None, settings: Settings) -> str:
    """科普成片清晰度：设置项；HD 且配置为 480p 时升到 720p（与 pipeline 一致）。"""
    raw = str(getattr(settings, "ark_video_resolution", "") or "480p")
    mode = str(getattr(project, "resolution_mode", "") or "")
    if mode == "hd" and raw.strip().lower() == "480p":
        return "720p"
    return raw


def _drama_video_resolution(payload: dict) -> str:
    """漫剧成片默认 720p，与前端与 asset_video 缺省一致。"""
    prepared = payload.get("prepared") if isinstance(payload.get("prepared"), dict) else {}
    raw = str((prepared or {}).get("resolution") or payload.get("resolution") or "").strip()
    return raw or "720p"


def _buffered_fen(fen: int, settings: Settings) -> int:
    """token / 时长类估价乘缓冲；结果至少 1 分。"""
    buf = float(settings.billing_estimate_buffer or 1.2)
    return max(1, math.ceil(max(0, int(fen)) * buf))


def _current_snapshot() -> Any:
    """Một snapshot routing dùng chung cho cả lần ước tính (tránh đọc cấu hình đổi giữa chừng)."""
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def _llm_fen(function_id: str, settings: Settings, snapshot: Any, *, calls: int = 1) -> int:
    """LLM：hằng số token ước tính × số lần gọi × giá model đắt nhất của chức năng, nhân buffer."""
    tokens = int(settings.billing_est_llm_tokens) * max(int(calls), 1)
    return _buffered_fen(text_fen(function_id, tokens, settings=settings, snapshot=snapshot), settings)


def _tts_fen(function_id: str, settings: Settings, snapshot: Any, *, units: int = 1) -> int:
    """TTS：hằng số token ước tính × số đoạn × giá model đắt nhất của chức năng giọng, nhân buffer."""
    tokens = int(settings.billing_est_tts_tokens) * max(int(units), 1)
    return _buffered_fen(tts_fen(function_id, tokens, settings=settings, snapshot=snapshot), settings)


def _image_fen(function_id: str, settings: Settings, snapshot: Any) -> int:
    """Ảnh：giá/ảnh cao nhất của chức năng, không nhân buffer (đã là giá quyết toán)."""
    return image_unit_fen(function_id, settings=settings, snapshot=snapshot)


def _estimate_assets_fen(project: Project, settings: Settings, snapshot: Any) -> int:
    """只估尚未完成的出图 + 整片配音（不含镜头视频）。"""
    shots = list(project.shots or [])
    need_img = sum(1 for s in shots if not shot_image_ready(s))
    need_tts = 0 if project_audio_ready(project) else 1
    if need_img <= 0 and need_tts <= 0:
        return 1
    total = max(need_img, 0) * _image_fen("kepu.image", settings, snapshot)
    if need_tts > 0:
        total += _tts_fen("kepu.tts", settings, snapshot, units=max(len(shots), 1))
    return max(total, 1)


def _estimate_videos_fen(project: Project, settings: Settings, snapshot: Any) -> int:
    """只估尚未出片的镜头视频；逐镜计价后整体乘缓冲。"""
    shots = [s for s in list(project.shots or []) if not shot_video_ready(s)]
    if not shots:
        return 1
    resolution = _kepu_video_resolution(project, settings)
    total = sum(
        video_fen("kepu.video", max(float(sh.duration or 4), 2.0), resolution=resolution,
                  settings=settings, snapshot=snapshot)
        for sh in shots
    )
    return _buffered_fen(total, settings)


def estimate_phase_fen(
    project: Project,
    phase: str,
    settings: Settings | None = None,
    *,
    snapshot: Any | None = None,
) -> int:
    """科普 pipeline 阶段估算：script | assets | videos | compose | produce(兼容→下一段)。"""
    s = settings or get_settings()
    snap = snapshot if snapshot is not None else _current_snapshot()
    raw = normalize_kepu_pipeline_phase(phase, project)
    if raw == "script":
        return _llm_fen("kepu.script", s, snap)
    if raw == "videos":
        return _estimate_videos_fen(project, s, snap)
    if raw == "compose":
        return 1
    return _estimate_assets_fen(project, s, snap)


async def _drama_video_duration(db: AsyncSession, task: TaskRun, payload: dict) -> float:
    """漫剧视频时长：payload → prepared → 分镜正文 @duration → 8 秒。"""
    dur = float(payload.get("duration_sec") or payload.get("duration") or 0)
    if dur <= 0 and isinstance(payload.get("prepared"), dict):
        dur = float(payload["prepared"].get("duration") or 0)
    if dur <= 0:
        frag_ids = payload.get("fragment_ids")
        frag_id = task.fragment_id or ((frag_ids or [None])[0] if isinstance(frag_ids, list) else None)
        if frag_id:
            from app.models_drama import DramaEpisodeFragment
            from app.services.drama.fragment_content_duration import resolve_seedance_duration_from_content

            frag = await db.get(DramaEpisodeFragment, int(frag_id))
            if frag is not None:
                dur = float(resolve_seedance_duration_from_content(
                    frag.content or "", fallback=int(frag.duration_sec or 8)))
    return dur if dur > 0 else 8.0


async def estimate_task_fen(db: AsyncSession, task: TaskRun, settings: Settings | None = None) -> int:
    """按 domain + task_type 估算单任务预扣（分）。"""
    s = settings or get_settings()
    snap = _current_snapshot()
    domain = (task.domain or "").strip()
    task_type = (task.task_type or "").strip()
    payload = task.payload if isinstance(task.payload, dict) else {}

    if domain == "kepu":
        if task_type == "project_pipeline":
            project_id = task.project_id or payload.get("project_id")
            project = None
            if project_id:
                result = await db.execute(
                    select(Project).where(Project.id == int(project_id)).options(selectinload(Project.shots))
                )
                project = result.scalar_one_or_none()
            if not project:
                return _llm_fen("kepu.script", s, snap)
            return estimate_phase_fen(project, str(payload.get("phase") or "script"), settings=s, snapshot=snap)
        if task_type == "shot_regen_image":
            return _image_fen("kepu.image", s, snap)
        if task_type == "shot_regen_video":
            project_id = task.project_id or payload.get("project_id")
            project = await db.get(Project, int(project_id)) if project_id else None
            fen = video_fen("kepu.video", max(float(payload.get("duration") or 5), 2.0),
                            resolution=_kepu_video_resolution(project, s), settings=s, snapshot=snap)
            return _buffered_fen(fen, s)
        if task_type in {"shot_regen_audio", "project_regen_audio"}:
            return _tts_fen("kepu.tts", s, snap, units=3)
        if task_type == "project_compose_only":
            return 1
        if task_type == "content_expand":
            return _llm_fen("kepu.script", s, snap)

    if domain == "drama":
        if task_type in {"script_summary", "fragment_plan", "agent_chat", "skill_optimize", "voice_prompt"}:
            return _llm_fen("drama.script", s, snap)
        if task_type == "episode_script":
            total_eps = int(payload.get("total") or payload.get("episode_count") or 1)
            return _llm_fen("drama.script", s, snap, calls=total_eps)
        if task_type == "seed_assets":
            return _llm_fen("drama.script", s, snap, calls=3)
        if task_type == "asset_image":
            return _image_fen("drama.asset_image", s, snap)
        if task_type in {"asset_video", "fragment_video"}:
            dur = await _drama_video_duration(db, task, payload)
            fen = _buffered_fen(video_fen("drama.video", max(dur, 2.0), resolution=_drama_video_resolution(payload),
                                          settings=s, snapshot=snap), s)
            if task_type == "fragment_video":
                fen += max(1, _image_fen("drama.asset_image", s, snap) // 2)
            return fen
        if task_type == "voice_synthesis":
            return _tts_fen("drama.tts", s, snap)

    if domain in {"api", "studio"}:
        if task_type in {"v1_image", "tool_image"}:
            return _image_fen("tools.image", s, snap)
        if task_type in {"v1_video", "v1_seedance", "tool_video"}:
            resolution = str(payload.get("resolution") or "").strip() or "480p"
            fen = video_fen("tools.video", max(float(payload.get("duration") or 5), 2.0), resolution=resolution,
                            settings=s, snapshot=snap)
            return _buffered_fen(fen, s)

    return _llm_fen("drama.script", s, snap)
