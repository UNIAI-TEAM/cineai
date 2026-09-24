"""从剧本抽取资产时组装 params（对齐 manju seedAssetsFromScript）。"""

from __future__ import annotations

from typing import Any

from app.services.content_lang import is_zh
from app.services.text_lang import is_cjk_text

# DEFAULT_APPEARANCE_NAME 从剧本抽取角色时的默认形象名
DEFAULT_APPEARANCE_NAME = "基础形象"

# DEFAULT_IMAGE_GENERATION 默认生图参数（空 modelId 走后台已分配的默认模型）
DEFAULT_IMAGE_GENERATION = {
    "modelId": "",
    "aspectRatio": "3:4",
    "resolution": "3K",
}


# 组装道具/素材等命名图片资产 params（对齐 manju buildNamedImageParams）
def build_named_image_params(prompt: str, aspect_ratio: str, *, kind: str = "prop") -> dict[str, Any]:
    text = (prompt or "").strip()
    return {
        "visualPrompt": text,
        "visualImage": text,
        "kind": kind,
        "canvas": {
            "generation": {
                "prompt": text,
                "modelId": DEFAULT_IMAGE_GENERATION["modelId"],
                "aspectRatio": aspect_ratio,
                "resolution": DEFAULT_IMAGE_GENERATION["resolution"],
            },
            "seededFromScript": True,
        },
    }


# 生图提示词字段标签：中文项目用中文；越南语 / 英文项目用英文（生图模型对英文理解更好）
_ZH_LABELS = {"title": "身份：", "roleType": "定位：", "coreTags": "标签：", "personality": "性格："}
_EN_LABELS = {"title": "Identity: ", "roleType": "Role: ", "coreTags": "Tags: ", "personality": "Personality: "}


def use_zh_prompt_labels(lang: str | None, sample: str = "") -> bool:
    """是否用中文拼生图提示词：显式 lang 优先；未给时按内容是否含中文判断（空内容沿用中文）。"""
    if lang:
        return is_zh(lang)
    return not sample.strip() or is_cjk_text(sample)


# 按 manju buildCharacterParams 规则拼接角色生图 prompt
def manju_join_character_prompt(character: dict[str, Any], lang: str | None = None) -> str:
    visual = str(character.get("visualImage") or "").strip()
    title = str(character.get("title") or "").strip()
    role_type = str(character.get("roleType") or "").strip()
    core_tags = str(character.get("coreTags") or "").strip()
    personality = str(character.get("personality") or "").strip()
    zh = use_zh_prompt_labels(lang, " ".join([visual, title, role_type, core_tags, personality]))
    labels = _ZH_LABELS if zh else _EN_LABELS
    if not zh:
        # 越南语 / 英文项目：丢掉 stub 里的中文占位值（如「出场人物」「配角」）
        title, role_type, core_tags, personality = (
            "" if is_cjk_text(v) else v for v in (title, role_type, core_tags, personality)
        )
    parts = [
        visual,
        f"{labels['title']}{title}" if title else "",
        f"{labels['roleType']}{role_type}" if role_type else "",
        f"{labels['coreTags']}{core_tags}" if core_tags else "",
        f"{labels['personality']}{personality}" if personality else "",
    ]
    return ("。" if zh else ". ").join(part for part in parts if part)


# 从摘要人物 dict 拼角色生图提示词正文（refresh/fallback 时可叙事化扩展）
def compose_character_visual_text(character: dict[str, Any], lang: str | None = None) -> str:
    visual = str(character.get("visualImage") or character.get("visualPrompt") or "").strip()
    if len(visual) >= 120:
        joined_full = manju_join_character_prompt(character, lang)
        return joined_full if joined_full != visual else visual

    segments: list[str] = []
    joined = manju_join_character_prompt(character, lang)
    if joined:
        segments.append(joined)
    identity = str(character.get("identityBackground") or "").strip()
    growth = str(character.get("growthExperience") or "").strip()
    relationships = str(character.get("relationships") or "").strip()
    if identity and identity not in joined:
        segments.append(identity)
    if growth and growth not in joined:
        segments.append(growth)
    if relationships and relationships not in joined:
        segments.append(relationships)
    sep = "。" if use_zh_prompt_labels(lang, joined) else ". "
    return sep.join(s for s in segments if s)


# 组装角色资产 params（形象名 + 生图提示词，对齐 manju buildCharacterParams）
def build_character_params(character: dict[str, Any], lang: str | None = None) -> dict[str, Any]:
    # 有 appearance（按字段的外形）时由字段拼 visualImage 正文；否则沿用旧逻辑
    from app.services.drama.appearance_prompt import (
        appearance_is_empty,
        compose_appearance_prompt,
        normalize_appearance,
    )

    appearance = normalize_appearance(character.get("appearance"))
    has_appearance = not appearance_is_empty(appearance)
    if has_appearance:
        character = {**character, "visualImage": compose_appearance_prompt(appearance, lang)}
    prompt = manju_join_character_prompt(character, lang)
    visual = prompt if has_appearance else (str(character.get("visualImage") or "").strip() or prompt)
    params: dict[str, Any] = {
        "visualImage": visual,
        "visualPrompt": prompt,
        "roleType": character.get("roleType"),
        "title": character.get("title"),
        "coreTags": character.get("coreTags"),
        "identityBackground": character.get("identityBackground"),
        "growthExperience": character.get("growthExperience"),
        "personality": character.get("personality"),
        "relationships": character.get("relationships"),
        "growthArc": character.get("growthArc"),
        "canvas": {
            "appearanceName": DEFAULT_APPEARANCE_NAME,
            "generation": {
                "prompt": prompt,
                **DEFAULT_IMAGE_GENERATION,
            },
            "seededFromScript": True,
        },
    }
    if has_appearance:
        params["appearance"] = appearance
        params["promptManual"] = False
    return params


# 组装场景资产 params（对齐 manju buildSceneParams）
def build_scene_params(scene_name: str, story_type: str = "", lang: str | None = None) -> dict[str, Any]:
    _ = story_type  # manju 场景 seed 未使用 storyType，保留参数供 refresh 扩展
    name = scene_name.strip()
    if use_zh_prompt_labels(lang, name):
        prompt = f"场景：{name}，影视级写实场景，构图清晰，适合短剧拍摄"
    else:
        prompt = (
            f"Scene: {name}, cinematic photorealistic environment, clear composition, "
            "suitable for short drama filming"
        )
    return build_named_image_params(prompt, "16:9", kind="scene")
