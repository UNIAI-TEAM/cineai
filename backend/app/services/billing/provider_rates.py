"""Bảng giá theo provider (`config_json["provider_rates"]`): glob theo model id, công thức theo đơn vị, USD → fen."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from typing import Any

from app.services.billing.money import usd_to_fen

RATE_UNITS: tuple[str, ...] = (
    "per_image",
    "per_m_tokens",
    "per_m_output_tokens",
    "per_m_input_output",
    "per_m_chars",
)
RATE_UNIT_LABELS: dict[str, str] = {
    "per_image": "USD / ảnh",
    "per_m_tokens": "USD / 1 triệu token",
    "per_m_output_tokens": "USD / 1 triệu token đầu ra",
    "per_m_input_output": "USD / 1 triệu token (vào | ra)",
    "per_m_chars": "USD / 1 triệu ký tự",
}
MAX_RATE_ROWS = 200
MAX_PATTERN_LEN = 128
MAX_USD = 100_000.0
# Văn bản chỉ có tổng token ước tính → tách 70% đầu vào / 30% đầu ra
LLM_PROMPT_SHARE = 0.7
# gpt-image chất lượng high 1536x1024 ≈ 6 240 token đầu ra theo bảng token ảnh của OpenAI
# (platform.openai.com/docs/guides/image-generation#calculating-costs, truy cập 2026-09-22):
# trần ước tính cho model ảnh tính theo token khi upstream không trả usage.
EST_IMAGE_OUTPUT_TOKENS = 6_240


@dataclass(frozen=True)
class ProviderRate:
    """Một dòng giá: glob model id + đơn vị + giá USD (usd_out chỉ dùng cho per_m_input_output)."""

    pattern: str
    unit: str
    usd: float
    usd_out: float | None = None
    note: str = ""


# Giá chính thức 2026-09-22 (spec mục 6.1). Thứ tự quan trọng: dòng đầu khớp thắng.
# Không thêm dòng cho seed-2-0-*: chưa có giá nguồn, model này rơi về ước tính theo token
# và hiện trong unpriced_models để admin tự đặt giá (xem docs/PROVIDERS.md).
DEFAULT_PROVIDER_RATES: tuple[ProviderRate, ...] = (
    ProviderRate("dola-seedream-5-0-pro*", "per_image", 0.045, None, "BytePlus Seedream 5.0 Pro"),
    ProviderRate("dola-seedream-5-0-flash*", "per_image", 0.018, None, "BytePlus Seedream 5.0 Flash"),
    ProviderRate("seedream-5-0*", "per_image", 0.035, None, "BytePlus Seedream 5.0"),
    ProviderRate("seedream-4-5*", "per_image", 0.04, None, "BytePlus Seedream 4.5"),
    ProviderRate("seedream-4-0*", "per_image", 0.03, None, "BytePlus Seedream 4.0"),
    ProviderRate("dreamina-seedance-2-5*", "per_m_tokens", 10.70, None, "BytePlus Seedance 2.5"),
    ProviderRate("dreamina-seedance-2-0-fast*", "per_m_tokens", 5.6, None, "BytePlus Seedance 2.0 Fast"),
    ProviderRate("dreamina-seedance-2-0-mini*", "per_m_tokens", 3.5, None, "BytePlus Seedance 2.0 Mini"),
    ProviderRate("dreamina-seedance-2-0*", "per_m_tokens", 7.0, None, "BytePlus Seedance 2.0"),
    ProviderRate("seedance-1-0-pro*", "per_m_tokens", 2.5, None, "BytePlus Seedance 1.0 Pro"),
    ProviderRate("gpt-image-2*", "per_m_output_tokens", 30.0, None, "OpenAI gpt-image-2 / 2.5"),
    ProviderRate("gpt-4o-mini-tts*", "per_m_output_tokens", 12.0, None, "OpenAI TTS (≈ 0.015 USD/phút)"),
    ProviderRate("tts-1", "per_m_chars", 15.0, None, "OpenAI tts-1"),
    ProviderRate("gpt-5.6-sol", "per_m_input_output", 4.0, 20.0, "OpenAI GPT-5.6 Sol"),
    ProviderRate("gpt-5.6-terra", "per_m_input_output", 2.0, 12.0, "OpenAI GPT-5.6 Terra"),
)

_rates: list[ProviderRate] = list(DEFAULT_PROVIDER_RATES)


def rate_to_dict(rate: ProviderRate) -> dict[str, Any]:
    """Dòng giá → dict JSON (lưu config_json / trả admin)."""
    return asdict(rate)


def default_provider_rates_payload() -> list[dict[str, Any]]:
    """Bảng mặc định dạng JSON để seed vào config_json lần đầu."""
    return [rate_to_dict(r) for r in DEFAULT_PROVIDER_RATES]


def _num(value: Any) -> float | None:
    """Số hữu hạn trong [0, MAX_USD]; bool/chuỗi rác/âm → None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num) or num < 0 or num > MAX_USD:
        return None
    return num


def validate_provider_rates(items: list[dict[str, Any]]) -> list[str]:
    """Lỗi theo dòng (tiếng Việt, đánh số từ 1); rỗng = hợp lệ. Bảng rỗng là hợp lệ."""
    if len(items) > MAX_RATE_ROWS:
        return [f"Bảng giá tối đa {MAX_RATE_ROWS} dòng"]
    errors: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(items, start=1):
        pattern = str(item.get("pattern") or "").strip()
        unit = str(item.get("unit") or "").strip()
        if not pattern:
            errors.append(f"Dòng {idx}: thiếu mẫu tên model")
            continue
        if len(pattern) > MAX_PATTERN_LEN:
            errors.append(f"Dòng {idx}: mẫu tên model dài quá {MAX_PATTERN_LEN} ký tự")
            continue
        if pattern.lower() in seen:
            errors.append(f"Dòng {idx}: mẫu '{pattern}' bị trùng")
            continue
        seen.add(pattern.lower())
        if unit not in RATE_UNITS:
            errors.append(f"Dòng {idx}: đơn vị '{unit}' không hợp lệ")
            continue
        if _num(item.get("usd")) is None:
            errors.append(f"Dòng {idx}: giá USD phải là số không âm")
            continue
        if unit == "per_m_input_output" and _num(item.get("usd_out")) is None:
            errors.append(f"Dòng {idx}: đơn vị vào/ra cần thêm giá token đầu ra (usd_out)")
    return errors


def parse_provider_rates(raw: Any) -> list[ProviderRate]:
    """Đọc bảng từ config_json, bỏ qua dòng hỏng (không ném lỗi lúc khởi động)."""
    if not isinstance(raw, list):
        return []
    out: list[ProviderRate] = []
    for item in raw:
        if not isinstance(item, dict) or validate_provider_rates([item]):
            continue
        out.append(
            ProviderRate(
                pattern=str(item["pattern"]).strip(),
                unit=str(item["unit"]).strip(),
                usd=float(_num(item["usd"]) or 0.0),
                usd_out=_num(item.get("usd_out")),
                note=str(item.get("note") or "")[:200],
            )
        )
    return out


def get_provider_rates() -> list[ProviderRate]:
    """Bảng giá đang áp dụng trong process (bản sao)."""
    return list(_rates)


def set_provider_rates(rates: list[ProviderRate] | None) -> None:
    """Ghi đè cache giá; None → quay về bảng mặc định (dùng cho test và lúc chưa nạp DB)."""
    global _rates
    _rates = list(DEFAULT_PROVIDER_RATES) if rates is None else list(rates)


def match_rate(model: str | None, rates: list[ProviderRate] | None = None) -> ProviderRate | None:
    """Dòng đầu tiên có glob khớp model id (không phân biệt hoa thường); không khớp → None."""
    mid = (model or "").strip().lower()
    if not mid:
        return None
    for rate in _rates if rates is None else rates:
        if fnmatchcase(mid, rate.pattern.strip().lower()):
            return rate
    return None


def first_priced_model(*candidates: str | None) -> tuple[str, bool]:
    """Chọn model để tính giá theo thứ tự ưu tiên: ứng viên đầu có dòng giá → (model, True);
    không ứng viên nào có giá → (ứng viên không rỗng đầu tiên hoặc "", False)."""
    names = [str(c or "").strip() for c in candidates]
    for name in names:
        if name and match_rate(name) is not None:
            return name, True
    return next((n for n in names if n), ""), False


def _int(usage: dict[str, Any], *keys: str) -> int:
    """Giá trị nguyên dương đầu tiên trong các khoá; không có → 0."""
    for key in keys:
        try:
            value = int(usage.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def usage_block(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Tách phần usage lồng trong payload thô upstream trả về; không có `usage` lồng thì coi cả payload là usage.

    Dùng chung cho mọi nơi đọc usage thô (billing settle, hiển thị) để tránh lặp lại cùng một quy tắc bóc lớp.
    """
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("usage")
    return nested if isinstance(nested, dict) else raw


def token_price_usd(quantity: int, usd_per_million: float) -> float:
    """Giá USD của `quantity` đơn vị (token/ký tự) theo đơn giá mỗi 1 triệu đơn vị — công thức dùng chung."""
    return quantity / 1_000_000 * usd_per_million


def rate_cost_usd(rate: ProviderRate, usage: dict[str, Any] | None, *, fallback_tokens: int = 0) -> float | None:
    """Chi phí USD theo đơn vị của dòng giá; thiếu số lượng thì dùng fallback_tokens; vẫn 0 → None.

    fallback_tokens: token ước tính (hoặc số ký tự với per_m_chars) khi usage không có số liệu.
    """
    u = usage if isinstance(usage, dict) else {}
    fb = max(0, int(fallback_tokens or 0))
    if rate.unit == "per_image":
        return (_int(u, "generated_images") or 1) * rate.usd
    if rate.unit == "per_m_input_output":
        tin = _int(u, "prompt_tokens", "input_tokens")
        tout = _int(u, "completion_tokens", "output_tokens")
        if tin + tout <= 0:
            if fb <= 0:
                return None
            tin = int(fb * LLM_PROMPT_SHARE)
            tout = fb - tin
        usd_out = rate.usd_out if rate.usd_out is not None else rate.usd
        return token_price_usd(tin, rate.usd) + token_price_usd(tout, usd_out)
    if rate.unit == "per_m_tokens":
        qty = _int(u, "total_tokens") or (
            _int(u, "prompt_tokens", "input_tokens") + _int(u, "completion_tokens", "output_tokens")
        ) or fb
    elif rate.unit == "per_m_output_tokens":
        qty = _int(u, "output_tokens", "completion_tokens") or fb
    elif rate.unit == "per_m_chars":
        qty = _int(u, "characters", "input_characters") or fb
    else:
        return None
    return token_price_usd(qty, rate.usd) if qty > 0 else None


def provider_cost_fen(
    model: str | None,
    raw_usage: dict[str, Any] | None,
    *,
    settings: Any | None = None,
    rates: list[ProviderRate] | None = None,
) -> int | None:
    """Chi phí fen từ usage thật của upstream (adapter.cost_fen); không usage/không khớp/không số lượng → None."""
    if not isinstance(raw_usage, dict) or not raw_usage:
        return None
    rate = match_rate(model, rates)
    if rate is None:
        return None
    usage = usage_block(raw_usage)
    # Upstream báo rõ 0 ảnh (hỏng/rỗng) → 0 fen; rate_cost_usd coi thiếu số ảnh là 1 nên phải chặn ở đây
    if rate.unit == "per_image" and usage.get("generated_images") is not None and not _int(usage, "generated_images"):
        return 0
    usd = rate_cost_usd(rate, usage)
    if not usd or usd <= 0:
        return None
    return usd_to_fen(usd, settings)
