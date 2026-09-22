# backend/tests/test_seedream_billing_usage.py
"""Quyết toán: cost_fen sẵn có → provider_rates theo model → giá token dự phòng; bỏ quota/yuan/Kie."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.billing.pricing import charge_fen_for_usage, parse_upstream_cost_fen
from app.services.billing.provider_rates import set_provider_rates

S = SimpleNamespace(
    billing_usd_cny=7.0, billing_est_seedream_tokens=45_000, billing_seedream_per_m=8.0,
    billing_seedance_video0=46.0, billing_seedance_video1=28.0, billing_llm_per_m=5.0, billing_tts_per_m=2.0,
    billing_markup=1.0,
)


def test_parse_upstream_cost_fen_only_reads_fen_fields():
    assert parse_upstream_cost_fen({"usage": {"cost_fen": 456}}) == 456
    assert parse_upstream_cost_fen({"cost_cents": 12}) == 12
    assert parse_upstream_cost_fen({"usage": {"cost": 1.23}}) is None                 # bỏ yuan
    assert parse_upstream_cost_fen({"usage": {"quota_consumed": 500_000}}) is None    # bỏ quota New API
    assert parse_upstream_cost_fen({"usage": {"creditsConsumed": 10}}) is None        # bỏ Kie
    assert parse_upstream_cost_fen(None) is None


def test_charge_prefers_upstream_cost_fen():
    assert charge_fen_for_usage(0, "seedream", raw_usage={"usage": {"cost_fen": 1000}}, settings=S) == (1000, 1000, True)


def test_charge_per_image_rate():
    out = charge_fen_for_usage(0, "seedream", raw_usage={"usage": {"generated_images": 2}}, settings=S,
                               model="seedream-4-5-251128")
    assert out == (56, 56, False)


def test_task_model_wins_over_echoed_model():
    """Ruling T4→T6 (2): model lúc tạo tác vụ (tham số `model`) trước, model Ark echo sau."""
    raw = {"model": "dreamina-seedance-2-0-fast-260128", "usage": {"total_tokens": 100_000}}
    out = charge_fen_for_usage(100_000, "seedance2:video0", raw_usage=raw, settings=S,
                               model="dreamina-seedance-2-5-260628")
    assert out == (749, 749, False)      # 100k × 10.70 USD/M × 7


def test_echoed_model_used_when_task_model_unpriced():
    raw = {"model": "dreamina-seedance-2-0-fast-260128", "usage": {"total_tokens": 100_000}}
    out = charge_fen_for_usage(100_000, "seedance2:video0", raw_usage=raw, settings=S, model="nhan-cu")
    assert out == (392, 392, False)      # 100k × 5.6 USD/M × 7


def test_video_endpoint_echo_priced_by_task_model():
    raw = {"model": "ep-2026-x", "usage": {"total_tokens": 108_000}}
    out = charge_fen_for_usage(108_000, "seedance2:video0", raw_usage=raw, settings=S,
                               model="dreamina-seedance-2-5-260628")
    assert out == (809, 809, False)


def test_unpriced_video_never_free():
    raw = {"model": "ep-2026-x", "usage": {"total_tokens": 108_000}}
    assert charge_fen_for_usage(108_000, "seedance2:video0", raw_usage=raw, settings=S, model="ep-2026-x") == (
        497, 497, False)                 # 108k × 46 元/M


def test_token_priced_image_without_usage_uses_output_ceiling():
    raw = {"usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
    assert charge_fen_for_usage(0, "seedream", raw_usage=raw, settings=S, model="gpt-image-2") == (132, 132, False)


def test_unpriced_image_without_usage_never_free():
    assert charge_fen_for_usage(0, "seedream", raw_usage=None, settings=S, model="ep-2026-img") == (36, 36, False)
    zero = {"usage": {"generated_images": 0}}
    assert charge_fen_for_usage(0, "seedream", raw_usage=zero, settings=S, model="ep-2026-img") == (36, 36, False)


def test_zero_image_result_settles_at_zero():
    """Upstream báo rõ 0 ảnh: cost_fen 0 do adapter trả, hoặc generated_images 0 trên model có giá → 0 fen."""
    assert charge_fen_for_usage(0, "seedream", raw_usage={"usage": {"cost_fen": 0}}, settings=S,
                                model="dola-seedream-5-0-pro-260628") == (0, 0, True)
    zero = {"usage": {"generated_images": 0}}
    assert charge_fen_for_usage(0, "seedream", raw_usage=zero, settings=S,
                                model="dola-seedream-5-0-pro-260628") == (0, 0, False)


def test_zero_cost_fen_not_trusted_for_video():
    raw = {"usage": {"cost_fen": 0, "total_tokens": 108_000}}
    out = charge_fen_for_usage(108_000, "seedance2:video0", raw_usage=raw, settings=S,
                               model="dreamina-seedance-2-5-260628")
    assert out == (809, 809, False)


def test_llm_estimated_tokens_split_in_out():
    assert charge_fen_for_usage(80_000, "llm_chat", settings=S, model="gpt-5.6-sol") == (493, 493, False)


def test_empty_rate_table_falls_back_to_tokens():
    set_provider_rates([])
    assert charge_fen_for_usage(0, "seedream", settings=S, model="dola-seedream-5-0-pro-260628") == (36, 36, False)
    # 250 000 token × 46 元/M = 11.5 元 = 1150 fen (chọn số tròn để tránh nhiễu float của charge_fen_for_tokens)
    assert charge_fen_for_usage(250_000, "seedance2:video0", settings=S, model="dreamina-seedance-2-5-260628") == (
        1150, 1150, False)
