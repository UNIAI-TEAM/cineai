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
from app.database import AsyncSessionLocal
from app.errors import AppError
from app.models import User
from app.models_drama import DramaAsset, DramaEpisode, DramaEpisodeFragment, DramaFragmentAssetRef, DramaProject
from app.models_tasks import TaskRun
from app.schemas_tasks import TaskCreateRequest
from app.services import storage
from app.services.ark import get_ark
from app.services.billing import record_line
from app.services.content_lang import project_content_lang
from app.services.drama.build_seedance_generate_body import resolve_character_prompt_name
from app.services.drama.dub_lines import extract_dub_lines
from app.services.drama.dub_voices import CharacterVoice, resolve_line_speaker, voice_source_asset_id
from app.services.drama.generation import fragment_generation_status
from app.services.drama.job_errors import gen_error_fields, with_error_code
from app.services.drama.voice_synthesis import _drama_tts_model, infer_character_speaker, usable_speaker
from app.services.dub_mix import run_dub_mix
from app.services.tasks.service import ACTIVE_TASK_STATUSES, create_task
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


async def has_active_fragment_dub_task(db: AsyncSession, fragment_id: int) -> bool:
    """Phân cảnh có TaskRun("drama","fragment_dub") nào CHƯA ở trạng thái kết thúc không.

    Dùng để chặn bấm đúp thay vì đọc params.dub.status: cờ "running" trên params có thể bị treo
    vĩnh viễn khi task kết thúc bất thường trước khi kịp ghi lại (freeze lỗi / cancel / lỗi ngay
    đầu dub_fragment) — tra task thật theo ACTIVE_TASK_STATUSES thì không bao giờ khoá cứng.
    """
    result = await db.execute(
        select(TaskRun.id)
        .where(
            TaskRun.domain == "drama",
            TaskRun.task_type == "fragment_dub",
            TaskRun.fragment_id == fragment_id,
            TaskRun.status.in_(tuple(ACTIVE_TASK_STATUSES)),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def assert_fragment_dubbable(fragment: Any, *, dub_task_active: bool) -> None:
    """4 điều kiện lồng tiếng lại: video không đang generate, đúng chế độ dub, đã có video, chưa có task fragment_dub nào đang chạy.

    dub_task_active: kết quả has_active_fragment_dub_task của gọi trước đó (endpoint tự truy vấn).
    """
    status = str(fragment_generation_status(fragment).get("status") or "")
    if status in {"queued", "running", "generating"}:
        raise AppError("drama.dub_fragment_generating")
    if (fragment.params or {}).get("voice_mode") != "dub":
        raise AppError("drama.dub_not_enabled")
    if not (fragment.video or "").strip():
        raise AppError("drama.dub_no_video")
    if dub_task_active:
        raise AppError("drama.dub_fragment_generating")


async def mark_fragment_dub_ended(db: AsyncSession, task: TaskRun, status: str) -> None:
    """Task fragment_dub thất bại/bị huỷ mà params.dub vẫn "running": đóng lại thành "failed" có error_code.

    Không có mã lỗi task.cancelled riêng trong danh mục hiện tại nên nhánh "cancelled" cũng ghi
    status="failed" (chỉ khác error_code khi mã đó tồn tại); mục đích chỉ là không để guard 4 của
    assert_fragment_dubbable/has_active_fragment_dub_task bị đánh lừa bởi cờ params treo mãi.
    Gọi trong CÙNG session của executor (không mở session riêng) — lỗi tại đây không được raise,
    caller (executor._fail_task*/_mark_cancelled) tự try/except + log.
    """
    if (task.task_type or "") != "fragment_dub" or not task.fragment_id:
        return
    fragment = await db.get(DramaEpisodeFragment, int(task.fragment_id))
    if not fragment:
        return
    dub = _dub_params(fragment)
    if str(dub.get("status") or "") != "running":
        return
    from app.errors import ERRORS

    task_error_code = getattr(task, "error_code", None)
    if status == "cancelled" and "task.cancelled" in ERRORS:
        code, params = "task.cancelled", None
    elif task_error_code in ERRORS:
        code, params = task_error_code, getattr(task, "error_params", None)
    else:
        code, params = "drama.dub_failed", None
    # Giữ nguyên url/sourceVideo cũ (nếu có) — chỉ đổi status + error, KHÔNG suy lại từ fragment.video:
    # đang re-dub thì fragment.video vẫn là bản đã lồng cũ (D), nếu lấy làm sourceVideo thì lần lồng
    # tiếp theo sẽ trộn TTS đè lên chính audio đã lồng thay vì video gốc (R). Hook không đổi fragment.video
    # nên cặp url/sourceVideo cũ (ghi lại nguyên vẹn khi enqueue_fragment_dub chuyển sang "running") vẫn đúng.
    prev = {k: v for k, v in dub.items() if k not in ("error", "error_code", "error_params")}
    _write_dub(fragment, with_error_code({**prev, "status": "failed"}, code, params))


async def enqueue_fragment_dub(
    db: AsyncSession,
    user: User,
    fragment: DramaEpisodeFragment,
    *,
    drama_project_id: int,
    episode_id: int,
) -> TaskRun:
    """Ghi params.dub=running (bỏ lỗi cũ) rồi vào hàng đợi TaskRun("drama","fragment_dub") qua task platform.

    Việc lồng tiếng thật chạy trong _run_drama_fragment_dub (handlers.py) → run_fragment_dub_job,
    độc lập phiên/billing với task video: tránh mất trạng thái do dub_fragment tự rollback nội bộ,
    và tách hẳn phí TTS khỏi vòng đời task video (không còn đua với reconcile/settle của task video).
    """
    lines = extract_dub_lines(fragment.content or "", await _fragment_asset_names(db, fragment))
    line_count = max(len(lines), 1)
    prev = {k: v for k, v in _dub_params(fragment).items() if k not in ("error", "error_code", "error_params")}
    _write_dub(fragment, {**prev, "status": "running"})
    task = await create_task(
        db,
        user,
        TaskCreateRequest(
            domain="drama",
            task_type="fragment_dub",
            dedupe_key=f"drama:fragment_dub:fragment:{fragment.id}",
            payload={"fragment_id": fragment.id, "line_count": line_count},
            drama_project_id=drama_project_id,
            episode_id=episode_id,
            fragment_id=fragment.id,
        ),
        commit=False,
    )
    await db.commit()
    return task


async def enqueue_fragment_dub_after_video(
    fragment_id: int,
    user_id: int,
    *,
    drama_project_id: int,
    episode_id: int,
) -> None:
    """Sau khi video xong: mở phiên RIÊNG (không đụng db/task của finalize) để tự vào hàng đợi lồng tiếng.

    Bỏ qua nếu phân cảnh đã có task fragment_dub đang hoạt động (task đó sẽ tự lồng nguồn hiện tại
    khi chạy, không cần thêm task trùng). Lỗi enqueue (kể cả không đủ số dư) ghi best-effort
    params.dub.status=failed rồi thôi; không bao giờ raise ra ngoài, để một lượt tự động lồng tiếng
    hỏng không kéo theo việc hoàn tất task video bị ảnh hưởng.
    """
    async with AsyncSessionLocal() as db:
        try:
            fragment = await db.get(DramaEpisodeFragment, fragment_id)
            user = await db.get(User, user_id)
            if not fragment or not user:
                return
            if await has_active_fragment_dub_task(db, fragment_id):
                return
            await enqueue_fragment_dub(
                db, user, fragment, drama_project_id=drama_project_id, episode_id=episode_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("tự động lồng tiếng: vào hàng đợi lỗi fragment_id=%s err=%s", fragment_id, exc)
            code = exc.code if isinstance(exc, AppError) else None
            params = getattr(exc, "params", None)
            if not (code and code.startswith("billing.")):
                code, params = "drama.dub_failed", None
            # create_task/enqueue có thể raise trước khi kịp commit; rollback rồi ghi failed riêng, best-effort.
            await db.rollback()
            frag = await db.get(DramaEpisodeFragment, fragment_id)
            if not frag:
                return
            # Khác với mark_fragment_dub_ended: ở đây dùng frag.video làm sourceVideo LÀ ĐÚNG, vì hàm này
            # chỉ gọi ngay sau apply_fragment_video_assets — apply đã pop hẳn params.dub cũ, nên frag.video
            # lúc này chắc chắn là video thô (native) vừa áp, không phải bản đã lồng tiếng trước đó; và vì
            # params.dub cũ đã bị pop nên không có url/sourceVideo nào để giữ lại cả (khởi tạo mới hoàn toàn).
            _write_dub(frag, with_error_code(
                {"status": "failed", "sourceVideo": frag.video},
                code,
                params,
            ))
            try:
                await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception(
                    "tự động lồng tiếng: ghi trạng thái failed cũng lỗi fragment_id=%s", fragment_id
                )


async def run_fragment_dub_job(task_run_id: int, fragment_id: int, user_id: int) -> dict[str, Any]:
    """Executor thật của TaskRun("drama","fragment_dub"): mở phiên RIÊNG của job (tách khỏi phiên executor).

    Nạp tường minh fragment → episode → project (tránh lazy-load async) rồi user, gọi dub_fragment.
    Không bắt exception ở đây: để nó lan ra ngoài, executor.py sẽ tự mở phiên mới để fail task + settle
    hoàn phí — dub_fragment.rollback() nội bộ chỉ tác động phiên của chính job này, không đụng tới
    phiên/đối tượng TaskRun mà executor đang giữ.
    """
    async with AsyncSessionLocal() as db:
        fragment = await db.get(DramaEpisodeFragment, fragment_id)
        if fragment is None:
            raise RuntimeError(f"phân cảnh không tồn tại: {fragment_id}")
        episode = await db.get(DramaEpisode, fragment.episode_id)
        if episode is None:
            raise RuntimeError(f"tập phim không tồn tại cho fragment_id={fragment_id}")
        project = await db.get(DramaProject, episode.project_id)
        if project is None:
            raise RuntimeError(f"dự án không tồn tại cho fragment_id={fragment_id}")
        user = await db.get(User, user_id)
        if user is None:
            raise RuntimeError(f"user không tồn tại: {user_id}")
        dub = await dub_fragment(db, user, project, fragment, task_run_id=task_run_id)
        return {"ok": True, "status": dub.get("status")}
