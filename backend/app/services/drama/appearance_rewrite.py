"""Người dùng sửa trường ngoại hình → AI viết lại đoạn mô tả đầy đủ (vi/en: tiếng Anh) thay cho bản ghép 8 trường ngắn.

8 trường ngắn ghép thẳng làm mất chi tiết (chất liệu, phối màu, phụ kiện, dáng đứng) nên ảnh ra người chung chung;
AI lấy các trường làm chuẩn và giữ lại chi tiết của mô tả cũ không mâu thuẫn với trường.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.drama.appearance_prompt import (
    APPEARANCE_KEYS,
    appearance_is_empty,
    apply_appearance_to_params,
    normalize_appearance,
)
from app.services.drama.llm import drama_chat_text
from app.services.drama.visual_prompt import normalize_visual_prompt_text

logger = logging.getLogger(__name__)

# Đoạn AI viết ngắn hơn mức này coi như hỏng, quay về bản ghép 8 trường
MIN_REWRITE_LEN = 60

APPEARANCE_REWRITE_SYSTEM = """你是短剧美术造型指导，为 Seedream 生图写角色「视觉形象描述」。
输入包含：角色的外形字段（用户刚修改过，是权威依据）与修改前的完整描述（仅作参考）。

输出要求：
1. 只输出一条简体中文，150–380 字，不要 JSON、不要标题、不要引号、不要「性别：」类字段标签
2. 每个非空字段的内容都必须体现，且以字段为准；字段可能用其他语言书写，照其含义写入
3. 修改前描述中与字段冲突的细节必须删除；不冲突的细节（材质、配色、纹样、配饰、姿态、神态）尽量保留
4. 不得编造与字段矛盾的特征；不写背景、构图、镜头指令，不写剧情与台词
5. 禁止空泛套话（如「五官清晰」「气质出众」）"""

_FIELD_NAMES = {
    "gender": "gender",
    "age": "age",
    "face": "face",
    "hair": "hair",
    "build": "build",
    "outfit": "outfit",
    "signature": "signature details",
    "style_note": "presence",
}


async def rewrite_appearance_description(
    appearance: dict[str, str], lang: str | None, *, name: str, previous: str
) -> str:
    """一次 LLM：按字段（权威）+ 旧描述（参考）写完整外形描述；过短返回 ""（调用方回退字段拼接）。"""
    fields = "\n".join(
        f"- {_FIELD_NAMES[k]}: {appearance[k]}" for k in APPEARANCE_KEYS if (appearance.get(k) or "").strip()
    )
    user = f"角色名：{name or ''}\n外形字段：\n{fields}"
    if (previous or "").strip():
        user += f"\n修改前的描述：\n{previous.strip()}"
    raw = await drama_chat_text(
        APPEARANCE_REWRITE_SYSTEM, user, temperature=0.4, max_tokens=1024, lang=lang, lang_kind="visual"
    )
    text = normalize_visual_prompt_text(raw)
    return text if len(text) >= MIN_REWRITE_LEN else ""


async def recompose_character_params(
    params: dict[str, Any],
    lang: str | None,
    *,
    name: str,
    previous: str,
    run: Callable[[Callable[[], Awaitable[str]]], Awaitable[str]],
) -> dict[str, Any]:
    """Ghép lại prompt nhân vật sau khi sửa trường: chế độ chỉnh tay / không có trường → như apply cũ;
    còn lại nhờ AI viết đoạn đầy đủ qua run (API bọc tính phí). AI lỗi / hết số dư → bản ghép 8 trường."""
    appearance = normalize_appearance(params.get("appearance"))
    if params.get("promptManual") is True or appearance_is_empty(appearance):
        return apply_appearance_to_params(params, lang)

    async def _job() -> str:
        return await rewrite_appearance_description(appearance, lang, name=name, previous=previous)

    try:
        body = await run(_job)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI viết lại mô tả ngoại hình thất bại, dùng bản ghép trường name=%s err=%s", name, exc)
        body = ""
    return apply_appearance_to_params(params, lang, body=body)
