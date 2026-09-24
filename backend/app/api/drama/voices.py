"""Danh mục giọng TTS để chọn tay cho nhân vật phim truyện."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.content_lang import project_content_lang
from app.services.drama.access import get_owned_drama_project
from app.services.voices import catalog_voices

router = APIRouter()


@router.get("/voices/catalog")
async def voice_catalog(
    project_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """按项目内容语言返回可手选的 TTS 音色（含试听样音 URL）。"""
    project = await get_owned_drama_project(db, project_id, user)
    lang = project_content_lang(project)
    return {"lang": lang, "voices": catalog_voices(lang)}
