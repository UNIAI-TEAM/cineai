# Bỏ TokenFree — Plan B: Billing (provider_rates, ước tính, quyết toán, bỏ đối chiếu upstream)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tính tiền hoàn toàn cục bộ theo bảng giá `provider_rates` (USD theo model, admin sửa được) cho cả đóng băng lẫn quyết toán; xoá `tokenfree_pricing.py`, `tokenfree_usage.py` và toàn bộ màn đối chiếu dùng lượng upstream, để không còn đường nào gửi key provider tới tokenfree.com.

**Architecture:** `services/billing/provider_rates.py` (thuần: dòng giá, glob khớp model, công thức theo `unit`, cache trong process) là nguồn giá duy nhất; bảng lưu ở `app_settings.config_json["provider_rates"]`, seed mặc định lúc migrate, nạp vào cache trong `load_model_settings_cache`. Adapter gọi `provider_cost_fen()` để gắn `upstream_cost_fen` ngay khi có usage; `pricing.charge_fen_for_usage` dùng `cost_fen` sẵn có → giá theo model → giá token dự phòng. `services/billing/rate_quotes.py` tính đơn giá ước tính theo **chức năng** (model đắt nhất trong slot hiệu lực) cho `estimates.py`. Admin có `GET/PUT /api/admin/settings/billing/model-rates`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async (asyncpg), pydantic v2, pytest (`asyncio_mode=auto`, `pythonpath=.`), httpx `ASGITransport` cho test HTTP.

**Spec:** `docs/superpowers/specs/2026-09-22-provider-migration-design.md` — mục 6 (Billing), 7.2 (phần model-rates / quota), 8.2 (seed `provider_rates`), 9.1 (`test_provider_rates.py`, chuỗi freeze → usage → settle). Plan A đã thực thi: `docs/superpowers/plans/2026-09-22-provider-migration-a-backend-core.md`.

## Global Constraints

- Lệnh chạy trong `backend/`, interpreter `.venv/bin/python`. Test một file: `cd backend && .venv/bin/python -m pytest tests/<file>.py -v`. Test có fixture `db_session` cần PostgreSQL đang chạy (`deploy/docker-compose.yml`).
- **Hết mỗi task** chạy toàn bộ: `cd backend && .venv/bin/python -m pytest -q`. Kỳ vọng: chỉ còn **2 lỗi có sẵn** trong `tests/test_agent_skills.py`; mọi file khác xanh. Mỗi task commit độc lập được.
- Tiền nội bộ luôn là **fen** (1/100 CNY). USD → fen: `ceil(round(usd × BILLING_USD_CNY × 100, 6))`, `usd > 0` thì tối thiểu 1 fen (hàm `money.usd_to_fen`). UI không bao giờ hiện CNY (hiển thị VND/USD qua `services/billing/money.py`, không đổi).
- Không Alembic; plan này **không** thêm cột DB. Cấu hình mới chỉ nằm trong `app_settings.config_json["provider_rates"]`.
- Không đổi `resolve_kepu_billing_phase()`, không đổi luồng nạp tiền chuyển khoản, không đổi đơn vị ví, không đổi tên field `ark_*` / `billing_*` trong `config.py`.
- Không thêm mã `AppError` mới (lỗi validation admin trả `HTTPException(400, detail=<câu tiếng Việt>)` như `PATCH /settings/routing`). Nếu buộc phải thêm, phải thêm vào cả 3 file `frontend/src/i18n/locales/{zh,en,vi}/errors.ts`.
- Mọi hàm/class mới có docstring một dòng mô tả chức năng (`docs/STANDARDS.md`). File mới ≤ 500 dòng. Không sửa `model_settings.py` quá vài dòng (file đã 541 dòng) — logic mới đặt ở `services/billing/`.
- Không làm UI admin (Plan C). Plan B chỉ backend + `docs/BILLING.md` (+ dòng billing trong `CLAUDE.md`, `docs/PROVIDERS.md` đang nhắc "Plan B"). Trong khoảng giữa Plan B và Plan C: card "đối chiếu upstream" ở Dashboard, nút sync ở Finance và bảng giá cũ ở `PaymentSettingsPanel` sẽ lỗi/404 — chấp nhận, Plan C sửa theo **Hợp đồng API cho Plan C** ở cuối file.
- Commit message tiếng Việt, kết thúc đúng một dòng: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Không commit `.env`.

## Review Focus

1. **Model id khác hoa/thường hoặc là endpoint `ep-…`** — glob phải so khớp không phân biệt hoa thường; ID không khớp dòng nào phải rơi về giá token dự phòng (không bao giờ tính 0 fen cho ảnh/video) và hiện trong `unpriced_models` của admin. Test: Task 1 (`test_match_rate_is_case_insensitive`), Task 5 (`test_unpriced_models_lists_endpoint_ids`), Task 6 (`test_unpriced_image_without_usage_never_free`).
2. **Pattern chồng nhau** — `dreamina-seedance-2-0-fast-*` không được tính theo giá `dreamina-seedance-2-0*`; dòng đầu khớp thắng. Test: Task 1 (`test_default_order_fast_and_mini_before_base`).
3. **Poll video không biết model** — route poll dựng theo kênh nên `upstream_model == ""`; chi phí phải tra theo `model` do Ark trả trong payload tác vụ, và đi tới dòng usage của tác vụ api/studio quyết toán qua `settle_deferred_video_poll`. Test: Task 4 (`test_fetch_task_once_prices_by_task_model`, `test_settle_deferred_video_poll_uses_upstream_cost_and_model`).
4. **Admin lưu bảng giá sai hoặc rỗng** — dòng sai bị từ chối với thông điệp tiếng Việt và cache giữ nguyên; bảng rỗng hợp lệ và khi đó mọi thứ tính theo giá token (không 0). Test: Task 5 (`test_save_invalid_rates_keeps_cache`, `test_put_invalid_returns_400_vietnamese`), Task 6 (`test_empty_rate_table_falls_back_to_tokens`).
5. **Provider tắt / thiếu key trong slot** — ước tính đóng băng chỉ lấy model của binding còn hiệu lực (không lấy giá của provider đã tắt). Test: Task 3 (`test_video_fen_ignores_disabled_provider`).

---

## Sơ đồ file

| File | Trách nhiệm | Task |
|---|---|---|
| `app/services/billing/money.py` (sửa) | thêm `usd_cny_rate()`, `usd_to_fen()` | 1 |
| `app/services/billing/provider_rates.py` (mới) | `ProviderRate`, bảng mặc định, validate/parse, cache, `match_rate`, `rate_cost_usd`, `provider_cost_fen` | 1 |
| `tests/conftest.py` (sửa) | reset cache giá mỗi test (T1); fixture `priced_routing` (T3); bỏ stub TokenFree (T3, T6) | 1, 3, 6 |
| `app/services/model_settings.py` (sửa ~8 dòng) | seed `provider_rates` khi migrate; nạp cache khi `load_model_settings_cache` | 2 |
| `app/services/billing/rate_quotes.py` (mới) | model hiệu lực theo chức năng; đơn giá ước tính ảnh/video/văn bản/giọng; `estimated_line_model` (T6) | 3, 6 |
| `app/services/billing/estimates.py` (viết lại) | đóng băng theo `rate_quotes`, bỏ `tokenfree_pricing` | 3 |
| `app/services/providers/base.py`, `ark_adapter.py`, `openai_adapter.py`, `volc_tts_adapter.py` (sửa) | `TaskResult.model`; `cost_fen` → `provider_cost_fen` | 4 |
| `app/services/media_gateway.py`, `studio_tools.py`, `billing/ephemeral.py`, `drama/billing_util.py`, `api/tools.py`, `api/v1/generation.py`, `tasks/poller.py` (sửa) | truyền `upstream_cost_fen` + model thật tới dòng usage | 4 |
| `app/schemas_provider_rates.py` (mới) | schema admin bảng giá | 5 |
| `app/services/billing/provider_rates_admin.py` (mới) | GET/PUT bảng giá, `unpriced_models` | 5 |
| `app/api/admin/settings.py` (sửa) | endpoint `GET/PUT /settings/billing/model-rates` | 5 |
| `app/services/billing/pricing.py`, `usage.py`, `display.py`, `drama/billing_util.py` (sửa) | quyết toán theo `provider_rates`, bỏ quota/yuan/Kie | 6 |
| xoá `app/services/tokenfree_pricing.py`, `tests/test_tokenfree_pricing.py`, `tests/test_tokenfree_usage.py` | | 6 |
| `app/api/admin/dashboard.py`, `app/api/admin/finance.py`, `app/services/admin/finance.py`, `app/schemas.py` (sửa); xoá `app/services/admin/upstream_usage.py`, `app/services/tokenfree_usage.py` | bỏ đối chiếu upstream; `actual_cost_fen = cost_fen` | 7 |
| `docs/BILLING.md`, `CLAUDE.md`, `docs/PROVIDERS.md` (sửa) | tài liệu | 8 |

---

### Task 1: Bảng giá `provider_rates` (module thuần) + `usd_to_fen`

**Files:**
- Modify: `backend/app/services/billing/money.py`
- Create: `backend/app/services/billing/provider_rates.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_provider_rates.py`

**Interfaces:**
- Produces:
  ```python
  # money.py
  def usd_cny_rate(settings: Settings | None = None) -> float
  def usd_to_fen(usd: float, settings: Settings | Any | None = None) -> int
  # provider_rates.py
  RATE_UNITS: tuple[str, ...]            # per_image | per_m_tokens | per_m_output_tokens | per_m_input_output | per_m_chars
  RATE_UNIT_LABELS: dict[str, str]
  EST_IMAGE_OUTPUT_TOKENS: int = 6_240
  @dataclass(frozen=True) class ProviderRate(pattern: str, unit: str, usd: float, usd_out: float | None = None, note: str = "")
  DEFAULT_PROVIDER_RATES: tuple[ProviderRate, ...]
  def rate_to_dict(rate: ProviderRate) -> dict[str, Any]
  def default_provider_rates_payload() -> list[dict[str, Any]]
  def validate_provider_rates(items: list[dict[str, Any]]) -> list[str]
  def parse_provider_rates(raw: Any) -> list[ProviderRate]
  def get_provider_rates() -> list[ProviderRate]
  def set_provider_rates(rates: list[ProviderRate] | None) -> None       # None → mặc định
  def match_rate(model: str | None, rates: list[ProviderRate] | None = None) -> ProviderRate | None
  def rate_cost_usd(rate: ProviderRate, usage: dict | None, *, fallback_tokens: int = 0) -> float | None
  def provider_cost_fen(model: str | None, raw_usage: dict | None, *, settings=None, rates=None) -> int | None
  ```

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_provider_rates.py
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
    assert payload[0] == {"pattern": "dola-seedream-5-0-pro*", "unit": "per_image", "usd": 0.045, "usd_out": None,
                          "note": payload[0]["note"]}
    assert pr.validate_provider_rates(payload) == []
    assert pr.parse_provider_rates(payload) == list(pr.DEFAULT_PROVIDER_RATES)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provider_rates.py -v`
Expected: FAIL — `ImportError: cannot import name 'provider_rates'` / `usd_to_fen`.

- [ ] **Step 3: Thêm `usd_cny_rate` / `usd_to_fen` vào `money.py`**

Trong `backend/app/services/billing/money.py` thêm `import math` sau `from __future__ import annotations`, và thêm sau hàm `_usd_cny`:

```python
def usd_cny_rate(settings: Settings | None = None) -> float:
    """Tỉ giá 1 USD → CNY (BILLING_USD_CNY) dùng quy đổi bảng giá provider sang fen."""
    return _usd_cny(settings or get_settings())


def usd_to_fen(usd: float, settings: Settings | None = None) -> int:
    """USD → fen: usd × BILLING_USD_CNY × 100, làm tròn lên (khử nhiễu float); ≤ 0 → 0, > 0 tối thiểu 1."""
    try:
        value = float(usd)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(value) or value <= 0:
        return 0
    rate = _usd_cny(settings or get_settings())
    return max(1, int(math.ceil(round(value * rate * 100, 6))))
```

- [ ] **Step 4: Tạo `provider_rates.py`**

```python
# backend/app/services/billing/provider_rates.py
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
# gpt-image chất lượng high 1536x1024 ≈ 6 240 token đầu ra: trần ước tính cho model ảnh tính theo token
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
        return tin / 1_000_000 * rate.usd + tout / 1_000_000 * usd_out
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
    return qty / 1_000_000 * rate.usd if qty > 0 else None


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
    usage = raw_usage.get("usage") if isinstance(raw_usage.get("usage"), dict) else raw_usage
    usd = rate_cost_usd(rate, usage)
    if not usd or usd <= 0:
        return None
    return usd_to_fen(usd, settings)
```

- [ ] **Step 5: Reset cache giá mỗi test trong `conftest.py`**

Trong `backend/tests/conftest.py`, thêm ngay **trên** fixture `skip_tokenfree_pricing_network`:

```python
@pytest.fixture(autouse=True)
def reset_provider_rates() -> None:
    """Mỗi test bắt đầu với bảng provider_rates mặc định (load_model_settings_cache ghi đè cache toàn process)."""
    from app.services.billing.provider_rates import set_provider_rates

    set_provider_rates(None)
```

- [ ] **Step 6: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provider_rates.py -v`
Expected: PASS (12 test).

- [ ] **Step 7: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/billing/money.py backend/app/services/billing/provider_rates.py backend/tests/conftest.py backend/tests/test_provider_rates.py
git commit -m "$(cat <<'EOF'
feat: bảng giá provider_rates (glob model, đơn vị, USD → fen)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Lưu/nạp `provider_rates` từ `app_settings.config_json`

**Files:**
- Modify: `backend/app/services/model_settings.py` (`_migrate_legacy_config`, `load_model_settings_cache`)
- Test: `backend/tests/test_provider_rates_store.py`

**Interfaces:**
- Consumes: `default_provider_rates_payload()`, `parse_provider_rates()`, `set_provider_rates()`, `match_rate()` (Task 1).
- Produces: sau `load_model_settings_cache(db)`, cache giá = `config_json["provider_rates"]`; config thiếu khoá → được seed bảng mặc định và lưu DB (spec 8.2). `[]` là giá trị hợp lệ (admin xoá hết dòng) và **không** bị seed lại.

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_provider_rates_store.py
"""provider_rates trong config_json: seed khi thiếu, giữ nguyên bảng rỗng, nạp vào cache khi load."""
from __future__ import annotations

import pytest

from app import config as config_module
from app.services import model_settings as ms
from app.services.billing.provider_rates import default_provider_rates_payload, get_provider_rates, match_rate


@pytest.fixture(autouse=True)
def _isolate_global_routing_state():
    """load_model_settings_cache ghi đè overlay/snapshot toàn process; khôi phục sau test."""
    saved_overlay = dict(ms._overlay)
    saved_snapshot = ms.get_routing_snapshot()
    yield
    ms._overlay.clear()
    ms._overlay.update(saved_overlay)
    ms._refresh_routing_snapshot(saved_snapshot.channels, saved_snapshot.function_bindings)
    config_module.get_settings.cache_clear()


def test_migrate_seeds_default_rates_when_missing():
    out, changed = ms._migrate_legacy_config({"flat": {}, "function_bindings": {"slots": {}, "overrides": {}}})
    assert changed
    assert out["provider_rates"] == default_provider_rates_payload()


def test_migrate_keeps_empty_rate_table():
    cfg = {"flat": {}, "function_bindings": {"slots": {}, "overrides": {}}, "provider_rates": []}
    out, changed = ms._migrate_legacy_config(cfg)
    assert not changed
    assert out["provider_rates"] == []


async def test_load_cache_reads_rates_from_db(db_session):
    row = await ms._get_or_create_app_row(db_session)
    row.config_json = {**(row.config_json or {}),
                       "provider_rates": [{"pattern": "house-model-*", "unit": "per_image", "usd": 0.5}]}
    await db_session.commit()
    await ms.load_model_settings_cache(db_session)
    assert match_rate("house-model-1").usd == 0.5
    assert match_rate("dola-seedream-5-0-pro-260628") is None


async def test_load_cache_seeds_and_persists_defaults(db_session):
    row = await ms._get_or_create_app_row(db_session)
    cfg = dict(row.config_json or {})
    cfg.pop("provider_rates", None)
    row.config_json = cfg
    await db_session.commit()
    await ms.load_model_settings_cache(db_session)
    await db_session.refresh(row)
    assert row.config_json["provider_rates"] == default_provider_rates_payload()
    assert len(get_provider_rates()) == len(default_provider_rates_payload())
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provider_rates_store.py -v`
Expected: FAIL — `KeyError: 'provider_rates'` và `match_rate("house-model-1")` là `None`.

- [ ] **Step 3: Sửa `_migrate_legacy_config`**

Trong `backend/app/services/model_settings.py`, hàm `_migrate_legacy_config`, ngay sau khối `if "function_bindings" not in out: ...` thêm:

```python
    if "provider_rates" not in out:
        # lazy import: gói billing kéo theo nhiều module, tránh vòng import lúc khởi động
        from app.services.billing.provider_rates import default_provider_rates_payload

        out["provider_rates"] = default_provider_rates_payload()
        changed = True
```

Và sửa docstring hàm thành: `"""Bỏ logical_models/default_models thời TokenFree, dọn flat còn sót; đảm bảo có function_bindings và provider_rates."""`

- [ ] **Step 4: Sửa `load_model_settings_cache`**

Thay toàn bộ hàm bằng:

```python
async def load_model_settings_cache(db: AsyncSession) -> None:
    """Nạp snapshot routing, overlay flat và bảng provider_rates lúc khởi động / sau khi lưu."""
    from app.services.billing.provider_rates import parse_provider_rates, set_provider_rates

    channels, bindings, flat, app_row = await _compose_runtime_state(db)
    rates_raw = (app_row.config_json or {}).get("provider_rates")
    await db.commit()
    _refresh_routing_snapshot(channels, bindings)
    _refresh_overlay({"flat": flat})
    reload_settings()
    set_provider_rates(parse_provider_rates(rates_raw))
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provider_rates_store.py tests/test_model_settings_bootstrap.py tests/test_admin_routing_settings.py -v`
Expected: PASS.

- [ ] **Step 6: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/model_settings.py backend/tests/test_provider_rates_store.py
git commit -m "$(cat <<'EOF'
feat: seed và nạp provider_rates từ app_settings khi khởi động

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Ước tính đóng băng theo `provider_rates` + slot chức năng (`rate_quotes.py`, viết lại `estimates.py`)

**Files:**
- Create: `backend/app/services/billing/rate_quotes.py`
- Rewrite: `backend/app/services/billing/estimates.py`
- Modify: `backend/tests/conftest.py` (fixture `priced_routing`; bỏ dòng stub `estimates.ensure_official_rates`)
- Rewrite: `backend/tests/test_signup_image_grant.py`, `backend/tests/test_fragment_video_estimate.py`
- Modify: `backend/tests/test_kepu_phase_billing.py` (2 test video)
- Test: `backend/tests/test_rate_quotes.py`

**Interfaces:**
- Consumes: `match_rate`, `rate_cost_usd`, `EST_IMAGE_OUTPUT_TOKENS` (Task 1); `usd_to_fen` (Task 1); `charge_fen_for_tokens(tokens, billing_key, *, settings) -> (cost, charge)` (có sẵn `pricing.py`); `function_router.allowed_bindings(function_id, *, snapshot)`; `functions.function_capability(function_id)`; `model_settings.get_routing_snapshot()` / `RoutingSnapshot`.
- Produces:
  ```python
  # rate_quotes.py
  VIDEO_FPS = 24
  VIDEO_PIXELS: dict[str, int]    # 480p 864×480, 720p 1280×720, 1080p 1920×1080
  def function_models(function_id: str, *, settings=None, snapshot=None) -> list[str]
  def normalize_video_resolution(resolution: str | None, settings) -> str
  def video_tokens(seconds: float, resolution: str) -> int     # ceil(max(s,2) × w × h × 24 / 1024)
  def image_unit_fen(function_id: str, *, settings=None, snapshot=None) -> int     # ≥ 1, không buffer
  def video_fen(function_id: str, seconds: float, *, resolution: str = "", settings=None, snapshot=None) -> int
  def text_fen(function_id: str, tokens: int, *, settings=None, snapshot=None) -> int
  def tts_fen(function_id: str, tokens: int, *, settings=None, snapshot=None) -> int
  # estimates.py (giữ tên public)
  def estimate_phase_fen(project, phase: str, settings=None, *, snapshot=None) -> int
  async def estimate_task_fen(db, task, settings=None) -> int
  ```
  Tất cả hàm `*_fen` của `rate_quotes` trả giá **chưa nhân buffer**; lấy **giá cao nhất** trong các model hiệu lực của chức năng; slot chưa gán → dùng nhãn `settings.model_llm/model_image/model_video/model_audio`; model không có giá → giá token dự phòng (`BILLING_*_PER_M`, ảnh dùng `billing_est_seedream_tokens`).
- Fixture `priced_routing` (conftest) — snapshot chuẩn dùng lại ở Task 4–6: kênh `byteplus` (ark: `dola-seedream-5-0-pro-260628`, `dreamina-seedance-2-5-260628`) + `openai` (openai: `gpt-5.6-sol`, `gpt-4o-mini-tts`), 4 slot gán tương ứng.

- [ ] **Step 1: Thêm fixture `priced_routing` và bỏ stub `estimates` trong `conftest.py`**

Trong `backend/tests/conftest.py`, trong fixture `skip_tokenfree_pricing_network` **xoá** dòng:

```python
    monkeypatch.setattr("app.services.billing.estimates.ensure_official_rates", _empty)
```

rồi thêm fixture mới ngay dưới `reset_provider_rates`:

```python
@pytest.fixture
def priced_routing():
    """Snapshot routing chuẩn cho test tính giá: BytePlus (ảnh/video) + OpenAI (văn bản/giọng), 4 slot đã gán."""
    from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
    from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot

    prev = get_routing_snapshot()
    channels = [
        SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
                           api_key="k", has_api_key=True, protocol="ark",
                           models=["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"], enabled=True),
        SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k",
                           has_api_key=True, protocol="openai", models=["gpt-5.6-sol", "gpt-4o-mini-tts"], enabled=True),
    ]
    bindings = FunctionBindings(slots={
        "text": [ModelBinding(channel_id="openai", model="gpt-5.6-sol")],
        "image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")],
        "video": [ModelBinding(channel_id="byteplus", model="dreamina-seedance-2-5-260628")],
        "audio": [ModelBinding(channel_id="openai", model="gpt-4o-mini-tts")],
    })
    _refresh_routing_snapshot(channels, bindings)
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)
```

- [ ] **Step 2: Viết test thất bại cho `rate_quotes`**

```python
# backend/tests/test_rate_quotes.py
"""rate_quotes: đơn giá ước tính theo chức năng = model đắt nhất trong slot hiệu lực × provider_rates."""
from __future__ import annotations

from types import SimpleNamespace

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.billing import rate_quotes as rq
from app.services.model_settings import RoutingSnapshot

S = SimpleNamespace(
    billing_usd_cny=7.0, billing_est_seedream_tokens=45_000, billing_seedream_per_m=8.0,
    billing_seedance_video0=46.0, billing_seedance_video1=28.0, billing_llm_per_m=5.0, billing_tts_per_m=2.0,
    billing_markup=1.0, ark_video_resolution="480p",
    model_llm="gpt-5.6-sol", model_image="dola-seedream-5-0-pro-260628",
    model_video="dreamina-seedance-2-5-260628", model_audio="gpt-4o-mini-tts",
)


def _ch(cid, protocol, models, enabled=True):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key="k", has_api_key=True,
                              protocol=protocol, models=models, enabled=enabled)


def _snap(slots, channels=None):
    channels = channels or [
        _ch("byteplus", "ark", ["dola-seedream-5-0-pro-260628", "seedream-5-0-260128", "ep-2026-img",
                                "dreamina-seedance-2-5-260628", "dreamina-seedance-2-0-fast-260128"]),
        _ch("openai", "openai", ["gpt-image-2", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-4o-mini-tts"]),
    ]
    return RoutingSnapshot(channels=channels, function_bindings=FunctionBindings(slots={
        cap: [ModelBinding(channel_id=c, model=m) for c, m in items] for cap, items in slots.items()
    }))


def test_video_tokens_formula():
    assert rq.video_tokens(5, "480p") == 48_600
    assert rq.video_tokens(5, "720p") == 108_000
    assert rq.video_tokens(1, "480p") == rq.video_tokens(2, "480p")      # tối thiểu 2 giây


def test_image_unit_takes_max_per_image_in_slot():
    snap = _snap({"image": [("byteplus", "seedream-5-0-260128"), ("byteplus", "dola-seedream-5-0-pro-260628")]})
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 32     # 0.045 USD


def test_image_unit_token_priced_model_uses_output_token_ceiling():
    snap = _snap({"image": [("openai", "gpt-image-2")]})
    assert rq.image_unit_fen("tools.image", settings=S, snapshot=snap) == 132   # 6240 × 30 / 1e6 USD


def test_image_unit_unpriced_model_uses_token_fallback():
    snap = _snap({"image": [("byteplus", "ep-2026-img")]})
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 36     # 45 000 token × 8 元/M


def test_video_fen_by_resolution():
    snap = _snap({"video": [("byteplus", "dreamina-seedance-2-5-260628")]})
    assert rq.video_fen("drama.video", 5, resolution="480p", settings=S, snapshot=snap) == 365
    assert rq.video_fen("drama.video", 5, resolution="720p", settings=S, snapshot=snap) == 809
    assert rq.video_fen("drama.video", 5, resolution="", settings=S, snapshot=snap) == 365      # theo settings 480p
    assert rq.video_fen("drama.video", 5, resolution="4k", settings=S, snapshot=snap) == 365    # lạ → 480p


def test_video_fen_ignores_disabled_provider():
    channels = [
        _ch("off", "ark", ["dreamina-seedance-2-5-260628"], enabled=False),
        _ch("byteplus", "ark", ["dreamina-seedance-2-0-fast-260128"]),
    ]
    snap = _snap({"video": [("off", "dreamina-seedance-2-5-260628"), ("byteplus", "dreamina-seedance-2-0-fast-260128")]},
                 channels)
    assert rq.video_fen("kepu.video", 5, resolution="480p", settings=S, snapshot=snap) == 191   # chỉ giá Fast 5.6


def test_text_fen_takes_priciest_model():
    snap = _snap({"text": [("openai", "gpt-5.6-terra"), ("openai", "gpt-5.6-sol")]})
    assert rq.text_fen("drama.script", 80_000, settings=S, snapshot=snap) == 493


def test_tts_fen_output_tokens():
    snap = _snap({"audio": [("openai", "gpt-4o-mini-tts")]})
    assert rq.tts_fen("drama.tts", 5_000, settings=S, snapshot=snap) == 42


def test_unassigned_slot_falls_back_to_settings_label():
    snap = _snap({})
    assert rq.function_models("kepu.image", settings=S, snapshot=snap) == ["dola-seedream-5-0-pro-260628"]
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 32


def test_override_wins_over_slot():
    snap = _snap({"image": [("byteplus", "dola-seedream-5-0-pro-260628")]})
    snap.function_bindings.overrides["tools.image"] = [ModelBinding(channel_id="openai", model="gpt-image-2")]
    assert rq.function_models("tools.image", settings=S, snapshot=snap) == ["gpt-image-2"]
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rate_quotes.py -v`
Expected: FAIL — `ImportError: cannot import name 'rate_quotes'`.

- [ ] **Step 4: Tạo `rate_quotes.py`**

```python
# backend/app/services/billing/rate_quotes.py
"""Đơn giá ước tính theo chức năng: model hiệu lực của slot × provider_rates, lấy mức đắt nhất (chưa buffer)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from app.config import get_settings
from app.services.billing.money import usd_to_fen
from app.services.billing.pricing import charge_fen_for_tokens
from app.services.billing.provider_rates import EST_IMAGE_OUTPUT_TOKENS, match_rate, rate_cost_usd

VIDEO_FPS = 24
# Diện tích khung 16:9 theo độ phân giải Seedance (tỉ lệ khác có diện tích xấp xỉ, đủ cho ước tính)
VIDEO_PIXELS: dict[str, int] = {"480p": 864 * 480, "720p": 1280 * 720, "1080p": 1920 * 1080}
_CAP_LABEL_FIELD = {"text": "model_llm", "image": "model_image", "video": "model_video", "audio": "model_audio"}


def _snapshot(snapshot: Any | None) -> Any:
    """Snapshot truyền vào, hoặc snapshot routing hiện hành."""
    if snapshot is not None:
        return snapshot
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def function_models(function_id: str, *, settings: Any | None = None, snapshot: Any | None = None) -> list[str]:
    """Model hiệu lực (đã loại provider tắt/thiếu key) của chức năng; slot chưa gán → nhãn settings.model_*."""
    from app.services.function_router import allowed_bindings
    from app.services.functions import function_capability

    s = settings or get_settings()
    models = list(dict.fromkeys(b.model for b in allowed_bindings(function_id, snapshot=_snapshot(snapshot))))
    if models:
        return models
    label = str(getattr(s, _CAP_LABEL_FIELD[function_capability(function_id)], "") or "").strip()
    return [label] if label else []


def _rate_fen(model: str, fallback_tokens: int, settings: Any) -> int | None:
    """Giá fen theo provider_rates với số lượng ước tính; model không có giá → None."""
    rate = match_rate(model)
    if rate is None:
        return None
    usd = rate_cost_usd(rate, {}, fallback_tokens=fallback_tokens)
    return usd_to_fen(usd, settings) if usd else None


def _max_fen(models: list[str], price: Callable[[str], int]) -> int:
    """Giá cao nhất trong danh sách model (rỗng → giá của model rỗng = dự phòng), tối thiểu 1 fen."""
    return max(1, max((price(m) for m in models), default=price("")))


def normalize_video_resolution(resolution: str | None, settings: Any) -> str:
    """Chỉ nhận 480p/720p/1080p; giá trị lạ → ark_video_resolution → 480p."""
    raw = (resolution or "").strip().lower()
    if raw in VIDEO_PIXELS:
        return raw
    fallback = str(getattr(settings, "ark_video_resolution", "") or "480p").strip().lower()
    return fallback if fallback in VIDEO_PIXELS else "480p"


def video_tokens(seconds: float, resolution: str) -> int:
    """Token Seedance ước tính: ceil(max(giây, 2) × rộng × cao × 24 / 1024)."""
    secs = max(float(seconds or 0), 2.0)
    return int(math.ceil(secs * VIDEO_PIXELS[resolution] * VIDEO_FPS / 1024))


def image_unit_fen(function_id: str, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá một ảnh (đắt nhất trong slot); model tính theo token dùng trần EST_IMAGE_OUTPUT_TOKENS."""
    s = settings or get_settings()

    def price(model: str) -> int:
        hit = _rate_fen(model, EST_IMAGE_OUTPUT_TOKENS, s)
        if hit is not None:
            return hit
        cost, _ = charge_fen_for_tokens(int(s.billing_est_seedream_tokens), "seedream", settings=s)
        return cost

    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot), price)


def video_fen(
    function_id: str,
    seconds: float,
    *,
    resolution: str = "",
    settings: Any | None = None,
    snapshot: Any | None = None,
) -> int:
    """Giá một video: token theo thời lượng × độ phân giải × giá/M của model đắt nhất trong slot."""
    s = settings or get_settings()
    tokens = video_tokens(seconds, normalize_video_resolution(resolution, s))

    def price(model: str) -> int:
        hit = _rate_fen(model, tokens, s)
        if hit is not None:
            return hit
        cost, _ = charge_fen_for_tokens(tokens, "seedance2:video0", settings=s)
        return cost

    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot), price)


def _token_price(model: str, tokens: int, billing_key: str, settings: Any) -> int:
    """Giá fen cho `tokens` theo provider_rates, không có giá → đơn giá token dự phòng của billing_key."""
    hit = _rate_fen(model, tokens, settings)
    if hit is not None:
        return hit
    cost, _ = charge_fen_for_tokens(tokens, billing_key, settings=settings)
    return cost


def text_fen(function_id: str, tokens: int, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá LLM cho số token ước tính (tách 70/30 vào/ra) theo model đắt nhất của chức năng văn bản."""
    s = settings or get_settings()
    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot),
                    lambda m: _token_price(m, int(tokens), "llm_chat", s))


def tts_fen(function_id: str, tokens: int, *, settings: Any | None = None, snapshot: Any | None = None) -> int:
    """Giá giọng đọc cho số token/ký tự ước tính theo model đắt nhất của chức năng giọng đọc."""
    s = settings or get_settings()
    return _max_fen(function_models(function_id, settings=s, snapshot=snapshot),
                    lambda m: _token_price(m, int(tokens), "tts", s))
```

- [ ] **Step 5: Chạy test `rate_quotes`, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rate_quotes.py -v`
Expected: PASS (11 test).

- [ ] **Step 6: Viết lại test ước tính (thất bại với `estimates.py` cũ)**

Thay toàn bộ `backend/tests/test_signup_image_grant.py`:

```python
"""Đóng băng ảnh phải vừa tiền tặng đăng ký; giá/ảnh theo provider_rates, không nhân buffer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.models_tasks import TaskRun
from app.services.billing.estimates import estimate_task_fen


@pytest.fixture
def _billing_settings(monkeypatch):
    """Tỉ giá 7, buffer 1.2 (để chứng minh ảnh không nhân buffer), tặng 500 fen."""
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.2)
    monkeypatch.setattr(settings, "billing_signup_grant_fen", 500)
    return settings


async def test_asset_image_freeze_fits_signup_grant(_billing_settings, priced_routing):
    """Seedream 5.0 Pro 0.045 USD → 32 fen ≤ 500 fen tặng."""
    task = TaskRun(id=1, domain="drama", task_type="asset_image", requested_by=1, payload={})
    fen = await estimate_task_fen(MagicMock(), task, settings=_billing_settings)
    assert fen == 32
    assert fen <= int(_billing_settings.billing_signup_grant_fen)


async def test_tool_image_freeze_skips_estimate_buffer(_billing_settings, priced_routing):
    task = TaskRun(id=2, domain="studio", task_type="tool_image", requested_by=1, payload={})
    assert await estimate_task_fen(MagicMock(), task, settings=_billing_settings) == 32


@pytest.mark.parametrize("payload", [{"resolution": "3K"}, {"size": "1K"}, {"size": "4K"}])
async def test_image_size_does_not_change_per_image_price(_billing_settings, priced_routing, payload):
    """Seedream tính giá theo ảnh, không theo độ phân giải (bỏ bậc 1K/2K/4K kiểu Kie)."""
    task = TaskRun(id=3, domain="studio", task_type="tool_image", requested_by=1, payload=payload)
    assert await estimate_task_fen(MagicMock(), task, settings=_billing_settings) == 32
```

Thay toàn bộ `backend/tests/test_fragment_video_estimate.py`:

```python
"""fragment_video: đóng băng theo thời lượng (payload / nội dung phân cảnh) × độ phân giải × giá Seedance."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import get_settings
from app.models_tasks import TaskRun
from app.services.billing.estimates import estimate_task_fen


@pytest.fixture
def _settings(monkeypatch):
    """Tỉ giá 7, buffer 1.0 để so số tuyệt đối."""
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.0)
    return settings


def _task(payload: dict, fragment_id: int = 9, task_id: int = 4) -> TaskRun:
    return TaskRun(id=task_id, domain="drama", task_type="fragment_video", requested_by=1,
                   payload=payload, fragment_id=fragment_id)


async def test_fragment_video_estimate_uses_payload_duration_sec(_settings, priced_routing):
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    fen8 = await estimate_task_fen(db, _task({"duration_sec": 8, "resolution": "720p"}), settings=_settings)
    fen16 = await estimate_task_fen(db, _task({"duration_sec": 16, "resolution": "720p"}), settings=_settings)
    assert fen16 > fen8


async def test_fragment_video_estimate_by_resolution(_settings, priced_routing):
    """Seedance 2.5 5 giây: 480p 365 fen, 720p 809 fen; cộng nửa giá ảnh (32 // 2 = 16); mặc định 720p."""
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    fen_480 = await estimate_task_fen(db, _task({"duration_sec": 5, "resolution": "480p"}), settings=_settings)
    fen_720 = await estimate_task_fen(db, _task({"duration_sec": 5, "resolution": "720p"}), settings=_settings)
    fen_default = await estimate_task_fen(db, _task({"duration_sec": 5}), settings=_settings)
    assert fen_480 == 365 + 16
    assert fen_720 == 809 + 16
    assert fen_default == fen_720


async def test_fragment_video_estimate_reads_fragment_content(_settings, priced_routing):
    """Không có thời lượng trong payload → đọc @duration trong nội dung phân cảnh."""
    frag = SimpleNamespace(content="@duration:12 thoại", duration_sec=8)
    db = MagicMock()
    db.get = AsyncMock(return_value=frag)
    fen = await estimate_task_fen(db, _task({"fragment_ids": [11]}, fragment_id=11), settings=_settings)
    assert fen > 0
    db.get.assert_awaited()
```

Trong `backend/tests/test_kepu_phase_billing.py`, thay hai test `test_videos_estimate_hd_doubles_480p` và `test_shot_regen_video_estimate_uses_project_hd` bằng:

```python
def test_videos_estimate_hd_uses_720p_price(monkeypatch, priced_routing) -> None:
    """HD và cấu hình 480p → đóng băng theo 720p (Seedance 2.5, 5 giây: 365 → 809 fen)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ark_video_resolution", "480p")
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.0)
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    shots = [_shot(image_url="/i.png", audio_url="/a.wav", duration=5)]
    preview = estimate_phase_fen(_project(shots), "videos", settings=settings)
    hd = estimate_phase_fen(_project(shots, resolution_mode="hd"), "videos", settings=settings)
    assert preview == 365
    assert hd == 809


@pytest.mark.asyncio
async def test_shot_regen_video_estimate_uses_project_hd(monkeypatch, priced_routing) -> None:
    """Tạo lại video một phân cảnh theo HD của dự án (480p → 720p)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ark_video_resolution", "480p")
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.0)
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    db = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(resolution_mode="hd"))
    task = TaskRun(id=9, domain="kepu", task_type="shot_regen_video", requested_by=1, project_id=3,
                   payload={"duration": 5})
    hd = await estimate_task_fen(db, task, settings=settings)
    db.get = AsyncMock(return_value=SimpleNamespace(resolution_mode="preview"))
    preview = await estimate_task_fen(db, task, settings=settings)
    assert (hd, preview) == (809, 365)
```

- [ ] **Step 7: Chạy test ước tính, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_signup_image_grant.py tests/test_fragment_video_estimate.py tests/test_kepu_phase_billing.py -v`
Expected: FAIL — số cũ kiểu Kie (35) / Volcano 480P (336), không khớp 32 / 365 / 809.

- [ ] **Step 8: Viết lại `estimates.py`**

Thay toàn bộ `backend/app/services/billing/estimates.py`:

```python
# -*- coding: utf-8 -*-
"""按 TaskRun 估算预扣金额：provider_rates × 功能 slot 内最贵模型（mục 6.2 spec）。"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.models import Project
from app.models_tasks import TaskRun
from app.services.billing.rate_quotes import image_unit_fen, text_fen, tts_fen, video_fen
from app.services.kepu_stages import (
    normalize_kepu_pipeline_phase,
    project_audio_ready,
    resolve_kepu_billing_phase,
    shot_image_ready,
    shot_video_ready,
)

__all__ = [
    "estimate_phase_fen",
    "estimate_task_fen",
    "resolve_kepu_billing_phase",
]


def _kepu_video_resolution(project: Project | None, settings: Settings) -> str:
    """科普成片清晰度：设置项；HD 且配置为 480p 时升到 720p（与 pipeline 一致）。"""
    raw = str(getattr(settings, "ark_video_resolution", "") or "480p")
    mode = str(getattr(project, "resolution_mode", "") or "")
    if mode == "hd" and raw.strip().lower() == "480p":
        return "720p"
    return raw


def _drama_video_resolution(payload: dict) -> str:
    """漫剧成片默认 720p，与前端与 asset_video 缺省一致。"""
    prepared = payload.get("prepared") if isinstance(payload.get("prepared"), dict) else {}
    raw = str((prepared or {}).get("resolution") or payload.get("resolution") or "").strip()
    return raw or "720p"


def _buffered_fen(fen: int, settings: Settings) -> int:
    """token / 时长类估价乘缓冲；结果至少 1 分。"""
    buf = float(settings.billing_estimate_buffer or 1.2)
    return max(1, math.ceil(max(0, int(fen)) * buf))


def _current_snapshot() -> Any:
    """Một snapshot routing dùng chung cho cả lần ước tính (tránh đọc cấu hình đổi giữa chừng)."""
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def _llm_fen(function_id: str, settings: Settings, snapshot: Any, *, calls: int = 1) -> int:
    """LLM：hằng số token ước tính × số lần gọi × giá model đắt nhất của chức năng, nhân buffer."""
    tokens = int(settings.billing_est_llm_tokens) * max(int(calls), 1)
    return _buffered_fen(text_fen(function_id, tokens, settings=settings, snapshot=snapshot), settings)


def _tts_fen(function_id: str, settings: Settings, snapshot: Any, *, units: int = 1) -> int:
    """TTS：hằng số token ước tính × số đoạn × giá model đắt nhất của chức năng giọng, nhân buffer."""
    tokens = int(settings.billing_est_tts_tokens) * max(int(units), 1)
    return _buffered_fen(tts_fen(function_id, tokens, settings=settings, snapshot=snapshot), settings)


def _image_fen(function_id: str, settings: Settings, snapshot: Any) -> int:
    """Ảnh：giá/ảnh cao nhất của chức năng, không nhân buffer (đã là giá quyết toán)."""
    return image_unit_fen(function_id, settings=settings, snapshot=snapshot)


def _estimate_assets_fen(project: Project, settings: Settings, snapshot: Any) -> int:
    """只估尚未完成的出图 + 整片配音（不含镜头视频）。"""
    shots = list(project.shots or [])
    need_img = sum(1 for s in shots if not shot_image_ready(s))
    need_tts = 0 if project_audio_ready(project) else 1
    if need_img <= 0 and need_tts <= 0:
        return 1
    total = max(need_img, 0) * _image_fen("kepu.image", settings, snapshot)
    if need_tts > 0:
        total += _tts_fen("kepu.tts", settings, snapshot, units=max(len(shots), 1))
    return max(total, 1)


def _estimate_videos_fen(project: Project, settings: Settings, snapshot: Any) -> int:
    """只估尚未出片的镜头视频；逐镜计价后整体乘缓冲。"""
    shots = [s for s in list(project.shots or []) if not shot_video_ready(s)]
    if not shots:
        return 1
    resolution = _kepu_video_resolution(project, settings)
    total = sum(
        video_fen("kepu.video", max(float(sh.duration or 4), 2.0), resolution=resolution,
                  settings=settings, snapshot=snapshot)
        for sh in shots
    )
    return _buffered_fen(total, settings)


def estimate_phase_fen(
    project: Project,
    phase: str,
    settings: Settings | None = None,
    *,
    snapshot: Any | None = None,
) -> int:
    """科普 pipeline 阶段估算：script | assets | videos | compose | produce(兼容→下一段)。"""
    s = settings or get_settings()
    snap = snapshot if snapshot is not None else _current_snapshot()
    raw = normalize_kepu_pipeline_phase(phase, project)
    if raw == "script":
        return _llm_fen("kepu.script", s, snap)
    if raw == "videos":
        return _estimate_videos_fen(project, s, snap)
    if raw == "compose":
        return 1
    return _estimate_assets_fen(project, s, snap)


async def _drama_video_duration(db: AsyncSession, task: TaskRun, payload: dict) -> float:
    """漫剧视频时长：payload → prepared → 分镜正文 @duration → 8 秒。"""
    dur = float(payload.get("duration_sec") or payload.get("duration") or 0)
    if dur <= 0 and isinstance(payload.get("prepared"), dict):
        dur = float(payload["prepared"].get("duration") or 0)
    if dur <= 0:
        frag_ids = payload.get("fragment_ids")
        frag_id = task.fragment_id or ((frag_ids or [None])[0] if isinstance(frag_ids, list) else None)
        if frag_id:
            from app.models_drama import DramaEpisodeFragment
            from app.services.drama.fragment_content_duration import resolve_seedance_duration_from_content

            frag = await db.get(DramaEpisodeFragment, int(frag_id))
            if frag is not None:
                dur = float(resolve_seedance_duration_from_content(
                    frag.content or "", fallback=int(frag.duration_sec or 8)))
    return dur if dur > 0 else 8.0


async def estimate_task_fen(db: AsyncSession, task: TaskRun, settings: Settings | None = None) -> int:
    """按 domain + task_type 估算单任务预扣（分）。"""
    s = settings or get_settings()
    snap = _current_snapshot()
    domain = (task.domain or "").strip()
    task_type = (task.task_type or "").strip()
    payload = task.payload if isinstance(task.payload, dict) else {}

    if domain == "kepu":
        if task_type == "project_pipeline":
            project_id = task.project_id or payload.get("project_id")
            project = None
            if project_id:
                result = await db.execute(
                    select(Project).where(Project.id == int(project_id)).options(selectinload(Project.shots))
                )
                project = result.scalar_one_or_none()
            if not project:
                return _llm_fen("kepu.script", s, snap)
            return estimate_phase_fen(project, str(payload.get("phase") or "script"), settings=s, snapshot=snap)
        if task_type == "shot_regen_image":
            return _image_fen("kepu.image", s, snap)
        if task_type == "shot_regen_video":
            project_id = task.project_id or payload.get("project_id")
            project = await db.get(Project, int(project_id)) if project_id else None
            fen = video_fen("kepu.video", max(float(payload.get("duration") or 5), 2.0),
                            resolution=_kepu_video_resolution(project, s), settings=s, snapshot=snap)
            return _buffered_fen(fen, s)
        if task_type in {"shot_regen_audio", "project_regen_audio"}:
            return _tts_fen("kepu.tts", s, snap, units=3)
        if task_type == "project_compose_only":
            return 1
        if task_type == "content_expand":
            return _llm_fen("kepu.script", s, snap)

    if domain == "drama":
        if task_type in {"script_summary", "fragment_plan", "agent_chat", "skill_optimize", "voice_prompt"}:
            return _llm_fen("drama.script", s, snap)
        if task_type == "episode_script":
            total_eps = int(payload.get("total") or payload.get("episode_count") or 1)
            return _llm_fen("drama.script", s, snap, calls=total_eps)
        if task_type == "seed_assets":
            return _llm_fen("drama.script", s, snap, calls=3)
        if task_type == "asset_image":
            return _image_fen("drama.asset_image", s, snap)
        if task_type in {"asset_video", "fragment_video"}:
            dur = await _drama_video_duration(db, task, payload)
            fen = _buffered_fen(video_fen("drama.video", max(dur, 2.0), resolution=_drama_video_resolution(payload),
                                          settings=s, snapshot=snap), s)
            if task_type == "fragment_video":
                fen += max(1, _image_fen("drama.asset_image", s, snap) // 2)
            return fen
        if task_type == "voice_synthesis":
            return _tts_fen("drama.tts", s, snap)

    if domain in {"api", "studio"}:
        if task_type in {"v1_image", "tool_image"}:
            return _image_fen("tools.image", s, snap)
        if task_type in {"v1_video", "v1_seedance", "tool_video"}:
            resolution = str(payload.get("resolution") or "").strip() or "480p"
            fen = video_fen("tools.video", max(float(payload.get("duration") or 5), 2.0), resolution=resolution,
                            settings=s, snapshot=snap)
            return _buffered_fen(fen, s)

    return _llm_fen("drama.script", s, snap)
```

- [ ] **Step 9: Chạy test ước tính + tích hợp, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rate_quotes.py tests/test_signup_image_grant.py tests/test_fragment_video_estimate.py tests/test_kepu_phase_billing.py tests/test_billing_integration.py -v`
Expected: PASS.

- [ ] **Step 10: Xác nhận `estimates.py` không còn phụ thuộc TokenFree**

Run: `cd backend && grep -n "tokenfree" app/services/billing/estimates.py app/services/billing/rate_quotes.py`
Expected: không có dòng nào.

- [ ] **Step 11: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 12: Commit**

```bash
git add backend/app/services/billing/rate_quotes.py backend/app/services/billing/estimates.py backend/tests/conftest.py backend/tests/test_rate_quotes.py backend/tests/test_signup_image_grant.py backend/tests/test_fragment_video_estimate.py backend/tests/test_kepu_phase_billing.py
git commit -m "$(cat <<'EOF'
feat: ước tính đóng băng theo provider_rates và model đắt nhất trong slot

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `adapter.cost_fen` thật + đưa model/chi phí thật tới dòng usage

**Files:**
- Modify: `backend/app/services/providers/base.py` (`TaskResult.model`)
- Modify: `backend/app/services/providers/ark_adapter.py` (`build_task_result_from_payload`, `cost_fen`)
- Modify: `backend/app/services/providers/openai_adapter.py` (`cost_fen`)
- Modify: `backend/app/services/providers/volc_tts_adapter.py` (`cost_fen`)
- Modify: `backend/app/services/media_gateway.py` (`fetch_task_once`)
- Modify: `backend/app/services/studio_tools.py` (`poll_video_task`)
- Modify: `backend/app/services/billing/ephemeral.py` (`settle_deferred_video_poll`)
- Modify: `backend/app/api/tools.py`, `backend/app/api/v1/generation.py`, `backend/app/services/tasks/poller.py` (truyền 2 tham số mới)
- Modify: `backend/app/services/drama/billing_util.py` (model thật cho dòng ảnh/video)
- Test: `backend/tests/test_adapter_cost_fen.py`

**Interfaces:**
- Consumes: `provider_cost_fen(model, raw_usage, *, settings=None)` (Task 1).
- Produces:
  ```python
  @dataclass class TaskResult: ...; model: str = ""          # model Ark báo trong payload tác vụ
  ArkAdapter/OpenAIAdapter/VolcTtsAdapter.cost_fen(model, raw_usage) -> int | None   # = provider_cost_fen
  poll_video_task(...) -> dict   # thêm khoá "upstream_cost_fen": int | None, "model": str (khi succeeded/failed)
  async def settle_deferred_video_poll(..., upstream_cost_fen: int | None = None, model: str = "") -> None
  ```
  `record_seedance_video_usage` / `record_seedream_image_usage` ghi `UsageEvent.model` = model thật (`task_result.model` / `image_result.model`), tham số `model` chỉ còn là nhãn dự phòng.

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_adapter_cost_fen.py
"""adapter.cost_fen tra provider_rates; poll video tính giá theo model tác vụ; chi phí thật tới dòng usage."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UsageEvent
from app.services.media_gateway import ImageResult
from app.services.providers import base
from app.services.providers.ark_adapter import ArkAdapter, build_task_result_from_payload
from app.services.providers.openai_adapter import OpenAIAdapter
from app.services.providers.volc_tts_adapter import VolcTtsAdapter
from tests.conftest import make_task, make_user
from tests.test_media_gateway import _FakeAdapter, _gateway, snapshot  # noqa: F401  (fixture dùng lại)


@pytest.fixture
def _usd7(monkeypatch):
    """Tỉ giá cố định 7 để so số fen tuyệt đối."""
    monkeypatch.setattr(get_settings(), "billing_usd_cny", 7.0)


def test_ark_cost_fen_video_tokens(_usd7):
    usage = {"completion_tokens": 108_000, "total_tokens": 108_000}
    assert ArkAdapter().cost_fen("dreamina-seedance-2-5-260628", usage) == 809


def test_ark_cost_fen_image_per_image(_usd7):
    assert ArkAdapter().cost_fen("dola-seedream-5-0-pro-260628", {"generated_images": 1, "size": "2K"}) == 32


def test_openai_cost_fen_image_output_tokens(_usd7):
    usage = {"input_tokens": 50, "output_tokens": 1200, "total_tokens": 1250}
    assert OpenAIAdapter().cost_fen("gpt-image-2", usage) == 26


def test_cost_fen_none_without_usage_or_rate(_usd7):
    assert ArkAdapter().cost_fen("dreamina-seedance-2-5-260628", None) is None
    assert OpenAIAdapter().cost_fen("ep-unknown", {"total_tokens": 10}) is None
    assert VolcTtsAdapter().cost_fen("seed-tts-1.0", None) is None


def test_build_task_result_keeps_task_model():
    data = {"status": "succeeded", "model": "dreamina-seedance-2-5-260628",
            "content": {"video_url": "https://x/v.mp4"}, "usage": {"completion_tokens": 9, "total_tokens": 9}}
    assert build_task_result_from_payload(data).model == "dreamina-seedance-2-5-260628"
    assert build_task_result_from_payload({"status": "running", "model": "m"}).model == "m"


class _CostAdapter(_FakeAdapter):
    """Adapter giả ghi lại model được dùng để tra giá."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cost_models: list[str] = []

    def cost_fen(self, model, raw):
        self.cost_models.append(model)
        return 777


async def test_fetch_task_once_prices_by_task_model(monkeypatch, snapshot):  # noqa: F811
    """Route poll dựng theo kênh (upstream_model rỗng) → giá phải tra theo model trong payload tác vụ."""
    fetched = base.TaskResult(status="succeeded", url="https://x/v.mp4", raw_usage={"total_tokens": 1000},
                              total_tokens=1000, model="dreamina-seedance-2-5-260628")
    ark = _CostAdapter("ark", fetch=fetched)
    g = _gateway(monkeypatch, {"ark": ark, "openai": _FakeAdapter("openai")})
    r = await g.fetch_task_once("cgt-1", channel_id="byteplus")
    assert ark.cost_models == ["dreamina-seedance-2-5-260628"]
    assert r.upstream_cost_fen == 777 and r.model == "dreamina-seedance-2-5-260628"


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
        upstream_cost_fen=809, model="dreamina-seedance-2-5-260628",
    )
    await db_session.commit()
    ev = (await db_session.execute(select(UsageEvent).where(UsageEvent.task_run_id == task.id))).scalar_one()
    assert ev.cost_fen == 809 and ev.charge_fen == 809
    assert ev.model == "dreamina-seedance-2-5-260628"
    assert ev.estimated is False


async def test_record_seedream_uses_actual_image_model(db_session: AsyncSession) -> None:
    from app.services.drama.billing_util import record_seedream_image_usage

    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", raw_usage={"generated_images": 1}, upstream_cost_fen=28,
                        channel_id="byteplus", model="seedream-4-5-251128")
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="nhan-cu", domain="studio",
                                           image_result=image)
    assert ev.model == "seedream-4-5-251128" and ev.cost_fen == 28
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_adapter_cost_fen.py -v`
Expected: FAIL — `cost_fen` trả `None`; `TaskResult.__init__() got an unexpected keyword argument 'model'`; `settle_deferred_video_poll() got an unexpected keyword argument 'upstream_cost_fen'`.

- [ ] **Step 3: `TaskResult.model`**

Trong `backend/app/services/providers/base.py`, class `TaskResult`, thêm dòng cuối sau `channel_id: str = ""`:

```python
    model: str = ""  # model upstream báo trong payload tác vụ (route poll không biết model)
```

- [ ] **Step 4: Ark — giữ model trong `TaskResult` và `cost_fen` thật**

Trong `backend/app/services/providers/ark_adapter.py`, thay toàn bộ hàm `build_task_result_from_payload` bằng:

```python
def build_task_result_from_payload(data: dict[str, Any]) -> TaskResult:
    """Đọc trực tiếp response truy vấn tác vụ Ark thành TaskResult (giữ cả model để tính giá)."""
    status = normalize_video_task_status(str(data.get("status", "") or "running"))
    usage_parsed = parse_usage_dict(data)
    common: dict[str, Any] = {
        "total_tokens": int(usage_parsed.get("total_tokens") or 0),
        "completion_tokens": int(usage_parsed.get("completion_tokens") or 0),
        "raw_usage": data.get("usage") if isinstance(data.get("usage"), dict) else None,
        "model": str(data.get("model") or ""),
    }
    if status == "succeeded":
        return TaskResult(
            status="succeeded",
            url=extract_video_result_url(data),
            last_frame_url=extract_seedance_last_frame_url(data),
            **common,
        )
    if status == "failed":
        err = data.get("error") or data.get("message") or data.get("fail_reason") or "failed"
        return TaskResult(status="failed", error=format_video_task_error(err), **common)
    return TaskResult(status="running", **common)
```

và thay `cost_fen` của `ArkAdapter`:

```python
    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates từ usage thật (Seedream: generated_images, Seedance: total_tokens)."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)
```

- [ ] **Step 5: OpenAI + Volc TTS `cost_fen`**

Trong `backend/app/services/providers/openai_adapter.py`, thay `cost_fen`:

```python
    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates từ usage thật (gpt-image: output_tokens)."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)
```

Trong `backend/app/services/providers/volc_tts_adapter.py`, thay `cost_fen`:

```python
    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates; openspeech không trả usage nên thực tế luôn None."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)
```

- [ ] **Step 6: `MediaGateway.fetch_task_once` tra giá theo model tác vụ**

Trong `backend/app/services/media_gateway.py`, ở cuối `fetch_task_once` thay:

```python
        result.provider_task_id = result.provider_task_id or task_id
        result.channel_id = result.channel_id or route.channel_id
        if result.raw_usage:
            result.upstream_cost_fen = adapter.cost_fen(route.upstream_model, result.raw_usage)
        return result
```

bằng:

```python
        result.provider_task_id = result.provider_task_id or task_id
        result.channel_id = result.channel_id or route.channel_id
        # Route poll dựng theo kênh (upstream_model rỗng) → tra giá theo model tác vụ trả về
        result.model = result.model or route.upstream_model
        if result.raw_usage:
            result.upstream_cost_fen = adapter.cost_fen(result.model, result.raw_usage)
        return result
```

- [ ] **Step 7: `poll_video_task` trả chi phí + model**

Trong `backend/app/services/studio_tools.py`, hàm `poll_video_task`: trong dict trả về của nhánh `succeeded` và nhánh `failed`, thêm sau khoá `"raw_usage": result.raw_usage,`:

```python
            "upstream_cost_fen": result.upstream_cost_fen,
            "model": result.model,
```

- [ ] **Step 8: `settle_deferred_video_poll` nhận chi phí + model**

Trong `backend/app/services/billing/ephemeral.py`, chữ ký `settle_deferred_video_poll` thêm hai tham số sau `billing_key: str | None = None,`:

```python
    upstream_cost_fen: int | None = None,
    model: str = "",
```

và thay khối dựng `task_result` + lời gọi `record_seedance_video_usage` trong nhánh `succeeded`:

```python
            task_result = None
            if usage_tokens > 0 or upstream_cost_fen is not None:
                from app.services.ark import TaskResult

                task_result = TaskResult(
                    status="succeeded",
                    total_tokens=int(usage_tokens),
                    completion_tokens=int(completion_tokens or usage_tokens),
                    raw_usage=raw_usage,
                    upstream_cost_fen=upstream_cost_fen,
                    model=model,
                )
            await record_seedance_video_usage(
                db,
                user_id=user.id,
                billing_key=key,
                model=model or get_settings().model_video,
                domain=task.domain or "api",
                task_result=task_result,
                fallback_duration_sec=payload.get("duration"),
                provider_task_id=provider_task_id,
                project_id=task.project_id,
                drama_project_id=task.drama_project_id,
                shot_id=task.shot_id,
                channel_id=task.provider_channel_id,
            )
```

- [ ] **Step 9: Ba chỗ gọi truyền tham số mới**

Trong `backend/app/services/tasks/poller.py` (`_poll_ephemeral_with_session`), `backend/app/api/tools.py` và `backend/app/api/v1/generation.py`, ở mỗi lời gọi `settle_deferred_video_poll(...)`, thêm hai đối số ngay sau dòng `raw_usage=data.get("raw_usage") if isinstance(data.get("raw_usage"), dict) else None,`:

```python
        upstream_cost_fen=data.get("upstream_cost_fen"),
        model=str(data.get("model") or ""),
```

- [ ] **Step 10: `billing_util` ghi model thật**

Trong `backend/app/services/drama/billing_util.py`:

(a) `record_seedance_video_usage`: ngay sau khối re-fetch (`if (not task_result or ...) and provider_id: ...`) thêm:

```python
    # Giá tra theo model tác vụ thực chạy; tham số `model` chỉ là nhãn dự phòng
    billing_model = str(getattr(task_result, "model", "") or "") or model
```

rồi ở **cả hai** lời gọi `record_line(...)` trong hàm, đổi `model=model,` thành `model=billing_model,`.

(b) `record_seedream_image_usage`: dòng đầu thân hàm thêm:

```python
    # Model thực tế đã sinh ảnh (ImageResult.model) thắng nhãn caller truyền vào
    model = str(getattr(image_result, "model", "") or "") or model
```

- [ ] **Step 11: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_adapter_cost_fen.py tests/test_media_gateway.py tests/test_ark_adapter.py tests/test_provider_channel_binding.py tests/test_billing_integration.py tests/test_record_seedream_image_usage.py -v`
Expected: PASS.

- [ ] **Step 12: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 13: Commit**

```bash
git add backend/app/services/providers backend/app/services/media_gateway.py backend/app/services/studio_tools.py backend/app/services/billing/ephemeral.py backend/app/api/tools.py backend/app/api/v1/generation.py backend/app/services/tasks/poller.py backend/app/services/drama/billing_util.py backend/tests/test_adapter_cost_fen.py
git commit -m "$(cat <<'EOF'
feat: adapter.cost_fen theo provider_rates, chi phí và model thật tới dòng usage

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: API admin `GET/PUT /api/admin/settings/billing/model-rates`

**Files:**
- Create: `backend/app/schemas_provider_rates.py`
- Create: `backend/app/services/billing/provider_rates_admin.py`
- Modify: `backend/app/api/admin/settings.py` (thay endpoint model-rates cũ)
- Test: `backend/tests/test_admin_provider_rates.py`

**Interfaces:**
- Consumes: Task 1 (`validate_provider_rates`, `parse_provider_rates`, `rate_to_dict`, `get_provider_rates`, `match_rate`, `DEFAULT_PROVIDER_RATES`, `RATE_UNITS`, `RATE_UNIT_LABELS`), `money.usd_cny_rate`, Task 2 (`load_model_settings_cache` nạp cache).
- Produces (hợp đồng Plan C, xem cuối file):
  ```python
  async def get_provider_rates_admin(db) -> AdminProviderRatesOut
  async def save_provider_rates_admin(db, body: AdminProviderRatesPut) -> AdminProviderRatesOut   # ValueError tiếng Việt
  def unpriced_models(snapshot=None, rates=None) -> list[UnpricedModel]
  ```
  Sau Task 5, `app/api/admin/settings.py` không còn import `tokenfree_pricing`.

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_admin_provider_rates.py
"""Admin bảng giá provider: GET mặc định, PUT lưu + nạp cache, lỗi tiếng Việt giữ nguyên cache, model chưa có giá."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config as config_module
from app.database import get_db
from app.deps import get_current_admin
from app.main import app
from app.models_settings import AppSettings
from app.schemas_provider_rates import AdminProviderRatesPut, ProviderRateRow
from app.schemas_routing import FunctionBindings, ModelBinding
from app.services import model_settings as ms
from app.services.billing import provider_rates_admin as pra
from app.services.billing.provider_rates import DEFAULT_PROVIDER_RATES, get_provider_rates, match_rate
from app.services.model_settings import RoutingSnapshot


@pytest.fixture(autouse=True)
def _isolate_global_routing_state():
    """save_* gọi load_model_settings_cache → ghi đè overlay/snapshot toàn process; khôi phục sau test."""
    saved_overlay = dict(ms._overlay)
    saved_snapshot = ms.get_routing_snapshot()
    yield
    ms._overlay.clear()
    ms._overlay.update(saved_overlay)
    ms._refresh_routing_snapshot(saved_snapshot.channels, saved_snapshot.function_bindings)
    config_module.get_settings.cache_clear()


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
    snap = RoutingSnapshot(channels=[], function_bindings=FunctionBindings(
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
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_provider_rates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas_provider_rates'`.

- [ ] **Step 3: Schema**

```python
# backend/app/schemas_provider_rates.py
"""Schema admin cho bảng giá provider (`/api/admin/settings/billing/model-rates`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderRateRow(BaseModel):
    """Một dòng giá admin xem/gửi; ràng buộc ngữ nghĩa kiểm ở service để trả thông điệp tiếng Việt."""

    pattern: str = Field(default="", max_length=256)
    unit: str = Field(default="", max_length=32)
    usd: float | None = None
    usd_out: float | None = None
    note: str = Field(default="", max_length=200)


class ProviderRateUnit(BaseModel):
    """Một đơn vị tính giá và nhãn hiển thị tiếng Việt."""

    id: str
    label: str


class UnpricedModel(BaseModel):
    """Model đang được gán nhưng chưa khớp dòng giá nào (sẽ tính theo giá token dự phòng)."""

    channel_id: str
    model: str
    capability: str


class AdminProviderRatesOut(BaseModel):
    """Bảng giá đang áp dụng + bảng mặc định + đơn vị + model chưa có giá + tỉ giá USD→CNY."""

    items: list[ProviderRateRow]
    defaults: list[ProviderRateRow]
    units: list[ProviderRateUnit]
    unpriced_models: list[UnpricedModel]
    usd_cny: float
    updated_at: datetime | None = None


class AdminProviderRatesPut(BaseModel):
    """Thay toàn bộ bảng giá (thứ tự dòng = thứ tự ưu tiên khớp)."""

    items: list[ProviderRateRow] = Field(default_factory=list)
```

- [ ] **Step 4: Service admin**

```python
# backend/app/services/billing/provider_rates_admin.py
"""Admin đọc/ghi bảng giá provider trong app_settings.config_json["provider_rates"]."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_settings import AppSettings
from app.schemas_provider_rates import (
    AdminProviderRatesOut,
    AdminProviderRatesPut,
    ProviderRateRow,
    ProviderRateUnit,
    UnpricedModel,
)
from app.services.billing.money import usd_cny_rate
from app.services.billing.provider_rates import (
    DEFAULT_PROVIDER_RATES,
    RATE_UNIT_LABELS,
    RATE_UNITS,
    ProviderRate,
    get_provider_rates,
    match_rate,
    parse_provider_rates,
    rate_to_dict,
    validate_provider_rates,
)


def _row(rate: ProviderRate) -> ProviderRateRow:
    """ProviderRate → dòng schema admin."""
    return ProviderRateRow(**rate_to_dict(rate))


def unpriced_models(snapshot: Any | None = None, rates: list[ProviderRate] | None = None) -> list[UnpricedModel]:
    """Model được gán ở slot/override mà không khớp dòng giá nào (theo thứ tự slot rồi override, không trùng)."""
    from app.services.functions import FUNCTION_BY_ID
    from app.services.model_settings import get_routing_snapshot

    snap = snapshot if snapshot is not None else get_routing_snapshot()
    table = rates if rates is not None else get_provider_rates()
    groups = list(snap.function_bindings.slots.items())
    groups += [(FUNCTION_BY_ID[fid].capability, items)
               for fid, items in snap.function_bindings.overrides.items() if fid in FUNCTION_BY_ID]
    seen: set[tuple[str, str]] = set()
    out: list[UnpricedModel] = []
    for capability, items in groups:
        for b in items:
            key = (b.channel_id, b.model)
            if key in seen or match_rate(b.model, table) is not None:
                continue
            seen.add(key)
            out.append(UnpricedModel(channel_id=b.channel_id, model=b.model, capability=capability))
    return out


async def _app_row(db: AsyncSession) -> AppSettings | None:
    """Dòng app_settings duy nhất (id="default")."""
    return (await db.execute(select(AppSettings).where(AppSettings.id == "default"))).scalar_one_or_none()


async def get_provider_rates_admin(db: AsyncSession) -> AdminProviderRatesOut:
    """Bảng giá đang áp dụng (cache process, đã nạp từ DB) kèm dữ liệu phụ cho màn admin."""
    rates = get_provider_rates()
    row = await _app_row(db)
    return AdminProviderRatesOut(
        items=[_row(r) for r in rates],
        defaults=[_row(r) for r in DEFAULT_PROVIDER_RATES],
        units=[ProviderRateUnit(id=u, label=RATE_UNIT_LABELS[u]) for u in RATE_UNITS],
        unpriced_models=unpriced_models(rates=rates),
        usd_cny=usd_cny_rate(),
        updated_at=row.updated_at if row else None,
    )


async def save_provider_rates_admin(db: AsyncSession, body: AdminProviderRatesPut) -> AdminProviderRatesOut:
    """Validate rồi thay toàn bộ bảng giá; lỗi → ValueError (tiếng Việt, tối đa 5 lỗi), cache giữ nguyên."""
    from app.services.model_settings import load_model_settings_cache

    items = [r.model_dump() for r in body.items]
    errors = validate_provider_rates(items)
    if errors:
        raise ValueError("; ".join(errors[:5]))
    await load_model_settings_cache(db)  # bảo đảm có dòng app_settings "default" đã migrate
    row = await _app_row(db)
    config = dict(row.config_json or {})
    config["provider_rates"] = [rate_to_dict(r) for r in parse_provider_rates(items)]
    row.config_json = config
    await db.commit()
    await load_model_settings_cache(db)
    return await get_provider_rates_admin(db)
```

- [ ] **Step 5: Endpoint**

Trong `backend/app/api/admin/settings.py`, thêm import:

```python
from app.schemas_provider_rates import AdminProviderRatesOut, AdminProviderRatesPut
from app.services.billing.provider_rates_admin import get_provider_rates_admin, save_provider_rates_admin
```

và thay toàn bộ hàm `admin_billing_model_rates` (khối `@router.get("/settings/billing/model-rates")` đang import `tokenfree_pricing`) bằng:

```python
@router.get("/settings/billing/model-rates", response_model=AdminProviderRatesOut)
async def admin_get_provider_rates(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProviderRatesOut:
    """Bảng giá provider_rates đang áp dụng + mặc định + đơn vị + model đã gán chưa có giá."""
    return await get_provider_rates_admin(db)


@router.put("/settings/billing/model-rates", response_model=AdminProviderRatesOut)
async def admin_put_provider_rates(
    body: AdminProviderRatesPut,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProviderRatesOut:
    """Thay toàn bộ bảng giá; lỗi validation trả 400 với thông điệp tiếng Việt."""
    try:
        return await save_provider_rates_admin(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 6: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_provider_rates.py -v`
Expected: PASS (8 test).

- [ ] **Step 7: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas_provider_rates.py backend/app/services/billing/provider_rates_admin.py backend/app/api/admin/settings.py backend/tests/test_admin_provider_rates.py
git commit -m "$(cat <<'EOF'
feat: API admin GET/PUT bảng giá provider_rates thay bảng giá TokenFree

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Quyết toán theo `provider_rates`; bỏ quota New API / yuan / Kie; xoá `tokenfree_pricing`

**Files:**
- Modify: `backend/app/services/billing/pricing.py`
- Modify: `backend/app/services/billing/rate_quotes.py` (thêm `priciest_model`, `estimated_line_model`)
- Modify: `backend/app/services/billing/usage.py` (`record_line`)
- Modify: `backend/app/services/billing/display.py`
- Modify: `backend/app/services/drama/billing_util.py` (bỏ gộp `creditsConsumed`)
- Modify: `backend/tests/conftest.py` (xoá fixture `skip_tokenfree_pricing_network`)
- Rewrite: `backend/tests/test_seedream_billing_usage.py`, `backend/tests/test_record_seedream_image_usage.py`
- Delete: `backend/app/services/tokenfree_pricing.py`, `backend/tests/test_tokenfree_pricing.py`, `backend/tests/test_tokenfree_usage.py`
- Test: `backend/tests/test_billing_rates_chain.py`

**Interfaces:**
- Consumes: Task 1 (`match_rate`, `rate_cost_usd`, `EST_IMAGE_OUTPUT_TOKENS`, `usd_to_fen`), Task 3 (`function_models`, `_token_price`), fixture `priced_routing`.
- Produces:
  ```python
  def parse_upstream_cost_fen(data: dict | None) -> int | None          # chỉ cost_fen / cost_cents
  def charge_fen_for_usage(tokens, billing_key, *, raw_usage=None, settings=None, model="") -> tuple[int, int, bool]
  # rate_quotes.py
  def priciest_model(function_id: str, tokens: int, billing_key: str, *, settings=None, snapshot=None) -> str
  def estimated_line_model(billing_key: str, domain: str | None, tokens: int, *, fallback: str = "", settings=None, snapshot=None) -> str
  ```
  Thứ tự tính `charge_fen_for_usage`: (1) `usage.cost_fen`/`cost_cents` > 0 → dùng, `used_upstream=True`; (2) dòng giá khớp `raw_usage["model"]` hoặc `model` → `rate_cost_usd(usage, fallback_tokens=tokens hoặc EST_IMAGE_OUTPUT_TOKENS cho ảnh)`; (3) giá token `BILLING_*_PER_M` (ảnh không token → `billing_est_seedream_tokens`). Không nhánh nào trả 0 cho ảnh.
  `record_line`: dòng `llm_chat`/`tts` ước tính mà `model` rỗng hoặc bằng nhãn `settings.model_llm`/`model_audio` → đổi `model` sang model đắt nhất của chức năng theo `domain` (`kepu` → `kepu.script`/`kepu.tts`, còn lại → `drama.script`/`drama.tts`), khớp số đã đóng băng.

- [ ] **Step 1: Viết test thất bại (thay `test_seedream_billing_usage.py`)**

```python
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


def test_raw_model_wins_over_label():
    raw = {"model": "dreamina-seedance-2-0-fast-260128", "usage": {"total_tokens": 100_000}}
    out = charge_fen_for_usage(100_000, "seedance2:video0", raw_usage=raw, settings=S,
                               model="dreamina-seedance-2-5-260628")
    assert out == (392, 392, False)


def test_token_priced_image_without_usage_uses_output_ceiling():
    raw = {"usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
    assert charge_fen_for_usage(0, "seedream", raw_usage=raw, settings=S, model="gpt-image-2") == (132, 132, False)


def test_unpriced_image_without_usage_never_free():
    assert charge_fen_for_usage(0, "seedream", raw_usage=None, settings=S, model="ep-2026-img") == (36, 36, False)


def test_llm_estimated_tokens_split_in_out():
    assert charge_fen_for_usage(80_000, "llm_chat", settings=S, model="gpt-5.6-sol") == (493, 493, False)


def test_empty_rate_table_falls_back_to_tokens():
    set_provider_rates([])
    assert charge_fen_for_usage(0, "seedream", settings=S, model="dola-seedream-5-0-pro-260628") == (36, 36, False)
    # 250 000 token × 46 元/M = 11.5 元 = 1150 fen (chọn số tròn để tránh nhiễu float của charge_fen_for_tokens)
    assert charge_fen_for_usage(250_000, "seedance2:video0", settings=S, model="dreamina-seedance-2-5-260628") == (
        1150, 1150, False)
```

- [ ] **Step 2: Viết test chuỗi đóng băng → usage → quyết toán (DB)**

```python
# backend/tests/test_billing_rates_chain.py
"""Chuỗi freeze → usage → settle dùng provider_rates; dòng LLM ước tính gắn model của slot."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UsageEvent
from app.services.billing.context import billing_scope
from app.services.billing.settlement import freeze_for_task, settle_task
from app.services.billing.usage import record_line
from app.services.drama.billing_util import record_seedream_image_usage
from app.services.media_gateway import ImageResult
from tests.conftest import make_task, make_user


@pytest.fixture
def _usd7(monkeypatch):
    """Tỉ giá 7, token LLM ước tính 80 000."""
    s = get_settings()
    monkeypatch.setattr(s, "billing_usd_cny", 7.0)
    monkeypatch.setattr(s, "billing_est_llm_tokens", 80_000)


async def test_asset_image_freeze_equals_settle(db_session: AsyncSession, priced_routing, _usd7) -> None:
    user = await make_user(db_session, balance_fen=1_000)
    task = await make_task(db_session, user, domain="drama", task_type="asset_image")
    await db_session.commit()
    need = await freeze_for_task(db_session, task)
    assert need == 32
    async with billing_scope(task.id):
        await record_seedream_image_usage(
            db_session, user_id=user.id, model="nhan-cu", domain="drama",
            image_result=ImageResult(local_url="/static/a.png", raw_usage={"generated_images": 1},
                                     channel_id="byteplus", model="dola-seedream-5-0-pro-260628"),
        )
    await db_session.commit()
    result = await settle_task(db_session, task.id)
    await db_session.commit()
    assert result == {"charged": 32, "refunded": 0}
    assert user.balance_fen == 1_000 - 32 and user.frozen_fen == 0


async def test_estimated_llm_line_uses_slot_model(db_session: AsyncSession, priced_routing, _usd7) -> None:
    user = await make_user(db_session)
    ev = await record_line(db_session, user_id=user.id, billing_key="llm_chat",
                           model=get_settings().model_llm, estimated=True, domain="drama")
    assert ev.model == "gpt-5.6-sol" and ev.charge_fen == 493 and ev.estimated is True
    kept = await record_line(db_session, user_id=user.id, billing_key="llm_chat", model="test-llm",
                             tokens=1000, estimated=True, domain="drama")
    assert kept.model == "test-llm"   # model caller đặt rõ ràng thì giữ nguyên


async def test_video_line_priced_by_task_model(db_session: AsyncSession, priced_routing, _usd7) -> None:
    from app.services.drama.billing_util import record_seedance_video_usage
    from app.services.providers.base import TaskResult

    user = await make_user(db_session)
    await record_seedance_video_usage(
        db_session, user_id=user.id, billing_key="seedance2:video0", model="nhan-cu", domain="drama",
        task_result=TaskResult(status="succeeded", total_tokens=108_000, completion_tokens=108_000,
                               raw_usage={"total_tokens": 108_000}, model="dreamina-seedance-2-5-260628"),
        drama_project_id=1,
    )
    await db_session.commit()
    ev = (await db_session.execute(select(UsageEvent).where(UsageEvent.user_id == user.id))).scalar_one()
    assert ev.cost_fen == 809 and ev.model == "dreamina-seedance-2-5-260628"
```

- [ ] **Step 3: Cập nhật kỳ vọng `test_record_seedream_image_usage.py`**

Thay toàn bộ file:

```python
"""record_seedream_image_usage: giá/ảnh theo provider_rates, cost_fen sẵn có thắng."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.drama.billing_util import record_seedream_image_usage
from app.services.media_gateway import ImageResult
from tests.conftest import make_user


@pytest.fixture(autouse=True)
def _usd7(monkeypatch):
    """Tỉ giá 7 để so số fen tuyệt đối."""
    monkeypatch.setattr(get_settings(), "billing_usd_cny", 7.0)


async def test_record_seedream_with_upstream_usage(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", total_tokens=120_000, completion_tokens=120_000,
                        raw_usage={"generated_images": 1, "total_tokens": 120_000})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="seedream-5-0-260128",
                                           domain="api", image_result=image)
    await db_session.commit()
    assert ev.estimated is False and ev.total_tokens == 120_000
    assert ev.charge_fen == 25          # 0.035 USD/ảnh, không phải 120k token × giá/M


async def test_record_seedream_empty_usage_token_priced_model(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", total_tokens=0,
                        raw_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="gpt-image-2", domain="drama",
                                           image_result=image)
    await db_session.commit()
    assert ev.estimated is True
    assert ev.charge_fen == ev.cost_fen == 132      # trần 6 240 token đầu ra × 30 USD/M


async def test_record_seedream_with_upstream_cost_fen(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "billing_markup", 2.0)
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", upstream_cost_fen=500, raw_usage={"cost_fen": 500})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="seedream-test", domain="studio",
                                           image_result=image)
    await db_session.commit()
    assert ev.estimated is False and ev.cost_fen == 500 and ev.charge_fen == 500
```

- [ ] **Step 4: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_seedream_billing_usage.py tests/test_billing_rates_chain.py tests/test_record_seedream_image_usage.py -v`
Expected: FAIL — `parse_upstream_cost_fen` vẫn đọc yuan/quota/Kie; `charge_fen_for_usage` vẫn trả giá Kie 35; dòng LLM ước tính vẫn mang nhãn `settings.model_llm` khi slot khác (hoặc giá 1000 token × 5 元/M).

- [ ] **Step 5: Viết lại phần giá trong `pricing.py`**

Trong `backend/app/services/billing/pricing.py`:

(a) Thêm import dưới `from app.config import Settings, get_settings`:

```python
from app.services.billing.money import usd_to_fen
from app.services.billing.provider_rates import EST_IMAGE_OUTPUT_TOKENS, match_rate, rate_cost_usd
```

(b) **Xoá** các định nghĩa: `DEFAULT_KIE_FEN_PER_CREDIT` (và comment Kie phía trên), `kie_fen_per_credit`, `kie_credits_to_cost_fen`, `_has_request_tokens`, `_extract_newapi_quota`, `_image_size_from_raw`, `_catalog_image_fen_if_per_call`, `billing_model_rate_rows`.

(c) Sửa docstring `user_charge_fen` thành `"""Tiền trừ user = chi phí upstream (không cộng markup)."""`.

(d) Thay `parse_upstream_cost_fen` và `charge_fen_for_usage` bằng:

```python
def parse_upstream_cost_fen(data: dict[str, Any] | None) -> int | None:
    """Chi phí đã quy sẵn ra fen trong usage (`cost_fen` / `cost_cents`); không có → None."""
    if not data:
        return None
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else data
    if not isinstance(usage, dict):
        return None
    for key in ("cost_fen", "cost_cents"):
        if usage.get(key) is not None:
            try:
                return max(0, int(usage[key]))
            except (TypeError, ValueError):
                pass
    return None


def _usage_block(raw_usage: dict[str, Any] | None) -> dict[str, Any]:
    """Khối usage bên trong raw (có lồng `usage` hay không)."""
    if not isinstance(raw_usage, dict):
        return {}
    inner = raw_usage.get("usage")
    return inner if isinstance(inner, dict) else raw_usage


def charge_fen_for_usage(
    tokens: int,
    billing_key: str,
    *,
    raw_usage: dict[str, Any] | None = None,
    settings: Settings | None = None,
    model: str = "",
) -> tuple[int, int, bool]:
    """(cost_fen, charge_fen, used_upstream_cost): cost_fen sẵn có → provider_rates theo model → giá token dự phòng.

    Model tra giá: `raw_usage["model"]` (model upstream thật) nếu có, không thì tham số `model`.
    Ảnh không có số token dùng trần EST_IMAGE_OUTPUT_TOKENS (giá token) hoặc billing_est_seedream_tokens (dự phòng).
    """
    s = settings or get_settings()
    upstream_cost = parse_upstream_cost_fen(raw_usage)
    if upstream_cost is not None and upstream_cost > 0:
        return upstream_cost, user_charge_fen(upstream_cost, s), True
    key = (billing_key or "").strip()
    t = max(0, int(tokens or 0))
    raw_model = str(raw_usage.get("model") or "") if isinstance(raw_usage, dict) else ""
    rate = match_rate(raw_model or model)
    if rate is not None:
        fallback_qty = t or (EST_IMAGE_OUTPUT_TOKENS if key == "seedream" else 0)
        usd = rate_cost_usd(rate, _usage_block(raw_usage), fallback_tokens=fallback_qty)
        if usd:
            cost = usd_to_fen(usd, s)
            return cost, user_charge_fen(cost, s), False
    if t <= 0 and key == "seedream":
        t = int(s.billing_est_seedream_tokens)
    cost, charge = charge_fen_for_tokens(t, key, settings=s)
    return cost, charge, False
```

- [ ] **Step 6: `rate_quotes` — model đắt nhất cho dòng ước tính**

Thêm vào cuối `backend/app/services/billing/rate_quotes.py`:

```python
# billing_key → (chức năng khi domain=kepu, chức năng cho domain khác)
_LINE_FUNCTIONS: dict[str, tuple[str, str]] = {
    "llm_chat": ("kepu.script", "drama.script"),
    "tts": ("kepu.tts", "drama.tts"),
}


def priciest_model(
    function_id: str,
    tokens: int,
    billing_key: str,
    *,
    settings: Any | None = None,
    snapshot: Any | None = None,
) -> str:
    """Model đắt nhất của chức năng cho `tokens` (cùng quy tắc với số đóng băng); không có model → ""."""
    s = settings or get_settings()
    models = function_models(function_id, settings=s, snapshot=snapshot)
    if not models:
        return ""
    return max(models, key=lambda m: _token_price(m, int(tokens), billing_key, s))


def estimated_line_model(
    billing_key: str,
    domain: str | None,
    tokens: int,
    *,
    fallback: str = "",
    settings: Any | None = None,
    snapshot: Any | None = None,
) -> str:
    """Nhãn model cho dòng usage LLM/TTS ước tính: model đắt nhất của chức năng theo domain; key khác → fallback."""
    pair = _LINE_FUNCTIONS.get(billing_key)
    if pair is None:
        return fallback
    function_id = pair[0] if (domain or "") == "kepu" else pair[1]
    return priciest_model(function_id, tokens, billing_key, settings=settings, snapshot=snapshot) or fallback
```

- [ ] **Step 7: `record_line` gắn model của slot cho dòng ước tính**

Trong `backend/app/services/billing/usage.py`:

(a) Thêm import: `from app.services.billing.rate_quotes import estimated_line_model`

(b) Trong nhánh `elif billing_key == "seedream":` thay comment `# TokenFree /responses 常回 0 token；按张价在 charge_fen_for_usage 计算` bằng `# Ảnh không có usage: charge_fen_for_usage tính theo giá/ảnh của provider_rates`.

(c) Ngay **trước** dòng `cost, charge, from_upstream = charge_fen_for_usage(` thêm:

```python
    # Dòng LLM/TTS ước tính còn mang nhãn settings.model_* → đổi sang model đắt nhất của slot (khớp số đã đóng băng)
    label = {"llm_chat": s.model_llm, "tts": s.model_audio}.get(billing_key)
    if estimated and label is not None and (not model or model == label):
        model = estimated_line_model(billing_key, domain, total, fallback=model, settings=s)
```

- [ ] **Step 8: `display.py` và `billing_util.py` bỏ khoá cũ**

Trong `backend/app/services/billing/display.py` thay hằng:

```python
_UPSTREAM_COST_JSON_KEYS = (
    "cost_fen",
    "cost_cents",
)
```

Trong `backend/app/services/drama/billing_util.py` (`record_seedance_video_usage`) xoá hai dòng:

```python
        if "creditsConsumed" in raw and "creditsConsumed" not in merged_usage:
            merged_usage["creditsConsumed"] = raw.get("creditsConsumed")
```

- [ ] **Step 9: Xoá `tokenfree_pricing` và test/fixture TokenFree**

```bash
cd backend
git rm app/services/tokenfree_pricing.py tests/test_tokenfree_pricing.py tests/test_tokenfree_usage.py
```

(`test_tokenfree_usage.py` kiểm quota New API trong `parse_upstream_cost_fen` — đã bỏ; module `tokenfree_usage.py` bị xoá ở Task 7.)

Trong `backend/tests/conftest.py` xoá toàn bộ fixture `skip_tokenfree_pricing_network` (decorator, hàm, `_empty`, `set_cached_rates`).

Run: `cd backend && grep -rn "tokenfree_pricing\|kie_credits_to_cost_fen\|kie_fen_per_credit\|quota_to_cost_fen" app tests`
Expected: chỉ còn `app/services/tokenfree_usage.py` và `app/services/admin/upstream_usage.py` (xoá ở Task 7).

- [ ] **Step 10: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_seedream_billing_usage.py tests/test_billing_rates_chain.py tests/test_record_seedream_image_usage.py tests/test_seedance_billing_usage.py tests/test_billing_display.py tests/test_billing_integration.py tests/test_billing_settlement.py tests/test_adapter_cost_fen.py -v`
Expected: PASS.

- [ ] **Step 11: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 12: Commit**

```bash
git add -A backend/app/services/billing backend/app/services/drama/billing_util.py backend/app/services/tokenfree_pricing.py backend/tests
git commit -m "$(cat <<'EOF'
feat: quyết toán theo provider_rates, bỏ quota New API/yuan/Kie và xoá tokenfree_pricing

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Bỏ đối chiếu dùng lượng upstream; xoá `tokenfree_usage` (không còn đường gửi key tới tokenfree.com)

**Files:**
- Modify: `backend/app/api/admin/dashboard.py` (xoá 2 endpoint `/stats/upstream-usage*`)
- Modify: `backend/app/api/admin/finance.py` (xoá `POST /finance/daily/sync`)
- Rewrite: `backend/app/services/admin/finance.py` (`actual_cost_fen = cost_fen`)
- Modify: `backend/app/schemas.py` (xoá `AdminUpstreamUsage*`; `AdminFinanceDailyOut` bỏ `configured`, `last_sync_at`)
- Delete: `backend/app/services/admin/upstream_usage.py`, `backend/app/services/tokenfree_usage.py`
- Rewrite: `backend/tests/test_admin_finance.py`, `backend/tests/test_admin_upstream_usage.py`
- Test: `backend/tests/test_no_tokenfree_egress.py`

**Interfaces:**
- Produces: `build_finance_daily_list(db, *, days=30) -> {"days", "totals", "series"}`; mỗi dòng `series` giữ khoá `actual_cost_fen` (= `cost_fen`) để UI cũ không vỡ; `_profit_fen(*, charge_fen, cost_fen) -> int`. Bảng `upstream_usage_daily` và model `UpstreamUsageDaily` **giữ nguyên, không đọc**.

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_no_tokenfree_egress.py
"""Bảo vệ an ninh: không module runtime nào còn gọi tokenfree.com (tránh gửi key OpenAI/BytePlus sang bên thứ ba)."""
from __future__ import annotations

from pathlib import Path

# model_settings.py chỉ chứa chuỗi để DỌN cấu hình TokenFree cũ, không gọi mạng
_ALLOWED = {"model_settings.py"}


def test_no_runtime_module_mentions_tokenfree_host():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if "tokenfree.com" in p.read_text(encoding="utf-8").lower() and p.name not in _ALLOWED
    )
    assert offenders == []
```

Thay toàn bộ `backend/tests/test_admin_upstream_usage.py`:

```python
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
```

Thay toàn bộ `backend/tests/test_admin_finance.py`:

```python
"""Tài chính theo ngày: chi phí thật = cost_fen local (provider_rates), lợi nhuận = tiền trừ − chi phí."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin.finance import _profit_fen, build_finance_daily_list
from tests.conftest import make_user
from tests.test_admin_stats import _add_usage, _utc_days_ago


def test_profit_fen_is_charge_minus_cost() -> None:
    assert _profit_fen(charge_fen=200, cost_fen=120) == 80


async def test_finance_daily_list_uses_local_cost(db_session: AsyncSession) -> None:
    """Dữ liệu mới phản ánh vào đúng ngày; actual_cost_fen == cost_fen (so tăng thêm, chịu DB test dùng chung)."""
    user = await make_user(db_session)
    target_day = _utc_days_ago(5)
    key = target_day.date().isoformat()
    before = next(r for r in (await build_finance_daily_list(db_session, days=30))["series"] if r["date"] == key)

    await _add_usage(db_session, user_id=user.id, charge_fen=200, cost_fen=120, total_tokens=5000,
                     created_at=target_day, capability="video", billing_key="seedance2:video0")
    await db_session.commit()

    out = await build_finance_daily_list(db_session, days=30)
    after = next(r for r in out["series"] if r["date"] == key)
    assert after["charge_fen"] - before["charge_fen"] == 200
    assert after["cost_fen"] - before["cost_fen"] == 120
    assert after["actual_cost_fen"] == after["cost_fen"]
    assert after["profit_fen"] == after["charge_fen"] - after["cost_fen"]
    assert set(out) == {"days", "totals", "series"}
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_no_tokenfree_egress.py tests/test_admin_upstream_usage.py tests/test_admin_finance.py -v`
Expected: FAIL — `tokenfree_usage.py` còn chứa `tokenfree.com`; route cũ còn; `_profit_fen()` sai chữ ký.

- [ ] **Step 3: Xoá endpoint dashboard**

Trong `backend/app/api/admin/dashboard.py`: xoá `AdminUpstreamUsageOut`, `AdminUpstreamUsageSyncOut` khỏi import `app.schemas`; xoá dòng `from app.services.admin.upstream_usage import build_upstream_usage_compare, sync_upstream_usage`; xoá toàn bộ hai hàm `admin_upstream_usage` và `admin_upstream_usage_sync` (kèm decorator).

- [ ] **Step 4: Xoá `POST /finance/daily/sync`**

Thay toàn bộ `backend/app/api/admin/finance.py`:

```python
# Admin finance daily ledger API
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models import User
from app.schemas import AdminFinanceDailyOut
from app.services.admin.finance import build_finance_daily_list

router = APIRouter(prefix="/finance", tags=["admin-finance"])


@router.get("/daily", response_model=AdminFinanceDailyOut)
async def admin_finance_daily(
    days: int = Query(30, ge=1, le=90),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminFinanceDailyOut:
    """Tài chính theo ngày: tiền trừ user, chi phí (cost_fen theo provider_rates), token, lợi nhuận."""
    raw = await build_finance_daily_list(db, days=days)
    return AdminFinanceDailyOut(**raw)
```

- [ ] **Step 5: Viết lại `services/admin/finance.py`**

```python
"""Admin: tài chính theo ngày — tiền trừ user vs chi phí local (cost_fen tính theo provider_rates)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent


def _utc_today() -> date:
    """Ngày UTC hiện tại, khớp cửa sổ danh sách tài chính."""
    return datetime.now(UTC).date()


async def _local_usage_daily(db: AsyncSession, *, since: date, until: date) -> dict[str, dict[str, int]]:
    """Gộp usage_events theo ngày: tiền trừ, chi phí, token."""
    day_expr = cast(UsageEvent.created_at, Date)
    rows = (
        await db.execute(
            select(
                day_expr.label("day"),
                func.coalesce(func.sum(UsageEvent.charge_fen), 0).label("charge_fen"),
                func.coalesce(func.sum(UsageEvent.cost_fen), 0).label("cost_fen"),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("tokens"),
            )
            .where(day_expr >= since, day_expr <= until)
            .group_by(day_expr)
            .order_by(day_expr.asc())
        )
    ).all()
    return {
        str(row.day)[:10]: {
            "charge_fen": int(row.charge_fen or 0),
            "cost_fen": int(row.cost_fen or 0),
            "tokens": int(row.tokens or 0),
        }
        for row in rows
    }


def _profit_fen(*, charge_fen: int, cost_fen: int) -> int:
    """Lợi nhuận = tiền trừ user − chi phí."""
    return int(charge_fen - cost_fen)


async def build_finance_daily_list(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Chuỗi N ngày gần nhất + tổng; actual_cost_fen = cost_fen (không còn đối chiếu upstream)."""
    window_days = max(1, min(90, int(days)))
    today = _utc_today()
    start = today - timedelta(days=window_days - 1)
    local_map = await _local_usage_daily(db, since=start, until=today)

    series: list[dict[str, Any]] = []
    totals: dict[str, Any] = {"charge_fen": 0, "cost_fen": 0, "tokens": 0, "actual_cost_fen": 0, "profit_fen": 0}
    cur = start
    while cur <= today:
        key = cur.isoformat()
        hit = local_map.get(key) or {"charge_fen": 0, "cost_fen": 0, "tokens": 0}
        charge_fen, cost_fen, tokens = hit["charge_fen"], hit["cost_fen"], hit["tokens"]
        profit_fen = _profit_fen(charge_fen=charge_fen, cost_fen=cost_fen)
        series.append({
            "date": key,
            "charge_fen": charge_fen,
            "cost_fen": cost_fen,
            "tokens": tokens,
            "actual_cost_fen": cost_fen,
            "profit_fen": profit_fen,
            "profit_pct": round(profit_fen / charge_fen * 100.0, 2) if charge_fen > 0 else None,
        })
        totals["charge_fen"] += charge_fen
        totals["cost_fen"] += cost_fen
        totals["tokens"] += tokens
        totals["actual_cost_fen"] += cost_fen
        totals["profit_fen"] += profit_fen
        cur += timedelta(days=1)
    if totals["charge_fen"] > 0:
        totals["profit_pct"] = round(totals["profit_fen"] / totals["charge_fen"] * 100.0, 2)
    return {"days": window_days, "totals": totals, "series": series}
```

- [ ] **Step 6: Schema**

Trong `backend/app/schemas.py`: xoá ba class `AdminUpstreamUsageDayOut`, `AdminUpstreamUsageOut`, `AdminUpstreamUsageSyncOut`; trong `AdminFinanceDailyOut` xoá hai field `configured: bool = False` và `last_sync_at: str | None = None`.

- [ ] **Step 7: Xoá module**

```bash
cd backend
git rm app/services/admin/upstream_usage.py app/services/tokenfree_usage.py
grep -rn "tokenfree_usage\|sync_upstream_usage\|build_upstream_usage_compare\|AdminUpstreamUsage" app tests
```

Expected: chỉ còn `tests/test_admin_upstream_usage.py` (chuỗi tên module trong test "đã xoá").

- [ ] **Step 8: Chạy test, xác nhận PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_no_tokenfree_egress.py tests/test_admin_upstream_usage.py tests/test_admin_finance.py tests/test_admin_stats.py -v`
Expected: PASS.

- [ ] **Step 9: Chạy toàn bộ suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 10: Commit**

```bash
git add -A backend/app/api/admin/dashboard.py backend/app/api/admin/finance.py backend/app/services/admin backend/app/services/tokenfree_usage.py backend/app/schemas.py backend/tests/test_no_tokenfree_egress.py backend/tests/test_admin_upstream_usage.py backend/tests/test_admin_finance.py
git commit -m "$(cat <<'EOF'
feat: bỏ đối chiếu dùng lượng upstream, xoá tokenfree_usage (không còn gửi key tới tokenfree.com)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Tài liệu billing

**Files:**
- Modify: `docs/BILLING.md`
- Modify: `CLAUDE.md` (dòng stub TokenFree ở mục test; đoạn "计费")
- Modify: `docs/PROVIDERS.md` (dòng `cost_fen` và hai gạch đầu dòng "Plan B")

**Interfaces:** không có mã. Ngôn ngữ tài liệu theo file hiện có (`BILLING.md`, `CLAUDE.md` tiếng Trung giản thể; `PROVIDERS.md` tiếng Việt).

- [ ] **Step 1: `docs/BILLING.md` — mục 原则 và 公式**

Thay 2 dòng đầu mục `## 原则`:

```markdown
- 按 **provider_rates 价目表**（各 provider 官方美元价，管理端可改）计算上游成本；无法拿到 usage 时用保守估价。
- 用户支付价 = 上游成本，**不再加价**。
```

Thay toàn bộ mục `### TokenFree / New API（quota 计费）` (tới hết đoạn "管理端「官方用量对照」…") bằng:

````markdown
### provider_rates（按模型的美元价目）

存于 `app_settings.config_json["provider_rates"]`，首次启动自动写入默认表；管理端「支付与计费」可改（`GET/PUT /api/admin/settings/billing/model-rates`）。每行 `{pattern, unit, usd, usd_out?, note}`，`pattern` 为模型 id 的 glob（不区分大小写），**自上而下第一条匹配生效**（如 `dreamina-seedance-2-0-fast*` 必须在 `dreamina-seedance-2-0*` 之前）。

| unit | 成本（USD） |
|---|---|
| `per_image` | `usage.generated_images`（缺省 1）× usd |
| `per_m_tokens` | `usage.total_tokens / 1e6 × usd` |
| `per_m_output_tokens` | `usage.output_tokens / 1e6 × usd` |
| `per_m_input_output` | `in / 1e6 × usd + out / 1e6 × usd_out`（只有总 token 时按 70/30 拆） |
| `per_m_chars` | `字符数 / 1e6 × usd` |

```
cost_fen = ceil(usd × BILLING_USD_CNY × 100)   # usd > 0 时至少 1 分
charge_fen = cost_fen
```

结算顺序（`pricing.charge_fen_for_usage`）：① usage 已带 `cost_fen`（adapter 按 provider_rates 用真实 usage 算好）→ 直接用；② 按 `raw_usage.model`（上游真实模型）或调用方模型匹配 provider_rates；③ 都不匹配 → 上表「按 token 估价」（`BILLING_*_PER_M`，元/百万 token）。生图不会记 0：按 token 计价的图像模型无 usage 时按 6 240 输出 token 封顶估，未匹配的图像模型按 `BILLING_EST_SEEDREAM_TOKENS`。已**移除** New API quota（500000 = 1 USD）、火山人民币 `cost`、Kie credits 解析。

预扣（`estimates.py` + `rate_quotes.py`）：按任务对应的**功能**（`kepu.image`、`drama.video`、`tools.image`…）取 slot/override 中仍有效的模型，**取其中最贵者**：

- 图片：每张价，**不乘** `BILLING_ESTIMATE_BUFFER`（清晰度不影响 Seedream 按张价）。
- 视频：`ceil(max(秒,2) × 宽 × 高 × 24 / 1024)` token × 每百万价 × 缓冲；480p=864×480、720p=1280×720、1080p=1920×1080；漫剧缺省 720p。
- LLM / TTS：`BILLING_EST_LLM_TOKENS` / `BILLING_EST_TTS_TOKENS` × 模型价 × 缓冲；对应 usage 行（估算）的 `model` 记为同一最贵模型，保证预扣与结算口径一致。

管理端返回 `unpriced_models`：已分配但没有任何价目行匹配的模型（如自定义 `ep-…` 接入点），这些模型会按 token 兜底价结算，请补价目行。
````

- [ ] **Step 2: `docs/BILLING.md` — 环境变量、API、管理端、验收清单、展示货币**

- 环境变量代码块：删除行 `BILLING_KIE_FEN_PER_CREDIT=3.5`。
- API 表：删除 `/api/admin/stats/upstream-usage`、`/api/admin/stats/upstream-usage/sync`、`/api/admin/settings/tokenfree/quota` 三行；把 model-rates 行替换为两行：

```markdown
| GET | `/api/admin/settings/billing/model-rates` | provider_rates 价目表（含默认表、单位、未定价模型、USD→CNY 汇率） |
| PUT | `/api/admin/settings/billing/model-rates` | 整表替换 `{items:[…]}`；校验失败 400（越南语提示） |
| GET | `/api/admin/finance/daily` | 按日扣费 / 成本 / 利润（成本 = 本地 `cost_fen`） |
```

- 管理端列表：第一条改为 `- **设置 → 支付与汇率**：银行转账收款信息、展示货币与汇率；按上游成本 1:1 扣费；可编辑 provider_rates 价目表。`；删除「仪表盘 → TokenFree 官方用量对照」一条。
- 验收清单：第 6 条改为 `6. 管理端修改 provider_rates 后，新任务预扣与结算按新价计算；未定价模型出现在 unpriced_models。`；第 7 条改为 `7. 生图 / 视频结算金额 = provider_rates 按真实 usage 计算（Seedream 按张、Seedance 按 total_tokens、gpt-image 按输出 token）。`
- 展示货币表 `BILLING_USD_CNY` 说明改为 `1 USD 折 CNY（同时用于 provider_rates 美元价折算）`。

- [ ] **Step 3: `CLAUDE.md`**

- Mục 测试: thay câu `conftest 已自动 stub TokenFree 价目网络请求。` bằng `conftest 每个用例自动把 provider_rates 重置为默认表；需要标准路由时用 fixture priced_routing。`
- Mục `### 计费`: thay đoạn `优先取上游真实 quota（New API: 500000 quota = 1 USD，BILLING_USD_CNY），取不到才用本地保守估价；官方价目由 tokenfree_pricing.py 拉取缓存。` bằng `成本按 provider_rates 价目表（app_settings.config_json，管理端可改；services/billing/provider_rates.py）计算：adapter.cost_fen 用真实 usage 算出 cost_fen，否则按模型匹配价目，再不行按 BILLING_*_PER_M token 兜底；预扣按功能 slot 内最贵模型估算（rate_quotes.py）。`

- [ ] **Step 4: `docs/PROVIDERS.md`**

- Dòng `- \`cost_fen(model, raw_usage)\` — ước tính chi phí (Plan B mới có bảng giá thật; hiện trả \`None\`)` → `- \`cost_fen(model, raw_usage)\` — chi phí fen tính từ usage thật theo bảng \`provider_rates\` (\`services/billing/provider_rates.py\`); không usage / model chưa có giá → \`None\``.
- Xoá hai gạch đầu dòng mục "Hạn chế đã biết" bắt đầu bằng `**\`cost_fen()\` của cả hai adapter hiện trả \`None\`**` và `**\`tokenfree_pricing.py\` / \`tokenfree_usage.py\` vẫn còn trong repo có chủ đích**`; thay bằng:

```markdown
- **Model chưa có dòng giá** (vd. endpoint `ep-…` tự đặt) được tính theo giá token dự phòng `BILLING_*_PER_M`
  và hiện trong `unpriced_models` của `GET /api/admin/settings/billing/model-rates` — thêm dòng giá cho chúng.
```

- [ ] **Step 5: Kiểm tra không còn nhắc TokenFree trong tài liệu billing**

Run: `grep -n -i "tokenfree\|quota\|Kie" docs/BILLING.md; grep -n "tokenfree_pricing\|stub TokenFree" CLAUDE.md docs/PROVIDERS.md`
Expected: không dòng nào (trừ câu "已**移除** New API quota…Kie credits 解析" trong BILLING.md — chấp nhận, đó là ghi chú đã bỏ).

- [ ] **Step 6: Chạy toàn bộ suite (không đổi mã, xác nhận vẫn xanh)**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 7: Commit**

```bash
git add docs/BILLING.md CLAUDE.md docs/PROVIDERS.md
git commit -m "$(cat <<'EOF'
docs: billing theo provider_rates, bỏ quota TokenFree và đối chiếu upstream

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Hợp đồng API cho Plan C (admin UI)

Plan C dựng UI theo đúng các hợp đồng dưới đây; mọi số tiền nội bộ là **fen**, hiển thị qua `admin/src/lib/currency.ts` (VND/USD), giá trong bảng `provider_rates` là **USD** thô.

### 1. `GET /api/admin/settings/billing/model-rates` → 200

```json
{
  "items": [
    {"pattern": "dola-seedream-5-0-pro*", "unit": "per_image", "usd": 0.045, "usd_out": null, "note": "BytePlus Seedream 5.0 Pro"},
    {"pattern": "gpt-5.6-sol", "unit": "per_m_input_output", "usd": 4.0, "usd_out": 20.0, "note": "OpenAI GPT-5.6 Sol"}
  ],
  "defaults": [ "…cùng shape với items, luôn là bảng mặc định trong code (nút 'Khôi phục mặc định' = PUT defaults)…" ],
  "units": [
    {"id": "per_image", "label": "USD / ảnh"},
    {"id": "per_m_tokens", "label": "USD / 1 triệu token"},
    {"id": "per_m_output_tokens", "label": "USD / 1 triệu token đầu ra"},
    {"id": "per_m_input_output", "label": "USD / 1 triệu token (vào | ra)"},
    {"id": "per_m_chars", "label": "USD / 1 triệu ký tự"}
  ],
  "unpriced_models": [{"channel_id": "byteplus", "model": "ep-20260923-abc", "capability": "image"}],
  "usd_cny": 7.0,
  "updated_at": "2026-09-23T08:00:00Z"
}
```

- Thứ tự `items` = thứ tự ưu tiên khớp (dòng đầu khớp thắng) → UI phải cho kéo/đổi thứ tự.
- `usd_out` chỉ có nghĩa khi `unit == "per_m_input_output"` (bắt buộc khi đó); các unit khác gửi `null`.
- Xem trước giá theo fen: `ceil(usd × usd_cny × 100)`, rồi đổi sang VND/USD bằng `per_fen` của `GET /api/billing/currency`.

### 2. `PUT /api/admin/settings/billing/model-rates`

- Body: `{"items": [{"pattern": str, "unit": str, "usd": number, "usd_out": number|null, "note": str}]}` — thay **toàn bộ** bảng; `items: []` hợp lệ (mọi model rơi về giá token dự phòng).
- 200 → cùng shape với GET (đã nạp cache).
- 400 → `{"detail": "Dòng 2: đơn vị 'per_second' không hợp lệ; Dòng 5: mẫu 'A*' bị trùng"}` (tối đa 5 lỗi, nối bằng `"; "`, tiếng Việt, đánh số dòng từ 1). Thông điệp có thể có: `Bảng giá tối đa 200 dòng`, `Dòng N: thiếu mẫu tên model`, `Dòng N: mẫu tên model dài quá 128 ký tự`, `Dòng N: mẫu '…' bị trùng`, `Dòng N: đơn vị '…' không hợp lệ`, `Dòng N: giá USD phải là số không âm`, `Dòng N: đơn vị vào/ra cần thêm giá token đầu ra (usd_out)`.
- 422 (pydantic) chỉ khi kiểu JSON sai (vd. `usd: "abc"`).

### 3. Endpoint đã xoá (UI phải bỏ lời gọi)

| Endpoint | Chỗ gọi hiện tại trong `admin/` |
|---|---|
| `GET /api/admin/stats/upstream-usage` | `DashboardPage.tsx` (card đối chiếu) |
| `POST /api/admin/stats/upstream-usage/sync` | `DashboardPage.tsx` |
| `POST /api/admin/finance/daily/sync` | `FinanceListPage.tsx` (nút đồng bộ) |
| `GET /api/admin/settings/tokenfree/quota` | `PaymentSettingsPanel.tsx` (nút số dư TokenFree — đã 404 từ Plan A) |

### 4. `GET /api/admin/finance/daily?days=30` (shape mới)

```json
{
  "days": 30,
  "totals": {"charge_fen": 0, "cost_fen": 0, "tokens": 0, "actual_cost_fen": 0, "profit_fen": 0, "profit_pct": null},
  "series": [{"date": "2026-09-23", "charge_fen": 200, "cost_fen": 120, "tokens": 5000, "actual_cost_fen": 120, "profit_fen": 80, "profit_pct": 40.0}]
}
```

Đã bỏ `configured` và `last_sync_at`; `actual_cost_fen` luôn bằng `cost_fen` (giữ để tương thích, UI nên gộp thành một cột "Chi phí").

### 5. Cấu hình flat không còn tác dụng

`billing_kie_fen_per_credit` (trong `GET/PATCH /api/admin/settings/models`) vẫn còn trong schema nhưng **không còn được đọc** — Plan C bỏ ô nhập ở `PaymentSettingsPanel`; có thể xoá field khỏi `config.py` / `schemas_settings.py` cùng lúc.

---

## Sau Plan B

- **Plan C (admin UI + frontend + docs)**: màn hình 2 cột provider/slot; `PaymentSettingsPanel` sửa bảng `provider_rates` theo hợp đồng trên (thêm/xoá/kéo thứ tự, "Khôi phục mặc định", cảnh báo `unpriced_models`); bỏ card/nút đối chiếu upstream ở `DashboardPage`/`FinanceListPage`; i18n frontend bỏ chữ TokenFree; `docs/releases/`.
