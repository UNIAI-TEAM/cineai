"""I-4: lưu trang phong cách của dự án cũ (model legacy đang lưu) không được báo 400."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.projects import _validate_project_media_models
from app.errors import AppError
from app.schemas_routing import FunctionBindings
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot


@pytest.fixture(autouse=True)
def _empty_routing():
    """Không gán model nào: mọi id đều không hợp lệ trừ khi trùng giá trị đang lưu."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([], FunctionBindings())
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_unchanged_legacy_models_are_accepted():
    project = SimpleNamespace(image_model="seedream-5.0", video_model="seedance-2.5")
    _validate_project_media_models(project, {"image_model": "seedream-5.0", "video_model": "seedance-2.5"})


def test_changed_invalid_image_model_is_rejected():
    project = SimpleNamespace(image_model="seedream-5.0", video_model="")
    with pytest.raises(AppError) as exc:
        _validate_project_media_models(project, {"image_model": "not-a-model"})
    assert exc.value.code == "project.invalid_image_model"


def test_changed_invalid_video_model_is_rejected():
    project = SimpleNamespace(image_model="", video_model="seedance-2.5")
    with pytest.raises(AppError) as exc:
        _validate_project_media_models(project, {"video_model": "seedance-2"})
    assert exc.value.code == "project.invalid_video_model"
