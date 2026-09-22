"""Admin bảng giá provider: GET mặc định, PUT lưu + nạp cache, lỗi tiếng Việt giữ nguyên cache, model chưa có giá."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.main import app
from app.models_settings import AppSettings
from app.schemas_provider_rates import AdminProviderRatesPut, ProviderRateRow
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.billing import provider_rates_admin as pra
from app.services.billing.provider_rates import DEFAULT_PROVIDER_RATES, get_provider_rates, match_rate
from app.services.model_settings import RoutingSnapshot


def _channel(channel_id: str, models: list[str], *, enabled: bool = True) -> SystemModelChannel:
    """Kênh test tối giản: đủ base_url + key để `channel_connection_ready` coi là sẵn sàng."""
    return SystemModelChannel(id=channel_id, name=channel_id, base_url=f"https://{channel_id}", api_key="k",
                               has_api_key=True, protocol="ark", models=models, enabled=enabled)


@pytest.fixture(autouse=True)
def _autouse_isolated_routing_state(isolated_routing_state):
    """Bật cách ly overlay/snapshot toàn process (fixture dùng chung ở conftest) cho mọi test trong file này."""
    yield


async def test_get_returns_defaults_units_and_rate(db_session):
    out = await pra.get_provider_rates_admin(db_session)
    assert out.items[0].pattern == "dola-seedream-5-0-pro*"
    assert len(out.defaults) == len(DEFAULT_PROVIDER_RATES)
    assert [u.id for u in out.units] == ["per_image", "per_m_tokens", "per_m_output_tokens",
                                         "per_m_input_output", "per_m_chars"]
    assert out.usd_cny > 0


async def test_save_persists_and_refreshes_cache(db_session):
    body = AdminProviderRatesPut(items=[ProviderRateRow(pattern="house-*", unit="per_image", usd=0.1, note="n")])
    out = await pra.save_provider_rates_admin(db_session, body)
    assert [r.pattern for r in out.items] == ["house-*"]
    assert match_rate("house-1").usd == 0.1
    assert match_rate("dola-seedream-5-0-pro-260628") is None
    row = (await db_session.execute(select(AppSettings).where(AppSettings.id == "default"))).scalar_one()
    assert row.config_json["provider_rates"] == [
        {"pattern": "house-*", "unit": "per_image", "usd": 0.1, "usd_out": None, "note": "n"}
    ]


async def test_save_empty_table_is_allowed(db_session):
    out = await pra.save_provider_rates_admin(db_session, AdminProviderRatesPut(items=[]))
    assert out.items == [] and get_provider_rates() == []


async def test_save_invalid_rates_keeps_cache(db_session):
    before = get_provider_rates()
    body = AdminProviderRatesPut(items=[ProviderRateRow(pattern="x*", unit="per_second", usd=1)])
    with pytest.raises(ValueError) as exc:
        await pra.save_provider_rates_admin(db_session, body)
    assert "Dòng 1: đơn vị 'per_second' không hợp lệ" in str(exc.value)
    assert get_provider_rates() == before


def test_unpriced_models_lists_endpoint_ids():
    channels = [_channel("byteplus", ["ep-20260923-abc", "dola-seedream-5-0-pro-260628", "ep-video-1"]),
                _channel("x", ["ep-ignored"])]
    snap = RoutingSnapshot(channels=channels, function_bindings=FunctionBindings(
        slots={"image": [ModelBinding(channel_id="byteplus", model="ep-20260923-abc"),
                         ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]},
        overrides={"tools.video": [ModelBinding(channel_id="byteplus", model="ep-video-1")],
                   "unknown.fn": [ModelBinding(channel_id="x", model="ep-ignored")]},
    ))
    rows = pra.unpriced_models(snapshot=snap)
    assert [(r.channel_id, r.model, r.capability) for r in rows] == [
        ("byteplus", "ep-20260923-abc", "image"),
        ("byteplus", "ep-video-1", "video"),
    ]


def test_unpriced_models_excludes_disabled_provider():
    """Binding của provider đã tắt không bao giờ được gọi → không liệt vào unpriced_models (Review Focus #5)."""
    channels = [_channel("on", ["house-on"], enabled=True), _channel("off", ["house-off"], enabled=False)]
    snap = RoutingSnapshot(channels=channels, function_bindings=FunctionBindings(slots={
        "image": [ModelBinding(channel_id="on", model="house-on"),
                 ModelBinding(channel_id="off", model="house-off")],
    }))
    rows = pra.unpriced_models(snapshot=snap)
    assert [(r.channel_id, r.model) for r in rows] == [("on", "house-on")]


@pytest.fixture
async def admin_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Client ASGI với get_db = session test, admin giả."""
    async def _db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_admin] = lambda: object()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_admin, None)


async def test_http_get_and_put(admin_client):
    res = await admin_client.get("/api/admin/settings/billing/model-rates")
    assert res.status_code == 200
    assert {"items", "defaults", "units", "unpriced_models", "usd_cny", "updated_at"} <= set(res.json())
    res = await admin_client.put("/api/admin/settings/billing/model-rates",
                                 json={"items": [{"pattern": "a*", "unit": "per_m_input_output", "usd": 1, "usd_out": 2}]})
    assert res.status_code == 200
    assert res.json()["items"][0]["usd_out"] == 2


async def test_put_invalid_returns_400_vietnamese(admin_client):
    res = await admin_client.put("/api/admin/settings/billing/model-rates",
                                 json={"items": [{"pattern": "", "unit": "per_image", "usd": 1}]})
    assert res.status_code == 400
    assert res.json()["detail"] == "Dòng 1: thiếu mẫu tên model"


async def test_put_overlong_unit_returns_400_vietnamese(admin_client):
    """Đơn vị quá dài bị service từ chối bằng 400 tiếng Việt (không phải 422 của schema)."""
    unit = "x" * 40
    res = await admin_client.put("/api/admin/settings/billing/model-rates",
                                 json={"items": [{"pattern": "a*", "unit": unit, "usd": 1}]})
    assert res.status_code == 400
    assert res.json()["detail"] == f"Dòng 1: đơn vị '{unit}' không hợp lệ"


async def test_put_overlong_note_is_truncated(admin_client):
    """Ghi chú quá dài không trả 422: được nhận và cắt còn 200 ký tự."""
    res = await admin_client.put("/api/admin/settings/billing/model-rates",
                                 json={"items": [{"pattern": "a*", "unit": "per_image", "usd": 1, "note": "n" * 300}]})
    assert res.status_code == 200
    assert res.json()["items"][0]["note"] == "n" * 200
