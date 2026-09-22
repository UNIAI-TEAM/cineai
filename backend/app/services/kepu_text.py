"""科普文字链路：拆镜（storyboard）与主题扩写，独立于图/视频 provider。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from app.services.ark_mock import mock_expand_content as _vi_mock_expand_content
from app.services.ark_mock import mock_storyboard_items
from app.services.drama.llm import _extract_json
from app.services.llm_client import chat_completions
from app.services import seedance_segments as segplan
from app.services.text_lang import cut_words, is_cjk_text

logger = logging.getLogger(__name__)


def _fallback_overlay_title(text: str, shot_no: int) -> str:
    """Last resort when LLM omits title — never blind-slice mid-word (e.g. ERP→ER)."""
    if text and not is_cjk_text(text):
        return _fallback_overlay_title_latin(text, shot_no)
    raw = re.sub(r"\s+", "", (text or "").strip())
    if not raw:
        return f"场景{shot_no}"
    clause = re.split(r"[，。；！？、,:;]", raw, maxsplit=1)[0].strip()
    if 2 <= len(clause) <= 10 and not _looks_truncated_token(clause, raw):
        return clause
    return f"场景{shot_no}"


def _fallback_overlay_title_latin(text: str, shot_no: int) -> str:
    """越南语 / 英文旁白的标题兜底：保留空格，取首个短分句，否则「Cảnh N」。"""
    raw = re.sub(r"\s+", " ", text.strip())
    clause = re.split(r"[,.;:!?]", raw, maxsplit=1)[0].strip()
    if 2 <= len(clause) <= 32 and not _looks_truncated_token(clause, raw):
        return clause
    return f"Cảnh {shot_no}"


def _fallback_overlay_subtitle(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if not is_cjk_text(raw):
        # 越南语 / 英文：保留空格，取首个分句并按词截断（中文规则会把词粘在一起）
        clause = re.split(r"[,.;:!?]", re.sub(r"\s+", " ", raw), maxsplit=1)[0].strip()
        return cut_words(clause or raw, 48)
    cleaned = re.sub(r"\s+", "", raw)
    clause = re.split(r"[，。；！？、,:;]", cleaned, maxsplit=1)[0].strip()
    if 4 <= len(clause) <= 22:
        return clause
    if len(clause) > 22:
        # Prefer a trailing noun-ish chunk over a head that cuts mid-phrase
        for n in range(18, 7, -1):
            tail = clause[-n:].lstrip("的与和及")
            if 6 <= len(tail) <= 18 and not re.match(r"[A-Za-z0-9]", tail[:1] or ""):
                if not _looks_truncated_token(tail, clause):
                    return tail
        head = clause[:18]
        if re.search(r"[A-Za-z0-9]$", head) and re.match(r"[A-Za-z0-9]", clause[18:19] or ""):
            m = re.search(r"[A-Za-z0-9]+$", head)
            if m and m.start() > 6:
                head = head[: m.start()]
        return head
    return cleaned[:22] if len(cleaned) > 22 else cleaned


def _looks_truncated_token(title: str, full_text: str) -> bool:
    """True if title is a prefix of narration that cuts a Latin/数字专有词 mid-way."""
    t = re.sub(r"\s+", "", (title or "").strip())
    full = re.sub(r"\s+", "", (full_text or "").strip())
    if not t or not full.startswith(t):
        return False
    if len(full) <= len(t):
        return False
    # Truncated mid-ASCII token: title ends with alnum and next char is alnum
    if re.search(r"[A-Za-z0-9]$", t) and re.match(r"[A-Za-z0-9]", full[len(t)]):
        return True
    # Obvious raw prefix grab of long narration
    if len(t) <= 12 and len(full) > len(t) + 8 and full.startswith(t):
        return True
    return False


def _normalize_overlay_title(title: str, text: str, shot_no: int) -> str:
    t = (title or "").strip()
    if not t or _looks_truncated_token(t, text):
        return _fallback_overlay_title(text, shot_no)
    return t[:32]


def _normalize_overlay_subtitle(subtitle: str, text: str) -> str:
    s = (subtitle or "").strip()
    if not s or _looks_truncated_token(s, text):
        return _fallback_overlay_subtitle(text)[:64]
    return s[:64]


def storyboard_name_policy(allow_source_names: bool) -> str:
    """旁白是否保留用户文案中的店名/产品名；画面始终不烧录 logo。"""
    if allow_source_names:
        return (
            "用户文案里出现的店名、地址、产品名、人名必须在旁白与 title 原样保留，"
            "禁止改成某店/某品牌；文案没有的名称一律不许编。"
            "img_prompt 仍禁止烧录真实 logo、商标图形或屏幕可读文字。"
        )
    return "禁止真实商标/公司名/人名（改用泛称）。"


@dataclass
class ShotPlan:
    shot: int
    duration: float
    text: str
    img_prompt: str
    video_prompt: str
    camera: str
    bgm: str
    overlay_title: str = ""
    overlay_subtitle: str = ""
    segment_script: str = ""


@dataclass
class StoryboardResult:
    shots: list[ShotPlan]
    character_bible: str = ""
    bgm_lock: str = ""


async def chat_storyboard(
    source_text: str,
    source_type: str,
    style_prefix: str,
    llm_system_addon: str,
    duration_min: int,
    duration_max: int,
    max_shot_duration: int,
    *,
    pipeline_mode: str = "full",
    character_hint: str = "",
    extra_requirements: str = "",
    consistency_mode: str = "character",
    output_ratio: str = "16:9",
    shot_range_override: tuple[int, int] | None = None,
    allow_source_names: bool = False,
    mock: bool,
) -> StoryboardResult:
    if mock:
        return await asyncio.to_thread(
            mock_storyboard,
            source_text,
            source_type,
            style_prefix,
            duration_min,
            duration_max,
            pipeline_mode,
            shot_range_override,
        )

    user_constraints = ""
    if (character_hint or "").strip():
        user_constraints += (
            f"用户指定人物设定（必须严格遵守，写入 character_bible）：{(character_hint or '').strip()}。"
        )
    if (extra_requirements or "").strip():
        user_constraints += f"用户其他画面要求：{(extra_requirements or '').strip()}。"

    mode = (consistency_mode or "character").strip().lower()
    if mode not in {"character", "style", "diverse"}:
        mode = "character"

    if mode == "diverse":
        if (character_hint or "").strip():
            person_rule = (
                "character_bible：概括用户人物设定（可换具体个人，但须同类）。"
                "【人物硬性】每镜必须出现符合用户人物设定的真人，面容清晰可见"
                "（三分之四侧脸或浅景深半身），禁止只拍手部、后脑勺、过肩无脸或空界面无人。"
                "img_prompt 须写清该镜人物族裔/发型/服装与可见面容角度，以及面前界面类型；各镜可换人。"
            )
        else:
            person_rule = (
                "character_bible：根据主题与模板系统规则决定是否出人物，不要默认全片必须有人或必须无人。"
                "模板要求人在场则写清操作者类型（可不锁同一张脸）；主题以界面/场景/示意图为主则可写「无固定人物」。"
                "img_prompt 写清本镜主体与构图，禁止与模板系统附加规则对着干。"
            )
        consistency = (
            "必须输出严格 JSON 对象（不要数组、不要 markdown、不要代码围栏）："
            '{"character_bible":"...","shots":[...]}。'
            f"{person_rule}"
            f"视觉气质仅作底线参考（不要被其颜色绑架）：{style_prefix}。"
            f"{user_constraints}"
            "【动态规划】先分析用户内容的领域、产品形态与使用场景，再决定色板与界面类型，"
            "再拆镜；每镜对应不同操作或能力（总览、接入、工作台、流程、结果、部署、生态等）。"
            "配色与材质必须贴合内容（浅色SaaS、文档站、深色IDE、终端、架构图、白板均可），"
            "禁止默认霓虹蓝/赛博大屏/蓝紫渐变HUD，禁止各镜画面雷同，禁止待办任务清单，"
            "禁止同一仪表盘复制粘贴换字。"
        )
    elif mode == "style":
        consistency = (
            "必须输出严格 JSON 对象（不要数组、不要 markdown、不要代码围栏）："
            '{"character_bible":"...","shots":[...]}。'
            "character_bible：可简写「无固定主角」或留空说明；不要强行统一人物外形。"
            f"画风气质统一：{style_prefix}。"
            f"{user_constraints}"
            "各镜场景与构图应随内容变化，只需保持同类画风，禁止镜头间画面几乎一样。"
            "每镜 img_prompt 只写本镜场景与构图。"
        )
    else:
        consistency = (
            "必须输出严格 JSON 对象（不要数组、不要 markdown、不要代码围栏）："
            '{"character_bible":"...","shots":[...]}。'
            "character_bible：80-160字，固定描述本片反复出现的人物/主体外形"
            "（年龄感、发型发色、五官气质、体型、服装配色与辨识物），全片唯一设定，禁止每镜改人设。"
            f"画风要求（全片强制统一）：{style_prefix}。"
            f"{user_constraints}"
            "禁止镜头间混用写实摄影/真人脸与插画或动漫；禁止换脸换装换发型。"
            "每镜 img_prompt 只写本镜场景与构图（景物、动作、光影），不要重复粘贴大段画风/人物锁定原文；"
            "出现人物时用短句点出与 character_bible 一致的关键特征即可。"
        )
    # shot_cap 单镜 duration 上限（秒）；shot_lo/shot_hi 按文案字数或模板锁定
    shot_cap = min(duration_max, max_shot_duration)
    if shot_range_override:
        shot_lo, shot_hi = shot_range_override
    else:
        shot_lo, shot_hi = segplan.suggested_kepu_shot_range(source_text, pipeline_mode=pipeline_mode)
    shot_range = f"{shot_lo}-{shot_hi}"
    # name_rule 获客模板保留用户文案中的店名；其它模板改用泛称以免商标入画
    name_rule = storyboard_name_policy(allow_source_names)
    # segment_rules 科普逐段脚本生产约束（对齐漫剧 cue，无 @asset）
    segment_rules = (
        "【segments 生产规范】"
        "segments 必填；系统会落成 @duration +【字幕：后期叠旁白字幕】/【BGM：后期混音】/"
        "【旁白·自然语速·同步字幕】生产脚本，成片字幕与配乐由后期合成，不由视频模型烧录。"
        "因此 kind/text/duration 必须可直接消费。"
        "段序优先「画面→旁白」交替，首段尽量 kind=visual（保证首帧有料）；"
        "visual/action 的 text 必须含景别+主体动作+场景/界面类型，禁止空镜与模糊氛围词堆砌；"
        "narration 的 text 为一句一事、可朗读口播，按约 5 字/秒估 duration（语速自然偏快）；"
        "旁白 duration 严格跟字数，最多多 1 秒呼吸，禁止把短句拉满到镜长上限或拖腔注水；"
        "单段 duration 3-12 秒，镜内各段之和约等于本镜 duration，且不超过 "
        f"{shot_cap} 秒。"
        f"{name_rule}"
        "character_bible 与 bgm_lock 全片唯一，各镜不得改人设或漂移 BGM 氛围。"
    )
    if pipeline_mode == "image_text":
        diversity_note = (
            f"拆成 {shot_range} 个分镜，每镜一个独立视觉场景；"
            + (
                "画风气质可统一，但界面/场景构图必须明显不同。"
                if mode != "character"
                else "但画风与人物必须一致。"
            )
        )
        ratio = (output_ratio or "16:9").strip() or "16:9"
        orient = "竖屏" if ratio == "9:16" else ("方形" if ratio == "1:1" else "横屏")
        system = (
            f"你是{orient}图文短视频编剧。所有字段必须使用简体中文。"
            f"{consistency}{llm_system_addon}"
            f"每镜 duration 在 {duration_min}-{shot_cap} 秒。"
            "这是「静图+叠字+配音」模式：不生成 AI 视频，但需要旁白配音；"
            "画面禁止出现任何文字/水印/字幕。"
            "shots 字段说明："
            "shot(序号)、duration(秒)、"
            "title(对本镜内容的概括短标题，2-8字，语义完整有力；"
            "必须是总结提炼，禁止从 text 截取前几个字，禁止截断专有名词如 ERP→ER)、"
            "subtitle(对本镜卖点/要点的一句概括，8-22字，同样禁止原文截取前缀)、"
            "text(旁白台词，口语化，约匹配该镜时长，可供 TTS 朗读，一般 20-60 字)、"
            "segments(数组，精确到每一段：每项含 duration 秒、kind=visual|narration、text；"
            "visual 写景别与画面动作，narration 写口播)、"
            f"img_prompt({orient} {ratio} 构图画面提示词，留出边缘给文字叠层，主体居中，"
            f"禁止要求画面内写字；{name_rule})、"
            "video_prompt(可留空或写轻微推拉)、camera(如：缓慢推近/轻拉远)、bgm(情绪，全片尽量同一氛围)。"
            "另输出顶层 bgm_lock(全片统一 BGM 氛围一句)。"
            f"{segment_rules}"
            f"{diversity_note}"
        )
    else:
        diversity_note = (
            f"拆成 {shot_range} 个分镜，短镜快切，各镜场景随内容变化，禁止雷同空镜。"
            if mode != "character"
            else f"画风与人物必须全片一致；拆成 {shot_range} 镜，短镜快切。"
        )
        system = (
            "你是短视频分镜编剧。所有字段必须使用简体中文"
            "（包括 title、text、img_prompt、video_prompt、camera、bgm、segments）。"
            f"{consistency}{llm_system_addon}"
            f"每镜 duration 在 {duration_min}-{shot_cap} 秒，不要为凑满上限而注水。"
            "shots 字段说明："
            "shot(序号)、duration(秒)、"
            "title(对本镜旁白的概括短标题，2-8字，语义完整；"
            "必须是总结提炼，禁止从 text 截取前缀，禁止截断专有名词如 ERP→ER)、"
            "subtitle(可选，一句要点概括 8-22字)、"
            "text(旁白台词，与 segments 中 narration 文案一致或为其摘要)、"
            "segments(必填数组，精确到每一段：每项 duration、kind=visual|narration|action、text)、"
            "img_prompt(与首段 visual 一致的中文首帧提示词，含具体景物与构图)、"
            "video_prompt(可与 segments 画面摘要一致)、"
            "camera(运镜，如：缓慢上摇/轻推/横移)、bgm(情绪，全片同一氛围)。"
            "顶层另输出 bgm_lock(全片统一 BGM 氛围一句，与各镜 bgm 一致)。"
            "img_prompt 与 video_prompt 禁止英文句子，专有名词可保留原文。"
            f"{segment_rules}"
            f"{diversity_note}"
        )
    user = (
        f"输入类型：{source_type}。请先理解内容与应用场景，再拆成精确到每一段的分镜"
        f"（{shot_range} 镜，短镜快切，禁止拖腔注水）：\n{source_text}"
    )
    json_format = {"type": "json_object"}
    try:
        content = await chat_completions(
            system,
            user,
            function_id="kepu.script",
            temperature=0.6,
            timeout=120.0,
            response_format=json_format,
        )
    except RuntimeError as exc:
        if "response_format" not in str(exc).lower():
            raise
        logger.warning("分镜 LLM 不支持 response_format，降级普通调用: %s", exc)
        content = await chat_completions(system, user, function_id="kepu.script", temperature=0.6, timeout=120.0)

    if not (content or "").strip():
        logger.warning("分镜 LLM 返回空内容，重试一次 source_type=%s", source_type)
        retry_user = (
            f"{user}\n\n"
            "【重要】请只输出一个完整 JSON 对象，顶层含 character_bible、bgm_lock、shots 数组；"
            "不要 markdown、不要代码围栏、字符串内不要未转义换行。"
        )
        try:
            content = await chat_completions(
                system,
                retry_user,
                function_id="kepu.script",
                temperature=0.6,
                timeout=120.0,
                response_format=json_format,
            )
        except RuntimeError as exc:
            if "response_format" not in str(exc).lower():
                raise
            content = await chat_completions(
                system, retry_user, function_id="kepu.script", temperature=0.6, timeout=120.0
            )

    if not (content or "").strip():
        raise RuntimeError("分镜模型返回空内容，请检查文字模型渠道配置或稍后重试")

    return parse_storyboard(
        content,
        style_prefix,
        duration_min,
        duration_max,
        max_shot_duration,
    )


def mock_storyboard(
    source_text: str,
    source_type: str,
    style_prefix: str,
    duration_min: int,
    duration_max: int,
    pipeline_mode: str = "full",
    shot_range_override: tuple[int, int] | None = None,
) -> StoryboardResult:
    # shot_lo/shot_hi 与正式拆镜区间一致，避免 mock 仍只出 5 镜
    if shot_range_override:
        shot_lo, shot_hi = shot_range_override
    else:
        shot_lo, shot_hi = segplan.suggested_kepu_shot_range(source_text, pipeline_mode=pipeline_mode)
    # 非中文输入：旁白与叠字用越南语 mock（见 ark_mock.py）；标题/副标题直接给定
    vi_items = (
        None
        if is_cjk_text(source_text)
        else mock_storyboard_items(source_text, source_type, shot_lo, shot_hi)
    )
    chunks = [c.strip() for c in re.split(r"[。！？\n\.\!\?]+", source_text) if c.strip()]
    if source_type == "theme" and len(chunks) <= 1:
        topic = source_text.strip()
        chunks = [
            f"引入主题：{topic}",
            f"核心概念解释：{topic}",
            f"一个关键例子说明{topic}",
            f"常见误解与澄清",
            f"总结与启发",
        ]
    if len(chunks) < 3:
        chunks = chunks + ["补充画面过渡", "收尾总结"]
    chunks = chunks[:shot_hi]
    while len(chunks) < shot_lo:
        chunks.append("补充画面过渡")
    mid = (duration_min + duration_max) // 2
    if pipeline_mode == "image_text":
        mid = min(mid, max(duration_min, 3))
    bible = (
        f"统一角色：与「{source_text.strip()[:24]}」相关的核心人物，"
        "中等身材，简洁服饰配色固定，五官清晰可辨，全片外形不变"
    )
    bgm_lock = segplan.infer_bgm_mood(source_text, style_prefix)
    plans: list[ShotPlan] = []
    rows = vi_items or [(None, None, c) for c in chunks]
    for i, (vi_title, vi_subtitle, text) in enumerate(rows, start=1):
        # Mock: invent short summary titles, do not slice narration mid-token
        topic_bit = re.sub(r"^(引入主题|核心概念解释|一个关键例子说明)[：:]?", "", text).strip()
        title = f"要点{i}" if len(topic_bit) > 10 else (topic_bit[:8] or f"场景{i}")
        if "：" in text or ":" in text:
            title = text.split("：", 1)[0].split(":", 1)[0][-6:] or title
        subtitle = _fallback_overlay_subtitle(text)
        if vi_title:
            title, subtitle = vi_title, vi_subtitle or ""
        img = f"{style_prefix}，{bible}，画面表现：{text[:80]}，竖屏构图，顶部留白，画面无文字"
        beats = [
            segplan.SegmentBeat(duration=segplan.estimate_visual_duration(img), kind="visual", text=img),
            segplan.SegmentBeat(
                duration=segplan.estimate_narration_duration(text),
                kind="narration",
                text=text[:120],
            ),
        ]
        script = segplan.build_segment_script(beats, bgm_mood=bgm_lock, max_total=min(duration_max, 30))
        dur = float(segplan.resolve_api_duration(script, fallback=mid, lo=duration_min, hi=duration_max))
        plans.append(
            ShotPlan(
                shot=i,
                duration=dur,
                text=text[:120],
                overlay_title=_normalize_overlay_title(title, text, i),
                overlay_subtitle=_normalize_overlay_subtitle(subtitle, text),
                img_prompt=img,
                video_prompt=script,
                segment_script=script,
                camera="缓慢推近" if i % 2 else "轻拉远",
                bgm=bgm_lock,
            )
        )
    return StoryboardResult(shots=plans, character_bible=bible, bgm_lock=bgm_lock)


def parse_storyboard(
    content: str,
    style_prefix: str,
    duration_min: int,
    duration_max: int,
    max_shot_duration: int,
) -> StoryboardResult:
    raw = (content or "").strip()
    if not raw:
        raise RuntimeError("分镜 JSON 为空，无法解析")
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"分镜 JSON 解析失败：{exc}") from exc
    character_bible = ""
    bgm_lock = ""
    items = data
    if isinstance(data, dict):
        character_bible = str(
            data.get("character_bible") or data.get("characters") or data.get("cast") or ""
        ).strip()
        bgm_lock = str(data.get("bgm_lock") or data.get("bgm") or "").strip()
        items = data.get("shots") or data.get("storyboard") or data.get("scenes") or []
    if not isinstance(items, list):
        raise RuntimeError("LLM storyboard JSON 格式无效：需要 shots 数组")
    if not items:
        raise RuntimeError("分镜模型未返回任何镜头（shots 为空）")
    hi = min(duration_max, max_shot_duration)
    plans: list[ShotPlan] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("audio_text") or f"镜头{i}")
        title = str(item.get("title") or item.get("overlay_title") or "").strip()
        subtitle = str(item.get("subtitle") or item.get("overlay_subtitle") or "").strip()
        title = _normalize_overlay_title(title, text, i)
        subtitle = _normalize_overlay_subtitle(subtitle, text)
        img = str(item.get("img_prompt") or f"{text}")
        camera = str(item.get("camera", "缓慢横移"))
        bgm = str(item.get("bgm") or item.get("bgm_mood") or bgm_lock or "平稳")
        if not bgm_lock:
            bgm_lock = bgm
        beats = segplan.parse_beats_from_llm_shot(item, narration_fallback=text)
        script = segplan.build_segment_script(beats, bgm_mood=bgm_lock or bgm, max_total=hi)
        narr = segplan.narration_from_script(script) or text
        visual = segplan.first_visual_prompt(script) or img
        dur = float(
            segplan.resolve_api_duration(
                script,
                fallback=float(item.get("duration", (duration_min + duration_max) / 2)),
                lo=duration_min,
                hi=hi,
            )
        )
        plans.append(
            ShotPlan(
                shot=int(item.get("shot", i)),
                duration=dur,
                text=narr,
                overlay_title=title,
                overlay_subtitle=subtitle,
                img_prompt=visual,
                video_prompt=script,
                segment_script=script,
                camera=camera,
                bgm=bgm_lock or bgm,
            )
        )
    if not bgm_lock and plans:
        bgm_lock = plans[0].bgm
    return StoryboardResult(
        shots=plans,
        character_bible=character_bible,
        bgm_lock=bgm_lock or segplan.infer_bgm_mood(style_prefix),
    )


async def expand_content(topic: str, mode: str = "theme", *, mock: bool) -> dict[str, str]:
    """Expand a short topic into title + theme brief or full narration script."""
    topic = (topic or "").strip() or "人工智能如何改变日常生活"
    mode = "script" if mode == "script" else "theme"
    if mock:
        return mock_expand_content(topic, mode)

    if mode == "script":
        system = (
            "你是科普短视频文案作者。根据用户主题写一篇可直接用于旁白的完整口播文案。"
            "只输出严格 JSON：{\"title\":\"作品名\",\"content\":\"完整文案\"}。"
            "title：8-18 字，吸引人、无标点堆砌。"
            "content：300-700 字，口语化，分 4-8 个自然段，有开场钩子、知识点、收尾；"
            "不要 markdown、不要分镜编号、不要标题行。"
        )
    else:
        system = (
            "你是科普短视频选题策划。把用户输入扩写成一句清晰具体的创作主题。"
            "只输出严格 JSON：{\"title\":\"作品名\",\"content\":\"主题句\"}。"
            "title：8-18 字。"
            "content：一句话主题，40-90 字，写清受众与要讲清的核心知识点；不要换行。"
        )
    content = await chat_completions(
        system,
        f"主题/素材：{topic}",
        function_id="kepu.script",
        temperature=0.6,
        max_tokens=4096,
        timeout=90.0,
    )
    return parse_expand_content(content or "{}", topic, mode)


def mock_expand_content(topic: str, mode: str) -> dict[str, str]:
    # 非中文主题给越南语占位（mock 与 LLM 解析失败兜底共用）
    if not is_cjk_text(topic):
        return _vi_mock_expand_content(topic, mode)
    short = topic[:18].rstrip("？?。.!！") or "科普短片"
    title = short if len(short) >= 4 else f"{short}的科普"
    if mode == "script":
        content = (
            f"你有没有想过：{topic.rstrip('？?')}？\n\n"
            f"今天我们用三分钟，把这件事讲清楚。"
            f"先从生活里最常见的现象说起，再拆开背后的原理，最后给你一个好记的结论。\n\n"
            f"很多人第一反应会想当然，但真正关键在于因果链条，而不是表象。"
            f"弄懂这一点，你就能解释身边更多类似的问题。\n\n"
            f"记住：观察现象、追问机制、再用例子验证。"
            f"下一次再遇到{short}相关话题，你也能自信地讲给别人听。"
        )
    else:
        content = (
            f"{topic.rstrip('？?')}：面向普通观众，用生活例子讲清核心原理与常见误区。"
        )[:100]
    return {"title": title[:24], "content": content}


def parse_expand_content(raw: str, topic: str, mode: str) -> dict[str, str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return mock_expand_content(topic, mode)
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return mock_expand_content(topic, mode)
    title = str(data.get("title") or "").strip() or topic[:18]
    content = str(data.get("content") or "").strip()
    if not content:
        return mock_expand_content(topic, mode)
    if mode == "theme":
        content = content.replace("\n", " ").strip()[:100]
    else:
        content = content[:8000]
    return {"title": title[:24], "content": content}
