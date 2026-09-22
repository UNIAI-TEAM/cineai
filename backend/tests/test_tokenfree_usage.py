"""TokenFree / New API 额度换算与日用量聚合。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import get_settings
from app.services.tokenfree_usage import (
    aggregate_quota_data_by_day,
    billing_usage_to_cost_fen,
    fetch_tokenfree_account,
    quota_to_cost_fen,
    tokenfree_site_origin,
    usage_dates_are_ignored,
    used_quota_from_raw_json,
)


def test_tokenfree_site_origin_strips_v1():
    assert tokenfree_site_origin("https://www.tokenfree.com/v1") == "https://www.tokenfree.com"
    assert tokenfree_site_origin("https://www.tokenfree.com/v1/") == "https://www.tokenfree.com"


def test_quota_to_cost_fen_one_usd():
    settings = get_settings()
    settings.billing_usd_cny = 7.0
    assert quota_to_cost_fen(500_000, settings) == 700
    assert quota_to_cost_fen(0, settings) == 0


def test_billing_usage_to_cost_fen_one_usd():
    settings = get_settings()
    settings.billing_usd_cny = 7.0
    # OpenAI 兼容 total_usage 单位是 0.01 USD，100 = $1
    assert billing_usage_to_cost_fen(100, settings) == 700


def test_usage_dates_are_ignored_when_values_match():
    assert usage_dates_are_ignored(1200.0, 1200.0, 1200.0) is True
    assert usage_dates_are_ignored(10.0, 20.0, 30.0) is False
    assert usage_dates_are_ignored(0.0, 0.0, 0.0) is False


def test_aggregate_quota_data_by_day():
    settings = get_settings()
    settings.billing_usd_cny = 7.0
    day_ts = int(datetime(2026, 9, 10, tzinfo=UTC).timestamp())
    items = [
        {"created_at": day_ts, "quota": 250_000, "prompt_tokens": 10, "completion_tokens": 5},
        {"date": "2026-09-10", "quota": 250_000, "token_used": 20},
    ]
    daily = aggregate_quota_data_by_day(items, settings)
    assert daily["2026-09-10"]["quota"] == 500_000
    assert daily["2026-09-10"]["cost_fen"] == 700


def test_used_quota_from_raw_json():
    assert used_quota_from_raw_json('{"used_quota": 123}') == 123
    assert used_quota_from_raw_json("not-json") is None


@pytest.mark.asyncio
async def test_fetch_tokenfree_account_prefers_self_when_dashboard_missing(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(path: str, *, params: dict | None = None):
        if path.endswith("/api/user/self"):
            return {"success": True, "data": {"quota": 500_000, "used_quota": 0}}
        return None

    monkeypatch.setattr("app.services.tokenfree_usage._try_tokenfree_get", fake_get)
    settings = get_settings()
    settings.billing_usd_cny = 7.0
    account = await fetch_tokenfree_account(settings)
    assert account["quota"] == 500_000
    assert account["remain_fen"] == 700


@pytest.mark.asyncio
async def test_fetch_tokenfree_account_from_dashboard_usage(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(path: str, *, params: dict | None = None):
        if path.endswith("/subscription"):
            return {"hard_limit_usd": 2.0}
        if "billing/usage" in path:
            return {"total_usage": 100}
        return None

    monkeypatch.setattr("app.services.tokenfree_usage._try_tokenfree_get", fake_get)
    settings = get_settings()
    settings.billing_usd_cny = 7.0
    account = await fetch_tokenfree_account(settings)
    assert account["used_usd"] == 1.0
    assert account["quota"] == 500_000
    assert account["remain_fen"] == 700


def test_resolve_tokenfree_api_key_never_falls_back_to_provider_keys(monkeypatch):
    """I-9: không có kênh TokenFree thì trả rỗng, không mượn key OpenAI/BytePlus gửi sang tokenfree.com."""
    from app.config import get_settings
    from app.schemas_routing import FunctionBindings, SystemModelChannel
    from app.services import model_settings as ms
    from app.services.tokenfree_usage import resolve_tokenfree_api_key, tokenfree_usage_configured

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-openai")
    monkeypatch.setattr(settings, "ark_api_key", "ak-byteplus")
    prev = ms.get_routing_snapshot()
    ms._refresh_routing_snapshot([SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1",
                                                     api_key="sk-openai", protocol="openai", enabled=True)], FunctionBindings())
    try:
        assert resolve_tokenfree_api_key() == ""
        assert tokenfree_usage_configured() is False
    finally:
        ms._refresh_routing_snapshot(prev.channels, prev.function_bindings)
