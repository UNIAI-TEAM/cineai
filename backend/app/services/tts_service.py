"""Giọng đọc: mock → model trong slot Giọng đọc (theo function) → edge-tts; thất bại thì raise, không ghi im lặng."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from app.config import Settings
from app.services import storage
from app.services.ffmpeg_compose import is_near_silent_audio
from app.services.function_router import resolve_function_candidates
from app.services.providers.base import TtsRequest
from app.services.providers.registry import get_adapter
from app.services.providers.volc_tts_adapter import is_volc_speaker, resolve_volc_speaker
from app.services.voices import edge_tts_voice_for_text

logger = logging.getLogger(__name__)


def _prefer_volc_for_speaker(routes: list, speaker: str) -> list:
    """Speaker kiểu Volc thì xếp các route volc_tts lên trước (giữ thứ tự tương đối), ngược lại giữ nguyên."""
    if not is_volc_speaker(speaker):
        return list(routes)
    volc = [r for r in routes if r.protocol == "volc_tts"]
    return volc + [r for r in routes if r.protocol != "volc_tts"]


class TtsService:
    """Cascade TTS cho khoa học và phim ngắn."""

    def __init__(self, settings: Settings, *, mock: bool) -> None:
        """Lưu cấu hình hiện hành và cờ chạy mock."""
        self.settings = settings
        self.mock = mock

    async def synthesize(
        self,
        text,
        voice,
        *,
        function_id="kepu.tts",
        project_id=None,
        shot_no=None,
        emotion_hint=None,
    ) -> str:
        """Sinh lời bình: mock trả file mock; thật thì thử từng model trong slot rồi mới edge-tts."""
        clean = (text or "").strip() or "这一幕。"
        # Alias giọng đọc (narrator_calm…) phải quy đổi trước khi gửi adapter hoặc edge-tts
        speaker = resolve_volc_speaker((voice or "").strip(), self.settings.volc_tts_speaker or "")
        if self.mock:
            digest = hashlib.md5(f"{speaker}:{clean}".encode()).hexdigest()[:8]
            dest = Path(__file__).resolve().parents[2] / "static" / "mock" / f"audio_{digest}.mp3"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or dest.stat().st_size < 1000:
                await self._tts_edge(clean, dest, voice_hint=speaker)
            return f"/static/mock/audio_{digest}.mp3"

        dest = storage.project_dir(project_id or 0) / f"shot_{(shot_no or 0):03d}_tts.mp3"
        req = TtsRequest(text=clean, voice=speaker, emotion_hint=emotion_hint)
        # Giọng clone S_* / giọng Volc do caller chỉ định: đưa provider volc_tts lên đầu để giữ đúng giọng nhân vật
        requested = resolve_volc_speaker((voice or "").strip(), "")
        for route in _prefer_volc_for_speaker(resolve_function_candidates(function_id), requested):
            adapter = get_adapter(route.protocol)
            try:
                audio = await adapter.tts(route, req)
            except Exception as exc:  # noqa: BLE001
                logger.warning("TTS %s/%s lỗi: %s", route.channel_id, route.upstream_model, exc)
                continue
            if self._persist_mp3(dest, audio):
                url = await self._accept_if_audible(dest, f"{route.channel_id}")
                if url:
                    return url
        try:
            await self._tts_edge(clean, dest, voice_hint=speaker)
            url = await self._accept_if_audible(dest, "edge-tts")
            if url:
                return url
        except Exception as exc:  # noqa: BLE001
            logger.warning("edge-tts failed: %s", exc)
        dest.unlink(missing_ok=True)
        raise RuntimeError("配音失败：语音服务暂不可用，请稍后重试")

    async def _accept_if_audible(self, dest: Path, label: str) -> str | None:
        """Từ chối file quá nhỏ hoặc gần im lặng; ngược lại publish và trả URL."""
        if not dest.exists() or dest.stat().st_size < 2000:
            return None
        if await asyncio.to_thread(is_near_silent_audio, dest):
            logger.warning("%s produced near-silence", label)
            dest.unlink(missing_ok=True)
            return None
        return storage.publish_local(dest)

    async def _tts_edge(self, text: str, dest: Path, voice_hint: str = "") -> None:
        """微软 edge-tts 兜底。国内连 api.msedgeservices.com 常超过默认 10s，拉长握手并重试。

        音色按 voice_hint（豆包 speaker）推性别；旁白非中文时换越南语 neural。
        """
        import edge_tts

        voice = edge_tts_voice_for_text(voice_hint, text)
        dest.parent.mkdir(parents=True, exist_ok=True)
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(
                    text,
                    voice,
                    connect_timeout=30,
                    receive_timeout=90,
                )
                await communicate.save(str(dest))
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("edge-tts attempt %s/3 failed: %s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(str(last_err) if last_err else "edge-tts failed")

    def _persist_mp3(self, dest: Path, audio: bytes) -> bool:
        """把 Omni WAV 转成配音 mp3；已是 MPEG 则直接落盘。转码失败返回 False。"""
        if len(audio) < 1000:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        if audio[:3] == b"ID3" or (audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0):
            dest.write_bytes(audio)
            return True
        import shutil
        import subprocess
        import tempfile

        # ffmpeg 可执行文件 / 临时 wav / 转码进程
        ffmpeg = shutil.which(self.settings.ffmpeg_path) or shutil.which("ffmpeg")
        if not ffmpeg:
            logger.warning("tts persist skipped: ffmpeg not found")
            return False
        with tempfile.TemporaryDirectory(prefix="pf_tts_") as tmp_dir:
            src = Path(tmp_dir) / "omni.wav"
            src.write_bytes(audio)
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-y",
                    "-i",
                    str(src),
                    "-q:a",
                    "4",
                    "-acodec",
                    "libmp3lame",
                    str(dest),
                ],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        if proc.returncode == 0 and dest.exists() and dest.stat().st_size >= 1000:
            return True
        logger.warning(
            "tts persist ffmpeg failed code=%s stderr=%s",
            proc.returncode,
            (proc.stderr or b"").decode("utf-8", errors="replace")[:300],
        )
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False
