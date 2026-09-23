"""Selectable TTS voice presets (豆包 openspeech + template aliases)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.text_lang import is_cjk_text

# id used in API / project.voice_id; speaker is openspeech speaker id
# label 为中文主值；label_i18n 提供 zh / en / vi 界面展示名，前端按语言取值，缺失回落 label
# languages：该音色能正确朗读的内容语言（zh|en|vi）；官方说明用不支持的语言合成可能失败或读错
VOICE_PRESETS: list[dict[str, Any]] = [
    {
        "id": "zh_female_cancan_uranus_bigtts",
        "label": "灿灿 · 女声旁白",
        "label_i18n": {"zh": "灿灿 · 女声旁白", "en": "Cancan · Female narration", "vi": "Cancan · giọng nữ đọc lời dẫn"},
        "languages": ["zh"],
        "gender": "female",
        "speaker": "zh_female_cancan_uranus_bigtts",
    },
    {
        "id": "zh_female_tianmeixiaoyuan_uranus_bigtts",
        "label": "甜美女声 · 故事",
        "label_i18n": {"zh": "甜美女声 · 故事", "en": "Sweet female · Story", "vi": "Giọng nữ ngọt ngào · kể chuyện"},
        "languages": ["zh"],
        "gender": "female",
        "speaker": "zh_female_tianmeixiaoyuan_uranus_bigtts",
    },
    {
        "id": "zh_female_shuangkuaisisi_uranus_bigtts",
        "label": "爽快女声 · 都市",
        "label_i18n": {"zh": "爽快女声 · 都市", "en": "Crisp female · Urban", "vi": "Giọng nữ nhanh gọn, thẳng thắn · chuyện đô thị"},
        "languages": ["zh"],
        "gender": "female",
        "speaker": "zh_female_shuangkuaisisi_uranus_bigtts",
    },
    {
        "id": "zh_female_vv_uranus_bigtts",
        "label": "Vivi · 国风女声",
        "label_i18n": {"zh": "Vivi · 国风女声", "en": "Vivi · Classical female", "vi": "Vivi · giọng nữ cổ phong"},
        "languages": ["zh"],
        "gender": "female",
        "speaker": "zh_female_vv_uranus_bigtts",
    },
    {
        "id": "zh_female_xiaohe_uranus_bigtts",
        "label": "小何 · 通用女声",
        "label_i18n": {"zh": "小何 · 通用女声", "en": "Xiaohe · General female", "vi": "Xiaohe · giọng nữ đa năng"},
        "languages": ["zh"],
        "gender": "female",
        "speaker": "zh_female_xiaohe_uranus_bigtts",
    },
    {
        "id": "zh_male_shaonianzixin_uranus_bigtts",
        "label": "少年梓辛 · 男声",
        "label_i18n": {"zh": "少年梓辛 · 男声", "en": "Zixin · Youthful male", "vi": "Zixin · giọng nam thiếu niên"},
        "languages": ["zh"],
        "gender": "male",
        "speaker": "zh_male_shaonianzixin_uranus_bigtts",
    },
    {
        "id": "zh_male_m191_uranus_bigtts",
        "label": "云舟 · 稳重男声",
        "label_i18n": {"zh": "云舟 · 稳重男声", "en": "Yunzhou · Steady male", "vi": "Yunzhou · giọng nam điềm đạm"},
        "languages": ["zh"],
        "gender": "male",
        "speaker": "zh_male_m191_uranus_bigtts",
    },
    {
        "id": "zh_male_taocheng_uranus_bigtts",
        "label": "小天 · 年轻男声",
        "label_i18n": {"zh": "小天 · 年轻男声", "en": "Xiaotian · Young male", "vi": "Xiaotian · giọng nam trẻ trung"},
        "languages": ["zh"],
        "gender": "male",
        "speaker": "zh_male_taocheng_uranus_bigtts",
    },
    {
        "id": "zh_male_ruyayichen_uranus_bigtts",
        "label": "儒雅逸辰 · 男声",
        "label_i18n": {"zh": "儒雅逸辰 · 男声", "en": "Yichen · Refined male", "vi": "Yichen · giọng nam nho nhã"},
        "languages": ["zh"],
        "gender": "male",
        "speaker": "zh_male_ruyayichen_uranus_bigtts",
    },
    {
        "id": "zh_male_baqiqingshu_uranus_bigtts",
        "label": "霸气青叔 · 男声",
        "label_i18n": {"zh": "霸气青叔 · 男声", "en": "Qingshu · Bold male", "vi": "Qingshu · giọng nam trung niên uy lực"},
        "languages": ["zh"],
        "gender": "male",
        "speaker": "zh_male_baqiqingshu_uranus_bigtts",
    },
    # --- 越南语 / 英语：BytePlus Seed Speech TTS 2.0 官方音色（*_uranus_bigtts，见 docs/PROVIDERS.md 来源）---
    # 每种语言排在最前的音色即该语言默认音色（voice_lang.default_voice_for_lang 与前端同一规则）
    *[
        {
            "id": speaker,
            "label": zh,
            "label_i18n": {"zh": zh, "en": en, "vi": vi},
            "languages": [lang],
            "gender": gender,
            "speaker": speaker,
        }
        for speaker, lang, gender, zh, en, vi in (
            ("vi_female_ruan_uranus_bigtts", "vi", "female",
             "Ruan · 越南语沉稳女声", "Ruan · Steady, poised female", "Ruan · giọng nữ điềm đạm, rõ ràng"),
            ("vi_male_wumg_uranus_bigtts", "vi", "male",
             "Wumg · 越南语稳重男声", "Wumg · Patient, measured male", "Wumg · giọng nam trẻ, từ tốn"),
            ("vi_female_ling_uranus_bigtts", "vi", "female",
             "Ling · 越南语温柔女声", "Ling · Gentle, kind female", "Ling · giọng nữ dịu dàng"),
            ("vi_female_linh_uranus_bigtts", "vi", "female",
             "Linh · 越南语爽利女声", "Linh · Crisp, energetic female", "Linh · giọng nữ trẻ, dứt khoát"),
            ("vi_female_wu_uranus_bigtts", "vi", "female",
             "Wu · 越南语开朗女声", "Wu · Outgoing, level-headed female", "Wu · giọng nữ cởi mở, mạch lạc"),
            ("vi_female_hong_uranus_bigtts", "vi", "female",
             "Hong · 越南语直爽女声", "Hong · Down-to-earth, frank female", "Hong · giọng nữ mộc mạc, thẳng thắn"),
            ("vi_female_partner_uranus_bigtts", "vi", "female",
             "Partner · 越南语饱满情绪女声", "Partner · Youthful, emotive female", "Partner · giọng nữ trẻ, giàu cảm xúc"),
            ("en_female_hayley_uranus_bigtts", "en", "female",
             "Hayley · 英语女声 · 故事", "Hayley · Lively female storyteller", "Hayley · giọng nữ kể chuyện sinh động"),
            ("en_male_tim_uranus_bigtts", "en", "male",
             "Tim · 英语清晰男声", "Tim · Clear, friendly male", "Tim · giọng nam rõ ràng, thân thiện"),
            ("en_female_skye_uranus_bigtts", "en", "female",
             "Skye · 英语真诚女声", "Skye · Clear, sincere female", "Skye · giọng nữ trong trẻo, chân thành"),
            ("en_female_jenny_uranus_bigtts", "en", "female",
             "Jenny · 英语温暖女声", "Jenny · Warm, cheerful female", "Jenny · giọng nữ ấm áp, vui tươi"),
            ("en_male_kevin_uranus_bigtts", "en", "male",
             "Kevin · 英语年轻男声", "Kevin · Young, articulate male", "Kevin · giọng nam trẻ, mạch lạc"),
            ("en_male_marcus_uranus_bigtts", "en", "male",
             "Marcus · 英语醇厚男声 · 故事", "Marcus · Deep, mellow storyteller", "Marcus · giọng nam trầm ấm, kể chuyện"),
        )
    ],
]

# 漫剧角色音色：按关键词为不同角色匹配不同 speaker（避免全员同一声线）
DRAMA_SPEAKER_RULES: list[dict[str, Any]] = [
    {
        "speaker": "zh_male_baqiqingshu_uranus_bigtts",
        "gender": "male",
        "keywords": (
            "老", "翁", "族老", "长者", "首领", "青叔", "大叔", "威严", "苍", "应龙",
            "爷爷", "祖父", "暮年", "苍老",
        ),
    },
    {
        "speaker": "zh_male_m191_uranus_bigtts",
        "gender": "male",
        "keywords": (
            "领袖", "帝王", "君主", "大王", "治水", "禹", "庄重", "浑厚", "史诗", "统帅",
            "低沉", "恢弘", "成年男", "管风琴", "悲悯", "厚重",
        ),
    },
    {
        "speaker": "zh_male_ruyayichen_uranus_bigtts",
        "gender": "male",
        "keywords": (
            "儒雅", "书生", "谋士", "伯益", "文士", "温和", "清朗", "参谋",
            "克制", "颗粒", "偏冷",
        ),
    },
    {
        "speaker": "zh_male_shaonianzixin_uranus_bigtts",
        "gender": "male",
        "keywords": ("少年", "少年音", "清亮", "梓辛", "稚", "青春期", "青壮"),
    },
    {
        "speaker": "zh_male_taocheng_uranus_bigtts",
        "gender": "male",
        "keywords": (
            "年轻", "青年", "小哥", "明快", "阳光", "清爽", "童声", "男孩", "儿童",
            "圆润", "憨厚", "小伙",
        ),
    },
    {
        "speaker": "zh_female_vv_uranus_bigtts",
        "gender": "female",
        "keywords": ("国风", "古风", "神话", "御姐", "女王", "仙", "神女"),
    },
    {
        "speaker": "zh_female_shuangkuaisisi_uranus_bigtts",
        "gender": "female",
        "keywords": ("爽快", "利落", "都市", "干练", "清脆"),
    },
    {
        "speaker": "zh_female_tianmeixiaoyuan_uranus_bigtts",
        "gender": "female",
        "keywords": ("温柔", "甜美", "柔和", "亲和", "少女", "姑娘"),
    },
    {
        "speaker": "zh_female_xiaohe_uranus_bigtts",
        "gender": "female",
        "keywords": ("通用", "百姓", "群众", "平民", "村妇", "妇人"),
    },
    {
        "speaker": "zh_female_cancan_uranus_bigtts",
        "gender": "female",
        "keywords": ("旁白", "解说", "叙述", "播报"),
    },
]

MALE_HINTS = (
    "男", "少年", "青年男", "老年男", "公子", "王爷", "少爷", "少年音", "大叔", "青壮",
    "将", "伯", "公", "爷爷", "男孩",
)
FEMALE_HINTS = ("女", "少女", "女声", "御姐", "小姐", "娘娘", "萝莉", "姑娘", "妇人", "村妇")
# 越南语 / 英文音色描述的性别词（整词匹配）
_LATIN_MALE_HINT_RE = re.compile(r"\b(giọng nam|nam giới|chàng trai|cậu bé|ông|male|man|boy)\b", re.IGNORECASE)
_LATIN_FEMALE_HINT_RE = re.compile(
    r"\b(giọng nữ|nữ giới|cô gái|bé gái|nữ|female|woman|girl|lady)\b", re.IGNORECASE
)

# edge-tts 确认可用的男声仅 Yunxi/Yunjian/Yunyang（Yunxia 实为女童，不给男角色）
EDGE_TTS_BY_SPEAKER: dict[str, str] = {
    "zh_male_shaonianzixin_uranus_bigtts": "zh-CN-YunxiNeural",
    "zh_male_taocheng_uranus_bigtts": "zh-CN-YunxiNeural",
    "zh_male_m191_uranus_bigtts": "zh-CN-YunjianNeural",
    "zh_male_baqiqingshu_uranus_bigtts": "zh-CN-YunyangNeural",
    "zh_male_ruyayichen_uranus_bigtts": "zh-CN-YunjianNeural",
    "zh_female_cancan_uranus_bigtts": "zh-CN-XiaoxiaoNeural",
    "zh_female_tianmeixiaoyuan_uranus_bigtts": "zh-CN-XiaoyiNeural",
    "zh_female_shuangkuaisisi_uranus_bigtts": "zh-CN-liaoning-XiaobeiNeural",
    "zh_female_vv_uranus_bigtts": "zh-CN-shaanxi-XiaoniNeural",
    "zh_female_xiaohe_uranus_bigtts": "zh-CN-XiaoxiaoNeural",
}

# Template audio_config.voice_preset aliases → speaker
VOICE_ALIASES: dict[str, str] = {
    "narrator_calm": "zh_female_cancan_uranus_bigtts",
    "warm_storyteller": "zh_female_tianmeixiaoyuan_uranus_bigtts",
    "teacher_clear": "zh_male_shaonianzixin_uranus_bigtts",
    "urban_editorial": "zh_female_shuangkuaisisi_uranus_bigtts",
    "retro_host": "zh_male_shaonianzixin_uranus_bigtts",
    "guqin_narrator": "zh_female_vv_uranus_bigtts",
}


def list_voices() -> list[dict[str, Any]]:
    return list(VOICE_PRESETS)


# 形如 vi_female_ruan_uranus_bigtts / en_male_tim_uranus_bigtts 的语种音色 id
_LANG_GENDER_SPEAKER_RE = re.compile(r"^[a-z]{2}_(female|male)_")


def infer_speaker_gender(speaker: str) -> str | None:
    """openspeech speaker id → female | male（勿用子串 male，zh_female_* 会误判）。"""
    s = (speaker or "").strip().lower()
    if not s:
        return None
    if s.startswith("zh_female_") or s.startswith("saturn_female"):
        return "female"
    if s.startswith("zh_male_") or s.startswith("saturn_male"):
        return "male"
    # 其它语种官方音色：vi_female_* / en_male_* …（语种前缀 + 性别段）
    m = _LANG_GENDER_SPEAKER_RE.match(s)
    if m:
        return m.group(1)
    return None


def edge_tts_voice_for_speaker(speaker: str) -> str:
    """edge-tts 兜底：按豆包 speaker 映射不同中文 neural，避免全员同一条 Yunxi。"""
    mapped = EDGE_TTS_BY_SPEAKER.get((speaker or "").strip())
    if mapped:
        return mapped
    g = infer_speaker_gender(speaker)
    if g == "male":
        return "zh-CN-YunxiNeural"
    if g == "female":
        return "zh-CN-XiaoxiaoNeural"
    hint = speaker or ""
    if "男" in hint and "女" not in hint:
        return "zh-CN-YunxiNeural"
    return "zh-CN-XiaoxiaoNeural"


# edge-tts 越南语 / 英语 neural（旁白非中文时使用；Azure 官方 neural 音色，见 docs/PROVIDERS.md）
EDGE_TTS_VI_FEMALE = "vi-VN-HoaiMyNeural"
EDGE_TTS_VI_MALE = "vi-VN-NamMinhNeural"
EDGE_TTS_EN_FEMALE = "en-US-JennyNeural"
EDGE_TTS_EN_MALE = "en-US-GuyNeural"
# 直接指定的 edge-tts 音色名（如 vi-VN-HoaiMyNeural），兜底时原样使用
_EDGE_VOICE_NAME_RE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}(?:-[a-z]+)?-[A-Za-z]+Neural$")


def is_edge_voice_name(voice: str) -> bool:
    """是否 edge-tts / Azure neural 音色名（xx-YY-NameNeural）。"""
    return bool(_EDGE_VOICE_NAME_RE.match((voice or "").strip()))


def edge_tts_voice_for_text(speaker: str, text: str, lang: str | None = None) -> str:
    """edge-tts 兜底音色：中文沿用 speaker→中文 neural；越南语 / 英语按性别换对应语种 neural。

    参数：speaker 豆包 speaker id（用于推断性别；本身是 edge 音色名时原样返回）；
         text 待合成文本；lang 内容语言 zh|vi|en（缺省按文本推断，拉丁文无越南语字母视为英语）
    返回：edge-tts voice 名称
    """
    if is_edge_voice_name(speaker):
        return speaker.strip()
    if lang is None:
        from app.services.content_lang import guess_text_lang

        lang = "zh" if is_cjk_text(text) else (guess_text_lang(text) or "vi")
    if lang == "zh":
        return edge_tts_voice_for_speaker(speaker)
    zh_voice = edge_tts_voice_for_speaker(speaker)
    male = infer_speaker_gender(speaker) == "male" or zh_voice.startswith("zh-CN-Yun")
    if lang == "en":
        return EDGE_TTS_EN_MALE if male else EDGE_TTS_EN_FEMALE
    return EDGE_TTS_VI_MALE if male else EDGE_TTS_VI_FEMALE


def resolve_speaker(voice_id: str | None, *, template_preset: str | None = None) -> str:
    """Map UI voice id / template alias to openspeech speaker."""
    raw = (voice_id or "").strip() or (template_preset or "").strip()
    if not raw:
        return "zh_female_cancan_uranus_bigtts"
    if raw in VOICE_ALIASES:
        return VOICE_ALIASES[raw]
    for preset in VOICE_PRESETS:
        if preset["id"] == raw or preset["speaker"] == raw:
            return str(preset["speaker"])
    # Pass-through custom speaker ids
    return raw


# 推断漫剧角色应使用的 TTS speaker（多声线 + 稳定哈希打散同分候选）
def infer_drama_speaker_from_prompt(
    voice_prompt: str,
    *,
    character_name: str = "",
    asset_id: int = 0,
) -> str:
    prompt = f"{character_name} {voice_prompt or ''}"
    male_score = sum(1 for k in MALE_HINTS if k in prompt) + len(_LATIN_MALE_HINT_RE.findall(prompt))
    female_score = sum(1 for k in FEMALE_HINTS if k in prompt) + len(
        _LATIN_FEMALE_HINT_RE.findall(prompt)
    )
    if male_score > female_score:
        gender = "male"
    elif female_score > male_score:
        gender = "female"
    else:
        gender = "male" if asset_id % 2 else "female"

    scored: list[tuple[int, str]] = []
    for rule in DRAMA_SPEAKER_RULES:
        if rule["gender"] != gender:
            continue
        score = sum(1 for kw in rule["keywords"] if kw in prompt)
        if score > 0:
            scored.append((score, str(rule["speaker"])))

    if not scored:
        pool = [str(r["speaker"]) for r in DRAMA_SPEAKER_RULES if r["gender"] == gender]
        if not pool:
            return "zh_female_cancan_uranus_bigtts"
        digest = hashlib.md5(f"{asset_id}:{character_name}:{voice_prompt}".encode()).hexdigest()
        return pool[int(digest[:8], 16) % len(pool)]

    max_score = max(s for s, _ in scored)
    top = [speaker for s, speaker in scored if s == max_score]
    if len(top) == 1:
        return top[0]
    digest = hashlib.md5(f"{asset_id}:{character_name}".encode()).hexdigest()
    return top[int(digest[:8], 16) % len(top)]


# 兼容旧调用
def infer_speaker_from_voice_prompt(voice_prompt: str, *, character_name: str = "", asset_id: int = 0) -> str:
    return infer_drama_speaker_from_prompt(voice_prompt, character_name=character_name, asset_id=asset_id)


PREVIEW_TEXT = "大家好，这是当前音色的试听效果，适合科普短视频旁白讲解。"
# 按界面语言的试听句（zh 沿用 PREVIEW_TEXT）
PREVIEW_TEXTS: dict[str, str] = {
    "zh": PREVIEW_TEXT,
    "vi": "Xin chào, đây là bản nghe thử của giọng đọc này, phù hợp để thuyết minh video ngắn.",
    "en": "Hello, this is a preview of this voice, suited for narrating short explainer videos.",
}
# 试听缓存文件名后缀：TTS 路由/edge 性别修复后递增，避免继续播放旧错误样例
PREVIEW_CACHE_TAG = "v3"


def preview_text_for_lang(lang: str | None) -> str:
    """试听句：按语言取，未知语言回落越南语。"""
    return PREVIEW_TEXTS.get(lang or "", PREVIEW_TEXTS["vi"])


async def ensure_voice_preview(voice_id: str, lang: str = "zh") -> str:
    """Generate (or reuse cached) short TTS sample; return public URL.

    lang：界面语言 zh|vi|en；音色不支持该语言时改用音色支持的语言试听（voice_lang.preview_lang_for_voice），
    缓存按 (voice, 实际试听语言) 区分；zh 沿用旧缓存文件名。
    """
    import hashlib
    from pathlib import Path

    from app.services import storage
    from app.services.ark import get_ark
    from app.services.voice_lang import preview_lang_for_voice

    speaker = resolve_speaker(voice_id)
    lang = preview_lang_for_voice(speaker, lang)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in speaker)[:80]
    cache_dir = Path(__file__).resolve().parents[2] / "static" / "voice_previews"
    cache_dir.mkdir(parents=True, exist_ok=True)
    lang_suffix = "" if lang == "zh" else f"_{lang}"
    dest = cache_dir / f"{safe}_{PREVIEW_CACHE_TAG}{lang_suffix}.mp3"
    if dest.exists() and dest.stat().st_size > 2000:
        return storage.publish_local(dest)

    ark = get_ark()
    shot_no = int(hashlib.md5(speaker.encode()).hexdigest()[:4], 16) % 800 + 100
    url = await ark.tts(
        preview_text_for_lang(lang), speaker, function_id="kepu.tts", project_id=0, shot_no=shot_no, lang=lang
    )
    src = storage.local_path_from_url(url)
    if src and src.exists():
        dest.write_bytes(src.read_bytes())
        return storage.publish_local(dest)
    if dest.exists() and dest.stat().st_size > 2000:
        return storage.publish_local(dest)
    return url
