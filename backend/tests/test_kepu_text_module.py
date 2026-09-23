"""kepu_text tách khỏi ark.py: parser/mock chạy độc lập, ark.py vẫn delegate."""
import pytest

from app.services import kepu_text


def test_parse_expand_content_reads_json():
    out = kepu_text.parse_expand_content('{"title": "Tiêu đề", "content": "Nội dung"}', "chủ đề", "theme")
    assert out["title"] == "Tiêu đề"
    assert out["content"] == "Nội dung"


def test_mock_expand_content_returns_title_and_content():
    out = kepu_text.mock_expand_content("năng lượng mặt trời", "script")
    assert out["title"]
    assert out["content"]


async def test_expand_content_mock_shortcut():
    out = await kepu_text.expand_content("AI trong y tế", "theme", mock=True)
    assert set(out) >= {"title", "content"}


async def test_ark_gateway_delegates_expand_content(monkeypatch):
    from app.services.ark import ArkGateway

    called = {}

    async def fake(topic, mode="theme", *, mock, lang=None):
        called["args"] = (topic, mode, mock)
        called["lang"] = lang
        return {"title": "t", "content": "c"}

    monkeypatch.setattr(kepu_text, "expand_content", fake)
    monkeypatch.setattr(ArkGateway, "mock", property(lambda self: True))
    out = await ArkGateway().expand_content("chủ đề", "theme")
    assert out == {"title": "t", "content": "c"}
    assert called["args"] == ("chủ đề", "theme", True)


async def test_ark_gateway_chat_storyboard_accepts_positional_args(monkeypatch):
    """Old call sites pass the first 7 args positionally; delegate must forward them intact."""
    from app.services.ark import ArkGateway

    monkeypatch.setattr(ArkGateway, "mock", property(lambda self: True))
    result = await ArkGateway().chat_storyboard(
        "Vì sao bầu trời có màu xanh, ánh sáng tán xạ ra sao",
        "theme",
        "phong cách hoạt hình",
        "",
        5,
        10,
        8,
        pipeline_mode="full",
    )
    assert len(result.shots) >= 1
