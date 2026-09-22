# -*- coding: utf-8 -*-
"""Token 单价与费用换算。"""
from __future__ import annotations

import math
from typing import Any

from app.config import Settings, get_settings
from app.services.billing.money import usd_to_fen
from app.services.billing.provider_rates import (
    first_priced_model,
    match_rate,
    provider_cost_fen,
    rate_cost_usd,
    usage_block,
)

# 充值包以 VND 定义；下单时按 billing_cny_vnd 换算成分（见 topup.sku_quote）
SKUS: list[dict[str, Any]] = [
    {"id": "topup_100k", "name": "体验充值", "amount_vnd": 100_000, "bonus_pct": 0},
    {"id": "topup_500k", "name": "基础充值", "amount_vnd": 500_000, "bonus_pct": 0},
    {"id": "topup_1m", "name": "进阶充值", "amount_vnd": 1_000_000, "bonus_pct": 5, "recommended": True},
    {"id": "topup_2m", "name": "专业充值", "amount_vnd": 2_000_000, "bonus_pct": 10},
]

# 历史网关订单（alipay/wxpay）的待支付有效期；银行转账按 topup_order_expire_hours
ORDER_EXPIRE_SECONDS = 300


def order_expire_seconds(pay_type: str | None, settings: Settings | None = None) -> int:
    """待支付单有效期（秒）：银行转账按小时配置，其余沿用 5 分钟。"""
    if (pay_type or "") == "bank_transfer":
        s = settings or get_settings()
        try:
            hours = int(getattr(s, "topup_order_expire_hours", 24) or 24)
        except (TypeError, ValueError):
            hours = 24
        return max(1, hours) * 3600
    return ORDER_EXPIRE_SECONDS


def provider_yuan_per_m(billing_key: str, settings: Settings | None = None) -> float:
    s = settings or get_settings()
    table = {
        "seedance2:video0": s.billing_seedance_video0,
        "seedance2:video1": s.billing_seedance_video1,
        "llm_chat": s.billing_llm_per_m,
        "seedream": s.billing_seedream_per_m,
        "tts": s.billing_tts_per_m,
    }
    return float(table.get(billing_key, s.billing_llm_per_m))


def user_charge_fen(cost_fen: int, settings: Settings | None = None) -> int:
    """Tiền trừ user = chi phí upstream (không cộng markup)."""
    if cost_fen <= 0:
        return 0
    return max(1, int(cost_fen))


def charge_fen_for_tokens(
    tokens: int,
    billing_key: str,
    *,
    settings: Settings | None = None,
) -> tuple[int, int]:
    """Return (cost_fen, charge_fen)；charge 与成本相同。"""
    s = settings or get_settings()
    t = max(0, int(tokens))
    yuan_per_m = provider_yuan_per_m(billing_key, s)
    cost = math.ceil(t / 1_000_000 * yuan_per_m * 100) if t else 0
    charge = user_charge_fen(cost, s)
    if t > 0 and charge < 1:
        charge = 1
        cost = max(cost, 1)
    return cost, charge


def parse_upstream_cost_fen(data: dict[str, Any] | None) -> int | None:
    """Chi phí đã quy sẵn ra fen trong usage (`cost_fen` / `cost_cents`); không có → None."""
    if not data:
        return None
    usage = usage_block(data)
    for key in ("cost_fen", "cost_cents"):
        if usage.get(key) is not None:
            try:
                return max(0, int(usage[key]))
            except (TypeError, ValueError):
                pass
    return None


def charge_fen_for_usage(
    tokens: int,
    billing_key: str,
    *,
    raw_usage: dict[str, Any] | None = None,
    settings: Settings | None = None,
    model: str = "",
) -> tuple[int, int, bool]:
    """(cost_fen, charge_fen, used_upstream_cost): cost_fen sẵn có → provider_rates theo model → giá token dự phòng.

    Model tra giá: `model` (model lúc tạo tác vụ) trước, `raw_usage["model"]` (model upstream echo) sau.
    Chi phí 0 chỉ được tin cho ảnh (upstream báo rõ 0 ảnh); ảnh không usage dùng rate_quotes.image_fallback_fen
    (cùng quy tắc với số đóng băng) nên model ảnh/video chưa có giá không bao giờ ra 0.
    """
    s = settings or get_settings()
    key = (billing_key or "").strip()
    is_image = key == "seedream"
    upstream_cost = parse_upstream_cost_fen(raw_usage)
    if upstream_cost is not None and (upstream_cost > 0 or is_image):
        return upstream_cost, user_charge_fen(upstream_cost, s), True
    t = max(0, int(tokens or 0))
    raw_model = str(raw_usage.get("model") or "") if isinstance(raw_usage, dict) else ""
    name, priced = first_priced_model(model, raw_model)
    if priced:
        exact = provider_cost_fen(name, raw_usage, settings=s)
        if exact is not None and (exact > 0 or is_image):
            return exact, user_charge_fen(exact, s), False
        usd = rate_cost_usd(match_rate(name), usage_block(raw_usage), fallback_tokens=t) if t else None
        if usd:
            cost = usd_to_fen(usd, s)
            return cost, user_charge_fen(cost, s), False
    if is_image and t <= 0:
        from app.services.billing.rate_quotes import image_fallback_fen

        cost = image_fallback_fen(name, s)
        return cost, user_charge_fen(cost, s), False
    cost, charge = charge_fen_for_tokens(t, key, settings=s)
    return cost, charge, False


def parse_usage_dict(data: dict[str, Any] | None) -> dict[str, int]:
    if not data:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else data
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("generated_tokens")
        or 0
    )
    total = int(usage.get("total_tokens") or (prompt + completion) or 0)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def billing_key_to_capability(billing_key: str) -> str:
    key = (billing_key or "").strip().lower()
    if key == "llm_chat":
        return "llm"
    if key == "seedream":
        return "image"
    if key.startswith("seedance"):
        return "video"
    if key == "tts":
        return "tts"
    return "other"


def billing_key_label(billing_key: str) -> str:
    cap = billing_key_to_capability(billing_key)
    labels = {"llm": "LLM 对话", "image": "图片生成", "video": "视频生成", "tts": "语音合成"}
    return labels.get(cap, billing_key or "其他")


def sku_by_id(sku_id: str) -> dict[str, Any] | None:
    for item in SKUS:
        if item["id"] == sku_id:
            return item
    return None
