# -*- coding: utf-8 -*-
"""/api/v1: lỗi cấu hình model (AppError) phải giữ nguyên code/status, không bị bọc thành 502."""
from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.generation import _resolve_api_user
from app.database import get_db
from app.errors import AppError
from app.main import app
from app.models import User

from tests.conftest import make_user


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[tuple[AsyncClient, User]]:
    """Client ASGI với get_db / người dùng API bị thay bằng session và user của test."""
    user = await make_user(db_session)

    async def _db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[_resolve_api_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, user
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(_resolve_api_user, None)


def _ark_raising(monkeypatch, method: str, exc: Exception) -> None:
    """Cho get_ark() trả về facade giả mà method chỉ định luôn ném exc."""
    fake = SimpleNamespace(**{method: AsyncMock(side_effect=exc)})
    monkeypatch.setattr("app.api.v1.generation.get_ark", lambda: fake)


async def test_image_slot_not_configured_returns_503(api_client, monkeypatch) -> None:
    """Chưa gán model cho tools.image → 503 kèm code, không phải 502."""
    client, _user = api_client
    _ark_raising(monkeypatch, "gen_image", AppError("model.slot_not_configured"))
    res = await client.post("/api/v1/images/generations", json={"prompt": "một con mèo"})
    assert res.status_code == 503
    assert res.json()["code"] == "model.slot_not_configured"


async def test_video_model_not_available_keeps_code(api_client, monkeypatch) -> None:
    """Model user chọn không còn được phép → giữ code model.not_available (400)."""
    client, _user = api_client
    _ark_raising(monkeypatch, "gen_video_i2v", AppError("model.not_available"))
    res = await client.post(
        "/api/v1/videos/generations",
        json={"image_url": "https://cdn.example.com/a.png", "prompt": "chuyển động nhẹ", "duration": 5},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "model.not_available"


async def test_seedance_slot_not_configured_returns_503(api_client, monkeypatch) -> None:
    """Chuyển tiếp Seedance cũng không được nuốt AppError thành 502."""
    client, _user = api_client
    _ark_raising(monkeypatch, "gen_video_seedance_body", AppError("model.slot_not_configured"))
    res = await client.post(
        "/api/v1/seedance/tasks",
        json={"content": [{"type": "text", "text": "cảnh đêm"}]},
    )
    assert res.status_code == 503
    assert res.json()["code"] == "model.slot_not_configured"


async def test_upstream_error_still_502(api_client, monkeypatch) -> None:
    """Lỗi upstream thường vẫn là 502, không bị nhánh AppError nuốt mất."""
    client, _user = api_client
    _ark_raising(monkeypatch, "gen_image", RuntimeError("Seedream error 500"))
    res = await client.post("/api/v1/images/generations", json={"prompt": "một con mèo"})
    assert res.status_code == 502
