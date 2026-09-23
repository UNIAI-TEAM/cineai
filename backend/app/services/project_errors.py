"""科普项目错误落库：error_msg 存原文（管理端 / 日志排查），error_code + error_params 供前端按界面语言翻译。"""

from __future__ import annotations

from typing import Any

from app.services.exc_format import stored_error_fields
from app.services.ffmpeg_compose import is_ffmpeg_interrupted_error

FFMPEG_INTERRUPTED_PROJECT_MSG = "FFmpeg 被系统中断（signal 15），请点击重新拼接"
CANCELLED_MSG = "用户取消"


def project_error_fields(
    exc: BaseException, default_code: str = "task.execution_failed"
) -> tuple[str, str, dict[str, Any] | None]:
    """异常 → (error_msg 原文, error_code, error_params)；FFmpeg 被 SIGTERM 中断单独归类。"""
    if is_ffmpeg_interrupted_error(exc):
        return FFMPEG_INTERRUPTED_PROJECT_MSG, "project.ffmpeg_interrupted", None
    code, params = stored_error_fields(exc, default_code)
    return str(exc)[:2000], code, params


def set_project_error(
    project: Any, message: str | None, code: str | None, params: dict[str, Any] | None = None
) -> None:
    """写项目错误三件套。"""
    project.error_msg = message
    project.error_code = code
    project.error_params = params


def set_project_cancelled(project: Any) -> None:
    """用户取消：固定文案 + project.cancelled。"""
    set_project_error(project, CANCELLED_MSG, "project.cancelled")


def clear_project_error(project: Any) -> None:
    """清空项目错误（重新开始 / 成功完成）。"""
    set_project_error(project, None, None, None)
