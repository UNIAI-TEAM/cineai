"""Agent Skill：列表、上传、启用、删除。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.models import User
from app.schemas_agent import (
    AgentSkillListOut,
    AgentSkillOptimizeBody,
    AgentSkillOptimizeOut,
    AgentSkillOut,
    AgentSkillUpdateBody,
    AgentSkillUploadBody,
)
from app.services.agent.compose import skill_to_public_dict
from app.services.agent.optimize import optimize_prompt_with_skills
from app.services.billing import record_llm_chat_line, run_billed_ephemeral
from app.services.billing.http import http_exception_for_value_error
from app.services.agent.store import (
    create_user_skill,
    delete_user_skill,
    get_visible_skill,
    list_visible_skills,
    update_user_skill,
)

router = APIRouter()


def _out(row) -> AgentSkillOut:
    return AgentSkillOut.model_validate(skill_to_public_dict(row))


@router.get("/skills", response_model=AgentSkillListOut)
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillListOut:
    # 内置 + 当前用户上传的 skill
    rows = await list_visible_skills(db, user.id)
    return AgentSkillListOut(items=[_out(row) for row in rows])


@router.post("/skills/optimize", response_model=AgentSkillOptimizeOut)
async def optimize_prompt(
    body: AgentSkillOptimizeBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillOptimizeOut:
    # 用勾选 Skill 改写提示词，保留 @asset 引用
    task_name = (body.task or "video_prompt").strip() or "video_prompt"
    skill_ids = list(body.skill_ids or [])
    if not skill_ids:
        prompt = (body.prompt or "").strip()
        return AgentSkillOptimizeOut(prompt=prompt, task_id=None)

    async def _do_optimize() -> str:
        prompt = await optimize_prompt_with_skills(
            db,
            user.id,
            prompt=body.prompt,
            skill_ids=skill_ids,
            task=task_name,
        )
        await record_llm_chat_line(
            db,
            user_id=user.id,
            domain="drama",
        )
        return prompt

    try:
        task, prompt = await run_billed_ephemeral(
            db,
            user,
            domain="drama",
            task_type="skill_optimize",
            executor=_do_optimize,
            payload={"task": task_name, "skill_count": len(skill_ids)},
            commit=True,
        )
    except ValueError as exc:
        raise http_exception_for_value_error(exc) from exc
    return AgentSkillOptimizeOut(prompt=prompt, task_id=task.id)


@router.get("/skills/{skill_id}", response_model=AgentSkillOut)
async def get_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillOut:
    row = await get_visible_skill(db, user.id, skill_id)
    if row is None:
        raise AppError("drama.skill_not_found")
    return _out(row)


@router.post("/skills", response_model=AgentSkillOut)
async def upload_skill_markdown(
    body: AgentSkillUploadBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillOut:
    # JSON 上传完整 markdown
    # SkillParseError 带错误码，交给全局处理器
    row = await create_user_skill(db, user.id, body.markdown)
    return _out(row)


@router.post("/skills/upload", response_model=AgentSkillOut)
async def upload_skill_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillOut:
    # 上传 .md 文件
    filename = (file.filename or "").lower()
    if filename and not filename.endswith((".md", ".markdown", ".txt")):
        raise AppError("drama.skill_md_only")
    raw = await file.read()
    if len(raw) > 200 * 1024:
        raise AppError("drama.skill_file_too_large", max_kb=200)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError("drama.skill_not_text") from exc
    row = await create_user_skill(db, user.id, text)
    return _out(row)


@router.patch("/skills/{skill_id}", response_model=AgentSkillOut)
async def patch_skill(
    skill_id: int,
    body: AgentSkillUpdateBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentSkillOut:
    row = await get_visible_skill(db, user.id, skill_id)
    if row is None:
        raise AppError("drama.skill_not_found")
    if not row.is_builtin and row.user_id != user.id:
        raise AppError("drama.skill_edit_forbidden")
    row = await update_user_skill(db, row, markdown=body.markdown, is_active=body.is_active)
    return _out(row)


@router.delete("/skills/{skill_id}")
async def remove_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    row = await get_visible_skill(db, user.id, skill_id)
    if row is None:
        raise AppError("drama.skill_not_found")
    if row.is_builtin:
        raise AppError("drama.skill_builtin_undeletable")
    if row.user_id != user.id:
        raise AppError("drama.skill_delete_forbidden")
    await delete_user_skill(db, row)
    return {"ok": True}
