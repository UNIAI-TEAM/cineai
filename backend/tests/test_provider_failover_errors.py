"""Failover chỉ khi request chắc chắn chưa tới upstream (tránh tạo trùng tác vụ bị tính tiền)."""
import httpx
import pytest

from app.services.providers.base import TransientUpstreamError, is_failover_safe_error, reraise_upstream_timeout


@pytest.mark.parametrize("exc,expected", [
    (TransientUpstreamError("503"), True),
    (httpx.ConnectError("refused"), True),
    (httpx.ConnectTimeout("t"), True),
    (httpx.PoolTimeout("t"), True),
    (httpx.ReadError("r"), False),
    (httpx.RemoteProtocolError("p"), False),
    (httpx.ReadTimeout("t"), False),
    (RuntimeError("400"), False),
])
def test_is_failover_safe_error(exc, expected):
    assert is_failover_safe_error(exc) is expected


def test_connect_timeout_reraised_as_transient():
    with pytest.raises(TransientUpstreamError):
        reraise_upstream_timeout(httpx.ConnectTimeout("t"), kind="生图", read_sec=10)
    with pytest.raises(RuntimeError) as info:
        reraise_upstream_timeout(httpx.ReadTimeout("t"), kind="生图", read_sec=10)
    assert not isinstance(info.value, TransientUpstreamError)
