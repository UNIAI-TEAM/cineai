"""Lồng tiếng một phân cảnh: TTS từng câu thoại → trộn lên video Seedance (giữ tiếng môi trường) → thay fragment.video."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.models import User
from app.models_drama import DramaAsset, DramaEpisodeFragment, DramaFragmentAssetRef, DramaProject
from app.services import storage
from app.services.ark import get_ark
from app.services.billing import record_line
from app.services.content_lang import project_content_lang
from app.services.drama.build_seedance_generate_body import resolve_character_prompt_name
from app.services.drama.dub_lines import extract_dub_lines
from app.services.drama.dub_voices import CharacterVoice, resolve_line_speaker, voice_source_asset_id
from app.services.drama.job_errors import gen_error_fields, with_error_code
from app.services.drama.voice_synthesis import _drama_tts_model, infer_character_speaker, usable_speaker
from app.services.dub_mix import run_dub_mix
from app.services.voice_lang import default_voice_for_lang

logger = logging.getLogger(__name__)


def _dub_params(fragment: Any) -> dict[str, Any]:
    """params.dub hiện tại (dict rỗng nếu chưa có)."""
    params = fragment.params if isinstance(fragment.params, dict) else {}
    dub = params.get("dub")
    return dub if isinstance(dub, dict) else {}


def dub_source_video(fragment: Any) -> str:
    """Video gốc của bản đang dùng: bản hiện tại là bản đã lồng → sourceVideo; ngược lại chính fragment.video."""
    video = (fragment.video or "").strip()
    dub = _dub_params(fragment)
    src = str(dub.get("sourceVideo") or "").strip()
    if src and str(dub.get("url") or "").strip() == video:
        return src
    return video


def _write_dub(fragment: Any, dub: dict[str, Any]) -> dict[str, Any]:
    """Ghi params.dub (gán dict mới để SQLAlchemy nhận thay đổi JSON)."""
    params = dict(fragment.params or {}) if isinstance(fragment.params, dict) else {}
    params["dub"] = {**dub, "updatedAt": datetime.now(UTC).isoformat()}
    fragment.params = params
    return params["dub"]


async def _fragment_asset_names(db: AsyncSession, fragment: Any) -> dict[int, str]:
    """{asset_id: tên hiển thị} của tư liệu gắn với phân cảnh (để thay @asset:N trong lời thoại)."""
    rows = (
        await db.execute(
            select(DramaAsset)
            .join(DramaFragmentAssetRef, DramaFragmentAssetRef.asset_id == DramaAsset.id)
            .where(DramaFragmentAssetRef.fragment_id == fragment.id)
        )
    ).scalars().all()
    return {a.id: resolve_character_prompt_name({"name": a.name, "params": a.params or {}}) for a in rows}


async def load_dub_voices(db: AsyncSession, project: Any, lang: str) -> tuple[list[CharacterVoice], str]:
    """Giọng từng nhân vật (tư liệu giọng đã gắn → speaker; không có thì suy theo mô tả) và giọng lời dẫn."""
    assets = (
        await db.execute(select(DramaAsset).where(DramaAsset.project_id == project.id))
    ).scalars().all()
    by_id = {a.id: a for a in assets}
    characters: list[CharacterVoice] = []
    narrator = ""
    for asset in assets:
        kind = (asset.type or "").lower()
        if kind not in ("character", "narration"):
            continue
        params = asset.params or {}
        voice = by_id.get(voice_source_asset_id(params) or 0)
        vparams = (voice.params or {}) if voice is not None else {}
        speaker = str(vparams.get("speaker") or "").strip()
        prompt = str(vparams.get("voicePrompt") or params.get("voicePrompt") or "")
        if not usable_speaker(speaker, lang, voice_prompt=prompt, character_name=asset.name):
            speaker = infer_character_speaker(prompt, asset.name, key_asset_id=asset.id, lang=lang)
        if kind == "narration":
            narrator = narrator or speaker
            continue
        names = tuple(
            dict.fromkeys(
                n for n in (resolve_character_prompt_name({"name": asset.name, "params": params}), asset.name) if n
            )
        )
        characters.append(CharacterVoice(asset_id=asset.id, names=names, speaker=speaker))
    narrator = narrator or default_voice_for_lang(lang) or get_settings().volc_tts_speaker
    return characters, narrator


async def _ensure_local_video(url: str) -> Path:
    """Đường dẫn cục bộ của video (tải về nếu mới có bản trên OSS)."""
    local = storage.local_path_from_url(url)
    if local is not None:
        if not local.exists():
            await storage.ensure_local_media(url, local)
        if local.exists():
            return local
    raise AppError("drama.dub_no_video")


async def dub_fragment(
    db: AsyncSession,
    user: User,
    project: DramaProject,
    fragment: DramaEpisodeFragment,
    *,
    task_run_id: int | None = None,
) -> dict[str, Any]:
    """Lồng tiếng phân cảnh; thành công/skip trả params.dub, lỗi thì ghi failed (giữ video gốc) rồi raise lại."""
    source = dub_source_video(fragment)
    if not source:
        raise AppError("drama.dub_no_video")
    lang = project_content_lang(project)
    lines = extract_dub_lines(fragment.content or "", await _fragment_asset_names(db, fragment))
    if not lines:
        fragment.video = source
        dub = _write_dub(fragment, {"status": "skipped", "url": None, "sourceVideo": source, "lines": []})
        await db.commit()
        return dub
    # Ghi "running" nhưng bỏ dấu vết lỗi của lần chạy trước (nếu có), tránh mang error_code cũ sang lần này
    prev = {k: v for k, v in _dub_params(fragment).items() if k not in ("error", "error_code", "error_params")}
    _write_dub(fragment, {**prev, "status": "running"})
    await db.commit()
    try:
        characters, narrator = await load_dub_voices(db, project, lang)
        stamp = int(time.time())
        clips: list[tuple[Path, float | None]] = []
        meta: list[dict[str, Any]] = []
        for idx, line in enumerate(lines):
            speaker = resolve_line_speaker(line, characters, lang=lang, narrator=narrator)
            url = await get_ark().tts(
                line.text,
                speaker,
                function_id="drama.tts",
                project_id=project.id,
                emotion_hint=line.emotion or None,
                lang=lang,
                out_name=f"dub_f{fragment.id}_{stamp}_{idx:02d}.mp3",
            )
            path = storage.local_path_from_url(url or "")
            if path is None or not path.exists():
                raise AppError("drama.dub_failed")
            clips.append((path, line.start_sec))
            meta.append({"kind": line.kind, "name": line.speaker, "speaker": speaker, "text": line.text})
        video_local = await _ensure_local_video(source)
        dest = storage.project_dir(project.id) / f"shot_{fragment.id}_{stamp}_dub.mp4"
        plan = await asyncio.to_thread(run_dub_mix, video_local, clips, dest)
        rel = storage.rel_static_url(dest)
        dubbed = storage.republish_url(rel, sync=True) or rel
        # Ghi thành công + tính tiền cùng trong vùng bảo vệ: record_line lỗi cũng phải rơi về "failed", giữ video gốc
        fragment.video = dubbed
        dub = _write_dub(fragment, {
            "status": "done", "url": dubbed, "sourceVideo": source, "lines": meta,
            "tempo": plan.tempo, "freezeSec": plan.freeze_sec,
        })
        await record_line(
            db,
            user_id=user.id,
            drama_project_id=project.id,
            billing_key="tts",
            model=_drama_tts_model() or get_settings().model_audio,
            tokens=sum(len(m["text"]) for m in meta),
            domain="drama",
            task_run_id=task_run_id,
        )
        await db.commit()
        return dub
    except Exception as exc:  # noqa: BLE001
        code, params = gen_error_fields(exc)
        logger.warning("lồng tiếng lỗi fragment_id=%s err=%s", fragment.id, exc)
        # DB có thể đã ở trạng thái aborted (vd. load_dub_voices/record_line lỗi giữa transaction):
        # rollback + refresh trước khi ghi lại, tránh commit tiếp raise đè lên lỗi gốc hoặc âm thầm no-op
        await db.rollback()
        await db.refresh(fragment)
        fragment.video = source
        _write_dub(fragment, with_error_code(
            {"status": "failed", "url": None, "sourceVideo": source, "error": str(exc)[:300]},
            code or "drama.dub_failed",
            params,
        ))
        try:
            await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("lồng tiếng: ghi trạng thái failed cũng lỗi fragment_id=%s", fragment.id)
        raise
