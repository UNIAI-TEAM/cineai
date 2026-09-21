"""TokenFree 公开 /api/pricing：推荐模型官方价与预估。"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.tokenfree_gateway import TOKENFREE_CONSOLE_URL, tokenfree_site_origin
from app.services.tokenfree_usage import usd_cny_rate

logger = logging.getLogger(__name__)

# New API：model_ratio=1 → $2 / 百万 tokens
NEWAPI_USD_PER_1M_AT_RATIO_1 = 2.0
# 视频价目常见占位倍率，不能当秒价
PLACEHOLDER_MODEL_RATIO = 37.5
_CACHE_TTL_SEC = 3600.0
_FAIL_TTL_SEC = 60.0
TOKENFREE_PRICING_PATH = "/api/pricing"
# LLM 预估按输入/输出拆分
LLM_PROMPT_SHARE = 0.7
# 费率表视频展示用的对照时长
VIDEO_RATE_SAMPLE_SECONDS = 5.0

# 火山 480P 5 秒官价折秒价（TokenFree 视频表不可信时预估用）
VENDOR_VIDEO_YUAN_PER_SEC_480P = {
    "seedance-2-5": 3.36 / 5.0,
    "seedance-2-0": 2.31 / 5.0,
    "seedance-2-0-mini": 2.31 / 5.0,
}
# 相对 480P 的预估倍率（宁多冻、少结算超扣）
VIDEO_RESOLUTION_MULT = {
    "480p": 1.0,
    "720p": 2.0,
    "1080p": 4.0,
}
# Kie sunburst 控制台档（USD / credits）；公开 /api/pricing 往往只有笼统 gpt-image-2-5
KIE_SUNBURST_USD_1K = 0.03
KIE_SUNBURST_USD_2K = 0.05
KIE_SUNBURST_USD_4K = 0.08
KIE_SUNBURST_CREDITS_1K = 6
KIE_SUNBURST_CREDITS_2K = 10
KIE_SUNBURST_CREDITS_4K = 16

# 产品里好用、目录有、方便去 TokenFree 核对的短名单
RECOMMENDED_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": "kimi-k2.6",
        "capability": "text",
        "label": "Kimi K2.6",
        "note": "默认剧本/分镜，中文长上下文",
        "recommended": True,
    },
    {
        "id": "deepseek-v3.2",
        "capability": "text",
        "label": "DeepSeek V3.2",
        "note": "便宜备选，扩写与闲聊",
        "recommended": False,
    },
    {
        "id": "qwen3.5-plus",
        "capability": "text",
        "label": "Qwen 3.5 Plus",
        "note": "便宜中文日常对话",
        "recommended": False,
    },
    {
        "id": "gpt-image-2-5",
        "capability": "image",
        "label": "GPT Image 2.5",
        "note": "TokenFree 实测可通；计费按 Kie 2K 约 $0.05/张。Seedream 会改走此模型",
        "recommended": True,
    },
    {
        "id": "nano-banana-2",
        "capability": "image",
        "label": "Nano Banana 2",
        "note": "极便宜闪图，草稿/批量",
        "recommended": False,
    },
    {
        "id": "seedance-2-5",
        "capability": "video",
        "label": "Seedance 2.5",
        "note": "默认成片，最长约 30 秒",
        "recommended": True,
    },
    {
        "id": "seedance-2-0",
        "capability": "video",
        "label": "Seedance 2.0",
        "note": "标准 2.0，与 Mini 不同价档",
        "recommended": False,
    },
    {
        "id": "seedance-2-0-mini",
        "capability": "video",
        "label": "Seedance 2.0 Mini",
        "note": "更快更便宜的备选",
        "recommended": False,
    },
    {
        "id": "qwen-tts-2025-05-22",
        "capability": "audio",
        "label": "Qwen TTS",
        "note": "默认配音逻辑名；Ali /audio/speech 未实现，实际走 qwen3-omni-flash 流式 chat",
        "recommended": True,
    },
    {
        "id": "gemini-3.1-flash-tts",
        "capability": "audio",
        "label": "Gemini 3.1 Flash TTS",
        "note": "TokenFree 目录备选配音",
        "recommended": True,
    },
    {
        "id": "elevenlabs-tts",
        "capability": "audio",
        "label": "ElevenLabs TTS",
        "note": "TokenFree 目录备选配音",
        "recommended": False,
    },
)

_cache: dict[str, "OfficialRate"] | None = None
_cache_at: float = 0.0
_cache_failed: bool = False


@dataclass(frozen=True)
class OfficialRate:
    """一条 TokenFree 官方价。"""

    model: str
    billing: str
    usd_per_call: float
    cny_per_call: float
    cny_in_per_1m: float
    cny_out_per_1m: float
    model_ratio: float
    placeholder: bool
    tags: str


def tokenfree_pricing_url() -> str:
    """公开价目接口，无需 Key。"""
    return f"{tokenfree_site_origin()}{TOKENFREE_PRICING_PATH}"


def cached_rates() -> dict[str, OfficialRate]:
    """内存缓存；未拉过返回空。"""
    return dict(_cache or {})


def set_cached_rates(rates: dict[str, OfficialRate] | None) -> None:
    """写入缓存；None 表示测试清空，空 dict 表示负缓存。"""
    global _cache, _cache_at, _cache_failed
    if rates is None:
        _cache = None
        _cache_at = 0.0
        _cache_failed = False
        return
    _cache = dict(rates)
    _cache_at = time.monotonic()
    _cache_failed = False


def _mark_fetch_failed() -> None:
    """拉取失败：保留旧表，刷新时间戳，避免预扣每次打外网。"""
    global _cache, _cache_at, _cache_failed
    if _cache is None:
        _cache = {}
    _cache_at = time.monotonic()
    _cache_failed = True


def parse_pricing_item(item: dict[str, Any], *, usd_cny: float) -> OfficialRate | None:
    """把 /api/pricing 一行折成人民币。"""
    name = str(item.get("model_name") or "").strip()
    if not name:
        return None
    try:
        qt = int(item.get("quota_type") or 0)
        mr = float(item.get("model_ratio") or 0)
        cr = float(item.get("completion_ratio") or 0)
        mp = float(item.get("model_price") or 0)
        rate = max(0.01, float(usd_cny))
    except (TypeError, ValueError):
        return None
    if qt == 1:
        return OfficialRate(
            model=name,
            billing="per_call",
            usd_per_call=mp,
            cny_per_call=round(mp * rate, 4),
            cny_in_per_1m=0.0,
            cny_out_per_1m=0.0,
            model_ratio=0.0,
            placeholder=False,
            tags=str(item.get("tags") or ""),
        )
    return OfficialRate(
        model=name,
        billing="token",
        usd_per_call=0.0,
        cny_per_call=0.0,
        cny_in_per_1m=round(mr * NEWAPI_USD_PER_1M_AT_RATIO_1 * rate, 4),
        cny_out_per_1m=round(mr * cr * NEWAPI_USD_PER_1M_AT_RATIO_1 * rate, 4),
        model_ratio=mr,
        placeholder=abs(mr - PLACEHOLDER_MODEL_RATIO) < 0.01,
        tags=str(item.get("tags") or ""),
    )


def parse_pricing_payload(payload: dict[str, Any], settings: Settings | None = None) -> dict[str, OfficialRate]:
    """解析 TokenFree 价目 JSON。"""
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    rate = usd_cny_rate(settings)
    out: dict[str, OfficialRate] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        parsed = parse_pricing_item(raw, usd_cny=rate)
        if parsed:
            out[parsed.model] = parsed
    return out


def lookup_rate(model: str, rates: dict[str, OfficialRate] | None = None) -> OfficialRate | None:
    """按模型 id 精确或忽略大小写查找。"""
    mid = (model or "").strip()
    table = rates if rates is not None else cached_rates()
    if not mid or not table:
        return None
    hit = table.get(mid)
    if hit:
        return hit
    key = mid.lower()
    for name, row in table.items():
        if name.lower() == key:
            return row
    return None


def video_catalog_id(model: str) -> str:
    """计费预估用：已知别名映射，未知 Seedance 回退 2.5。"""
    mapped = canonicalize_channel_model_id(model)
    if _is_canonical_seedance(mapped):
        return mapped
    return "seedance-2-5"


def _is_canonical_seedance(model: str) -> bool:
    """是否为 TokenFree 目录里的三档 Seedance id。"""
    return model in {"seedance-2-5", "seedance-2-0", "seedance-2-0-mini"}


def canonicalize_channel_model_id(model: str) -> str:
    """已知 Seedance 别名收到 TokenFree 目录 id；对不上则原样返回。"""
    mid = (model or "").strip()
    if "seedance" not in mid.lower():
        return mid
    low = mid.lower()
    if "mini" in low:
        return "seedance-2-0-mini"
    if any(token in low for token in ("2-5", "2.5", "260628")):
        return "seedance-2-5"
    if any(token in low for token in ("2-0", "2.0", "260128")):
        return "seedance-2-0"
    compact = low.replace("_", "-")
    if compact in {"seedance-2", "seedance2"} or compact.endswith("seedance-2"):
        return "seedance-2-0"
    return mid


def canonicalize_channel_models(models: list[str] | None) -> list[str]:
    """合并 Seedance 2.0 三档别名，保持原顺序。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in models or []:
        mid = canonicalize_channel_model_id(raw)
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


def _markup_charge(cost_fen: int, settings: Settings) -> int:
    """用户预扣金额 = 官方成本，不再乘倍率。"""
    from app.services.billing.pricing import user_charge_fen

    return user_charge_fen(cost_fen, settings)


def _kie_sunburst_tier(size: str | None = "") -> str:
    """Kie sunburst 清晰度档：1k / 2k / 4k。"""
    raw = (size or "").strip().upper().replace(" ", "")
    if raw.startswith("1K"):
        return "1k"
    if raw.startswith("3K") or raw.startswith("4K"):
        return "4k"
    if raw.startswith("2K"):
        return "2k"
    for sep in ("X", "×"):
        if sep not in raw:
            continue
        left, right = raw.split(sep, 1)
        if left.isdigit() and right.isdigit():
            pixels = int(left) * int(right)
            if pixels <= 1_200_000:
                return "1k"
            if pixels >= 8_000_000:
                return "4k"
            return "2k"
        break
    return "2k"


def kie_sunburst_usd_for_size(size: str | None = "") -> float:
    """Kie sunburst 按清晰度：1K $0.03 / 2K $0.05 / 3K·4K $0.08。"""
    return {
        "1k": KIE_SUNBURST_USD_1K,
        "2k": KIE_SUNBURST_USD_2K,
        "4k": KIE_SUNBURST_USD_4K,
    }[_kie_sunburst_tier(size)]


def kie_sunburst_credits_for_size(size: str | None = "") -> int:
    """Kie sunburst 积分：1K 6 / 2K 10 / 4K 16。"""
    return {
        "1k": KIE_SUNBURST_CREDITS_1K,
        "2k": KIE_SUNBURST_CREDITS_2K,
        "4k": KIE_SUNBURST_CREDITS_4K,
    }[_kie_sunburst_tier(size)]


def resolve_billing_image_size(settings: Settings, *, model: str = "", size: str = "") -> str:
    """计费用清晰度：与 ark 生成侧一致，Pro / sunburst 把 3K·4K 钳到 2K。"""
    from app.services.drama.seedream_options import is_seedream_pro_model
    from app.services.tokenfree_image import tokenfree_working_image_model

    raw = (size or "").strip() or str(getattr(settings, "ark_image_size", "") or "2K")
    upstream = (model or getattr(settings, "model_image", "") or "").strip()
    working = tokenfree_working_image_model(upstream)
    if (
        is_seedream_pro_model(upstream)
        or "sunburst" in working.lower()
        or "gpt-image" in working.lower()
    ):
        if raw.strip().upper() in {"3K", "4K"}:
            return "2K"
    return raw


def charge_fen_official_image(settings: Settings, *, model: str = "", size: str = "") -> int:
    """生图预估：sunburst / Seedream / gpt-image 按 Kie 积分档；其它按张走价目。"""
    from app.services.billing.pricing import kie_credits_to_cost_fen
    from app.services.tokenfree_image import is_seedream_family, tokenfree_working_image_model

    raw_model = model or getattr(settings, "model_image", "") or ""
    mid = tokenfree_working_image_model(raw_model)
    rate = lookup_rate(mid)
    use_kie_table = (
        "sunburst" in mid.lower()
        or is_seedream_family(raw_model)
        or "gpt-image" in mid.lower()
    )
    if use_kie_table:
        credits = kie_sunburst_credits_for_size(size or getattr(settings, "ark_image_size", "") or "2K")
        fen = kie_credits_to_cost_fen(credits, settings) or 1
        return _markup_charge(fen, settings)
    if rate and rate.billing == "per_call" and rate.cny_per_call > 0:
        return _markup_charge(max(1, int(math.ceil(rate.cny_per_call * 100))), settings)
    credits = kie_sunburst_credits_for_size("2K")
    fen = kie_credits_to_cost_fen(credits, settings) or 1
    return _markup_charge(fen, settings)


def charge_fen_official_llm(tokens: int, settings: Settings, *, model: str = "") -> int:
    """LLM 预估：官方 in/out，按 70% 输入 / 30% 输出拆。"""
    from app.services.billing.pricing import charge_fen_for_tokens

    t = max(0, int(tokens))
    mid = (model or getattr(settings, "model_llm", "") or "kimi-k2.6").strip()
    rate = lookup_rate(mid)
    if t and rate and rate.billing == "token" and (rate.cny_in_per_1m or rate.cny_out_per_1m):
        prompt = int(t * LLM_PROMPT_SHARE)
        completion = t - prompt
        yuan = prompt / 1_000_000 * rate.cny_in_per_1m + completion / 1_000_000 * rate.cny_out_per_1m
        return _markup_charge(max(1, int(math.ceil(yuan * 100))), settings)
    _, charge = charge_fen_for_tokens(t, "llm_chat", settings=settings)
    return charge


def normalize_video_resolution(resolution: str | None, settings: Settings | None = None) -> str:
    """预估用清晰度：只认 480p/720p/1080p。"""
    raw = (resolution or "").strip().lower()
    if raw in VIDEO_RESOLUTION_MULT:
        return raw
    fallback = str(getattr(settings or get_settings(), "ark_video_resolution", "") or "480p").strip().lower()
    return fallback if fallback in VIDEO_RESOLUTION_MULT else "480p"


def charge_fen_official_video(
    seconds: float,
    settings: Settings,
    *,
    model: str = "",
    resolution: str = "",
) -> int:
    """视频预估：火山 480P 秒价 × 清晰度倍率，不用 TokenFree 占位 37.5。"""
    from app.services.billing.pricing import charge_fen_for_tokens

    secs = max(float(seconds or 0), 2.0)
    mid = video_catalog_id(model or getattr(settings, "model_video", "") or "seedance-2-5")
    vendor = VENDOR_VIDEO_YUAN_PER_SEC_480P.get(mid)
    mult = VIDEO_RESOLUTION_MULT[normalize_video_resolution(resolution, settings)]
    if vendor:
        return _markup_charge(max(1, int(math.ceil(secs * vendor * mult * 100))), settings)
    tok = int(secs * settings.billing_est_seedance_tokens_per_sec * mult)
    _, charge = charge_fen_for_tokens(tok, "seedance2:video0", settings=settings)
    return charge


def build_official_rate_rows(
    rates: dict[str, OfficialRate],
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """管理端推荐模型费率表（含用户价）。"""
    # 局部导入：billing 包的 estimates 依赖本模块，顶层导入会形成循环
    from app.services.billing.money import format_money

    s = settings or get_settings()
    usd_cny = usd_cny_rate(s)
    items: list[dict[str, Any]] = []
    for spec in RECOMMENDED_MODELS:
        rate = lookup_rate(str(spec["id"]), rates)
        official_yuan = 0.0
        basis = "missing"
        rate_label = "TokenFree 价目未收录，请到控制台核对"
        if spec["capability"] == "video":
            vendor = VENDOR_VIDEO_YUAN_PER_SEC_480P.get(str(spec["id"]))
            if vendor:
                official_yuan = round(vendor * VIDEO_RATE_SAMPLE_SECONDS, 4)
                basis = "vendor_sec"
                listed = ""
                if rate and rate.placeholder:
                    listed = f"；TokenFree 表 model_ratio={rate.model_ratio} 疑似占位"
                rate_label = (
                    f"预估按火山 480P 约 {vendor:.3f} 元/秒"
                    f"（{VIDEO_RATE_SAMPLE_SECONDS:g}秒 {format_money(int(round(official_yuan * 100)))}；720P×2 / 1080P×4）{listed}"
                )
        elif spec["capability"] == "image" and (
            "sunburst" in str(spec["id"]).lower() or "gpt-image-2-5" in str(spec["id"]).lower()
        ):
            from app.services.billing.pricing import kie_fen_per_credit

            credits = kie_sunburst_credits_for_size("2K")
            fen = max(1, int(round(credits * kie_fen_per_credit(s))))
            official_yuan = round(fen / 100.0, 4)
            basis = "kie_sunburst"
            rate_label = (
                f"Kie sunburst 2K {credits} 积分 ≈ {format_money(fen)}"
                f"（1K {KIE_SUNBURST_CREDITS_1K} / 4K {KIE_SUNBURST_CREDITS_4K} 积分）"
            )
        elif rate and rate.billing == "per_call":
            official_yuan = rate.cny_per_call
            basis = "per_call"
            rate_label = f"TokenFree ${rate.usd_per_call:.4f}/次 ≈ {format_money(int(round(official_yuan * 100)))}"
        elif rate and rate.billing == "token":
            official_yuan = rate.cny_out_per_1m
            basis = "token"
            rate_label = (
                f"TokenFree 输入 {format_money(int(round(rate.cny_in_per_1m * 100)))} / "
                f"输出 {format_money(int(round(rate.cny_out_per_1m * 100)))} 每百万"
            )
        items.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "provider": "tokenfree",
                "capability": spec["capability"],
                "recommended": bool(spec["recommended"]),
                "note": spec["note"],
                "basis": basis,
                "rate_label": rate_label,
                "official_cost_yuan": official_yuan,
                "user_charge_yuan": official_yuan,
                "placeholder": bool(rate.placeholder) if rate else False,
                "markup": 1.0,
                "usd_cny": usd_cny,
                "verify_url": TOKENFREE_CONSOLE_URL,
            }
        )
    return items


async def fetch_tokenfree_pricing() -> dict[str, Any]:
    """GET TokenFree 公开价目，无需 API Key。"""
    url = tokenfree_pricing_url()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"TokenFree pricing 网络失败: {exc}") from exc
    if resp.status_code >= 400:
        raise RuntimeError(f"TokenFree pricing HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError("TokenFree 价目返回非 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TokenFree 价目格式异常")
    return payload


async def ensure_official_rates(settings: Settings | None = None) -> dict[str, OfficialRate]:
    """有缓存且未过期则复用；失败写短 TTL，预扣不因外网挂掉。"""
    ttl = _FAIL_TTL_SEC if _cache_failed else _CACHE_TTL_SEC
    if _cache is not None and _cache_at and (time.monotonic() - _cache_at) < ttl:
        return _cache
    try:
        payload = await fetch_tokenfree_pricing()
        parsed = parse_pricing_payload(payload, settings)
        if parsed:
            set_cached_rates(parsed)
            return parsed
        _mark_fetch_failed()
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.info("tokenfree pricing skipped: %s", exc)
        _mark_fetch_failed()
    return cached_rates()


async def billing_official_rate_rows(settings: Settings | None = None) -> list[dict[str, Any]]:
    """拉取（或复用）官方价后生成推荐模型费率表。"""
    s = settings or get_settings()
    rates = await ensure_official_rates(s)
    return build_official_rate_rows(rates, s)
