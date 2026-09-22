"""越南语内容的兜底文案：叠字标题/副标题、edge-tts 音色、ARK_MOCK 占位内容。"""

from app.services import kepu_text
from app.services.ark_mock import mock_expand_content, mock_storyboard_items
from app.services.text_lang import cut_words, is_cjk_text
from app.services.voices import edge_tts_voice_for_text


def test_is_cjk_text():
    assert is_cjk_text("天空为什么是蓝色")
    assert not is_cjk_text("Vì sao bầu trời có màu xanh")
    assert not is_cjk_text("")


def test_cut_words_keeps_whole_words():
    assert cut_words("Nguyễn Văn A đang học lập trình Python", 20) == "Nguyễn Văn A đang…"
    assert cut_words("ngắn", 20) == "ngắn"


def test_overlay_fallbacks_keep_spaces_for_vietnamese():
    text = "Vi nhựa đã có mặt trong nước uống, muối ăn và cả hải sản"
    assert kepu_text._normalize_overlay_subtitle("", text) == "Vi nhựa đã có mặt trong nước uống"
    assert kepu_text._normalize_overlay_title("", text * 2, 3) == "Cảnh 3"


def test_overlay_fallbacks_unchanged_for_chinese():
    text = "为什么天空是蓝色的，这和光的散射有关"
    assert kepu_text._normalize_overlay_title("", text, 3) == "场景3"
    assert kepu_text._normalize_overlay_subtitle("", text) == "为什么天空是蓝色的"


def test_edge_voice_follows_text_language():
    assert edge_tts_voice_for_text("zh_male_x", "Xin chào") == "vi-VN-NamMinhNeural"
    assert edge_tts_voice_for_text("zh_female_x", "Xin chào") == "vi-VN-HoaiMyNeural"
    assert edge_tts_voice_for_text("zh_male_x", "你好") == "zh-CN-YunxiNeural"


def test_mock_storyboard_vietnamese_titles_survive_normalize():
    items = mock_storyboard_items("Vì sao bầu trời có màu xanh", "theme", 4, 8)
    assert 4 <= len(items) <= 8
    for i, (title, _sub, text) in enumerate(items, start=1):
        assert kepu_text._normalize_overlay_title(title, text, i) == title


def test_mock_storyboard_padding_ends_with_closing():
    items = mock_storyboard_items("Nhựa đi đâu? Phần lớn trôi ra biển", "script", 6, 8)
    assert len(items) == 6
    assert items[-1][0] == "Kết thúc"


def test_mock_expand_content_vietnamese():
    theme = mock_expand_content("Vì sao bầu trời có màu xanh", "theme")
    assert theme["title"] == "Vì sao bầu trời có màu xanh"
    assert len(theme["content"]) <= 100
    script = mock_expand_content("Vì sao bầu trời có màu xanh", "script")
    assert "“Vì sao bầu trời có màu xanh”" in script["content"]
