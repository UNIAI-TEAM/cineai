"""Đã bỏ đối chiếu dùng lượng upstream (TokenFree): route và module cũ không còn."""
from __future__ import annotations

import importlib.util

from app.main import app

_REMOVED_ROUTES = {
    "/api/admin/stats/upstream-usage",
    "/api/admin/stats/upstream-usage/sync",
    "/api/admin/finance/daily/sync",
    "/api/admin/settings/tokenfree/quota",
}


def test_upstream_usage_routes_removed():
    paths = {getattr(r, "path", "") for r in app.routes}
    assert not (_REMOVED_ROUTES & paths)
    assert "/api/admin/finance/daily" in paths
    assert "/api/admin/settings/billing/model-rates" in paths


def test_tokenfree_modules_deleted():
    for name in ("app.services.admin.upstream_usage", "app.services.tokenfree_usage", "app.services.tokenfree_pricing"):
        assert importlib.util.find_spec(name) is None, name
