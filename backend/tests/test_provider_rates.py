"""provider_rates: khớp glob theo model id, công thức từng đơn vị, USD → fen, validate/parse, cache."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.billing import provider_rates as pr
from app.services.billing.money import usd_to_fen

S = SimpleNamespace(billing_usd_cny=7.0)


def test_usd_to_fen_rounds_up_without_float_noise():
    assert usd_to_fen(0.045, S) == 32        # 31.5 → 32
    assert usd_to_fen(0.07, S) == 49         # 49.000000000000001 không được thành 50
    assert usd_to_fen(1.0, S) == 700
    assert usd_to_fen(0, S) == 0
    assert usd_to_fen(-1, S) == 0
    assert usd_to_fen(0.0000001, S) == 1     # > 0 thì tối thiểu 1 fen


def test_default_order_fast_and_mini_before_base():
    assert pr.match_rate("dreamina-seedance-2-0-fast-260128").usd == 5.6
    assert pr.match_rate("dreamina-seedance-2-0-mini-260615").usd == 3.5
    assert pr.match_rate("dreamina-seedance-2-0-260128").usd == 7.0
    assert pr.match_rate("dreamina-seedance-2-5-260628").usd == 10.70
    assert pr.match_rate("seedream-5-0-260128").usd == 0.035
    assert pr.match_rate("dola-seedream-5-0-flash-260915").usd == 0.018


def test_match_rate_is_case_insensitive():
    rate = pr.match_rate("DOLA-Seedream-5-0-PRO-260628")
    assert rate is not None and rate.unit == "per_image" and rate.usd == 0.045


def test_gpt_image_pattern_covers_2_5():
    rate = pr.match_rate("gpt-image-2.5-sunburst")
    assert rate.unit == "per_m_output_tokens" and rate.usd == 30


def test_unmatched_and_empty_model():
    assert pr.match_rate("ep-20260923-abcdef") is None
    assert pr.match_rate("") is None
    assert pr.match_rate(None) is None


def test_rate_cost_per_unit():
    img = pr.ProviderRate("x", "per_image", 0.045)
    assert pr.rate_cost_usd(img, {"generated_images": 2}) == pytest.approx(0.09)
    assert pr.rate_cost_usd(img, {}) == pytest.approx(0.045)            # thiếu generated_images → 1 ảnh
    vid = pr.ProviderRate("x", "per_m_tokens", 10.70)
    assert pr.rate_cost_usd(vid, {"total_tokens": 108_000}) == pytest.approx(1.1556)
    assert pr.rate_cost_usd(vid, {}) is None
    assert pr.rate_cost_usd(vid, {}, fallback_tokens=108_000) == pytest.approx(1.1556)
    out = pr.ProviderRate("x", "per_m_output_tokens", 30)
    assert pr.rate_cost_usd(out, {"input_tokens": 50, "output_tokens": 1200}) == pytest.approx(0.036)
    io = pr.ProviderRate("x", "per_m_input_output", 4, 20)
    assert pr.rate_cost_usd(io, {"prompt_tokens": 1000, "completion_tokens": 500}) == pytest.approx(0.014)
    assert pr.rate_cost_usd(io, {}, fallback_tokens=80_000) == pytest.approx(0.704)   # tách 70/30
    chars = pr.ProviderRate("x", "per_m_chars", 15)
    assert pr.rate_cost_usd(chars, {}, fallback_tokens=1000) == pytest.approx(0.015)


def test_provider_cost_fen_reads_nested_usage():
    assert pr.provider_cost_fen("seedream-4-5-251128", {"generated_images": 1}, settings=S) == 28
    assert pr.provider_cost_fen("seedream-4-5-251128", {"usage": {"generated_images": 1}}, settings=S) == 28
    assert pr.provider_cost_fen("dreamina-seedance-2-5-260628", {"total_tokens": 108_000}, settings=S) == 809
    assert pr.provider_cost_fen("seedream-4-5-251128", None, settings=S) is None
    assert pr.provider_cost_fen("ep-unknown", {"total_tokens": 5}, settings=S) is None
    assert pr.provider_cost_fen("dreamina-seedance-2-5-260628", {"total_tokens": 0}, settings=S) is None


def test_validate_reports_vietnamese_row_errors():
    errors = pr.validate_provider_rates([
        {"pattern": "", "unit": "per_image", "usd": 1},
        {"pattern": "a*", "unit": "per_second", "usd": 1},
        {"pattern": "b*", "unit": "per_image", "usd": -1},
        {"pattern": "c*", "unit": "per_m_input_output", "usd": 1},
        {"pattern": "A*", "unit": "per_image", "usd": 1},
    ])
    assert errors == [
        "Dòng 1: thiếu mẫu tên model",
        "Dòng 2: đơn vị 'per_second' không hợp lệ",
        "Dòng 3: giá USD phải là số không âm",
        "Dòng 4: đơn vị vào/ra cần thêm giá token đầu ra (usd_out)",
        "Dòng 5: mẫu 'A*' bị trùng",
    ]
    assert pr.validate_provider_rates([{"pattern": "x" * 129, "unit": "per_image", "usd": 1}]) == [
        "Dòng 1: mẫu tên model dài quá 128 ký tự"
    ]


def test_parse_skips_bad_rows_and_keeps_order():
    rates = pr.parse_provider_rates([
        {"pattern": "b*", "unit": "per_image", "usd": 1},
        "rác",
        {"pattern": "a*", "unit": "nope", "usd": 1},
        {"pattern": "a*", "unit": "per_m_input_output", "usd": 1, "usd_out": 2, "note": "n"},
    ])
    assert [r.pattern for r in rates] == ["b*", "a*"]
    assert rates[1].usd_out == 2.0 and rates[1].note == "n"
    assert pr.parse_provider_rates(None) == []
    assert pr.parse_provider_rates({"x": 1}) == []


def test_set_provider_rates_none_restores_defaults():
    pr.set_provider_rates([pr.ProviderRate("only-*", "per_image", 1.0)])
    assert pr.match_rate("dreamina-seedance-2-5-260628") is None
    pr.set_provider_rates(None)
    assert pr.get_provider_rates() == list(pr.DEFAULT_PROVIDER_RATES)


def test_default_payload_round_trips():
    payload = pr.default_provider_rates_payload()
    assert payload[0] == {
        "pattern": "dola-seedream-5-0-pro*",
        "unit": "per_image",
        "usd": 0.045,
        "usd_out": None,
        "note": "BytePlus Seedream 5.0 Pro",
    }
    assert pr.validate_provider_rates(payload) == []
    assert pr.parse_provider_rates(payload) == list(pr.DEFAULT_PROVIDER_RATES)
