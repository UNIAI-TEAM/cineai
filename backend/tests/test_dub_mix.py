"""Xếp mốc câu thoại và lệnh FFmpeg lồng tiếng (unit + integration với ffmpeg thật nếu có)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import dub_mix
from app.services.dub_mix import DubPlan, build_dub_mix_cmd, plan_dub_timeline


def test_plan_sequential_without_timestamps():
    plan = plan_dub_timeline([1.0, 2.0], [None, None], video_duration=8.0)
    assert plan.starts == [0.2, 1.45] and plan.tempo == 1.0
    assert plan.out_duration == 8.0 and plan.freeze_sec == 0.0


def test_plan_respects_script_timestamps_but_never_overlaps():
    plan = plan_dub_timeline([3.0, 1.0], [0.0, 2.0], video_duration=10.0)
    assert plan.starts[0] == 0.0
    assert plan.starts[1] == pytest.approx(3.25)  # 00:02 bị câu trước chiếm → lùi sau câu trước + GAP


def test_plan_speeds_up_before_freezing():
    plan = plan_dub_timeline([4.0, 4.0], [None, None], video_duration=8.0)
    assert 1.0 < plan.tempo <= dub_mix.MAX_TEMPO
    assert plan.freeze_sec == 0.0


def test_plan_never_cuts_speech_freezes_last_frame():
    plan = plan_dub_timeline([6.0, 6.0], [None, None], video_duration=6.0)
    assert plan.tempo == dub_mix.MAX_TEMPO
    speech_end = plan.starts[-1] + 6.0 / plan.tempo
    assert plan.out_duration >= speech_end + dub_mix.TAIL - 1e-6
    assert plan.freeze_sec == pytest.approx(plan.out_duration - 6.0)


def test_cmd_ducks_ambient_and_copies_video_when_no_freeze(tmp_path):
    plan = DubPlan(starts=[0.2, 1.5], tempo=1.0, out_duration=8.0, freeze_sec=0.0)
    cmd = build_dub_mix_cmd("ffmpeg", tmp_path / "v.mp4", [tmp_path / "a.mp3", tmp_path / "b.mp3"],
                            plan, tmp_path / "o.mp4", has_video_audio=True)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=200|200" in graph and "adelay=1500|1500" in graph
    assert "sidechaincompress" in graph and "atempo" not in graph
    assert cmd[cmd.index("-c:v") + 1] == "copy"


def test_cmd_without_video_audio_and_with_freeze(tmp_path):
    plan = DubPlan(starts=[0.2], tempo=1.25, out_duration=9.0, freeze_sec=1.5)
    cmd = build_dub_mix_cmd("ffmpeg", tmp_path / "v.mp4", [tmp_path / "a.mp3"],
                            plan, tmp_path / "o.mp4", has_video_audio=False)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "sidechaincompress" not in graph and "[0:a]" not in graph
    assert "atempo=1.250" in graph and "tpad=stop_mode=clone:stop_duration=1.500" in graph
    assert cmd[cmd.index("-c:v") + 1] == "libx264"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")
@pytest.mark.parametrize("with_audio", [True, False])
def test_run_dub_mix_real_ffmpeg(tmp_path: Path, with_audio: bool):
    video = tmp_path / "v.mp4"
    src = ["-f", "lavfi", "-i", "color=c=black:s=320x240:d=3"]
    if with_audio:
        src += ["-f", "lavfi", "-i", "anoisesrc=d=3:a=0.05"]
    subprocess.run(["ffmpeg", "-y", *src, "-shortest", "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True)
    voice = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=440:d=4", str(voice)], check=True, capture_output=True)
    dest = tmp_path / "o.mp4"
    plan = dub_mix.run_dub_mix(video, [(voice, None)], dest)
    assert dest.exists() and dest.stat().st_size > 1000
    from app.services.ffmpeg_compose import probe_duration
    assert probe_duration(dest) >= 4.0 / plan.tempo  # lời 4 giây không bị cắt dù video chỉ 3 giây


def test_empty_clips_rejected_before_ffmpeg(tmp_path):
    """Không có câu thoại nào: dựng lệnh/chạy trộn đều báo ValueError, không gọi FFmpeg với filter hỏng."""
    plan = DubPlan(starts=[], tempo=1.0, out_duration=8.0, freeze_sec=0.0)
    with pytest.raises(ValueError):
        build_dub_mix_cmd("ffmpeg", tmp_path / "v.mp4", [], plan, tmp_path / "o.mp4", has_video_audio=True)
    with pytest.raises(ValueError):
        dub_mix.run_dub_mix(tmp_path / "v.mp4", [], tmp_path / "o.mp4")
