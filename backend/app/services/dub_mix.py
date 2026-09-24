"""Lồng tiếng hậu kỳ: xếp mốc câu thoại TTS lên video và trộn với tiếng môi trường (hạ nhỏ khi có thoại)."""

from __future__ import annotations

import logging
import math
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.services.ffmpeg_compose import (
    _escape_drawtext,
    _escape_fontfile,
    _find_cjk_font,
    _probe_has_audio,
    _run,
    _strip_caption_punct,
    _which,
    probe_duration,
    probe_video_dimensions,
)

logger = logging.getLogger(__name__)

LEAD_IN = 0.2  # câu đầu không có mốc: bắt đầu sau 0.2s
GAP = 0.25  # khoảng nghỉ tối thiểu giữa hai câu
TAIL = 0.3  # đuôi im lặng sau câu cuối
MAX_TEMPO = 1.25  # tăng tốc tối đa (atempo giữ cao độ) trước khi phải lùi câu sau / kéo dài khung cuối
AMBIENT_VOLUME = 0.6  # tiếng môi trường Seedance trước khi sidechain

# Font phụ đề có đủ dấu tiếng Việt (ưu tiên), không có thì dùng font CJK chung của hệ thống
_CAPTION_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
)


@dataclass(frozen=True)
class DubPlan:
    """Kết quả xếp mốc: giây bắt đầu và hệ số tăng tốc của từng câu, độ dài video ra, số giây giữ khung cuối."""

    starts: list[float]
    tempos: list[float] = field(default_factory=list)
    out_duration: float = 0.0
    freeze_sec: float = 0.0

    @property
    def tempo(self) -> float:
        """Hệ số tăng tốc lớn nhất đã dùng (1.0 = không câu nào bị tăng tốc)."""
        return max(self.tempos, default=1.0)

    def speech_end(self, idx: int, duration: float) -> float:
        """Giây kết thúc câu idx sau khi tăng tốc."""
        return self.starts[idx] + duration / self.tempos[idx]


def _runs(starts: list[float | None]) -> list[list[int]]:
    """Gom câu thành từng cụm: mỗi cụm mở đầu bằng một câu có mốc kịch bản (hoặc câu đầu tiên)."""
    runs: list[list[int]] = []
    for idx, wanted in enumerate(starts):
        if not runs or wanted is not None:
            runs.append([idx])
        else:
            runs[-1].append(idx)
    return runs


def plan_dub_timeline(
    durations: list[float],
    starts: list[float | None],
    video_duration: float,
    ends: list[float | None] | None = None,
) -> DubPlan:
    """Xếp từng câu đúng mốc kịch bản; cụm câu dài hơn khung của nó thì tăng tốc riêng cụm đó (≤ MAX_TEMPO).

    Khung của một cụm kết thúc ở mốc cụm sau (trừ GAP), ở cuối khối thời gian của câu (ends) nếu có,
    hoặc cuối video (trừ TAIL) với cụm cuối. Vẫn thiếu chỗ thì câu sau lùi lại, cuối cùng giữ khung hình
    cuối cho đủ lời — không bao giờ cắt lời thoại.
    """
    ends = list(ends) if ends is not None else [None] * len(durations)
    runs = _runs(starts)
    placed = [0.0] * len(durations)
    tempos = [1.0] * len(durations)
    prev_end: float | None = None
    for r_idx, run in enumerate(runs):
        floor = prev_end + GAP if prev_end is not None else 0.0
        wanted = starts[run[0]]
        begin = max(wanted if wanted is not None else (floor if prev_end is not None else LEAD_IN), floor)
        limit = video_duration - TAIL
        if r_idx + 1 < len(runs):
            limit = starts[runs[r_idx + 1][0]] - GAP  # type: ignore[operator]
        if ends[run[-1]] is not None:
            limit = min(limit, float(ends[run[-1]]))  # type: ignore[arg-type]
        speech = sum(durations[i] for i in run)
        avail = limit - begin - GAP * (len(run) - 1)
        tempo = 1.0
        if speech > avail:
            tempo = min(MAX_TEMPO, math.ceil(speech / max(avail, 1e-3) * 1000) / 1000)
        cursor = begin
        for pos, idx in enumerate(run):
            if pos:
                cursor = prev_end + GAP  # type: ignore[operator]
            placed[idx] = round(cursor, 3)
            tempos[idx] = tempo
            prev_end = cursor + durations[idx] / tempo
    end = prev_end or 0.0
    out_duration = round(max(video_duration, end + TAIL), 3)
    return DubPlan(starts=placed, tempos=tempos, out_duration=out_duration,
                   freeze_sec=round(max(0.0, out_duration - video_duration), 3))


@lru_cache(maxsize=4)
def ffmpeg_has_filter(ffmpeg: str, name: str) -> bool:
    """Bản FFmpeg đang dùng có filter name không (vd. drawtext cần build kèm libfreetype)."""
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(len(cols) > 1 and cols[1] == name for cols in (line.split() for line in out.splitlines()))


def _find_caption_font() -> str | None:
    """Font cho phụ đề lồng tiếng: FRAMECUT_FONT → font Latin đủ dấu tiếng Việt → font CJK của hệ thống."""
    env = os.environ.get("FRAMECUT_FONT")
    if env and Path(env).exists():
        return env
    for path in _CAPTION_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return _find_cjk_font()


def _wrap_caption(text: str, max_chars: int) -> list[str]:
    """Chia câu thoại dài thành các dòng phụ đề ≤ max_chars ký tự, ngắt theo từ (tiếng Trung ngắt theo ký tự)."""
    words = text.split()
    if len(words) <= 1:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [text]
    chunks: list[str] = []
    cur = ""
    for word in words:
        if cur and len(cur) + 1 + len(word) > max_chars:
            chunks.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def _caption_windows(
    captions: list[tuple[float, float, str]], max_chars: int
) -> list[tuple[float, float, str]]:
    """Mỗi câu thoại → một hay nhiều cửa sổ phụ đề (chia thời lượng theo độ dài chữ), luôn một dòng.

    Bỏ dấu câu như phụ đề ghép phim: dấu nháy đơn (vd. "don't") sẽ đóng chuỗi drawtext giữa chừng và làm vỡ filtergraph.
    """
    out: list[tuple[float, float, str]] = []
    for start, end, text in captions:
        chunks = _wrap_caption(_strip_caption_punct(text), max_chars)
        total = sum(len(c) for c in chunks) or 1
        cursor = start
        for chunk in chunks:
            nxt = cursor + (end - start) * len(chunk) / total
            out.append((cursor, nxt, chunk))
            cursor = nxt
    return out


def _captions_filter(captions: list[tuple[float, float, str]], video_size: tuple[int, int] | None) -> str:
    """Chuỗi drawtext đốt phụ đề đáy khung, bật/tắt đúng lúc từng câu TTS được đọc."""
    w, h = video_size or (720, 1280)
    portrait = h / max(w, 1) > 1.2
    font_size = max(20, int(min(w, h) * (0.052 if portrait else 0.048)))
    max_chars = max(12, int(w * 0.9 / (font_size * 0.55)))
    y = int(h * (0.86 if portrait else 0.88)) - font_size
    font = _find_caption_font()
    font_opt = f":fontfile='{_escape_fontfile(font)}'" if font else ""
    parts = [
        f"drawtext=text='{_escape_drawtext(text)}'{font_opt}:fontsize={font_size}:"
        f"fontcolor=white:borderw=3:bordercolor=black@0.85:"
        f"x=(w-text_w)/2:y={y}:"
        f"enable='between(t\\,{a:.2f}\\,{b:.2f})'"
        for a, b, text in _caption_windows(captions, max_chars)
        if text.strip() and b - a >= 0.05
    ]
    return ",".join(parts)


def build_dub_mix_cmd(
    ffmpeg: str,
    video: Path,
    clips: list[Path],
    plan: DubPlan,
    dest: Path,
    *,
    has_video_audio: bool,
    captions: list[tuple[float, float, str]] | None = None,
    video_size: tuple[int, int] | None = None,
) -> list[str]:
    """Lệnh FFmpeg: đặt từng câu bằng adelay (tăng tốc riêng từng câu), trộn, hạ tiếng môi trường bằng sidechain,
    giữ khung cuối nếu cần và đốt phụ đề khớp giọng TTS nếu có captions."""
    if not clips:
        raise ValueError("không có câu thoại nào để lồng tiếng")
    cmd = [ffmpeg, "-nostdin", "-y", "-i", str(video)]
    for clip in clips:
        cmd += ["-i", str(clip)]
    parts: list[str] = []
    labels: list[str] = []
    for idx, start in enumerate(plan.starts):
        ms = int(round(start * 1000))
        rate = plan.tempos[idx] if idx < len(plan.tempos) else 1.0
        tempo = f"atempo={rate:.3f}," if rate != 1.0 else ""
        parts.append(
            f"[{idx + 1}:a]aresample=44100,{tempo}aformat=channel_layouts=stereo,adelay={ms}|{ms}[c{idx}]"
        )
        labels.append(f"[c{idx}]")
    if len(labels) == 1:
        parts.append(f"{labels[0]}apad[vo]")
    else:
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad[vo]")
    if has_video_audio:
        parts.append(
            f"[0:a]aresample=44100,aformat=channel_layouts=stereo,volume={AMBIENT_VOLUME},apad[bg]"
        )
        parts.append("[vo]asplit=2[vo1][sc]")
        parts.append("[bg][sc]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[duck]")
        parts.append("[duck][vo1]amix=inputs=2:duration=longest:normalize=0[a]")
    else:
        parts.append("[vo]anull[a]")
    video_filters: list[str] = []
    if plan.freeze_sec > 0:
        video_filters.append(f"tpad=stop_mode=clone:stop_duration={plan.freeze_sec:.3f}")
    subs = _captions_filter(captions, video_size) if captions else ""
    if subs:
        video_filters.append(subs)
    if video_filters:
        parts.append(f"[0:v]{','.join(video_filters)}[v]")
        video_map, vcodec = ["-map", "[v]"], ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    else:
        video_map, vcodec = ["-map", "0:v:0"], ["-c:v", "copy"]
    cmd += ["-filter_complex", ";".join(parts), *video_map, "-map", "[a]", *vcodec,
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-t", f"{plan.out_duration:.3f}",
            "-movflags", "+faststart", str(dest)]
    return cmd


def run_dub_mix(
    video: Path,
    clips: list[tuple[Path, float | None]] | list[tuple[Path, float | None, float | None]],
    dest: Path,
    *,
    subtitles: list[str] | None = None,
) -> DubPlan:
    """Đo độ dài video/câu, xếp mốc rồi chạy FFmpeg ghi dest; trả DubPlan đã dùng.

    clips: (file mp3, mốc bắt đầu kịch bản[, giây hết khối]); subtitles: chữ từng câu (cùng thứ tự clips)
    để đốt phụ đề đúng lúc giọng TTS đọc — None thì không đốt.
    """
    if not clips:
        raise ValueError("không có câu thoại nào để lồng tiếng")
    video_dur = probe_duration(video) or 0.0
    if video_dur <= 0:
        raise RuntimeError("không đọc được độ dài video để lồng tiếng")
    durations = [max(probe_duration(clip[0]) or 0.0, 0.05) for clip in clips]
    ends = [clip[2] if len(clip) > 2 else None for clip in clips]
    plan = plan_dub_timeline(durations, [clip[1] for clip in clips], video_dur, ends=ends)
    ffmpeg = _which("ffmpeg")
    captions = None
    if subtitles and not ffmpeg_has_filter(ffmpeg, "drawtext"):
        logger.warning("lồng tiếng: FFmpeg thiếu filter drawtext, bỏ qua đốt phụ đề")
    elif subtitles:
        captions = [
            (plan.starts[i], plan.speech_end(i, durations[i]), subtitles[i])
            for i in range(min(len(subtitles), len(clips)))
        ]
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(build_dub_mix_cmd(
        ffmpeg, video, [clip[0] for clip in clips], plan, dest,
        has_video_audio=_probe_has_audio(video),
        captions=captions,
        video_size=probe_video_dimensions(video) if captions else None,
    ))
    return plan
