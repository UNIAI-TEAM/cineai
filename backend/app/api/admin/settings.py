# Admin model / provider settings API
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models import User
from app.schemas_provider_rates import AdminProviderRatesOut, AdminProviderRatesPut
from app.schemas_routing import AdminRoutingSettingsOut, AdminRoutingSettingsPatch, AdminRoutingSettingsSaveOut
from app.schemas_settings import (
    AdminModelSettingsImportEnvOut,
    AdminModelSettingsOut,
    AdminModelSettingsPatch,
    AdminModelSettingsSaveOut,
)
from app.services.billing.provider_rates_admin import get_provider_rates_admin, save_provider_rates_admin
from app.services.model_settings import (
    get_admin_model_settings,
    get_admin_routing_settings,
    import_admin_model_settings_from_env,
    patch_admin_model_settings,
    patch_admin_routing_settings,
)
from app.services.providers.host_guard import ProviderHostChangedError
from app.services.upstream_model_catalog import list_upstream_models

router = APIRouter()
logger = logging.getLogger(__name__)


class AdminUpstreamModelsRequest(BaseModel):
    """按渠道凭证拉取上游 /models 目录。"""

    channel_id: str | None = Field(default=None, max_length=64)
    protocol: str = Field(default="auto", max_length=32)
    base_url: str = Field(default="", max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    capability: str = Field(default="all", max_length=32)


@router.get("/settings/routing", response_model=AdminRoutingSettingsOut)
async def admin_get_routing_settings(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRoutingSettingsOut:
    # Đọc toàn bộ cấu hình routing: provider + function_bindings + readiness
    return await get_admin_routing_settings(db)


@router.patch("/settings/routing", response_model=AdminRoutingSettingsSaveOut)
async def admin_patch_routing_settings(
    body: AdminRoutingSettingsPatch,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRoutingSettingsSaveOut:
    # Lưu provider và/hoặc function_bindings (validate trước khi commit, lỗi trả 400)
    try:
        settings, applied = await patch_admin_routing_settings(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminRoutingSettingsSaveOut(settings=settings, applied=applied)


@router.get("/settings/models", response_model=AdminModelSettingsOut)
async def admin_get_model_settings(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminModelSettingsOut:
    # 读取当前生效的模型配置（DB 优先，env 兜底）
    return await get_admin_model_settings(db)


@router.patch("/settings/models", response_model=AdminModelSettingsSaveOut)
async def admin_patch_model_settings(
    body: AdminModelSettingsPatch,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminModelSettingsSaveOut:
    # 部分更新模型配置；密钥留空表示不修改
    try:
        settings, applied = await patch_admin_model_settings(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminModelSettingsSaveOut(settings=settings, applied_fields=applied)


@router.post("/settings/models/import-env", response_model=AdminModelSettingsImportEnvOut)
async def admin_import_model_settings_from_env(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminModelSettingsImportEnvOut:
    # 一键将 .env / 环境变量中的可管理项导入 DB（空密钥跳过，避免覆盖已有密文）
    settings, imported, skipped = await import_admin_model_settings_from_env(db)
    return AdminModelSettingsImportEnvOut(
        settings=settings,
        imported_fields=imported,
        skipped_secret_fields=skipped,
    )


@router.post("/settings/upstream/models")
async def admin_list_upstream_models(
    body: AdminUpstreamModelsRequest,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Danh mục model của một provider (openai: GET /models; ark/volc_tts: danh sách tĩnh); lỗi trả 400."""
    try:
        models = await list_upstream_models(
            db,
            channel_id=body.channel_id,
            protocol=body.protocol,
            base_url=body.base_url,
            api_key_override=body.api_key,
            capability=body.capability,
        )
    except (RuntimeError, ProviderHostChangedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"models": models}


@router.get("/settings/billing/model-rates", response_model=AdminProviderRatesOut)
async def admin_get_provider_rates(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProviderRatesOut:
    """Bảng giá provider_rates đang áp dụng + mặc định + đơn vị + model đã gán chưa có giá."""
    return await get_provider_rates_admin(db)


@router.put("/settings/billing/model-rates", response_model=AdminProviderRatesOut)
async def admin_put_provider_rates(
    body: AdminProviderRatesPut,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProviderRatesOut:
    """Thay toàn bộ bảng giá; lỗi validation trả 400 với thông điệp tiếng Việt."""
    try:
        return await save_provider_rates_admin(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class AdminProviderTestRequest(BaseModel):
    """Kiểm tra kết nối provider trước khi lưu."""

    channel_id: str | None = Field(default=None, max_length=64)
    protocol: str = Field(default="openai", max_length=32)
    base_url: str = Field(default="", max_length=512)
    api_key: str | None = Field(default=None, max_length=512)


@router.post("/settings/providers/test")
async def admin_test_provider(
    body: AdminProviderTestRequest,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """openai: GET /models; ark/volc_tts: chỉ kiểm tra có key (không có endpoint rẻ để test)."""
    try:
        models = await list_upstream_models(
            db,
            channel_id=body.channel_id,
            protocol=body.protocol,
            base_url=body.base_url,
            api_key_override=body.api_key,
        )
    except ProviderHostChangedError as exc:
        # Đổi host mà không nhập lại key: từ chối hẳn, không dùng key đã lưu
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    if body.protocol in ("ark", "volc_tts"):
        # Hai protocol này không có endpoint kiểm tra miễn phí: danh sách model là bảng tĩnh, key chưa được gọi thử
        return {"ok": True, "message": "Đã có key (chưa gọi thử nhà cung cấp)", "models_count": len(models)}
    return {"ok": True, "message": f"Kết nối thành công, {len(models)} model", "models_count": len(models)}
