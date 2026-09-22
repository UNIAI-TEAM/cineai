# -*- coding: utf-8 -*-
"""业务错误码：AppError + 错误码目录 + 全局异常处理器。

响应体 {detail, code, params}：detail 为中文（兼容管理端 / 漫剧 / 开放 API），
前端按 code 查 i18n/locales/*/errors.ts 翻译。新增错误码时三份前端文案要同步加，
tests/test_app_errors.py 会校验。
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# code -> (默认 HTTP 状态码, 中文 detail 模板)；占位符 {x} 若参数里只有 x_fen 则按展示货币格式化
ERRORS: dict[str, tuple[int, str]] = {
    # 通用
    "common.unsupported_image_type": (400, "仅支持 JPG / PNG / WebP / GIF"),
    "common.empty_file": (400, "空文件"),
    "common.file_too_large": (400, "文件不能超过 {max_mb}MB"),
    "common.invalid_image": (400, "文件不是有效图片"),
    "common.user_not_found": (404, "用户不存在"),
    # 账号
    "auth.email_registered": (400, "邮箱已注册"),
    "auth.invalid_credentials": (401, "邮箱或密码错误"),
    "auth.wrong_current_password": (400, "当前密码不正确"),
    "auth.same_password": (400, "新密码不能与当前密码相同"),
    "auth.email_taken": (400, "该邮箱已被使用"),
    "auth.service_unavailable": (503, "服务暂时不可用，请稍后再试"),
    "auth.reset_token_invalid": (400, "重置链接无效或已过期"),
    "auth.username_required": (400, "用户名不能为空"),
    "auth.username_too_long": (400, "用户名不能超过 {max} 个字符"),
    "auth.email_invalid": (400, "邮箱格式不正确"),
    "auth.phone_invalid": (400, "手机号格式不正确"),
    # 计费
    "billing.insufficient_balance": (402, "余额不足：需要 {need}，当前 {available}，请先充值"),
    "billing.insufficient_balance_pending": (
        402,
        "余额不足：本次需要 {need}（含排队中 {pending}），当前 {available}，请先充值",
    ),
    "billing.insufficient_balance_batch": (
        402,
        "余额不足：批量生成 {qty} 项需 {need}（含排队中 {pending}），当前 {available}，请先充值",
    ),
    "billing.unknown_package": (400, "未知充值包"),
    "billing.topup_unavailable": (503, "充值暂未开放：尚未配置收款账户"),
    "billing.alert_not_found": (404, "告警不存在"),
    "billing.order_not_found": (404, "订单不存在"),
    "billing.order_paid_cannot_close": (400, "已支付订单无法关闭"),
    "billing.order_cannot_close": (400, "当前状态不可关闭"),
    "billing.order_closed": (400, "订单已关闭，无法确认到账"),
    # 任务平台
    "task.not_found": (404, "任务不存在"),
    "task.mock_limit": (429, "模拟延时任务最多同时运行 {max} 个"),
    "task.type_not_supported": (400, "当前任务类型尚未接入任务平台"),
    "task.target_not_found": (404, "任务目标不存在或无权限"),
    "task.target_mismatch": (400, "任务目标不匹配"),
    "task.invalid_payload": (400, "任务参数无效：{field}"),
    "task.cancel_not_supported": (400, "任务不支持取消"),
    "task.already_finished": (400, "任务已结束，不能取消"),
    # 工具中心
    "tool.unknown": (400, "未知工具"),
    "tool.missing_task": (400, "缺少任务"),
    "tool.run_not_found": (404, "记录不存在"),
    "tool.unsupported_file_type": (400, "仅支持 png / jpg / webp / gif / mp4 / mov / webm"),
    "tool.prompt_required": (400, "请填写提示词"),
    "tool.reference_required": (400, "请上传参考图"),
    "tool.product_image_required": (400, "请上传商品图"),
    "tool.stitch_min_images": (400, "拼接至少上传 {min} 张图片"),
    "tool.video_script_required": (400, "请填写视频脚本"),
    "tool.video_source_required": (400, "请上传源视频或首帧图"),
    "tool.first_frame_extract_failed": (400, "无法从视频抽取首帧"),
    "tool.first_frame_required": (400, "缺少首帧图，无法生成视频"),
    "tool.run_failed": (500, "生成失败，请稍后重试"),
    # API Key / 模板
    "api_key.not_found": (404, "Key 不存在或已撤销"),
    "template.not_found": (404, "模板不存在"),
    # 科普 / 获客短视频项目
    "project.not_found": (404, "项目不存在"),
    "project.invalid_template": (400, "无效模板"),
    "project.topic_required": (400, "请输入选题"),
    "project.ai_generate_failed": (502, "AI 生成失败，请稍后重试"),
    "project.voice_preview_failed": (502, "试听生成失败，请稍后重试"),
    "project.full_generation_running": (409, "整片生成进行中，请稍后"),
    "project.generation_running": (409, "生成进行中，请稍后"),
    "project.locked_while_generating": (409, "生成进行中，无法修改"),
    "project.cover_locked": (409, "生成进行中，无法更换封面"),
    "project.download_selection_required": (400, "请选择要下载的作品"),
    "project.download_limit": (400, "一次最多打包 {max} 个"),
    "project.no_downloadable_video": (400, "所选作品暂无成片可下载（需状态为已完成）"),
    "project.invalid_cover_url": (400, "无效封面地址"),
    "project.invalid_image_model": (400, "无效图片模型"),
    "project.invalid_video_model": (400, "无效视频模型"),
    "project.ready_to_compose": (409, "素材已齐，请点击合成成片"),
    "project.cannot_cancel": (400, "当前状态不可取消"),
    "project.shot_list_incomplete": (400, "镜头列表不完整"),
    "project.shot_not_found": (404, "分镜不存在"),
    "project.image_text_no_video": (400, "图文模式无需生成 AI 视频，请直接重新合成成片"),
    "project.shot_image_required": (400, "请先生成该镜画面"),
    "project.no_shots": (400, "暂无分镜，请先生成"),
    "project.compose_missing_media": (400, "缺少分镜图或镜头视频，无法合成"),
    "project.not_ready_to_publish": (400, "成片未完成，无法发布"),
    "project.narration_empty": (400, "全部镜头旁白为空，无法配音"),
    "project.shot_narration_empty": (400, "旁白为空，无法配音"),
}


def _render(template: str, params: dict[str, Any]) -> str:
    """用参数填充中文模板；*_fen 额外生成去后缀的格式化金额（如 need_fen → {need}）。"""
    values: dict[str, Any] = dict(params)
    for key, value in params.items():
        if key.endswith("_fen"):
            # 延迟导入：billing 包初始化会反向导入本模块
            from app.services.billing.money import format_money

            values[key[: -len("_fen")]] = format_money(int(value))
    return template.format(**values)


class AppError(ValueError):
    """带错误码的业务错误；继承 ValueError，已有 except ValueError 仍能捕获。

    参数:
        code: ERRORS 中登记的错误码，未登记直接 KeyError
        status: 覆盖默认 HTTP 状态码
        **params: 原始数据（数字 / id / 用户输入的名称），金额用 *_fen
    """

    def __init__(self, code: str, status: int | None = None, **params: Any) -> None:
        default_status, template = ERRORS[code]
        self.code = code
        self.status = status or default_status
        self.params = params
        self.detail = _render(template, params)
        super().__init__(self.detail)

    def to_payload(self) -> dict[str, Any]:
        """HTTP 响应体。"""
        return {"detail": self.detail, "code": self.code, "params": self.params}

    def clone(self) -> "AppError":
        """复制一份，供 `raise ... from exc` 时避免异常以自身为 cause。"""
        return AppError(self.code, status=self.status, **self.params)


def register_app_error_handler(app: FastAPI) -> None:
    """注册全局处理器：AppError → JSON {detail, code, params}。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_payload())
