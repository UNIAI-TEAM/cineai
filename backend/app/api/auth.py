from fastapi import APIRouter, Depends, File, UploadFile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.models import User, WalletLedger
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services import storage
from app.services.auth import (
    create_access_token,
    get_user_by_email,
    hash_password,
    verify_password,
)
from app.services.password_reset import (
    InvalidTokenError,
    RedisUnavailableError,
    apply_password_reset,
    request_password_reset,
)
from app.services.profile import prepare_profile_update

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise AppError("auth.email_registered")
    grant = int(settings.billing_signup_grant_fen or 0)
    user = User(
        email=body.email.lower(),
        nickname=body.nickname,
        hashed_password=hash_password(body.password),
        quota_left=settings.new_user_quota,
        balance_fen=grant,
        plan="free",
    )
    db.add(user)
    await db.flush()
    if grant > 0:
        db.add(
            WalletLedger(
                user_id=user.id,
                delta_fen=grant,
                balance_after=grant,
                kind="grant",
                ref_type="signup",
                ref_id=str(user.id),
                note="signup_grant",
            )
        )
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await get_user_by_email(db, body.email.lower())
    if not user or not verify_password(body.password, user.hashed_password):
        raise AppError("auth.invalid_credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """校验当前密码后写入新密码。"""
    if not verify_password(body.current_password, user.hashed_password):
        raise AppError("auth.wrong_current_password")
    if body.current_password == body.new_password:
        raise AppError("auth.same_password")
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """发送密码重置邮件；统一成功文案，避免邮箱枚举。"""
    try:
        return await request_password_reset(db, str(body.email))
    except RedisUnavailableError as exc:
        raise AppError("auth.service_unavailable") from exc


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """用邮件中的一次性 token 设置新密码。"""
    try:
        await apply_password_reset(db, token=body.token, new_password=body.new_password)
    except RedisUnavailableError as exc:
        raise AppError("auth.service_unavailable") from exc
    except InvalidTokenError as exc:
        raise AppError("auth.reset_token_invalid") from exc
    return {"ok": True}


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """更新当前用户的用户名、登录邮箱与联系手机号（仅记录，无验证码）。"""
    fields = prepare_profile_update(
        nickname=body.nickname,
        email=body.email,
        phone=body.phone,
    )

    if fields["email"] != user.email:
        taken = await get_user_by_email(db, fields["email"])
        if taken and taken.id != user.id:
            raise AppError("auth.email_taken")

    user.nickname = fields["nickname"]
    user.email = fields["email"]
    user.phone = fields["phone"]
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Upload or replace the current user's profile avatar."""
    content_type = (file.content_type or "").lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    ext = allowed.get(content_type)
    if not ext:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            ext = ".jpg" if suffix == ".jpeg" else suffix
        else:
            raise AppError("common.unsupported_image_type")

    raw = await file.read()
    if not raw:
        raise AppError("common.empty_file")
    if len(raw) > 5 * 1024 * 1024:
        raise AppError("common.file_too_large", max_mb=5)

    dest = storage.user_dir(user.id) / f"avatar{ext}"
    dest.write_bytes(raw)
    user.avatar_url = storage.publish_local(dest)
    await db.commit()
    await db.refresh(user)
    return user
