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
    "task.target_not_found": (400, "任务目标不存在或无权限"),
    "task.target_mismatch": (400, "任务目标不匹配"),
    "task.invalid_payload": (400, "任务参数无效：{field}"),
    "task.payload_out_of_range": (400, "任务参数 {field} 须在 {min}-{max} 之间"),
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
    # 漫剧：项目 / 剧本 / 分集
    "drama.project_not_found": (404, "漫剧项目不存在"),
    "drama.script_not_found": (404, "剧本不存在"),
    "drama.script_missing": (400, "缺少剧本"),
    "drama.summary_required": (400, "请先生成剧本摘要"),
    "drama.episode_scripts_required": (400, "请先生成分集剧本"),
    "drama.creative_too_short": (400, "原始创意至少需要 {min} 个字"),
    "drama.invalid_generate_mode": (400, "generate_mode 须为 optimize/summary/body/full/brief"),
    "drama.episodes_generating": (409, "全集剧本正在生成，请稍后再优化单集"),
    "drama.episodes_generating_add": (409, "全集剧本正在生成，请完成后再加集"),
    "drama.draft_required": (400, "请先输入本集剧本草稿，再让 AI 优化"),
    "drama.draft_too_short": (400, "剧本草稿至少 {min} 字"),
    "drama.episode_creative_required": (400, "请先填写本集原始创意（至少 {min} 字）"),
    "drama.episode_body_required": (400, "请先有本集剧本内容，再补齐创意与摘要"),
    "drama.max_episodes": (400, "最多 {max} 集"),
    "drama.llm_unavailable": (503, "文字模型暂不可用，请稍后再试"),
    "drama.episode_not_found": (404, "分集不存在"),
    "drama.invalid_episode_number": (400, "集号无效"),
    "drama.episode_script_not_found": (400, "找不到第 {number} 集剧本"),
    "drama.episode_body_too_short": (400, "第 {number} 集正文过短，请先写完或让 AI 优化后再确认进入分镜"),
    "drama.episode_reload_failed": (400, "分集写入后未能重新加载"),
    # 漫剧：资产
    "drama.asset_not_found": (404, "资产不存在"),
    "drama.character_asset_not_found": (404, "角色资产不存在"),
    "drama.character_asset_only": (400, "仅支持角色资产"),
    "drama.prompt_required": (400, "缺少提示词"),
    "drama.voice_prompt_required": (400, "缺少音色描述"),
    "drama.voice_generate_failed": (500, "音色生成失败，请稍后重试"),
    "drama.upload_unavailable": (503, "OSS 未启用，无法上传资产媒体"),
    "drama.upload_read_failed": (400, "无法读取上传文件"),
    "drama.upload_failed": (502, "上传失败，请稍后重试"),
    "drama.asset_generating": (409, "形象生成中，请稍后再更换图片"),
    "drama.asset_generating_version": (409, "形象生成中，无法切换历史版本"),
    "drama.no_history_version": (400, "没有可切换的历史版本"),
    "drama.version_not_found": (400, "指定版本不存在"),
    "drama.assets_extracting": (409, "资产抽取进行中，请稍后再确认"),
    "drama.asset_extract_failed": (502, "资产抽取失败，请稍后重试"),
    # 漫剧：分镜与成片
    "drama.fragment_not_found": (404, "分镜不存在"),
    "drama.fragments_protected": (409, "本集含已生成视频或手改分镜，请确认后强制重新分镜"),
    "drama.fragment_generating": (409, "分镜正在生成，请完成后再切换版本"),
    "drama.no_fragments_to_generate": (400, "没有可生成的分镜（保存后分镜已更新，请再点一次生成）"),
    "drama.fragments_all_generating": (409, "所选分镜正在生成，请等待完成后再试"),
    "drama.prev_fragment_required": (400, "已开启尾帧衔接：请先生成上一镜并等待尾帧就绪后，再点本镜生成"),
    "drama.compose_no_videos": (400, "本集还没有可拼接的分镜视频"),
    "drama.compose_clip_download_failed": (400, "无法下载分镜视频，请稍后重试"),
    "drama.compose_failed": (500, "全片合成失败，请稍后重试"),
    # 漫剧：导演 Skill
    "drama.skill_not_found": (404, "Skill 不存在"),
    "drama.skill_md_only": (400, "请上传 .md 文件"),
    "drama.skill_file_too_large": (400, "文件不能超过 {max_kb}KB"),
    "drama.skill_not_text": (400, "文件须为 UTF-8 文本"),
    "drama.skill_edit_forbidden": (403, "不能修改他人 Skill"),
    "drama.skill_delete_forbidden": (403, "不能删除他人 Skill"),
    "drama.skill_builtin_undeletable": (400, "系统内置 Skill 不能删除，可停用"),
    "drama.skill_builtin_readonly": (400, "系统内置 Skill 不能改正文"),
    "drama.skill_empty": (400, "Skill 内容为空"),
    "drama.skill_invalid_name": (400, "Skill 名称只能用小写字母、数字和连字符"),
    "drama.skill_body_empty": (400, "Skill 正文不能为空"),
    "drama.skill_too_long": (400, "Skill 不能超过 {max} 字"),
    "drama.skill_limit": (400, "最多上传 {max} 条自定义 Skill"),
    "drama.skill_duplicate": (400, "已有同名 Skill，请换 name 或先删除旧的"),
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
        return type(self)(self.code, status=self.status, **self.params)

    def __reduce__(self):
        """支持 copy / pickle：按 code / status / params 重建。"""
        return (_rebuild_app_error, (type(self), self.code, self.status, self.params))


def _rebuild_app_error(
    cls: type[AppError], code: str, status: int | None, params: dict[str, Any]
) -> AppError:
    """__reduce__ 的重建函数：copy.copy / pickle.loads 都按此还原（保留子类）。"""
    return cls(code, status=status, **params)


def register_app_error_handler(app: FastAPI) -> None:
    """注册全局处理器：AppError → JSON {detail, code, params}。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_payload())
