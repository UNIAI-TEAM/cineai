"""provider_rates trong config_json: seed khi thiếu, giữ nguyên bảng rỗng, nạp vào cache khi load."""
from __future__ import annotations

import pytest

from app.services import model_settings as ms
from app.services.billing.provider_rates import default_provider_rates_payload, get_provider_rates, match_rate


@pytest.fixture(autouse=True)
def _autouse_isolated_routing_state(isolated_routing_state):
    """Bật cách ly overlay/snapshot toàn process (fixture dùng chung ở conftest) cho mọi test trong file này."""
    yield


def test_migrate_seeds_default_rates_when_missing():
    """Config thiếu khoá provider_rates → được seed bảng mặc định và đánh dấu changed."""
    out, changed = ms._migrate_legacy_config({"flat": {}, "function_bindings": {"slots": {}, "overrides": {}}})
    assert changed
    assert out["provider_rates"] == default_provider_rates_payload()


def test_migrate_keeps_empty_rate_table():
    """Bảng giá rỗng ([]) là giá trị hợp lệ (admin xoá hết dòng), không bị seed lại."""
    cfg = {"flat": {}, "function_bindings": {"slots": {}, "overrides": {}}, "provider_rates": []}
    out, changed = ms._migrate_legacy_config(cfg)
    assert not changed
    assert out["provider_rates"] == []


async def test_load_cache_reads_rates_from_db(db_session):
    """load_model_settings_cache nạp provider_rates đã lưu trong config_json vào cache process."""
    row = await ms._get_or_create_app_row(db_session)
    row.config_json = {**(row.config_json or {}),
                       "provider_rates": [{"pattern": "house-model-*", "unit": "per_image", "usd": 0.5}]}
    await db_session.commit()
    await ms.load_model_settings_cache(db_session)
    assert match_rate("house-model-1").usd == 0.5
    assert match_rate("dola-seedream-5-0-pro-260628") is None


async def test_load_cache_seeds_and_persists_defaults(db_session):
    """Config chưa từng có provider_rates → load_model_settings_cache seed bảng mặc định và lưu lại DB."""
    row = await ms._get_or_create_app_row(db_session)
    cfg = dict(row.config_json or {})
    cfg.pop("provider_rates", None)
    row.config_json = cfg
    await db_session.commit()
    await ms.load_model_settings_cache(db_session)
    await db_session.refresh(row)
    assert row.config_json["provider_rates"] == default_provider_rates_payload()
    assert len(get_provider_rates()) == len(default_provider_rates_payload())
