"""adapter.cost_fen tra provider_rates; poll video tính giá theo model tác vụ; chi phí thật tới dòng usage."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UsageEvent
from app.services.billing.provider_rates import provider_cost_fen
from app.services.media_gateway import ImageResult
from app.services.providers import base
from app.services.providers.ark_adapter import ArkAdapter, build_task_result_from_payload
from app.services.providers.openai_adapter import OpenAIAdapter
from app.services.providers.volc_tts_adapter import VolcTtsAdapter
from tests.conftest import make_task, make_user
from tests.test_media_gateway import _FakeAdapter, _gateway

SEEDANCE_25 = "dreamina-seedance-2-5-260628"
VIDEO_USAGE = {"completion_tokens": 108_000, "total_tokens": 108_000}


@pytest.fixture
def _usd7(monkeypatch):
    """Tỉ giá cố định 7 để so số fen tuyệt đối."""
    monkeypatch.setattr(get_settings(), "billing_usd_cny", 7.0)


def test_ark_cost_fen_video_tokens(_usd7):
    assert ArkAdapter().cost_fen(SEEDANCE_25, dict(VIDEO_USAGE)) == 809


def test_ark_cost_fen_image_per_image(_usd7):
    assert ArkAdapter().cost_fen("dola-seedream-5-0-pro-260628", {"generated_images": 1, "size": "2K"}) == 32


def test_ark_cost_fen_zero_images_is_free(_usd7):
    """generated_images: 0 (ảnh hỏng/rỗng) không được tính là 1 ảnh."""
    assert ArkAdapter().cost_fen("dola-seedream-5-0-pro-260628", {"generated_images": 0, "size": "2K"}) == 0


def test_openai_cost_fen_image_output_tokens(_usd7):
    usage = {"input_tokens": 50, "output_tokens": 1200, "total_tokens": 1250}
    assert OpenAIAdapter().cost_fen("gpt-image-2", usage) == 26


def test_cost_fen_none_without_usage_or_rate(_usd7):
    assert ArkAdapter().cost_fen(SEEDANCE_25, None) is None
    assert OpenAIAdapter().cost_fen("ep-unknown", {"total_tokens": 10}) is None
    assert VolcTtsAdapter().cost_fen("seed-tts-1.0", None) is None


def test_build_task_result_keeps_task_model():
    data = {"status": "succeeded", "model": SEEDANCE_25,
            "content": {"video_url": "https://x/v.mp4"}, "usage": {"completion_tokens": 9, "total_tokens": 9}}
    assert build_task_result_from_payload(data).model == SEEDANCE_25
    assert build_task_result_from_payload({"status": "running", "model": "m"}).model == "m"


class _CostAdapter(_FakeAdapter):
    """Adapter giả ghi lại model được dùng để tra giá; `real=True` thì tính giá thật theo provider_rates."""

    def __init__(self, *args, real: bool = False, **kwargs):
        """Khởi tạo adapter giả; real chọn giữa giá cố định 777 và provider_cost_fen."""
        super().__init__(*args, **kwargs)
        self.real = real
        self.cost_models: list[str] = []

    def cost_fen(self, model, raw):
        """Ghi lại model tra giá rồi trả 777 hoặc giá thật."""
        self.cost_models.append(model)
        return provider_cost_fen(model, raw) if self.real else 777


async def test_fetch_task_once_prices_by_task_model(monkeypatch, priced_routing):
    """Route poll dựng theo kênh (upstream_model rỗng) → giá phải tra theo model trong payload tác vụ."""
    fetched = base.TaskResult(status="succeeded", url="https://x/v.mp4", raw_usage={"total_tokens": 1000},
                              total_tokens=1000, model=SEEDANCE_25)
    ark = _CostAdapter("ark", fetch=fetched)
    g = _gateway(monkeypatch, {"ark": ark, "openai": _FakeAdapter("openai")})
    r = await g.fetch_task_once("cgt-1", channel_id="byteplus")
    assert ark.cost_models == [SEEDANCE_25]
    assert r.upstream_cost_fen == 777 and r.model == SEEDANCE_25


async def test_fetch_prefers_create_time_model_over_endpoint_echo(monkeypatch, priced_routing, _usd7):
    """Ark trả `ep-…` trong payload nhưng tác vụ tạo bằng Seedance 2.5 → tính theo model lúc tạo (809 fen)."""
    fetched = base.TaskResult(status="succeeded", url="https://x/v.mp4", raw_usage=dict(VIDEO_USAGE),
                              total_tokens=108_000, model="ep-2026-x")
    ark = _CostAdapter("ark", task_id="cgt-ep", fetch=fetched, real=True)
    g = _gateway(monkeypatch, {"ark": ark, "openai": _FakeAdapter("openai")})
    task_id = await g.gen_video_seedance_body({"duration": 5}, function_id="drama.video")
    assert task_id == "cgt-ep"
    r = await g.fetch_task_once(task_id)
    assert ark.cost_models == [SEEDANCE_25]
    assert r.upstream_cost_fen == 809 and r.model == SEEDANCE_25


async def test_fetch_after_restart_uses_echoed_model(monkeypatch, priced_routing, _usd7):
    """Sau khởi động lại (không còn nhớ model lúc tạo) → dùng model Ark trả trong payload."""
    fetched = base.TaskResult(status="succeeded", url="https://x/v.mp4", raw_usage=dict(VIDEO_USAGE),
                              total_tokens=108_000, model="dreamina-seedance-2-0-260128")
    ark = _CostAdapter("ark", fetch=fetched, real=True)
    g = _gateway(monkeypatch, {"ark": ark, "openai": _FakeAdapter("openai")})
    r = await g.fetch_task_once("cgt-old", channel_id="byteplus")
    assert ark.cost_models == ["dreamina-seedance-2-0-260128"]
    assert r.upstream_cost_fen == 530 and r.model == "dreamina-seedance-2-0-260128"


async def test_poll_video_task_exposes_cost_and_model(monkeypatch):
    from app.services import studio_tools

    result = base.TaskResult(status="failed", error="x", raw_usage={"total_tokens": 5}, total_tokens=5,
                             upstream_cost_fen=12, model="dreamina-seedance-2-0-260128")
    fake = SimpleNamespace(fetch_task_once=AsyncMock(return_value=result))
    monkeypatch.setattr(studio_tools, "get_ark", lambda: fake)
    data = await studio_tools.poll_video_task(SimpleNamespace(id=1), "cgt-9", channel_id="byteplus")
    assert data["upstream_cost_fen"] == 12 and data["model"] == "dreamina-seedance-2-0-260128"


async def test_settle_deferred_video_poll_uses_upstream_cost_and_model(db_session: AsyncSession) -> None:
    from app.services.billing.ephemeral import settle_deferred_video_poll
    from app.services.billing.settlement import freeze_for_task

    user = await make_user(db_session, balance_fen=50_000)
    task = await make_task(db_session, user, domain="api", task_type="v1_video", status="awaiting_poll",
                           billing_status="none", provider_task_id="cost-prop-1")
    task.provider_channel_id = "byteplus"
    await freeze_for_task(db_session, task)
    task.status = "awaiting_poll"
    await db_session.commit()

    await settle_deferred_video_poll(
        db_session, user, provider_task_id="cost-prop-1", poll_status="succeeded", billing_task_id=task.id,
        usage_tokens=108_000, completion_tokens=108_000, raw_usage={"total_tokens": 108_000},
        upstream_cost_fen=809, model=SEEDANCE_25,
    )
    await db_session.commit()
    ev = (await db_session.execute(select(UsageEvent).where(UsageEvent.task_run_id == task.id))).scalar_one()
    assert ev.cost_fen == 809 and ev.charge_fen == 809
    assert ev.model == SEEDANCE_25
    assert ev.estimated is False


async def test_record_seedream_uses_actual_image_model(db_session: AsyncSession) -> None:
    from app.services.drama.billing_util import record_seedream_image_usage

    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", raw_usage={"generated_images": 1}, upstream_cost_fen=28,
                        channel_id="byteplus", model="seedream-4-5-251128")
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="nhan-cu", domain="studio",
                                           image_result=image)
    assert ev.model == "seedream-4-5-251128" and ev.cost_fen == 28
