"""Lồng tiếng hậu kỳ: xếp mốc câu thoại TTS lên video và trộn với tiếng môi trường (hạ nhỏ khi có thoại)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.ffmpeg_compose import _probe_has_audio, _run, _which, probe_duration

LEAD_IN = 0.2  # câu đầu không có mốc: bắt đầu sau 0.2s
GAP = 0.25  # khoảng nghỉ tối thiểu giữa hai câu
TAIL = 0.3  # đuôi im lặng sau câu cuối
MAX_TEMPO = 1.25  # tăng tốc tối đa trước khi phải kéo dài khung cuối
AMBIENT_VOLUME = 0.6  # tiếng môi trường Seedance trước khi sidechain


@dataclass(frozen=True)
class DubPlan:
    """Kết quả xếp mốc: giây bắt đầu từng câu, hệ số tăng tốc, độ dài video ra, số giây giữ khung cuối."""

    starts: list[float]
    tempo: float
    out_duration: float
    freeze_sec: float


def _place(durations: list[float], starts: list[float | None], tempo: float) -> tuple[list[float], float]:
    """Đặt các câu theo mốc kịch bản (nếu có) nhưng không chồng lên câu trước; trả (mốc, giây kết thúc)."""
    out: list[float] = []
    prev_end = 0.0
    for dur, wanted in zip(durations, starts):
        floor = prev_end + GAP if out else 0.0
        default = prev_end + GAP if out else LEAD_IN
        begin = max(wanted if wanted is not None else default, floor)
        out.append(round(begin, 3))
        prev_end = begin + dur / tempo
    return out, prev_end


def plan_dub_timeline(durations: list[float], starts: list[float | None], video_duration: float) -> DubPlan:
    """Xếp mốc; thừa thời gian thì tăng tốc từng nấc tới MAX_TEMPO, vẫn thừa thì giữ khung cuối (không cắt lời)."""
    tempo = 1.0
    placed, end = _place(durations, starts, tempo)
    for step in (1.1, 1.2, MAX_TEMPO):
        if end + TAIL <= video_duration:
            break
        tempo = step
        placed, end = _place(durations, starts, tempo)
    out_duration = round(max(video_duration, end + TAIL), 3)
    return DubPlan(starts=placed, tempo=tempo, out_duration=out_duration,
                   freeze_sec=round(max(0.0, out_duration - video_duration), 3))


def build_dub_mix_cmd(
    ffmpeg: str, video: Path, clips: list[Path], plan: DubPlan, dest: Path, *, has_video_audio: bool
) -> list[str]:
    """Lệnh FFmpeg: đặt từng câu bằng adelay, trộn, hạ tiếng môi trường bằng sidechain, giữ khung cuối nếu cần."""
    cmd = [ffmpeg, "-nostdin", "-y", "-i", str(video)]
    for clip in clips:
        cmd += ["-i", str(clip)]
    parts: list[str] = []
    labels: list[str] = []
    tempo = f"atempo={plan.tempo:.3f}," if plan.tempo != 1.0 else ""
    for idx, start in enumerate(plan.starts):
        ms = int(round(start * 1000))
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
    if plan.freeze_sec > 0:
        parts.append(f"[0:v]tpad=stop_mode=clone:stop_duration={plan.freeze_sec:.3f}[v]")
        video_map, vcodec = ["-map", "[v]"], ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    else:
        video_map, vcodec = ["-map", "0:v:0"], ["-c:v", "copy"]
    cmd += ["-filter_complex", ";".join(parts), *video_map, "-map", "[a]", *vcodec,
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-t", f"{plan.out_duration:.3f}",
            "-movflags", "+faststart", str(dest)]
    return cmd


def run_dub_mix(video: Path, clips: list[tuple[Path, float | None]], dest: Path) -> DubPlan:
    """Đo độ dài video/câu, xếp mốc rồi chạy FFmpeg ghi dest; trả DubPlan đã dùng."""
    video_dur = probe_duration(video) or 0.0
    if video_dur <= 0:
        raise RuntimeError("không đọc được độ dài video để lồng tiếng")
    durations = [max(probe_duration(path) or 0.0, 0.05) for path, _ in clips]
    plan = plan_dub_timeline(durations, [start for _, start in clips], video_dur)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(build_dub_mix_cmd(_which("ffmpeg"), video, [p for p, _ in clips], plan, dest,
                           has_video_audio=_probe_has_audio(video)))
    return plan
