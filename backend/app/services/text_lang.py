"""文本语言小工具：判断是否中日文、按词边界截断（越南语 / 英文不能按字切）。"""

from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def is_cjk_text(text: str) -> bool:
    """文本是否含中日文字（用于区分中文内容与越南语 / 英文内容）。"""
    return bool(_CJK_RE.search(text or ""))


def cut_words(text: str, limit: int, *, ellipsis: bool = True) -> str:
    """按词边界截断到 limit 字符以内，避免把越南语单词切半。

    参数：text 原文；limit 最大长度；ellipsis 截断时是否补「…」
    返回：截断后的文本（未超长则原样返回）
    """
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if len(raw) <= limit:
        return raw
    budget = limit - 1 if ellipsis else limit
    head = raw[:budget]
    if " " in head and not raw[budget : budget + 1].isspace():
        head = head.rsplit(" ", 1)[0]
    head = head.rstrip(" ,.;:!?-–—")
    return f"{head}…" if ellipsis else head
