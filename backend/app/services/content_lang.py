"""AI 生成内容的输出语言（zh / en / vi）。

系统提示词保持中文（保证提示质量），但面向用户的产出（剧名、摘要、台词、旁白、人物描述等）
按用户界面语言输出。来源优先级：
- 请求：前端每个请求带 `X-UI-Locale`，其次 `Accept-Language`，默认越南语；
- 漫剧项目：创建时写入 `DramaProject.params["content_lang"]`，后台任务只读项目，不依赖请求；
  老项目没有该字段时按已有内容推断（见 `project_content_lang`）。

生图 / 生视频提示词：lang=zh 保持中文；vi / en 用英文写画面描述（Seedream / Seedance 对英文理解更好），
台词、字幕、旁白按内容语言。
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.services.text_lang import is_cjk_text

ContentLang = Literal["zh", "en", "vi"]

DEFAULT_LANG: ContentLang = "vi"
UI_LOCALE_HEADER = "X-UI-Locale"

# 越南语特有的带调/变音字母（不含与英文共用的基本拉丁字母）
_VI_CHARS_RE = re.compile(
    r"[ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ]",
    re.IGNORECASE,
)


def normalize_lang(value: Any) -> ContentLang | None:
    """把 'vi-VN' / 'en_US' / 'zh-CN' 等归一为 zh|en|vi；无法识别返回 None。"""
    if not isinstance(value, str):
        return None
    head = value.strip().lower().replace("_", "-").split("-", 1)[0]
    if head in ("zh", "en", "vi"):
        return head  # type: ignore[return-value]
    return None


def _from_accept_language(header: str | None) -> ContentLang | None:
    """按 Accept-Language 顺序取第一个可识别的语言（忽略 q 权重排序，浏览器已按偏好排列）。"""
    for part in (header or "").split(","):
        lang = normalize_lang(part.split(";", 1)[0])
        if lang:
            return lang
    return None


def request_lang(request: Any) -> ContentLang:
    """从请求头推断输出语言：X-UI-Locale → Accept-Language → 默认 vi。

    参数：request 为 FastAPI/Starlette Request（None 时返回默认）
    """
    headers = getattr(request, "headers", None)
    if headers is None:
        return DEFAULT_LANG
    return (
        normalize_lang(headers.get(UI_LOCALE_HEADER))
        or _from_accept_language(headers.get("accept-language"))
        or DEFAULT_LANG
    )


def guess_text_lang(text: str | None) -> ContentLang | None:
    """按文本内容猜语言：含中日文字 → zh；含越南语字母 → vi；有拉丁字母 → en；空 → None。"""
    raw = (text or "").strip()
    if not raw:
        return None
    if is_cjk_text(raw):
        return "zh"
    if _VI_CHARS_RE.search(raw):
        return "vi"
    if re.search(r"[A-Za-z]", raw):
        return "en"
    return None


def _project_sample_text(project: Any) -> str:
    """取项目里可用于判断语言的文本：剧本原始创意 / 摘要 / 项目标题。"""
    parts: list[str] = []
    script = getattr(project, "__dict__", {}).get("script") if project is not None else None
    if script is not None:
        parts.append(str(getattr(script, "source", "") or ""))
        summary = getattr(script, "summary", None)
        if isinstance(summary, dict):
            for key in ("synopsis", "seriesTitle", "logline"):
                val = summary.get(key)
                if isinstance(val, str):
                    parts.append(val)
    title = getattr(project, "title", None)
    # 默认占位名（中文）不参与判断
    if isinstance(title, str) and title not in ("未命名漫剧", "自由画布项目", "未命名"):
        parts.append(title)
    return "\n".join(p for p in parts if p.strip())


def project_content_lang(project: Any, request: Any = None) -> ContentLang:
    """漫剧项目的内容语言：params.content_lang → 按已有内容推断 → 请求语言 / 默认 vi。

    注意：只读取已加载的 script 关系（避免异步 session 下触发懒加载）。
    """
    params = getattr(project, "params", None)
    if isinstance(params, dict):
        lang = normalize_lang(params.get("content_lang"))
        if lang:
            return lang
    guessed = guess_text_lang(_project_sample_text(project)) if project is not None else None
    if guessed:
        return guessed
    return request_lang(request) if request is not None else DEFAULT_LANG


def lang_display_name(lang: ContentLang | str | None) -> str:
    """语言的中文名（用于拼进中文提示词）。"""
    return {"zh": "简体中文", "en": "英语（English）", "vi": "越南语（Tiếng Việt）"}.get(
        normalize_lang(lang) or DEFAULT_LANG, "越南语（Tiếng Việt）"
    )


def output_language_directive(lang: ContentLang | str | None) -> str:
    """插入系统/用户提示词的输出语言指令（中文书写）；zh 返回沿用旧规则的简体中文指令。"""
    code = normalize_lang(lang) or DEFAULT_LANG
    if code == "zh":
        return "【输出语言】所有面向观众/用户的文本使用简体中文。"
    name = lang_display_name(code)
    return (
        f"【输出语言】所有面向观众/用户的文本（标题、摘要、剧情、台词、旁白、字幕、角色名与人物描述、"
        f"场景名、道具名等）必须使用{name}书写，不要输出中文；"
        "JSON key 与结构标签保持原样；协议标记（如【字幕：…】、空镜：、推镜：、@duration 等）"
        "保持原样不翻译，只翻译标记内/后面的内容。"
    )


def visual_prompt_directive(lang: ContentLang | str | None) -> str:
    """生图 / 生视频画面提示词的语言指令：zh 用简体中文，vi/en 用英文（台词/字幕仍按内容语言）。"""
    code = normalize_lang(lang) or DEFAULT_LANG
    if code == "zh":
        return "【提示词语言】画面描述使用简体中文。"
    name = lang_display_name(code)
    return (
        "【提示词语言】画面描述（人物外观、场景、构图、光影、镜头运动等）用英文（English）书写，"
        f"便于图像/视频模型理解；其中的台词、旁白、字幕文字使用{name}，不要输出中文。"
    )


def is_zh(lang: ContentLang | str | None) -> bool:
    """是否中文内容。"""
    return normalize_lang(lang) == "zh"


# 中文字数 → 越南语 / 英文词数的近似换算（1 个汉字 ≈ 0.7 个词）
_WORDS_PER_HANZI = 0.7
# 生图提示词更紧凑（下游按字符截断，如 visual_prompt 的 680 字符上限）
_VISUAL_WORDS_PER_HANZI = 0.3
# 「90–200 字」「4-12 个汉字」「约 550 汉字」；排除 字段/字幕/字号/字体/字符/字母
_HANZI_RANGE_RE = re.compile(
    r"(\d+)\s*([-–—~～至到])\s*(\d+)\s*(?:个)?(?:汉字|字(?![段幕号体符母]))"
)
_HANZI_SINGLE_RE = re.compile(r"(\d+)\s*(?:个)?(?:汉字|字(?![段幕号体符母]))")


def _scale_count(raw: str, factor: float = _WORDS_PER_HANZI) -> str:
    """把汉字数换算为词数（≥30 取整到 10）。"""
    val = int(raw) * factor
    if val >= 30:
        return str(int(round(val / 10.0)) * 10)
    return str(max(1, int(round(val))))


def localize_length_units(
    text: str, lang: ContentLang | str | None, *, factor: float = _WORDS_PER_HANZI
) -> str:
    """vi / en 时把提示词里的「N–M 个汉字 / N 字」换算成「个词（word）」；zh 原样返回。"""
    if is_zh(lang) or not text:
        return text
    out = _HANZI_RANGE_RE.sub(
        lambda m: (
            f"{_scale_count(m.group(1), factor)}{m.group(2)}"
            f"{_scale_count(m.group(3), factor)} 个词（word）"
        ),
        text,
    )
    return _HANZI_SINGLE_RE.sub(lambda m: f"{_scale_count(m.group(1), factor)} 个词（word）", out)


# 旧提示词里强制中文的说法
# 只替换「用简体中文」「中文画面描述 / 叙述」等输出约束，不动「保持中文原样」之类的结构说明
_FORCE_ZH_RE = re.compile(
    r"(?:语言)?(?:统一)?(?:使用|用)?简体中文|中文(?=画面描述|叙述|描述|台词|旁白|首帧提示词|提示词)"
)


def localize_system_prompt(
    system: str,
    lang: ContentLang | str | None,
    *,
    kind: Literal["text", "visual"] = "text",
) -> str:
    """按内容语言改写中文系统提示词：去掉「使用简体中文」约束、换算字数，并追加输出语言指令。

    参数：kind=text 面向观众的文字（剧本/摘要/台词）；kind=visual 生图/生视频画面提示词（vi/en 用英文）
    返回：lang=zh（或 None 以外无法识别时按默认 vi 处理）时 zh 原样返回
    """
    if lang is None or is_zh(lang):
        return system
    code = normalize_lang(lang) or DEFAULT_LANG
    if kind == "visual":
        target = "英文（English）"
        directive = visual_prompt_directive(code)
    else:
        target = lang_display_name(code)
        directive = output_language_directive(code)

    def _swap(m: re.Match[str]) -> str:
        word = m.group(0)
        if word.startswith("语言"):
            return f"语言使用{target}"
        if "使用" in word or word.startswith("用"):
            return f"使用{target}" if "使用" in word else f"用{target}"
        return target

    body = _FORCE_ZH_RE.sub(_swap, system or "")
    factor = _VISUAL_WORDS_PER_HANZI if kind == "visual" else _WORDS_PER_HANZI
    body = localize_length_units(body, code, factor=factor)
    return f"{body.rstrip()}\n\n{directive}"


def kepu_content_lang(source_text: str | None, stored: str | None = None) -> ContentLang:
    """科普短视频的内容语言：文本含中文 → zh；含越南语字母 → vi；否则用项目记录的界面语言，再退到按文本猜。

    说明：短主题 / 专有名词（如「iPhone 15」）无法判断语言，此时跟随用户界面语言而不是默认中文。
    """
    guessed = guess_text_lang(source_text)
    if guessed in ("zh", "vi"):
        return guessed  # type: ignore[return-value]
    return normalize_lang(stored) or guessed or DEFAULT_LANG
