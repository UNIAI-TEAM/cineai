"""Load, cache, and persist provider routing (channels + function bindings) plus flat runtime settings."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings, reload_settings
from app.models_settings import AppSettings, SystemModelChannelRow
from app.schemas_routing import (
    AdminRoutingSettingsOut,
    AdminRoutingSettingsPatch,
    FunctionBindings,
    FunctionInfo,
    ModelBinding,
    SystemChannelAdvancedConfig,
    SystemModelChannel,
)
from app.schemas_settings import (
    SECRET_FIELD_FLAGS,
    SECRET_FIELDS,
    AdminModelSettingsOut,
    AdminModelSettingsPatch,
    ModelCapabilityReadiness,
    model_config_field_names,
)
from app.services.function_bindings import bindings_to_dict, parse_function_bindings, validate_function_bindings

logger = logging.getLogger("app.model_settings")

ENCRYPTED_PREFIX = "enc:"

_overlay: dict[str, Any] = {}


@dataclass
class RoutingSnapshot:
    """Ảnh chụp routing hiện hành: danh sách provider (kèm key thật) và gán model theo chức năng."""

    channels: list[SystemModelChannel]
    function_bindings: FunctionBindings


_routing_snapshot = RoutingSnapshot(channels=[], function_bindings=FunctionBindings())


# 从 secret_key 派生 Fernet 密钥
def _fernet() -> Fernet:
    """Suy khoá Fernet từ SECRET_KEY của app (dùng để mã hoá key nhạy cảm trong DB)."""
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


# 加密敏感字段
def _encrypt_secret(value: str) -> str:
    """Mã hoá một chuỗi bí mật, tiền tố `enc:` để nhận diện lúc giải mã."""
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


# 解密敏感字段
def _decrypt_secret(value: str) -> str:
    """Giải mã một chuỗi đã mã hoá bằng `_encrypt_secret`; chuỗi rỗng/chưa mã hoá trả nguyên."""
    if not value:
        return ""
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    token = value[len(ENCRYPTED_PREFIX) :]
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


# 返回当前路由快照
def get_routing_snapshot() -> RoutingSnapshot:
    """Trả snapshot routing đang cache trong process (channels + function_bindings)."""
    return _routing_snapshot


# 返回 flat overlay
def get_overlay_dict() -> dict[str, Any]:
    """Trả bản sao overlay flat hiện hành (dùng để debug/kiểm tra)."""
    return dict(_overlay)


# 刷新 flat overlay
def _refresh_overlay(config: dict[str, Any]) -> None:
    """Nạp lại overlay flat từ config đã lưu; chuỗi rỗng vẫn giữ (là tín hiệu "đã xoá khoá")."""
    global _overlay
    flat = config.get("flat") if isinstance(config.get("flat"), dict) else config
    # 空串必须保留：它是管理端「清除密钥」写入的显式值，
    # 若在此过滤，get_settings() 会回落 .env 中的旧密钥——界面显示已清除、请求仍带旧 Key。
    # 仅 None（DB 未设置该字段）跳过，让 base Settings 默认值生效。
    _overlay = {
        field: flat[field]
        for field in model_config_field_names()
        if field in flat and flat[field] is not None
    }


def _refresh_routing_snapshot(channels: list[SystemModelChannel], function_bindings: FunctionBindings) -> None:
    """Ghi đè snapshot routing toàn cục (gọi sau khi nạp/lưu cấu hình)."""
    global _routing_snapshot
    _routing_snapshot = RoutingSnapshot(channels=channels, function_bindings=function_bindings)


# Seed provider từ .env lần đầu (chỉ khi DB chưa có provider nào)
def _bootstrap_channels_from_env(settings: Settings | None = None) -> list[SystemModelChannel]:
    """Suy ra 0..3 provider (openai/byteplus/volc_tts) từ các key .env đang có."""
    from app.services.model_routing_config import infer_model_capability
    from app.services.providers.ark_adapter import ARK_DEFAULT_BASE_URL
    from app.services.providers.openai_adapter import OPENAI_DEFAULT_BASE_URL

    src = settings or get_settings()
    env_models = [m for m in (src.model_llm, src.model_image, src.model_image_45, src.model_video, src.model_video_2, src.model_audio) if (m or "").strip()]
    out: list[SystemModelChannel] = []
    okey = (src.openai_api_key or "").strip()
    if okey:
        models = [m for m in env_models if infer_model_capability(m) in ("text", "audio")]
        out.append(SystemModelChannel(id="openai", name="OpenAI", base_url=(src.openai_base_url or OPENAI_DEFAULT_BASE_URL).rstrip("/"),
                                      api_key=okey, has_api_key=True, protocol="openai", api_format="openai", models=models, enabled=True, sort_order=0))
    akey = (src.ark_api_key or "").strip()
    if akey:
        models = [m for m in env_models if infer_model_capability(m) in ("image", "video")]
        out.append(SystemModelChannel(id="byteplus", name="BytePlus ModelArk", base_url=(src.ark_base_url or ARK_DEFAULT_BASE_URL).rstrip("/"),
                                      api_key=akey, has_api_key=True, protocol="ark", api_format="ark", models=models, enabled=True, sort_order=1))
    vkey = (src.volc_tts_api_key or "").strip()
    if vkey or (src.volc_tts_app_id and src.volc_tts_access_key):
        out.append(SystemModelChannel(id="volc_tts", name="BytePlus Seed Speech", base_url=(src.volc_tts_url or "").rstrip("/"),
                                      api_key=vkey, has_api_key=bool(vkey), protocol="volc_tts", api_format="openai",
                                      models=[src.volc_tts_resource_id or "seed-tts-2.0"], enabled=True, sort_order=2))
    return out


# Gán slot mặc định từ MODEL_* của env: mỗi năng lực lấy model đầu tiên có provider bật
def _bootstrap_bindings_from_env(settings: Settings, channels: list[SystemModelChannel]) -> FunctionBindings:
    """Gán mỗi năng lực (text/image/video/audio) vào provider .env đang chứa model MODEL_* tương ứng."""
    from app.services.model_routing_config import normalize_model_name

    slots: dict[str, list[ModelBinding]] = {}
    for cap, model in (("text", settings.model_llm), ("image", settings.model_image), ("video", settings.model_video), ("audio", settings.model_audio)):
        mid = (model or "").strip()
        for ch in channels:
            if any(normalize_model_name(m) == normalize_model_name(mid) for m in ch.models):
                slots[cap] = [ModelBinding(channel_id=ch.id, model=mid)]
                break
        else:
            if cap == "audio":
                volc = next((c for c in channels if c.protocol == "volc_tts"), None)
                if volc:
                    slots[cap] = [ModelBinding(channel_id=volc.id, model=volc.models[0])]
    return FunctionBindings(slots=slots)


def _migrate_legacy_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Bỏ logical_models/default_models thời TokenFree; đảm bảo có function_bindings."""
    out = dict(config)
    changed = False
    for key in ("logical_models", "default_models"):
        if key in out:
            out.pop(key)
            changed = True
    if "function_bindings" not in out:
        out["function_bindings"] = bindings_to_dict(FunctionBindings())
        changed = True
    return out, changed


# ORM 行转领域模型（admin 视图，密钥打码）
def _channel_row_to_admin(row: SystemModelChannelRow) -> SystemModelChannel:
    """Chuyển 1 dòng provider trong DB sang model admin (khoá bị che, chỉ giữ cờ has_api_key)."""
    api_key = _decrypt_secret(row.api_key_ciphertext or "")
    return SystemModelChannel(
        id=row.id,
        name=row.name,
        base_url=row.base_url or "",
        api_key="",
        has_api_key=bool(api_key),
        api_format=row.api_format or "openai",
        protocol=row.protocol or "auto",
        models=list(row.models or []),
        enabled=bool(row.enabled),
        sort_order=int(row.sort_order or 0),
        advanced_config=SystemChannelAdvancedConfig.model_validate(row.advanced_config)
        if row.advanced_config
        else None,
    )


# 运行时渠道（含明文密钥）
def _channel_row_to_runtime(row: SystemModelChannelRow) -> SystemModelChannel:
    """Chuyển 1 dòng provider trong DB sang model runtime (khoá giải mã, dùng để gọi upstream)."""
    channel = _channel_row_to_admin(row)
    return channel.model_copy(update={"api_key": _decrypt_secret(row.api_key_ciphertext or "")})


async def _get_or_create_app_row(db: AsyncSession) -> AppSettings:
    """Lấy dòng app_settings duy nhất (id="default"); tạo mới với flat = env hiện hành nếu chưa có."""
    row = (await db.execute(select(AppSettings).where(AppSettings.id == "default"))).scalar_one_or_none()
    if row:
        return row
    row = AppSettings(id="default", config_json={"flat": _settings_to_dict()})
    db.add(row)
    await db.flush()
    return row


async def _load_channels(db: AsyncSession, *, runtime: bool) -> list[SystemModelChannel]:
    """Đọc toàn bộ provider theo sort_order/id; `runtime=True` trả khoá thật, ngược lại khoá bị che."""
    rows = list(
        (await db.execute(select(SystemModelChannelRow).order_by(SystemModelChannelRow.sort_order, SystemModelChannelRow.id)))
        .scalars()
        .all()
    )
    if not rows:
        return []
    if runtime:
        return [_channel_row_to_runtime(row) for row in rows]
    return [_channel_row_to_admin(row) for row in rows]


async def _ensure_bootstrapped_channels(db: AsyncSession) -> None:
    """Xoá kênh tokenfree cũ; DB trống provider thì seed từ env (kèm bindings)."""
    rows = list((await db.execute(select(SystemModelChannelRow))).scalars().all())
    legacy = [r for r in rows if r.id == "tokenfree" or "tokenfree.com" in (r.base_url or "")]
    for r in legacy:
        await db.delete(r)
    rows = [r for r in rows if r not in legacy]
    if rows:
        await db.flush()
        return
    channels = _bootstrap_channels_from_env()
    for channel in channels:
        db.add(SystemModelChannelRow(id=channel.id, name=channel.name, base_url=channel.base_url,
                                     api_key_ciphertext=_encrypt_secret(channel.api_key) if channel.api_key else None,
                                     api_format=channel.api_format, protocol=channel.protocol, models=channel.models,
                                     enabled=channel.enabled, sort_order=channel.sort_order, advanced_config=None))
    app_row = await _get_or_create_app_row(db)
    config = dict(app_row.config_json or {})
    if channels and not parse_function_bindings(config.get("function_bindings")).slots:
        config["function_bindings"] = bindings_to_dict(_bootstrap_bindings_from_env(get_settings(), channels))
    if "flat" not in config:
        config["flat"] = _encrypt_flat_config(_settings_to_dict())
    app_row.config_json = config
    await db.flush()


def _settings_to_dict(settings: Settings | None = None) -> dict[str, Any]:
    """Chụp các trường Settings quản lý được ở admin thành dict phẳng."""
    src = settings or get_settings()
    return {field: getattr(src, field) for field in model_config_field_names()}


def _decrypt_flat_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Giải mã các trường bí mật trong config flat đã lưu DB."""
    data = dict((raw or {}).get("flat") or raw or {})
    for field in SECRET_FIELDS:
        if field in data and data[field]:
            try:
                data[field] = _decrypt_secret(str(data[field]))
            except Exception:  # noqa: BLE001
                logger.warning("failed to decrypt flat settings field %s", field)
                data[field] = ""
    return data


def _encrypt_flat_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Mã hoá các trường bí mật trước khi ghi config flat vào DB."""
    data = dict(raw)
    for field in SECRET_FIELDS:
        value = data.get(field)
        if value:
            data[field] = _encrypt_secret(str(value))
    return data


def _effective_flat(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Hợp nhất flat đã lưu (nếu có) lên trên mặc định Settings hiện hành."""
    merged = _settings_to_dict()
    if stored:
        for field in model_config_field_names():
            if field in stored and stored[field] is not None:
                merged[field] = stored[field]
    return merged


async def _compose_runtime_state(db: AsyncSession) -> tuple[list[SystemModelChannel], FunctionBindings, dict[str, Any], AppSettings]:
    """Kênh runtime (key thật) + bindings + flat overlay."""
    app_row = await _get_or_create_app_row(db)
    await _ensure_bootstrapped_channels(db)
    channels = await _load_channels(db, runtime=True)
    config, changed = _migrate_legacy_config(dict(app_row.config_json or {}))
    if changed:
        app_row.config_json = config
        await db.flush()
    bindings = parse_function_bindings(config.get("function_bindings"))
    flat = _effective_flat(_decrypt_flat_config(config))
    return channels, bindings, flat, app_row


async def load_model_settings_cache(db: AsyncSession) -> None:
    """Nạp snapshot lúc khởi động / sau khi lưu."""
    channels, bindings, flat, _ = await _compose_runtime_state(db)
    await db.commit()
    _refresh_routing_snapshot(channels, bindings)
    _refresh_overlay({"flat": flat})
    reload_settings()


_CAP_LABEL = {"text": "Văn bản", "image": "Ảnh", "video": "Video", "audio": "Giọng đọc"}


def _build_readiness(bindings: FunctionBindings, channels: list[SystemModelChannel]) -> list[ModelCapabilityReadiness]:
    """Trạng thái 4 slot năng lực."""
    from app.services.function_router import allowed_bindings

    snap = RoutingSnapshot(channels=channels, function_bindings=bindings)
    items: list[ModelCapabilityReadiness] = []
    first_fn = {"text": "kepu.script", "image": "kepu.image", "video": "kepu.video", "audio": "kepu.tts"}
    for cap, label in _CAP_LABEL.items():
        assigned = bindings.slots.get(cap) or []
        usable = allowed_bindings(first_fn[cap], snapshot=snap) if assigned else []
        model = usable[0].model if usable else (assigned[0].model if assigned else "")
        if not assigned:
            msg = "Chưa gán model cho slot này"
        elif not usable:
            msg = "Model đã gán tạm không dùng được (provider tắt hoặc thiếu key)"
        else:
            msg = f"{len(usable)} model sẵn sàng"
        items.append(ModelCapabilityReadiness(capability=cap, label=label, model=model, ready=bool(usable), message=msg))
    return items


def _to_admin_flat_out(
    flat: dict[str, Any],
    *,
    source: str,
    updated_at: Any,
    channels: list[SystemModelChannel],
    bindings: FunctionBindings,
) -> AdminModelSettingsOut:
    """Chuyển flat dict + readiness theo bindings thành payload admin (khoá bị che theo cờ has_*)."""
    payload = {field: flat.get(field) for field in model_config_field_names()}
    for field, flag in SECRET_FIELD_FLAGS.items():
        payload[field] = ""
        payload[flag] = bool(str(flat.get(field) or "").strip())
    payload["source"] = source
    payload["updated_at"] = updated_at
    payload["readiness"] = _build_readiness(bindings, channels)
    return AdminModelSettingsOut.model_validate(payload)


async def get_admin_model_settings(db: AsyncSession) -> AdminModelSettingsOut:
    """Đọc cấu hình flat hiện hành (DB ưu tiên, env dự phòng) kèm readiness theo slot chức năng."""
    channels, bindings, flat, app_row = await _compose_runtime_state(db)
    admin_channels = await _load_channels(db, runtime=False)
    source = "db" if app_row.config_json else "env"
    return _to_admin_flat_out(flat, source=source, updated_at=app_row.updated_at, channels=admin_channels, bindings=bindings)


async def get_admin_routing_settings(db: AsyncSession) -> AdminRoutingSettingsOut:
    """Toàn bộ cấu hình routing cho admin: provider, function_bindings, readiness, danh mục chức năng, preset."""
    from app.services.functions import function_catalog_payload
    from app.services.providers.presets import PROVIDER_PRESETS

    channels, bindings, _, app_row = await _compose_runtime_state(db)
    admin_channels = await _load_channels(db, runtime=False)
    return AdminRoutingSettingsOut(
        providers=admin_channels, function_bindings=bindings,
        readiness=_build_readiness(bindings, channels),
        function_catalog=[FunctionInfo(**row) for row in function_catalog_payload()],
        presets=PROVIDER_PRESETS, validation_errors=validate_function_bindings(bindings, admin_channels),
        updated_at=app_row.updated_at,
    )


async def patch_admin_routing_settings(
    db: AsyncSession,
    body: AdminRoutingSettingsPatch,
) -> tuple[AdminRoutingSettingsOut, list[str]]:
    """Lưu danh sách provider (thay thế toàn bộ) và/hoặc function_bindings; validate trước khi commit."""
    app_row = await _get_or_create_app_row(db)
    applied: list[str] = []
    existing = {row.id: row for row in (await db.execute(select(SystemModelChannelRow))).scalars().all()}
    if body.providers is not None:
        keep: set[str] = set()
        for idx, item in enumerate(body.providers):
            cid = (item.id or "").strip()
            if not cid or not (item.name or "").strip():
                raise ValueError("Provider cần có id và tên")
            if (item.protocol or "auto") not in ("openai", "ark", "volc_tts"):
                raise ValueError(f"Provider {item.name}: protocol không hỗ trợ")
            row = existing.get(cid) or SystemModelChannelRow(id=cid)
            prev_key = _decrypt_secret(row.api_key_ciphertext or "") if row.api_key_ciphertext else ""
            key = "" if item.clear_api_key else (str(item.api_key).strip() if item.api_key and str(item.api_key).strip() else prev_key)
            row.name = item.name.strip(); row.base_url = (item.base_url or "").strip().rstrip("/")
            row.api_key_ciphertext = _encrypt_secret(key) if key else None
            row.protocol = item.protocol; row.api_format = "ark" if item.protocol == "ark" else "openai"
            row.models = list(dict.fromkeys(m.strip() for m in item.models if m and m.strip()))
            row.enabled = bool(item.enabled); row.sort_order = idx; row.advanced_config = None
            db.add(row); keep.add(cid)
        for cid, row in existing.items():
            if cid not in keep:
                await db.delete(row)
        await db.flush()
        applied.append("providers")
    config, _ = _migrate_legacy_config(dict(app_row.config_json or {}))
    bindings = parse_function_bindings(config.get("function_bindings"))
    if body.function_bindings is not None:
        bindings = parse_function_bindings(body.function_bindings.model_dump())
        applied.append("function_bindings")
    admin_channels = await _load_channels(db, runtime=False)
    errors = validate_function_bindings(bindings, admin_channels)
    if errors:
        raise ValueError("; ".join(errors[:5]))
    config["function_bindings"] = bindings_to_dict(bindings)
    if "flat" not in config:
        config["flat"] = _encrypt_flat_config(_settings_to_dict())
    app_row.config_json = config
    await db.commit()
    await load_model_settings_cache(db)
    return await get_admin_routing_settings(db), applied


async def patch_admin_model_settings(
    db: AsyncSession,
    body: AdminModelSettingsPatch,
) -> tuple[AdminModelSettingsOut, list[str]]:
    """Cập nhật một phần cấu hình flat (giá trị rỗng nghĩa là không đổi; clear_* để xoá khoá)."""
    app_row = await _get_or_create_app_row(db)
    config = dict(app_row.config_json or {})
    stored_flat = _decrypt_flat_config(config)
    current = _effective_flat(stored_flat if stored_flat else None)
    patch = body.model_dump(exclude_unset=True)
    applied: list[str] = []

    for field in SECRET_FIELDS:
        clear_flag = f"clear_{field}"
        if patch.pop(clear_flag, False):
            current[field] = ""
            applied.append(clear_flag)
        value = patch.pop(field, None)
        if value is not None and str(value).strip():
            current[field] = str(value).strip()
            applied.append(field)

    for field, value in patch.items():
        if value is None:
            continue
        current[field] = value
        applied.append(field)

    config["flat"] = _encrypt_flat_config(current)
    app_row.config_json = config
    await db.commit()
    await load_model_settings_cache(db)
    channels, bindings, flat, app_row = await _compose_runtime_state(db)
    admin_channels = await _load_channels(db, runtime=False)
    return _to_admin_flat_out(flat, source="db", updated_at=app_row.updated_at, channels=admin_channels, bindings=bindings), applied


def _flat_from_env_settings() -> dict[str, Any]:
    """Đọc trực tiếp process env / .env (không qua overlay DB)."""
    env = Settings()
    return {field: getattr(env, field) for field in model_config_field_names()}


async def import_admin_model_settings_from_env(
    db: AsyncSession,
) -> tuple[AdminModelSettingsOut, list[str], list[str]]:
    """将 .env 中可管理字段写入 app_settings.flat（密钥加密存库）。"""
    app_row = await _get_or_create_app_row(db)
    config = dict(app_row.config_json or {})
    current = _effective_flat(_decrypt_flat_config(config))
    env_flat = _flat_from_env_settings()
    imported: list[str] = []
    skipped_secrets: list[str] = []

    for field in model_config_field_names():
        value = env_flat[field]
        if field in SECRET_FIELDS:
            if not str(value or "").strip():
                skipped_secrets.append(field)
                continue
        current[field] = value
        imported.append(field)

    config["flat"] = _encrypt_flat_config(current)
    app_row.config_json = config
    await db.commit()
    await load_model_settings_cache(db)
    channels, bindings, flat, app_row = await _compose_runtime_state(db)
    admin_channels = await _load_channels(db, runtime=False)
    out = _to_admin_flat_out(
        flat,
        source="db",
        updated_at=app_row.updated_at,
        channels=admin_channels,
        bindings=bindings,
    )
    logger.info("imported %d fields from env, skipped %d empty secrets", len(imported), len(skipped_secrets))
    return out, imported, skipped_secrets
