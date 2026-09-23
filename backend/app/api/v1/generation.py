"""对外 REST API：生图 / 生视频 / Seedance 转发。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_api_user
from app.errors import AppError
from app.models import User
from app.models_tasks import TaskRun
from app.schemas_api import (
    V1GenerationOut,
    V1ImageGenerateRequest,
    V1SeedanceTaskRequest,
    V1VideoGenerateRequest,
)
from app.services.ark import get_ark
from app.services.billing import (
    run_billed_ephemeral,
    run_billed_ephemeral_deferred,
    settle_deferred_video_poll,
)
from app.services.billing.http import http_exception_for_billed_value_error
from app.services.drama.billing_util import record_seedream_image_usage
from app.services.studio_tools import poll_video_task, ratio_to_size
from app.services import storage

router = APIRouter(prefix="/v1", tags=["public-api"])

logger = logging.getLogger(__name__)

# 开放 API 视频任务失败：可安全透出的已登记错误码 → 固定英文短句（不含上游原文）
# poll_video_task（studio_tools._video_fail_code）只区分审核拦截与其他失败，故只登记 content_rejected
_V1_VIDEO_ERROR_TEXTS: dict[str, str] = {
    "provider.content_rejected": "The content was rejected by the model provider's moderation",
}
_V1_VIDEO_FALLBACK = ("api.upstream_failed", "Video generation failed at the model provider")


def _v1_video_task_error(data: dict) -> tuple[str, str]:
    """poll_video_task 结果 → (error_code, 英文短句)：已登记的安全码原样返回，其余归为 api.upstream_failed。"""
    code = str(data.get("error_code") or "")
    text = _V1_VIDEO_ERROR_TEXTS.get(code)
    return (code, text) if text else _V1_VIDEO_FALLBACK


def _upstream_failed(exc: BaseException) -> AppError:
    """上游生成失败：原文只进日志，响应只带错误码（不回传服务商原始报错）。"""
    logger.warning("v1 upstream failed: %s", str(exc)[:800])
    return AppError("api.upstream_failed")


async def _resolve_api_user(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
) -> User:
    from fastapi.security import HTTPAuthorizationCredentials

    creds = None
    if authorization and authorization.lower().startswith("bearer "):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=authorization[7:].strip())
    return await get_api_user(creds=creds, db=db, x_api_key=x_api_key)


@router.post("/images/generations", response_model=V1GenerationOut)
async def generate_image(
    body: V1ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_resolve_api_user),
) -> V1GenerationOut:
    """文生图 / 图生图（Seedream）。"""

    async def _exec() -> str:
        ark = get_ark()
        refs: list[str] | None = None
        prompt = body.prompt.strip()
        if body.image_url:
            refs = [body.image_url.strip()]
            prompt = f"{prompt}。在保持主体可识别的前提下适度改变风格"
        size = ratio_to_size(body.ratio)
        try:
            result = await ark.gen_image(
                prompt,
                body.negative,
                refs,
                function_id="tools.image",
                project_id=0,
                shot_no=user.id,
                size=size,
            )
        except AppError:
            # Lỗi cấu hình model phải giữ nguyên code/status, không bọc thành 502
            raise
        except Exception as exc:  # noqa: BLE001
            raise _upstream_failed(exc) from exc

        await record_seedream_image_usage(
            db,
            user_id=user.id,
            model=result.model or get_settings().model_image,
            domain="api",
            image_result=result,
            extra_raw={"source": "api_v1_image"},
        )
        url = result.local_url or result.remote_url or ""
        if url:
            url = storage.republish_url(url, sync=True) or url
        return url

    try:
        task, url = await run_billed_ephemeral(
            db,
            user,
            domain="api",
            task_type="v1_image",
            executor=_exec,
            payload={"prompt_len": len(body.prompt or "")},
            commit=True,
        )
    except ValueError as exc:
        raise http_exception_for_billed_value_error(exc) from exc

    return V1GenerationOut(
        status="succeeded",
        kind="image",
        urls=[url] if url else [],
        task_id=str(task.id),
    )


@router.post("/videos/generations", response_model=V1GenerationOut)
async def generate_video(
    body: V1VideoGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_resolve_api_user),
) -> V1GenerationOut:
    """首帧图 + 文案 → Seedance 图生视频，返回 task_id。"""

    async def _exec() -> str:
        ark = get_ark()
        try:
            upstream_id = await ark.gen_video_i2v(
                body.image_url.strip(),
                body.prompt.strip(),
                body.duration,
                function_id="tools.video",
                resolution=body.resolution,
                generate_audio=body.generate_audio,
            )
        except AppError:
            # Lỗi cấu hình model phải giữ nguyên code/status, không bọc thành 502
            raise
        except Exception as exc:  # noqa: BLE001
            raise _upstream_failed(exc) from exc

        return upstream_id

    try:
        task, upstream_id = await run_billed_ephemeral_deferred(
            db,
            user,
            domain="api",
            task_type="v1_video",
            executor=_exec,
            payload={"duration": body.duration},
            commit=True,
        )
    except ValueError as exc:
        raise http_exception_for_billed_value_error(exc) from exc

    return V1GenerationOut(
        status="queued",
        kind="video",
        task_id=upstream_id,
        preview_url=body.image_url,
        urls=[],
    )


@router.post("/seedance/tasks", response_model=V1GenerationOut)
async def forward_seedance(
    body: V1SeedanceTaskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_resolve_api_user),
) -> V1GenerationOut:
    """Chuyển tiếp body Seedance đa phương thức lên provider đang gán cho tools.video."""
    if not body.content:
        raise AppError("api.content_required")
    payload: dict = {
        "content": body.content,
        "resolution": body.resolution,
        "watermark": body.watermark,
        "generate_audio": body.generate_audio,
        "return_last_frame": body.return_last_frame,
    }
    if body.duration is not None:
        payload["duration"] = body.duration
    if body.ratio:
        payload["ratio"] = body.ratio

    async def _exec() -> str:
        ark = get_ark()
        try:
            upstream_id = await ark.gen_video_seedance_body(
                payload, function_id="tools.video", project_id=0
            )
        except AppError:
            # Lỗi cấu hình model phải giữ nguyên code/status, không bọc thành 502
            raise
        except Exception as exc:  # noqa: BLE001
            raise _upstream_failed(exc) from exc

        return upstream_id

    try:
        task, upstream_id = await run_billed_ephemeral_deferred(
            db,
            user,
            domain="api",
            task_type="v1_seedance",
            executor=_exec,
            payload={"duration": body.duration},
            commit=True,
        )
    except ValueError as exc:
        raise http_exception_for_billed_value_error(exc) from exc

    return V1GenerationOut(status="queued", kind="video", task_id=upstream_id, urls=[])


@router.get("/tasks/{task_id}", response_model=V1GenerationOut)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_resolve_api_user),
) -> V1GenerationOut:
    """查询 Seedance 视频任务状态（仅可查询本人提交的任务）。"""
    if not task_id.strip():
        raise AppError("api.task_id_required")
    tid = task_id.strip()
    # 归属校验：上游 task_id 本身是可传递的凭据，不校验会拖走他人视频
    owned_row = (
        await db.execute(
            select(TaskRun.id, TaskRun.provider_channel_id)
            .where(TaskRun.requested_by == user.id, TaskRun.provider_task_id == tid)
            .limit(1)
        )
    ).first()
    if owned_row is None:
        raise AppError("task.not_found")
    data = await poll_video_task(user, tid, channel_id=owned_row.provider_channel_id)
    await settle_deferred_video_poll(
        db,
        user,
        provider_task_id=tid,
        poll_status=str(data.get("status") or ""),
        error=str(data.get("error") or "") or None,
        usage_tokens=int((data.get("usage") or {}).get("total_tokens") or 0),
        completion_tokens=int((data.get("usage") or {}).get("completion_tokens") or 0),
        raw_usage=data.get("raw_usage") if isinstance(data.get("raw_usage"), dict) else None,
        upstream_cost_fen=data.get("upstream_cost_fen"),
        model=str(data.get("model") or ""),
    )
    await db.commit()
    raw_error = str(data.get("error") or "").strip()
    if raw_error:
        # 上游原文只记日志，不返回给开放 API 客户端
        logger.warning("v1 video task failed task_id=%s error=%s", tid, raw_error[:400])
    error_code, error_text = _v1_video_task_error(data) if raw_error else (None, None)
    return V1GenerationOut(
        status=str(data.get("status") or "running"),
        kind="video",
        urls=list(data.get("urls") or []),
        task_id=task_id.strip(),
        error=error_text,
        error_code=error_code,
    )
