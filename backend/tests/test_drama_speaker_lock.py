"""Khóa giọng người dùng đã chọn: không bị đổi theo giới tính mô tả; sai ngôn ngữ thì rơi về luồng cũ."""

import logging

from app.services.drama import fragment_dub, voice_synthesis
from app.services.drama.voice_synthesis import lockable_speaker, resolve_bound_speaker


def _resolve(speaker, lang, locked, prompt="giọng nữ trẻ"):
    return resolve_bound_speaker(
        speaker, lang, locked=locked, voice_prompt=prompt, character_name="Lan", key_asset_id=5
    )


def test_locked_keeps_speaker_even_if_gender_mismatch():
    assert _resolve("vi_male_wumg_uranus_bigtts", "vi", True) == "vi_male_wumg_uranus_bigtts"


def test_unlocked_gender_mismatch_is_reinferred():
    assert _resolve("vi_male_wumg_uranus_bigtts", "vi", False) != "vi_male_wumg_uranus_bigtts"


def test_locked_wrong_language_falls_back_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        out = _resolve("en_male_bruce_uranus_bigtts", "vi", True, prompt="giọng nam trầm")
    assert out.startswith("vi_")
    assert "en_male_bruce_uranus_bigtts" in caplog.text


def test_locked_empty_speaker_falls_back():
    assert _resolve("", "vi", True).startswith("vi_")


def test_lockable_speaker():
    assert lockable_speaker("en_male_bruce_uranus_bigtts")
    assert lockable_speaker("S_abc123")
    assert not lockable_speaker("made_up_voice")
    assert not lockable_speaker("")


class _A:
    def __init__(self, id, type, name, params):
        self.id, self.type, self.name, self.params = id, type, name, params


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Db:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _Result(self._rows)


class _Project:
    id = 1


async def test_load_dub_voices_honours_lock(monkeypatch):
    voice = _A(20, "voice", "Lan · Wumg", {"speaker": "vi_male_wumg_uranus_bigtts", "speakerLocked": True,
                                            "voicePrompt": "giọng nữ trẻ"})
    char = _A(10, "character", "Lan", {"voiceAudio": {"sourceAssetId": 20, "url": "/static/x.mp3"}})
    monkeypatch.setattr(fragment_dub, "resolve_character_prompt_name", lambda d: d["name"], raising=False)
    characters, _narrator = await fragment_dub.load_dub_voices(_Db([char, voice]), _Project(), "vi")
    assert characters[0].speaker == "vi_male_wumg_uranus_bigtts"


async def test_load_dub_voices_unlocked_reinfers(monkeypatch):
    voice = _A(20, "voice", "Lan · Wumg", {"speaker": "vi_male_wumg_uranus_bigtts", "voicePrompt": "giọng nữ trẻ"})
    char = _A(10, "character", "Lan", {"voiceAudio": {"sourceAssetId": 20, "url": "/static/x.mp3"}})
    monkeypatch.setattr(fragment_dub, "resolve_character_prompt_name", lambda d: d["name"], raising=False)
    characters, _ = await fragment_dub.load_dub_voices(_Db([char, voice]), _Project(), "vi")
    assert characters[0].speaker != "vi_male_wumg_uranus_bigtts"
