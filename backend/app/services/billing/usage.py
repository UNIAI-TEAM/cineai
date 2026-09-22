# -*- coding: utf-8 -*-
"""用量行写入：唯一写 usage_events 的入口。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UsageEvent
from app.services.billing.context import drain_llm_usage, get_current_task_run_id
from app.services.billing.pricing import billing_key_to_capability, charge_fen_for_usage
from app.services.billing.rate_quotes import estimated_line_model


def _captured_llm_usage(raw: dict | None, settings: Any) -> tuple[str, int, int, dict] | None:
    """Gộp các lần gọi LLM thật đã ghi trong scope → (model chính, prompt, completion, raw có cost_fen); không có → None.

    Mỗi lần gọi tính theo provider_rates của model route thực chạy (có usage thật) hoặc theo ước tính
    mỗi lần gọi `billing_est_llm_tokens` (upstream không trả usage) — một scope trộn hai loại vẫn cộng đủ.
    `llm_calls` đánh dấu dòng này là usage thật gộp (không phải upstream báo thẳng chi phí) để
    `resolve_billing_basis` không nhầm sang "实测(费用)".
    """
    calls = drain_llm_usage()
    if not calls:
        return None
    prompt = sum(c["prompt_tokens"] for c in calls)
    completion = sum(c["completion_tokens"] for c in calls)
    total = sum(c["total_tokens"] for c in calls)
    cost = sum(
        charge_fen_for_usage(
            c["total_tokens"] or settings.billing_est_llm_tokens,
            "llm_chat",
            raw_usage=c,
            settings=settings,
            model=c["model"],
        )[0]
        for c in calls
    )
    model = max(calls, key=lambda c: c["total_tokens"])["model"]
    usage = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total, "cost_fen": cost}
    return model, prompt, completion, {**(raw or {}), "model": model, "llm_calls": len(calls), "usage": usage}


async def record_line(
    db: AsyncSession,
    *,
    user_id: int,
    billing_key: str,
    model: str = "",
    tokens: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated: bool = False,
    raw: dict | None = None,
    project_id: int | None = None,
    drama_project_id: int | None = None,
    shot_id: int | None = None,
    provider: str = "ark",
    task_run_id: int | None = None,
    domain: str | None = None,
) -> UsageEvent:
    s = get_settings()
    tid = task_run_id if task_run_id is not None else get_current_task_run_id()
    # LLM: usage thật do llm_client ghi trong billing_scope thắng số token ước tính
    captured = _captured_llm_usage(raw, s) if billing_key == "llm_chat" and estimated else None
    if captured is not None:
        model, prompt_tokens, completion_tokens, raw = captured
        tokens, estimated = 0, False
    total = int(tokens) or (int(prompt_tokens) + int(completion_tokens))
    if total <= 0:
        if billing_key == "llm_chat":
            total = s.billing_est_llm_tokens
            estimated = True
        elif billing_key == "seedream":
            # Ảnh không có usage: charge_fen_for_usage tính theo giá/ảnh của provider_rates
            estimated = True
        elif billing_key == "tts":
            total = s.billing_est_tts_tokens
            estimated = True
        elif billing_key.startswith("seedance"):
            total = s.billing_est_seedance_tokens_per_sec * 5
            estimated = True
    # Dòng LLM/TTS ước tính còn mang nhãn settings.model_* → đổi sang model đắt nhất của slot (khớp số đã đóng băng)
    label = {"llm_chat": s.model_llm, "tts": s.model_audio}.get(billing_key)
    if estimated and label is not None and (not model or model == label):
        model = estimated_line_model(billing_key, domain, total, fallback=model, settings=s)
    cost, charge, from_upstream = charge_fen_for_usage(
        total, billing_key, raw_usage=raw, settings=s, model=model
    )
    if from_upstream:
        estimated = False
    elif total > 0 and not estimated:
        pass
    elif total > 0 and estimated and raw:
        usage_parsed = raw.get("usage") if isinstance(raw.get("usage"), dict) else raw
        if isinstance(usage_parsed, dict) and int(usage_parsed.get("total_tokens") or 0) > 0:
            estimated = False
    capability = billing_key_to_capability(billing_key)
    ev = UsageEvent(
        user_id=user_id,
        project_id=project_id,
        drama_project_id=drama_project_id,
        task_run_id=tid,
        domain=domain,
        capability=capability,
        shot_id=shot_id,
        provider=provider,
        billing_key=billing_key,
        model=model or "",
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        total_tokens=total,
        cost_fen=cost,
        charge_fen=charge,
        estimated=estimated,
        settled=False,
        raw_usage_json=json.dumps(raw, ensure_ascii=False)[:4000] if raw else None,
    )
    db.add(ev)
    await db.flush()
    return ev


async def record_llm_chat_line(
    db: AsyncSession,
    *,
    user_id: int,
    domain: str,
    drama_project_id: int | None = None,
    project_id: int | None = None,
    tokens: int | None = None,
) -> UsageEvent | None:
    """在 billing_scope 内记录一次 LLM 调用；无 scope 时跳过（由调用方聚合计费）。"""
    if get_current_task_run_id() is None:
        return None
    s = get_settings()
    return await record_line(
        db,
        user_id=user_id,
        billing_key="llm_chat",
        model=s.model_llm,
        tokens=int(tokens or 0),
        estimated=True,
        project_id=project_id,
        drama_project_id=drama_project_id,
        domain=domain,
    )


# 兼容旧调用名
async def record_usage(
    db: AsyncSession,
    *,
    user_id: int,
    project_id: int | None,
    billing_key: str,
    model: str = "",
    tokens: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated: bool = False,
    raw: dict | None = None,
    shot_id: int | None = None,
    provider: str = "ark",
    drama_project_id: int | None = None,
    domain: str | None = None,
    task_run_id: int | None = None,
) -> UsageEvent:
    return await record_line(
        db,
        user_id=user_id,
        billing_key=billing_key,
        model=model,
        tokens=tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated=estimated,
        raw=raw,
        project_id=project_id,
        drama_project_id=drama_project_id,
        shot_id=shot_id,
        provider=provider,
        domain=domain,
        task_run_id=task_run_id,
    )
