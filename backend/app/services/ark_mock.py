"""ARK_MOCK / 解析兜底用的越南语占位内容。

规则：用户输入含中日文字时沿用 ark.py 里原有的中文 mock；否则（越南语 / 英文 / 空）走这里的越南语文案。
只替换用户可见的文字（旁白、叠字标题/副标题、扩写结果、mock 图说明）；
发给模型的提示词骨架（img_prompt、角色设定、运镜、BGM）仍由调用方按中文拼接，不在此处翻译。
"""

from __future__ import annotations

import re

from app.services.text_lang import cut_words, is_cjk_text


def _topic_label(topic: str) -> str:
    """主题的短称，用于句中引用。"""
    return cut_words((topic or "").strip().rstrip("?？.!！。"), 60)


def mock_storyboard_items(
    source_text: str,
    source_type: str,
    shot_lo: int,
    shot_hi: int,
) -> list[tuple[str, str, str]]:
    """越南语 mock 分镜：返回 [(叠字标题, 叠字副标题, 旁白)]，数量落在 [shot_lo, shot_hi]。

    注意：标题不要与旁白开头相同，否则 _normalize_overlay_title 会判为截断并回落成中文「场景N」。
    """
    sentences = [s.strip() for s in re.split(r"[\n.!?。！？]+", source_text or "") if s.strip()]
    items: list[tuple[str, str, str]]
    if source_type == "theme" and len(sentences) <= 1:
        topic = _topic_label(source_text)
        intro = f"chủ đề “{topic}”" if topic else "một chủ đề thú vị"
        items = [
            (
                "Mở đầu",
                "Vì sao chủ đề này đáng quan tâm",
                f"Hôm nay cùng tìm hiểu {intro}. Chỉ mất vài phút thôi.",
            ),
            (
                "Hiểu cho đúng",
                "Khái niệm cốt lõi",
                "Trước hết, hãy nắm rõ khái niệm cốt lõi của chủ đề này.",
            ),
            (
                "Ví dụ thực tế",
                "Một tình huống quen thuộc",
                "Lấy một ví dụ ngay trong đời sống hằng ngày để thấy rõ hơn.",
            ),
            (
                "Hiểu lầm thường gặp",
                "Điều nhiều người vẫn nghĩ sai",
                "Nhiều người hay hiểu sai điểm này, thực ra nguyên nhân nằm ở chỗ khác.",
            ),
            (
                "Điều cần nhớ",
                "Ý chính trong một câu",
                "Chỉ cần nhớ ý chính này là bạn đã có thể giải thích cho người khác.",
            ),
        ]
    else:
        items = [
            (f"Phần {i}", cut_words(s, 48), cut_words(s, 120))
            for i, s in enumerate(sentences, start=1)
        ]

    filler = (
        "Chuyển cảnh",
        "Hình ảnh minh hoạ thêm",
        "Thêm vài hình ảnh minh hoạ để câu chuyện liền mạch hơn.",
    )
    closing = (
        "Kết thúc",
        "Cảm ơn bạn đã xem",
        "Cảm ơn bạn đã xem, hẹn gặp lại ở video sau.",
    )
    # 内容太少时补过渡镜，并以收尾镜结束（过渡镜始终排在收尾镜之前）
    needs_closing = len(items) < max(3, shot_lo)
    reserve = 1 if needs_closing else 0
    if needs_closing:
        items = items + [filler]
    items = items[: max(shot_hi - reserve, 1)]
    while len(items) < shot_lo - reserve:
        items.append(filler)
    if needs_closing:
        items.append(closing)
    return items


def mock_expand_content(topic: str, mode: str) -> dict[str, str]:
    """越南语 mock 扩写：mode=script 返回完整口播稿，否则返回一句主题。"""
    label = _topic_label(topic) or "kiến thức quanh ta"
    title = cut_words(label, 48, ellipsis=False)
    if len(title) < 4:
        title = f"Hiểu nhanh về {title}"
    if mode == "script":
        content = (
            f"Bạn có bao giờ thắc mắc: {label}?\n\n"
            "Hôm nay mình dành ba phút để nói cho rõ chuyện này. "
            "Bắt đầu từ những điều quen thuộc hằng ngày, sau đó đi vào nguyên lý phía sau, "
            "cuối cùng là một kết luận dễ nhớ.\n\n"
            "Nhiều người thường nghĩ theo cảm tính, nhưng điều quan trọng là quan hệ nguyên nhân – kết quả, "
            "chứ không phải những gì nhìn thấy bên ngoài. "
            "Hiểu được điều này, bạn sẽ giải thích được nhiều hiện tượng tương tự quanh mình.\n\n"
            "Hãy nhớ: quan sát hiện tượng, tìm hiểu cơ chế, rồi kiểm chứng bằng ví dụ. "
            f"Lần sau gặp lại chủ đề “{label}”, bạn hoàn toàn có thể tự tin giải thích cho người khác."
        )
    else:
        # 与正式扩写一致，主题句不超过 100 字符
        content = cut_words(f"{label}: giải thích dễ hiểu bằng ví dụ đời thường, kèm những hiểu lầm hay gặp.", 100)
    return {"title": title, "content": content}


def mock_image_caption(prompt: str) -> tuple[str, str]:
    """mock 图上的两行说明：返回 (大标题, 画面描述)。

    kepu mock 的 img_prompt 形如「风格，角色设定，画面表现：<旁白>，竖屏构图…」，
    越南语场景只取「画面表现」段，避免把中文提示词骨架印在图上。
    """
    raw = (prompt or "").strip()
    scene = raw.split("画面表现：", 1)[-1].split("，竖屏", 1)[0].strip()
    if is_cjk_text(scene):
        label = (raw[:42] + "…") if len(raw) > 42 else raw
        return "Mock Storyboard", label
    return "Ảnh mẫu (chế độ mock)", cut_words(scene or raw, 60)
