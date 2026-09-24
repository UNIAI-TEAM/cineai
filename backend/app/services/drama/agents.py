"""Drama script agents: summary + episode outline + episode scripts."""

from __future__ import annotations

from typing import Any

from app.errors import AppError
from app.services.content_lang import is_zh, lang_display_name, localize_length_units
from app.services.drama.episode_target import EPISODE_TARGET_AUTO, episode_content_length, format_target_label_zh
from app.services.drama.llm import drama_chat_json
from app.services.drama.naming import default_episode_title, is_default_episode_title
from app.services.drama.script_summary_prompt import (
    SCRIPT_SUMMARY_SYSTEM_PROMPT,
    build_script_summary_user_message,
)

# 正文过短阈值（汉字量近似用去空白后长度）
MIN_EPISODE_CONTENT_CHARS = 450
# 单集目标篇幅随项目目标时长变化，见 episode_target.episode_content_length
# 手动加集标记；自动流水线不会填这些空集
MANUAL_EPISODE_ORIGIN = "manual"
# 与创建项目上限对齐
MAX_DRAMA_EPISODES = 120

# 与 manju episodeScript 对齐：先规划全集集名
EPISODE_OUTLINE_SYSTEM = """你是专业的短剧/网剧编剧策划，负责根据原始创意与剧本摘要，规划全部分集的「集数 + 集名」大纲。

输出要求：
1. 必须严格按照用户给定的总集数生成，episodes 数组长度必须与总集数完全一致
2. episodeNumber 从 1 开始连续递增，不得跳号、不得重复
3. 每集 title 为 4-12 个汉字的集名，概括本集核心事件或冲突钩子，风格参考：金箍碎佛规、罪臣之子承玄圭
4. 全剧分集须覆盖剧本摘要中的起承转合：前期立人设与世界观、中期升级矛盾与反转、后期高潮与结局，节奏适合短剧连载
5. 相邻集名之间要有因果衔接与追剧钩子，避免重复套路
6. 语言使用简体中文

必须输出严格 JSON：
{"episodes":[{"episodeNumber":1,"title":"集名"}, ...]}"""

# 与 manju episodeScript 对齐：逐集撰写拍摄正文
EPISODE_BATCH_CONTENT_SYSTEM = """你是专业的短剧/网剧编剧，负责根据原始创意、剧本摘要、分集规划与已有剧集正文，撰写指定集数的拍摄剧本正文。

输出要求：
1. 每次任务只输出用户指定批次范围内的集数，episodes 数组长度必须与批次集数完全一致
2. episodeNumber 须与用户指定的集数一一对应，不得遗漏、不得额外生成
3. 须携带并参考「已有剧集正文」保持剧情、人设与世界观连贯；首批次无已有正文时从第 1 集开篇写起
4. 批次内各集之间须有因果衔接，末集结尾留追剧钩子
5. 必须输出对象格式：{"episodes":[{"episodeNumber":数字,"title":"集名","creative":"本集创意","summary":"本集摘要","content":"..."}]}，不要直接输出数组
6. creative 为本集 80-200 字创意梗概；summary 为本集 120-300 字剧情摘要；content 为正文主字段；不要把正文写得过短

格式要求（每集 content 须严格遵守）：
1. 按场次组织，场号格式为 ### 场{集数}-{场次}，如第 1 集第 2 场：### 场1-2
2. 场头下一行写时间内外景，如：日 内 灵山大雄宝殿 / 夜 外 妖寨大门外 / 晨外 羽山刑场
3. 下一行写：出场人物：角色A、角色B（只写可出镜人物名；不要写「某某（声音）」「某某音色」等音色标注）
4. 动作用 △ 开头，独占一行；动作须具体可拍（景别、调度、道具、表情），禁止一句带过
5. 台词格式：角色名（情绪/vo/os/动作）：台词内容；旁白用 vo，内心独白用 os；台词要有潜台词与冲突；括号内写情绪/vo/os，不要写「声音」「音色」
6. 关键镜头可用【空镜：描述】收尾一场或一段
7. content 内不要输出「第X集」或「X.集名：」标题行，只输出场戏正文
8. 每集 2-3 场；每场 2-3 段 △ 动作与 2-3 句台词（或对白+vo）；整集 content 约 450-600 汉字，节奏紧凑、不注水
9. 语言使用简体中文，偏影视剧本风格，动作与台词可拍摄、有张力"""

# 把用户草稿改写成可拍摄分集正文
EPISODE_OPTIMIZE_SYSTEM = """你是专业的短剧/网剧编剧，负责把用户提供的分集剧本草稿，改写成可拍摄的分集正文。

工作原则：
1. 以用户草稿为剧情与台词的主要依据，保留人物、冲突、场次意图和关键对白，不要另起一套故事
2. 草稿已经接近拍摄格式时，做结构整理、补全场头/动作/台词，不要大幅改情节
3. 草稿只是梗概或提纲时，按草稿情节扩写成完整场戏，不得跑题
4. 须参考原始创意、剧本摘要与前后集，保持人设与世界观连贯
5. 只输出用户指定的那一集，episodes 数组必须恰好 1 项

格式要求（content 须严格遵守）：
1. 按场次组织，场号格式为 ### 场{集数}-{场次}，如第 2 集第 1 场：### 场2-1
2. 场头下一行写时间内外景，如：日 内 教室 / 夜 外 天台
3. 下一行写：出场人物：角色A、角色B（只写可出镜人物名；不要写音色标注）
4. 动作用 △ 开头，独占一行；动作须具体可拍
5. 台词格式：角色名（情绪/vo/os/动作）：台词内容；旁白用 vo，内心独白用 os
6. 关键镜头可用【空镜：描述】
7. content 内不要输出「第X集」或「X.集名：」标题行，只输出场戏正文
8. 每集 2-3 场；整集 content 约 450-600 汉字，节奏紧凑
9. 语言使用简体中文

必须输出严格 JSON：
{"episodes":[{"episodeNumber":数字,"title":"集名","content":"..."}]}"""


# 本集创意 → 集级摘要
EPISODE_SUMMARY_FROM_CREATIVE_SYSTEM = """你是专业的短剧/网剧编剧策划，根据整剧设定与本集原始创意，撰写本集「剧情摘要」。

输出要求：
1. 只输出用户指定的那一集，episodes 数组必须恰好 1 项
2. summary 为本集 120-300 字剧情摘要：人物、冲突、转折、结尾钩子；不要写成场戏正文
3. 可顺带优化 title（4-12 字集名）；不要输出 content/body
4. 须参考整剧创意、全剧摘要、全集集名、邻集正文与邻集摘要，保持人设与世界观连贯
5. 若提供「已有定妆角色名」，摘要中人物称呼须优先使用这些定妆名；新角色须写清全名
6. 语言使用简体中文

必须输出严格 JSON：
{"episodes":[{"episodeNumber":数字,"title":"集名","summary":"..."}]}"""


# 本集创意+摘要 → 拍摄正文（约束与批量 EPISODE_BATCH_CONTENT_SYSTEM 对齐）
EPISODE_BODY_FROM_BRIEF_SYSTEM = """你是专业的短剧/网剧编剧，根据本集原始创意与剧情摘要，撰写可拍摄的分集正文。

输出要求：
1. 只输出用户指定的那一集，episodes 数组必须恰好 1 项
2. 以本集创意与摘要为情节依据，不要另起故事
3. 须参考整剧设定、全集集名与邻集正文，保持剧情、人设与世界观连贯
4. content 为正文主字段；不要把正文写得过短
5. 若提供「已有定妆角色名」，出场人物与台词角色名须优先使用这些定妆名；新角色须在出场人物行写清全名

格式要求（content 须严格遵守）：
1. 按场次组织，场号格式为 ### 场{集数}-{场次}，如第 2 集第 1 场：### 场2-1
2. 场头下一行写时间内外景，如：日 内 教室 / 夜 外 天台 / 晨外 操场
3. 下一行写：出场人物：角色A、角色B（只写可出镜人物名；不要写「某某（声音）」「某某音色」等音色标注）
4. 动作用 △ 开头，独占一行；动作须具体可拍（景别、调度、道具、表情），禁止一句带过
5. 台词格式：角色名（情绪/vo/os/动作）：台词内容；旁白用 vo，内心独白用 os；台词要有潜台词与冲突；括号内写情绪/vo/os，不要写「声音」「音色」
6. 关键镜头可用【空镜：描述】收尾一场或一段
7. content 内不要输出「第X集」或「X.集名：」标题行，只输出场戏正文
8. 每集 2-3 场；每场 2-3 段 △ 动作与 2-3 句台词（或对白+vo）；整集 content 约 450-600 汉字
9. 语言使用简体中文，偏影视剧本风格，动作与台词可拍摄、有张力

必须输出严格 JSON：
{"episodes":[{"episodeNumber":数字,"title":"集名","content":"..."}]}"""


# 已有正文 → 反推本集创意 + 摘要
EPISODE_BRIEF_FROM_BODY_SYSTEM = """你是专业的短剧/网剧编剧策划。根据已有拍摄正文，反推本集「原始创意」与「剧情摘要」。

输出要求：
1. 只输出用户指定的那一集，episodes 数组必须恰好 1 项
2. creative 为本集 80-200 字原始创意：故事起点、核心冲突、看点；不要写成场戏
3. summary 为本集 120-300 字剧情摘要：人物、冲突、转折、结尾钩子；不要写成场戏正文
4. 可顺带优化 title（4-12 字集名）；不要输出 content/body
5. 须忠实于正文已有情节，不要另起故事
6. 语言使用简体中文

必须输出严格 JSON：
{"episodes":[{"episodeNumber":数字,"title":"集名","creative":"...","summary":"..."}]}"""


def _script_system(prompt: str, lang: str | None) -> str:
    """剧本类系统提示词：vi/en 时补充「结构标签保留中文」说明（build_fragments / seed 按这些标签解析）。"""
    if lang is None or is_zh(lang):
        return prompt
    name = lang_display_name(lang)
    return (
        f"{prompt}\n\n【结构标签】以下标签是程序解析用的固定格式，必须原样照写、不要翻译："
        "场号「### 场1-2」、时间内外景开头的「日/夜/晨 内/外」、「出场人物：」、动作行开头「△」、"
        "台词括号内的 vo / os、【空镜：…】。"
        f"标签之后的地点、人物名、动作描写、台词内容一律使用{name}。"
    )


def _length_spec(target_sec: int | None) -> tuple[int, int, str]:
    # 本集篇幅 (目标字数, 最少字数, 场次提示)；None / 0 沿用默认篇幅
    return episode_content_length(target_sec or EPISODE_TARGET_AUTO)


def _content_length_hint(lang: str | None, target_sec: int | None = None) -> str:
    """用户消息里的单集篇幅要求（vi/en 换算为词数）；target_sec 为用户选的单集目标时长。"""
    target_chars, min_chars, scenes = _length_spec(target_sec)
    hint = localize_length_units(
        f"每集 content 约 {target_chars} 汉字（不少于 {min_chars} 字，也不要明显超出），"
        f"含 {scenes}、精简 △ 与台词",
        lang,
    )
    if target_sec:
        hint += (
            f"；本集目标成片约 {format_target_label_zh(target_sec)}，"
            "正文须能在该时长内演完（慢速口播约 3–5 秒一句），宁短勿长"
        )
    return hint


def _too_short_retry_hint(lang: str | None, target_sec: int | None, tail: str) -> str:
    # 正文过短时的重试强调（按目标时长给字数）
    target_chars, min_chars, scenes = _length_spec(target_sec)
    return localize_length_units(
        f"{target_chars} 汉字（不少于 {min_chars} 字），含 {scenes}、{tail}",
        lang,
    )


def _format_neighbor_episode_briefs(episodes: list[dict[str, Any]], number: int, limit: int = 3) -> str:
    """邻集标题/创意/摘要，作正文节选的补充。"""
    others = [
        item
        for item in episodes
        if isinstance(item, dict) and int(item.get("episodeNumber") or 0) != number
    ]
    others.sort(key=lambda x: abs(int(x.get("episodeNumber") or 0) - number))
    picked = others[:limit]
    if not picked:
        return "（暂无邻集）"
    blocks: list[str] = []
    for item in sorted(picked, key=lambda x: int(x.get("episodeNumber") or 0)):
        num = item.get("episodeNumber")
        title = item.get("title") or f"第 {num} 集"
        creative = str(item.get("creative") or "").strip()
        summary = str(item.get("summary") or "").strip()
        parts = [f"第 {num} 集《{title}》"]
        if creative:
            parts.append(f"创意：{creative[:400]}")
        if summary:
            parts.append(f"摘要：{summary[:500]}")
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def _format_neighbor_episode_bodies(
    episodes: list[dict[str, Any]],
    number: int,
    limit: int = 3,
) -> str:
    """与 batch 同级：取距当前集最近、且已有正文的若干集节选。"""
    others = [
        item
        for item in episodes
        if isinstance(item, dict)
        and int(item.get("episodeNumber") or 0) != number
        and str(item.get("body") or item.get("content") or "").strip()
    ]
    others.sort(key=lambda x: abs(int(x.get("episodeNumber") or 0) - number))
    picked = others[:limit]
    if not picked:
        return "（暂无邻集正文）"
    blocks: list[str] = []
    for item in sorted(picked, key=lambda x: int(x.get("episodeNumber") or 0)):
        num = item.get("episodeNumber")
        title = item.get("title") or f"第 {num} 集"
        body = str(item.get("body") or item.get("content") or "").strip()
        if len(body) > 1800:
            body = body[:1800] + "\n…（上文已截断）"
        blocks.append(f"{num}.{title}：\n{body}")
    return "\n\n".join(blocks)


def format_character_asset_names_line(names: list[str] | None) -> str:
    """定妆角色名一行，供单集 prompt 约束称呼。"""
    cleaned: list[str] = []
    for raw in names or []:
        name = str(raw or "").strip()
        if name and name not in cleaned:
            cleaned.append(name)
    if not cleaned:
        return "（暂无定妆角色资产；新角色须在出场人物行写清全名）"
    joined = "、".join(cleaned[:80])
    return f"须优先使用这些定妆名：{joined}；新角色须在出场人物行写清全名"


def build_single_episode_context(
    project_summary: dict[str, Any],
    existing: list[dict[str, Any]],
    number: int,
    *,
    project_source: str = "",
    character_asset_names: list[str] | None = None,
) -> list[str]:
    """单集 summary/body/full/brief/optimize 共用的厚上下文块。"""
    return [
        f"整剧原始创意：\n{(project_source or '').strip() or '（无）'}",
        f"全剧剧本摘要：\n{format_summary_text(project_summary)}",
        f"全剧分集规划：\n{_format_episode_title_list(existing)}",
        f"邻集正文（近 {3} 集节选）：\n{_format_neighbor_episode_bodies(existing, number)}",
        f"邻集创意/摘要补充：\n{_format_neighbor_episode_briefs(existing, number)}",
        f"已有定妆角色名：\n{format_character_asset_names_line(character_asset_names)}",
    ]


async def run_episode_summary_from_creative(
    project_summary: dict[str, Any],
    existing: list[dict[str, Any]],
    number: int,
    creative: str,
    *,
    project_source: str = "",
    title: str | None = None,
    character_asset_names: list[str] | None = None,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """本集创意 → 集级 summary（可更新 title）。"""
    brief = (creative or "").strip()
    if len(brief) < 20:
        raise AppError("drama.episode_creative_required", min=20)
    title_text = (title or "").strip() or default_episode_title(number, lang)
    user_parts = [
        *build_single_episode_context(
            project_summary,
            existing,
            number,
            project_source=project_source,
            character_asset_names=character_asset_names,
        ),
        f"当前集号：{number}",
        f"当前集名：{title_text}",
        f"本集原始创意：\n{brief}",
        "请只输出本集 title 与 summary。",
    ]
    data = await drama_chat_json(
        EPISODE_SUMMARY_FROM_CREATIVE_SYSTEM,
        "\n\n".join(user_parts),
        max_tokens=4096,
        lang=lang,
    )
    episodes = data.get("episodes") if isinstance(data, dict) else None
    if not isinstance(episodes, list) or not episodes:
        raise AppError("drama.llm_empty_output")
    item = episodes[0] if isinstance(episodes[0], dict) else {}
    out_summary = str(item.get("summary") or item.get("synopsis") or "").strip()
    if len(out_summary) < 40:
        raise AppError("drama.llm_output_too_short")
    out_title = str(item.get("title") or "").strip() or title_text
    return [
        {
            "episodeNumber": number,
            "title": out_title,
            "creative": brief,
            "summary": out_summary,
            "body": "",
        }
    ]


async def run_episode_body_from_brief(
    project_summary: dict[str, Any],
    existing: list[dict[str, Any]],
    number: int,
    *,
    creative: str,
    summary: str,
    project_source: str = "",
    title: str | None = None,
    character_asset_names: list[str] | None = None,
    lang: str | None = None,
    target_sec: int | None = None,
) -> list[dict[str, Any]]:
    """本集创意+摘要 → 拍摄正文 body；target_sec 为单集目标时长（None 用默认篇幅）。"""
    brief = (creative or "").strip()
    syn = (summary or "").strip()
    if len(brief) < 10 and len(syn) < 40:
        raise AppError("drama.episode_input_required")
    title_text = (title or "").strip() or default_episode_title(number, lang)
    user_parts = [
        *build_single_episode_context(
            project_summary,
            existing,
            number,
            project_source=project_source,
            character_asset_names=character_asset_names,
        ),
        f"当前集号：{number}",
        f"当前集名：{title_text}",
        f"本集原始创意：\n{brief or '（无，以摘要为准）'}",
        f"本集剧情摘要：\n{syn or '（无，以创意为准）'}",
        _content_length_hint(lang, target_sec),
        "请撰写本集拍摄正文 content。",
    ]
    data = await drama_chat_json(
        _script_system(EPISODE_BODY_FROM_BRIEF_SYSTEM, lang),
        "\n\n".join(user_parts),
        max_tokens=8192,
        lang=lang,
    )
    episodes = data.get("episodes") if isinstance(data, dict) else None
    if not isinstance(episodes, list):
        raise AppError("drama.llm_empty_output")
    title_by_num = {number: title_text}
    normalized = _normalize_batch_episodes(episodes, number, number, title_by_num, lang=lang)
    if not normalized:
        raise AppError("drama.llm_empty_output")
    row = normalized[0]
    row["creative"] = brief or str(row.get("creative") or "")
    row["summary"] = syn or str(row.get("summary") or "")
    _, min_chars, _ = _length_spec(target_sec)
    if _content_char_len(str(row.get("body") or "")) < min_chars:
        # 短则再试一次强调长度
        retry = await drama_chat_json(
            _script_system(EPISODE_BODY_FROM_BRIEF_SYSTEM, lang),
            "\n\n".join(
                user_parts
                + [
                    "上一稿过短，请扩写至约 "
                    + _too_short_retry_hint(
                        lang, target_sec, f"每场 2-3 段 △ 与 2-3 句台词，仍只输出第 {number} 集。"
                    )
                ]
            ),
            max_tokens=8192,
            lang=lang,
        )
        retry_eps = retry.get("episodes") if isinstance(retry, dict) else None
        if isinstance(retry_eps, list):
            normalized = _normalize_batch_episodes(retry_eps, number, number, title_by_num, lang=lang) or normalized
            row = normalized[0]
            row["creative"] = brief or str(row.get("creative") or "")
            row["summary"] = syn or str(row.get("summary") or "")
    return [row]


async def run_episode_full_from_creative(
    project_summary: dict[str, Any],
    existing: list[dict[str, Any]],
    number: int,
    creative: str,
    *,
    project_source: str = "",
    title: str | None = None,
    character_asset_names: list[str] | None = None,
    lang: str | None = None,
    target_sec: int | None = None,
) -> list[dict[str, Any]]:
    """创意 → 摘要 → 正文（一键整集）。"""
    summary_rows = await run_episode_summary_from_creative(
        project_summary,
        existing,
        number,
        creative,
        project_source=project_source,
        title=title,
        character_asset_names=character_asset_names,
        lang=lang,
    )
    syn_row = summary_rows[0]
    body_rows = await run_episode_body_from_brief(
        project_summary,
        existing,
        number,
        creative=str(syn_row.get("creative") or creative),
        summary=str(syn_row.get("summary") or ""),
        project_source=project_source,
        title=str(syn_row.get("title") or title or ""),
        character_asset_names=character_asset_names,
        lang=lang,
        target_sec=target_sec,
    )
    out = body_rows[0]
    out["creative"] = str(syn_row.get("creative") or creative).strip()
    out["summary"] = str(syn_row.get("summary") or "").strip()
    out["title"] = str(
        out.get("title") or syn_row.get("title") or title or default_episode_title(number, lang)
    )
    return [out]


async def run_episode_brief_from_body(
    project_summary: dict[str, Any],
    existing: list[dict[str, Any]],
    number: int,
    body: str,
    *,
    project_source: str = "",
    title: str | None = None,
    character_asset_names: list[str] | None = None,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """已有拍摄正文 → 反推本集 creative + summary（不改 body）。"""
    script_body = (body or "").strip()
    if len(script_body) < 80:
        raise AppError("drama.episode_body_required")
    title_text = (title or "").strip() or default_episode_title(number, lang)
    user_parts = [
        *build_single_episode_context(
            project_summary,
            existing,
            number,
            project_source=project_source,
            character_asset_names=character_asset_names,
        ),
        f"当前集号：{number}",
        f"当前集名：{title_text}",
        f"本集拍摄正文：\n{script_body[:12000]}",
        "请只输出本集 title、creative、summary；不要改写正文。",
    ]
    data = await drama_chat_json(
        EPISODE_BRIEF_FROM_BODY_SYSTEM,
        "\n\n".join(user_parts),
        max_tokens=4096,
        lang=lang,
    )
    episodes = data.get("episodes") if isinstance(data, dict) else None
    if not isinstance(episodes, list) or not episodes:
        raise AppError("drama.llm_empty_output")
    item = episodes[0] if isinstance(episodes[0], dict) else {}
    out_creative = str(item.get("creative") or "").strip()
    out_summary = str(item.get("summary") or item.get("synopsis") or "").strip()
    if len(out_creative) < 20:
        raise AppError("drama.llm_output_too_short")
    if len(out_summary) < 40:
        raise AppError("drama.llm_output_too_short")
    out_title = str(item.get("title") or "").strip() or title_text
    return [
        {
            "episodeNumber": number,
            "title": out_title,
            "creative": out_creative,
            "summary": out_summary,
            "body": script_body,
        }
    ]


async def run_script_summary(
    creative: str,
    episode_count: int | None = None,
    image_style_id: str | None = None,
    *,
    lang: str | None = None,
) -> dict[str, Any]:
    # Build structured outline from creative brief
    trimmed = (creative or "").strip()
    if len(trimmed) < 10:
        raise AppError("drama.creative_too_short", min=10)

    user_message = build_script_summary_user_message(
        trimmed,
        episode_count=episode_count,
        image_style_id=image_style_id,
    )
    system = SCRIPT_SUMMARY_SYSTEM_PROMPT
    if lang is not None and not is_zh(lang):
        # 定妆提示词给生图模型：vi/en 用英文；其余字段按内容语言
        system += (
            "\n14. characters[].visualImage 是定妆照生图提示词，用英文（English）书写；"
            f"其余所有字段（含 seriesTitle、name、synopsis）使用{lang_display_name(lang)}"
        )
    data = await drama_chat_json(
        system,
        user_message,
        max_tokens=8192,
        lang=lang,
    )
    if episode_count:
        data["episodeCount"] = episode_count
    return data


def resolve_episode_target(
    summary: dict[str, Any] | None,
    project_params: dict[str, Any] | None = None,
    script_params: dict[str, Any] | None = None,
) -> int:
    # 解析目标总集数：优先项目创建时的集数，其次摘要 / 剧本参数
    candidates = [
        (project_params or {}).get("episode_count"),
        (summary or {}).get("episodeCount"),
        (script_params or {}).get("episode_count"),
    ]
    for raw in candidates:
        try:
            value = int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if value >= 1:
            return value
    return 12


def merge_episode_bodies(
    existing: list[dict[str, Any]],
    batch: list[dict[str, Any]],
    prefer_incoming: bool = False,
) -> list[dict[str, Any]]:
    # 按集号合并；默认更长文本优先，prefer_incoming 时以后写入为准（空值回退保留旧值）
    by_number: dict[int, dict[str, Any]] = {}
    for item in existing + batch:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("episodeNumber") or item.get("episode_number") or 0)
        except (TypeError, ValueError):
            continue
        if number < 1:
            continue
        body = str(item.get("body") or item.get("content") or "")
        creative = str(item.get("creative") or "").strip()
        summary = str(item.get("summary") or item.get("synopsis") or "").strip()
        title = str(item.get("title") or "").strip() or f"第 {number} 集"
        prev = by_number.get(number)
        if prev:
            prev_body = str(prev.get("body") or "")
            prev_creative = str(prev.get("creative") or "").strip()
            prev_summary = str(prev.get("summary") or "").strip()
            if prefer_incoming:
                body = body if body.strip() else prev_body
                creative = creative or prev_creative
                summary = summary or prev_summary
            else:
                if len(prev_body.strip()) > len(body.strip()):
                    body = prev_body
                if len(prev_creative) > len(creative):
                    creative = prev_creative
                if len(prev_summary) > len(summary):
                    summary = prev_summary
                if not creative:
                    creative = prev_creative
                if not summary:
                    summary = prev_summary
            if (title.startswith("第 ") or is_default_episode_title(title, number)) and prev.get("title"):
                title = str(prev.get("title"))
            elif not title or is_default_episode_title(title, number):
                title = str(prev.get("title") or title)
        new_origin = str(item.get("origin") or "").strip()
        prev_origin = str(prev.get("origin") or "").strip() if prev else ""
        origin = new_origin or prev_origin
        merged: dict[str, Any] = {
            "episodeNumber": number,
            "title": title,
            "body": body,
        }
        if creative:
            merged["creative"] = creative
        if summary:
            merged["summary"] = summary
        if origin == MANUAL_EPISODE_ORIGIN:
            merged["origin"] = MANUAL_EPISODE_ORIGIN
        by_number[number] = merged
    return [by_number[n] for n in sorted(by_number)]


def auto_missing_episode_numbers(
    existing: list[dict[str, Any]],
    total: int,
    *,
    min_chars: int = MIN_EPISODE_CONTENT_CHARS,
) -> list[int]:
    """自动流水线待填集号：跳过手动加集且正文未达标的空集。"""
    by_num: dict[int, dict[str, Any]] = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("episodeNumber") or 0)
        except (TypeError, ValueError):
            continue
        if number >= 1:
            by_num[number] = item
    missing: list[int] = []
    target = max(int(total or 0), 0)
    for number in range(1, target + 1):
        item = by_num.get(number)
        if item is None:
            missing.append(number)
            continue
        body = str(item.get("body") or item.get("content") or "")
        if _content_char_len(body) >= min_chars:
            continue
        if str(item.get("origin") or "") == MANUAL_EPISODE_ORIGIN:
            continue
        missing.append(number)
    return missing


def append_manual_episode(
    existing: list[dict[str, Any]],
    title: str | None = None,
    *,
    lang: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """在已有分集后追加一集空的手动集，返回 (新列表, 新集号)。"""
    max_number = 0
    for item in existing:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("episodeNumber") or 0)
        except (TypeError, ValueError):
            continue
        if number > max_number:
            max_number = number
    next_number = max_number + 1
    if next_number < 1:
        next_number = 1
    if next_number > MAX_DRAMA_EPISODES:
        raise AppError("drama.max_episodes", max=MAX_DRAMA_EPISODES)
    title_text = (title or "").strip() or default_episode_title(next_number, lang)
    added = {
        "episodeNumber": next_number,
        "title": title_text,
        "creative": "",
        "summary": "",
        "body": "",
        "origin": MANUAL_EPISODE_ORIGIN,
    }
    merged = merge_episode_bodies(existing, [added])
    return merged, next_number


def count_completed_episodes(
    episodes: list[dict[str, Any]],
    total: int,
    *,
    min_chars: int = MIN_EPISODE_CONTENT_CHARS,
) -> int:
    # 统计 1..total 中正文达到质量阈值（min_chars，随项目目标时长）的集数
    done = 0
    for item in episodes:
        try:
            number = int(item.get("episodeNumber") or 0)
        except (TypeError, ValueError):
            continue
        body = str(item.get("body") or "").strip()
        if 1 <= number <= total and _content_char_len(body) >= min_chars:
            done += 1
    return done


def _content_char_len(text: str) -> int:
    return len("".join((text or "").split()))


def normalize_series_title(raw: str | None) -> str:
    """清洗 AI 输出的剧名，去掉书名号/引号与过长尾巴。"""
    title = str(raw or "").strip()
    if not title:
        return ""
    title = title.strip("「」『』《》\"'“”‘’").strip()
    title = title.splitlines()[0].strip()
    # 截到合理项目名长度（中文短剧名）
    if len(title) > 24:
        title = title[:24].rstrip("，。；、…·-— ")
    return title


def pick_auto_project_title(
    summary: dict[str, Any],
    *,
    creative: str,
    current_title: str,
) -> str | None:
    """摘要完成后：优先用 AI 剧名覆盖「创意截断/过长」默认标题；用户已改名则不覆盖。"""
    series = normalize_series_title(
        summary.get("seriesTitle") or summary.get("title") or summary.get("projectTitle")
    )
    if not series:
        return None
    current = (current_title or "").strip()
    creative_prefix = (creative or "").strip()[:20]
    looks_default = (
        not current
        or current in {"未命名漫剧", "自由画布项目"}
        or len(current) > 36
        or (creative_prefix and current.startswith(creative_prefix))
        or current.endswith("…")
    )
    if not looks_default:
        return None
    return series


def format_summary_text(summary: dict[str, Any]) -> str:
    # Human-readable outline for UI / LLM context
    lines = [
        f"剧名：{summary.get('seriesTitle', '')}",
        f"集数：{summary.get('episodeCount', '')}",
        f"类型：{summary.get('storyType', '')}",
        f"受众：{summary.get('targetAudience', '')}",
        f"钩子：{summary.get('coreHook', '')}",
        f"一句话：{summary.get('oneLineStory', '')}",
        "",
        "人物：",
    ]
    for c in summary.get("characters") or []:
        if isinstance(c, dict):
            lines.append(
                f"- {c.get('name', '')}（{c.get('roleType', '')}/{c.get('title', '')}）："
                f"{c.get('visualImage', '')}；标签：{c.get('coreTags', '')}；"
                f"弧光：{c.get('growthArc', '')}"
            )
    lines.extend(["", "梗概：", str(summary.get("synopsis") or "")])
    return "\n".join(lines)


def _format_episode_title_list(episodes: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in sorted(episodes, key=lambda x: int(x.get("episodeNumber") or 0)):
        num = item.get("episodeNumber")
        title = item.get("title") or f"第 {num} 集"
        rows.append(f"第 {num} 集：{title}")
    return "\n".join(rows) if rows else "（暂无分集规划）"


def _format_existing_episode_content(episodes: list[dict[str, Any]], limit: int = 3) -> str:
    # 仅附最近若干集正文，控制上下文长度
    completed = [
        item
        for item in episodes
        if isinstance(item, dict) and str(item.get("body") or item.get("content") or "").strip()
    ]
    completed.sort(key=lambda x: int(x.get("episodeNumber") or 0))
    if not completed:
        return "（暂无，本批次从开篇写起）"
    tail = completed[-limit:]
    blocks: list[str] = []
    for item in tail:
        num = item.get("episodeNumber")
        title = item.get("title") or f"第 {num} 集"
        body = str(item.get("body") or item.get("content") or "").strip()
        # 过长时截断尾部摘要，避免挤占当前集生成空间
        if len(body) > 1800:
            body = body[:1800] + "\n…（上文已截断）"
        blocks.append(f"{num}.{title}：\n{body}")
    return "\n\n".join(blocks)


def _titles_ready(existing: list[dict[str, Any]], total: int) -> bool:
    titled = {
        int(item.get("episodeNumber") or 0)
        for item in existing
        if isinstance(item, dict)
        and str(item.get("title") or "").strip()
        and not str(item.get("title") or "").startswith("第 ")
        and not is_default_episode_title(item.get("title"))
    }
    # 也接受「第 N 集」以外、或至少有 total 条带 title 的记录
    with_title = [
        item
        for item in existing
        if isinstance(item, dict)
        and 1 <= int(item.get("episodeNumber") or 0) <= total
        and str(item.get("title") or "").strip()
    ]
    if len(with_title) >= total:
        # 若全是占位「第 N 集」则仍需重跑大纲
        placeholder_only = all(
            is_default_episode_title(item.get("title"), item.get("episodeNumber"))
            for item in with_title
        )
        return not placeholder_only
    return len(titled) >= total


async def run_episode_outline(
    creative: str,
    summary: dict[str, Any],
    episode_count: int,
    *,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    # 生成全集集名大纲
    summary_text = format_summary_text(summary)
    user = "\n".join(
        [
            f"总集数：{episode_count} 集（episodes 数组必须恰好 {episode_count} 项）",
            "",
            f"原始创意：\n{(creative or '').strip()}",
            "",
            f"剧本摘要：\n{summary_text}",
            "",
            "请输出全部分集的 episodeNumber 与 title。",
        ]
    )
    data = await drama_chat_json(
        _script_system(EPISODE_OUTLINE_SYSTEM, lang), user, max_tokens=4096, lang=lang
    )
    episodes = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(episodes, list) or not episodes:
        raise AppError("drama.llm_bad_format")
    result: list[dict[str, Any]] = []
    for i, item in enumerate(episodes):
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("episodeNumber") or (i + 1))
        except (TypeError, ValueError):
            number = i + 1
        title = str(item.get("title") or "").strip() or default_episode_title(number, lang)
        result.append({"episodeNumber": number, "title": title, "body": ""})
    if len(result) < episode_count:
        # 补齐缺失集号
        have = {int(x["episodeNumber"]) for x in result}
        for n in range(1, episode_count + 1):
            if n not in have:
                result.append({"episodeNumber": n, "title": default_episode_title(n, lang), "body": ""})
    result.sort(key=lambda x: int(x["episodeNumber"]))
    return result[:episode_count]


async def ensure_episode_outline(
    creative: str,
    summary: dict[str, Any],
    existing: list[dict[str, Any]],
    total: int,
    *,
    lang: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """返回 (合并后分集列表, 是否实际调用 LLM 生成大纲)。"""
    if _titles_ready(existing, total):
        return existing, False
    outline = await run_episode_outline(creative, summary, total, lang=lang)
    return merge_episode_bodies(outline, existing), True


async def run_episode_script_batch(
    summary: dict[str, Any],
    existing: list[dict[str, Any]],
    batch_size: int = 1,
    total: int | None = None,
    creative: str = "",
    *,
    lang: str | None = None,
    target_sec: int | None = None,
) -> list[dict[str, Any]]:
    # 按缺失集号生成下一批正文（默认逐集）；手动空集不参与自动补写；target_sec 为单集目标时长
    target = int(total or summary.get("episodeCount") or 12)
    _, min_chars, _ = _length_spec(target_sec)
    missing = auto_missing_episode_numbers(existing, target, min_chars=min_chars)
    if not missing:
        return []
    start = missing[0]
    end = start
    for i in range(1, min(batch_size, len(missing))):
        if missing[i] != end + 1:
            break
        end = missing[i]

    title_by_num = {
        int(item.get("episodeNumber") or 0): str(item.get("title") or "")
        for item in existing
        if isinstance(item, dict)
    }
    batch_titles = "\n".join(
        f"第 {n} 集：{title_by_num.get(n) or f'第 {n} 集'}" for n in range(start, end + 1)
    )
    batch_size_n = end - start + 1
    summary_text = format_summary_text(summary)
    user = "\n".join(
        [
            f"当前任务：撰写第 {start} 集至第 {end} 集（共 {batch_size_n} 集）的完整剧本正文",
            f"全剧共 {target} 集",
            f"episodes 输出数组必须恰好 {batch_size_n} 项，episodeNumber 从 {start} 到 {end}",
            _content_length_hint(lang, target_sec),
            "",
            f"原始创意：\n{(creative or '').strip() or '（无额外创意，以摘要为准）'}",
            "",
            f"剧本摘要：\n{summary_text}",
            "",
            f"全剧分集规划：\n{_format_episode_title_list(existing)}",
            "",
            f"本批次待撰写：\n{batch_titles}",
            "",
            f"已有剧集正文：\n{_format_existing_episode_content(existing)}",
            "",
            f"请输出第 {start}–{end} 集各集的 content 字段（可附带 title）。",
        ]
    )

    data = await drama_chat_json(
        _script_system(EPISODE_BATCH_CONTENT_SYSTEM, lang),
        user,
        temperature=0.6,
        max_tokens=16384,
        lang=lang,
    )

    episodes = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(episodes, list):
        raise AppError("drama.llm_bad_format")

    normalized = _normalize_batch_episodes(episodes, start, end, title_by_num, lang=lang)
    # 正文过短则带强调提示重试一次
    too_short = [
        item
        for item in normalized
        if _content_char_len(str(item.get("body") or "")) < min_chars
    ]
    if too_short:
        retry_user = (
            user
            + "\n\n上次输出过短。请重写本批次，每集 content 约 "
            + _too_short_retry_hint(lang, target_sec, "精简 △ 与台词，不得压缩成梗概。")
        )
        retry = await drama_chat_json(
            _script_system(EPISODE_BATCH_CONTENT_SYSTEM, lang),
            retry_user,
            temperature=0.6,
            max_tokens=16384,
            lang=lang,
        )
        retry_eps = retry.get("episodes") if isinstance(retry, dict) else retry
        if isinstance(retry_eps, list):
            normalized = _normalize_batch_episodes(retry_eps, start, end, title_by_num, lang=lang)

    if not normalized:
        raise AppError("drama.llm_empty_output")
    return normalized


async def run_episode_script_from_draft(
    summary: dict[str, Any],
    existing: list[dict[str, Any]],
    episode_number: int,
    draft: str,
    creative: str = "",
    character_asset_names: list[str] | None = None,
    *,
    lang: str | None = None,
    target_sec: int | None = None,
) -> list[dict[str, Any]]:
    """把用户草稿优化成指定集的拍摄正文；target_sec 为单集目标时长。"""
    number = int(episode_number)
    draft_text = (draft or "").strip()
    if number < 1:
        raise AppError("drama.invalid_episode_number")
    if len(draft_text) < 20:
        raise AppError("drama.draft_too_short", min=20)

    title_by_num = {
        int(item.get("episodeNumber") or 0): str(item.get("title") or "")
        for item in existing
        if isinstance(item, dict)
    }
    current_title = title_by_num.get(number) or default_episode_title(number, lang)
    ctx = build_single_episode_context(
        summary,
        existing,
        number,
        project_source=creative,
        character_asset_names=character_asset_names,
    )
    user = "\n\n".join(
        [
            f"当前任务：把用户草稿优化为第 {number} 集完整拍摄剧本",
            f"episodeNumber 必须为 {number}，episodes 数组必须恰好 1 项",
            f"当前集名：{current_title}（可按草稿核心事件微调 title）",
            _content_length_hint(lang, target_sec),
            *ctx,
            f"用户提供的第 {number} 集草稿：\n{draft_text}",
            f"请输出第 {number} 集的 title 与 content。",
        ]
    )
    data = await drama_chat_json(
        _script_system(EPISODE_OPTIMIZE_SYSTEM, lang),
        user,
        temperature=0.55,
        max_tokens=16384,
        lang=lang,
    )
    episodes = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(episodes, list):
        raise AppError("drama.llm_bad_format")
    normalized = _normalize_batch_episodes(episodes, number, number, title_by_num, lang=lang)
    too_short = [
        item
        for item in normalized
        if _content_char_len(str(item.get("body") or "")) < _length_spec(target_sec)[1]
    ]
    if too_short:
        retry_user = (
            user
            + "\n\n上次输出过短。请按用户草稿重写第 "
            + str(number)
            + " 集，content 约 "
            + _too_short_retry_hint(lang, target_sec, "精简 △ 与台词。")
        )
        retry = await drama_chat_json(
            _script_system(EPISODE_OPTIMIZE_SYSTEM, lang),
            retry_user,
            temperature=0.55,
            max_tokens=16384,
            lang=lang,
        )
        retry_eps = retry.get("episodes") if isinstance(retry, dict) else retry
        if isinstance(retry_eps, list):
            normalized = _normalize_batch_episodes(retry_eps, number, number, title_by_num, lang=lang)
    if not normalized:
        raise AppError("drama.llm_empty_output")
    origin_item = next(
        (
            item
            for item in existing
            if isinstance(item, dict) and int(item.get("episodeNumber") or 0) == number
        ),
        None,
    )
    origin = str((origin_item or {}).get("origin") or "")
    if origin == MANUAL_EPISODE_ORIGIN:
        for item in normalized:
            item["origin"] = MANUAL_EPISODE_ORIGIN
    return normalized


def _normalize_batch_episodes(
    episodes: list[Any],
    start: int,
    end: int,
    title_by_num: dict[int, str],
    *,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for offset, item in enumerate(episodes):
        if not isinstance(item, dict):
            continue
        number = item.get("episodeNumber") or item.get("episode_number") or (start + offset)
        try:
            number_i = int(number)
        except (TypeError, ValueError):
            number_i = start + offset
        if number_i < start or number_i > end:
            continue
        body = str(item.get("content") or item.get("body") or "").strip()
        if not body:
            continue
        title = (
            str(item.get("title") or "").strip()
            or title_by_num.get(number_i)
            or default_episode_title(number_i, lang)
        )
        row: dict[str, Any] = {
            "episodeNumber": number_i,
            "title": title,
            "body": body,
        }
        creative = str(item.get("creative") or "").strip()
        summary = str(item.get("summary") or item.get("synopsis") or "").strip()
        if creative:
            row["creative"] = creative
        if summary:
            row["summary"] = summary
        normalized.append(row)
    return normalized
