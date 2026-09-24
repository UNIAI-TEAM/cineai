"""AI tách mô tả ngoại hình cũ (visualPrompt / visualImage) của nhân vật thành 8 trường appearance."""

from __future__ import annotations

import json
import logging

from app.errors import AppError
from app.models_drama import DramaAsset
from app.services.content_lang import is_zh
from app.services.drama.appearance_prompt import APPEARANCE_KEYS, appearance_is_empty, normalize_appearance
from app.services.drama.llm import drama_chat_json

logger = logging.getLogger(__name__)

APPEARANCE_EXTRACT_SYSTEM = """你是影视定妆设计师。把给定的角色外形描述拆成 8 个短字段，输出严格 JSON 对象（不要 markdown）：
{"gender": string, "age": string, "face": string, "hair": string, "build": string, "outfit": string, "signature": string, "style_note": string}
要求：
1. 只根据描述拆分，不要编造描述里没有的信息；描述未提及的字段给空字符串
2. 每个字段 ≤ 30 字，具体、可拍摄
3. gender 性别；age 年龄感；face 脸型五官；hair 发型发色；build 体型身高；outfit 服饰材质与配色；signature 标志性道具或细节；style_note 气质神态"""


def _source_text(asset: DramaAsset) -> str:
    """待拆分的外形描述：优先 visualPrompt，其次 visualImage。"""
    params = asset.params if isinstance(asset.params, dict) else {}
    for key in ("visualPrompt", "visualImage"):
        text = str(params.get(key) or "").strip()
        if text:
            return text
    return ""


async def extract_appearance_fields(
    asset: DramaAsset, lang: str, source_text: str | None = None
) -> dict[str, str]:
    """一次 LLM 调用把外形描述拆成 8 字段；source_text 优先（前端未保存的描述），否则用已保存描述；
    无描述或结果全空 → AppError(drama.appearance_extract_failed)。"""
    source = (source_text or "").strip() or _source_text(asset)
    if not source:
        raise AppError("drama.appearance_extract_failed")
    system = APPEARANCE_EXTRACT_SYSTEM
    if not is_zh(lang):
        system += "\n4. 各字段值用英文（English）书写"
    user = f"角色名：{asset.name or ''}\n外形描述：\n{source}"
    try:
        data = await drama_chat_json(system, user, temperature=0.2, max_tokens=1024, lang=lang)
    except (RuntimeError, json.JSONDecodeError) as exc:
        logger.warning("外形字段拆分 LLM 失败 asset_id=%s err=%s", asset.id, exc)
        raise AppError("drama.appearance_extract_failed") from exc
    appearance = normalize_appearance(data)
    if appearance_is_empty(appearance):
        raise AppError("drama.appearance_extract_failed")
    return {k: appearance[k] for k in APPEARANCE_KEYS}
