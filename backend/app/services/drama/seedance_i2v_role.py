"""Seedance i2v 图片角色：逻辑已迁移至 ark_adapter，此处仅保留向后兼容的 re-export。"""

from __future__ import annotations

from app.services.providers.ark_adapter import resolve_seedance_i2v_image_role  # noqa: F401
