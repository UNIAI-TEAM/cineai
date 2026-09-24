"""Sinh app/services/data/byteplus_tts_voices.json từ Phụ lục A của spec cấu hình nhân vật.

Chạy từ backend/: python scripts/gen_byteplus_voices.py
Nguồn: https://docs.byteplus.com/en/docs/byteplusvoice/tts-voice-list (lấy ngày 2026-09-24).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/superpowers/specs/2026-09-24-character-config-design.md"
OUT = ROOT / "backend/app/services/data/byteplus_tts_voices.json"

# 13 giọng đã có trước đây: giữ thứ tự cũ ở đầu mỗi ngôn ngữ và vẫn vào pool tự động
LEGACY_ORDER = [
    "vi_female_ruan_uranus_bigtts",
    "vi_male_wumg_uranus_bigtts",
    "vi_female_ling_uranus_bigtts",
    "vi_female_linh_uranus_bigtts",
    "vi_female_wu_uranus_bigtts",
    "vi_female_hong_uranus_bigtts",
    "vi_female_partner_uranus_bigtts",
    "en_female_hayley_uranus_bigtts",
    "en_male_tim_uranus_bigtts",
    "en_female_skye_uranus_bigtts",
    "en_female_jenny_uranus_bigtts",
    "en_male_kevin_uranus_bigtts",
    "en_male_marcus_uranus_bigtts",
]
ROW_RE = re.compile(r"^\| `([^`]+)` \| ([^|]*) \| (female|male) \| ([^|]*) \| [^|]* \| ([^|]*) \| (\S*) \|$")


def main() -> None:
    text = SPEC.read_text(encoding="utf-8")
    appendix = text.split("## Phụ lục A", 1)[1]
    rows = {}
    for line in appendix.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        speaker_raw, name, gender, scenario, desc, sample = (g.strip() for g in m.groups())
        # Vài dòng nguồn có ghi chú "（Note：...)" dính sau id trong cùng cặp backtick
        # (giới hạn API streaming) — tách ra, chỉ giữ id thật để dùng làm openspeech speaker.
        speaker = speaker_raw.split(" ", 1)[0]
        rows[speaker] = {
            "speaker": speaker,
            "name": name,
            "gender": gender,
            "languages": [speaker.split("_", 1)[0]],
            "scenario": scenario,
            "description": desc,
            "sample_url": sample,
        }
    missing = [s for s in LEGACY_ORDER if s not in rows]
    assert not missing, f"thiếu giọng cũ trong phụ lục: {missing}"
    ordered = []
    for lang in ("vi", "en"):
        legacy = [s for s in LEGACY_ORDER if s.startswith(f"{lang}_")]
        rest = [s for s in rows if s.startswith(f"{lang}_") and s not in legacy]
        ordered += [{**rows[s], "auto_pool": True} for s in legacy]
        ordered += [{**rows[s], "auto_pool": False} for s in rest]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(ordered)} voices → {OUT}")


if __name__ == "__main__":
    main()
