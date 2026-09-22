"""Bảo vệ an ninh: không module runtime nào còn gọi tokenfree.com (tránh gửi key OpenAI/BytePlus sang bên thứ ba)."""
from __future__ import annotations

from pathlib import Path

# model_settings.py chỉ chứa chuỗi để DỌN cấu hình TokenFree cũ, không gọi mạng
_ALLOWED = {"model_settings.py"}


def test_no_runtime_module_mentions_tokenfree_host():
    root = Path(__file__).resolve().parents[1] / "app"
    files = list(root.rglob("*.py"))
    # Chặn pass rỗng: thư mục quét phải tồn tại và đủ lớn (đổi layout thì test phải đỏ, không im lặng xanh)
    assert root.is_dir(), f"không thấy thư mục quét {root}"
    assert len(files) >= 50, f"chỉ quét được {len(files)} file .py trong {root}"
    offenders = sorted(
        str(p.relative_to(root))
        for p in files
        if "tokenfree.com" in p.read_text(encoding="utf-8").lower() and p.name not in _ALLOWED
    )
    assert offenders == []
