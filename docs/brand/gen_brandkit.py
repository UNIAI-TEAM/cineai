"""Tạo bảng brand kit CineAI bằng model ảnh OpenAI, dùng logo concept làm ảnh tham chiếu.

Cách chạy (ở thư mục gốc repo):
    OPENAI_API_KEY=sk-... python3 docs/brand/gen_brandkit.py [--model gpt-image-x] [--n 2]

- Prompt lấy từ khối ```text``` đầu tiên trong mục 6 của docs/brand/BRAND.md.
- Không truyền --model thì tự chọn model gpt-image-* mới nhất mà key có quyền dùng.
- Ảnh lưu vào docs/brand/boards/ (không commit ảnh sinh ra).
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _request(req: urllib.request.Request, timeout: int = 600) -> dict:
    """Gửi request, trả JSON; in lỗi rõ ràng khi API từ chối."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Lỗi API {e.code}: {e.read().decode(errors='replace')[:800]}")


def pick_model(key: str) -> str:
    """Chọn model gpt-image-* có phiên bản cao nhất trong danh sách model của key."""
    req = urllib.request.Request(f"{API}/models", headers={"Authorization": f"Bearer {key}"})
    ids = [m["id"] for m in _request(req, 60).get("data", []) if m["id"].startswith("gpt-image")]
    if not ids:
        sys.exit("Key không có quyền dùng model gpt-image-* nào.")

    def version(mid: str) -> tuple:
        # gpt-image-1.5 > gpt-image-1 > gpt-image-1-mini; bản mini/snapshot xếp sau bản chính
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", mid.removeprefix("gpt-image-"))[:1]] or [0.0]
        return (nums[0], "mini" not in mid, -len(mid))

    ids.sort(key=version, reverse=True)
    print("Model ảnh khả dụng:", ", ".join(ids))
    return ids[0]


def load_prompt() -> str:
    """Lấy prompt từ khối ```text``` trong docs/brand/BRAND.md."""
    md = (HERE / "BRAND.md").read_text(encoding="utf-8")
    m = re.search(r"```text\n(.*?)```", md, re.S)
    if not m:
        sys.exit("Không tìm thấy khối ```text``` trong BRAND.md")
    return m.group(1).strip()


def multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Đóng gói multipart/form-data. files: {tên_field: (tên_file, bytes, mime)}."""
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, (name, data, mime) in files.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode() + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def main() -> None:
    """Gọi images/edits với logo tham chiếu và lưu ảnh kết quả."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--size", default="1536x1024")
    ap.add_argument("--quality", default="high")
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("Chưa đặt biến môi trường OPENAI_API_KEY.")

    model = args.model or pick_model(key)
    print(f"Dùng model: {model}")
    body, ctype = multipart(
        {"model": model, "prompt": load_prompt(), "n": args.n, "size": args.size, "quality": args.quality},
        {"image[]": ("logo-concept.jpg", (HERE / "logo-concept.jpg").read_bytes(), "image/jpeg")},
    )
    req = urllib.request.Request(f"{API}/images/edits", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": ctype})
    t0 = time.time()
    data = _request(req)
    out_dir = HERE / "boards"
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for i, item in enumerate(data.get("data", []), 1):
        path = out_dir / f"brandkit-{model}-{stamp}-{i}.png"
        path.write_bytes(base64.b64decode(item["b64_json"]))
        print("Đã lưu:", path.relative_to(HERE.parent.parent))
    print(f"Xong sau {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
