"""漫剧默认名称（集名 / 资产名 / 画布节点名）按项目内容语言生成。

- zh（含老项目、未传语言）：沿用中文默认名「第 N 集」「未命名资产」等，前端 displayEpisodeName /
  displayDramaAssetName 负责老数据的界面翻译；
- vi / en：直接落库「Tập N」「Episode N」等，与前端文案一致。

判断「占位集名」时三种语言都要认，避免大纲 / 合并逻辑把越南语、英文占位名当成真实集名。
"""

from __future__ import annotations

import re

from app.services.content_lang import normalize_lang

# 占位集名：第 N 集 / 第N集 / Tập N / Episode N（大小写不敏感）
_DEFAULT_EPISODE_TITLE_RE = re.compile(
    r"^\s*(?:第\s*(\d+)\s*集|tập\s+(\d+)|episode\s+(\d+))\s*$", re.IGNORECASE
)


def default_episode_title(number: int | str | None, lang: str | None = None, *, compact: bool = False) -> str:
    """默认集名。lang 为空或 zh 时返回中文（compact=True 为「第N集」，否则「第 N 集」）。"""
    code = normalize_lang(lang)
    if code == "vi":
        return f"Tập {number}"
    if code == "en":
        return f"Episode {number}"
    return f"第{number}集" if compact else f"第 {number} 集"


def is_default_episode_title(title: str | None, number: int | str | None = None) -> bool:
    """是否为占位集名（任一语言）；传 number 时还要求集号一致。"""
    m = _DEFAULT_EPISODE_TITLE_RE.match(str(title or ""))
    if not m:
        return False
    if number is None:
        return True
    found = next(g for g in m.groups() if g)
    try:
        return int(found) == int(number)
    except (TypeError, ValueError):
        return False


def default_asset_name(lang: str | None = None) -> str:
    """未命名资产的默认名。"""
    return {"vi": "Chưa đặt tên", "en": "Untitled"}.get(normalize_lang(lang) or "", "未命名资产")


def default_voice_name(lang: str | None = None) -> str:
    """未命名音色的默认名。"""
    return {"vi": "Giọng chưa đặt tên", "en": "Untitled voice"}.get(normalize_lang(lang) or "", "未命名音色")


def default_canvas_node_name(node_id: str, lang: str | None = None) -> str:
    """画布节点在资产表里的默认名。"""
    code = normalize_lang(lang)
    if code == "vi":
        return f"Nút {node_id}"
    if code == "en":
        return f"Node {node_id}"
    return f"节点 {node_id}"
