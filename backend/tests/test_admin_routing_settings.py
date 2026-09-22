"""PATCH /settings/routing: thêm provider, gán slot, lỗi validation; kênh tokenfree cũ bị xoá."""
import pytest
from sqlalchemy import select

from app import config as config_module
from app.models_settings import SystemModelChannelRow
from app.schemas_routing import AdminRoutingSettingsPatch, FunctionBindings, ModelBinding, SystemModelChannelIn
from app.services import model_settings as ms


@pytest.fixture(autouse=True)
def _isolate_global_routing_state() -> None:
    """Các hàm patch_*/load_model_settings_cache ghi đè `_overlay`/`_routing_snapshot` toàn process;
    khôi phục sau mỗi test để không rò rỉ sang các file test khác (vd. test_model_settings_overlay.py)."""
    saved_overlay = dict(ms._overlay)
    saved_snapshot = ms.get_routing_snapshot()
    yield
    ms._overlay.clear()
    ms._overlay.update(saved_overlay)
    ms._refresh_routing_snapshot(saved_snapshot.channels, saved_snapshot.function_bindings)
    config_module.get_settings.cache_clear()


async def test_patch_creates_two_providers_and_bindings(db_session):
    body = AdminRoutingSettingsPatch(
        providers=[
            SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-1", protocol="openai", models=["gpt-5.6-sol"]),
            SystemModelChannelIn(id="byteplus", name="BytePlus", base_url="https://ark.ap-southeast.bytepluses.com/api/v3", api_key="ak-1", protocol="ark", models=["dola-seedream-5-0-pro-260628"]),
        ],
        function_bindings=FunctionBindings(slots={"text": [ModelBinding(channel_id="openai", model="gpt-5.6-sol")],
                                                  "image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]}),
    )
    out, applied = await ms.patch_admin_routing_settings(db_session, body)
    assert set(applied) == {"providers", "function_bindings"}
    assert {p.id for p in out.providers} == {"openai", "byteplus"}
    assert all(p.api_key == "" and p.has_api_key for p in out.providers)      # key bị che
    assert out.function_bindings.slots["image"][0].channel_id == "byteplus"
    snap = ms.get_routing_snapshot()
    assert {c.id for c in snap.channels} == {"openai", "byteplus"} and snap.channels[0].api_key


async def test_patch_rejects_binding_to_unknown_model(db_session):
    body = AdminRoutingSettingsPatch(
        providers=[SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk", protocol="openai", models=["gpt-5.6-sol"])],
        function_bindings=FunctionBindings(slots={"text": [ModelBinding(channel_id="openai", model="gpt-9")]}),
    )
    with pytest.raises(ValueError) as exc:
        await ms.patch_admin_routing_settings(db_session, body)
    assert "gpt-9" in str(exc.value)


async def test_patch_removes_provider_not_in_list_and_blank_key_keeps_old(db_session):
    first = AdminRoutingSettingsPatch(providers=[
        SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-old", protocol="openai", models=["gpt-5.6-sol"]),
        SystemModelChannelIn(id="tmp", name="Tmp", base_url="https://x/v1", api_key="k", protocol="openai", models=["m"]),
    ])
    await ms.patch_admin_routing_settings(db_session, first)
    second = AdminRoutingSettingsPatch(providers=[
        SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key=None, protocol="openai", models=["gpt-5.6-sol"]),
    ])
    await ms.patch_admin_routing_settings(db_session, second)
    rows = {r.id: r for r in (await db_session.execute(select(SystemModelChannelRow))).scalars().all()}
    assert "tmp" not in rows
    assert ms._decrypt_secret(rows["openai"].api_key_ciphertext) == "sk-old"


async def test_legacy_tokenfree_row_is_deleted_on_load(db_session):
    db_session.add(SystemModelChannelRow(id="tokenfree", name="TokenFree", base_url="https://www.tokenfree.com/v1", protocol="auto", models=["kimi-k2.6"], enabled=True))
    await db_session.flush()
    await ms.load_model_settings_cache(db_session)
    rows = (await db_session.execute(select(SystemModelChannelRow.id))).scalars().all()
    assert "tokenfree" not in rows


async def test_patch_rejects_duplicate_provider_id_in_same_body(db_session):
    body = AdminRoutingSettingsPatch(providers=[
        SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-1", protocol="openai", models=["gpt-5.6-sol"]),
        SystemModelChannelIn(id="openai", name="OpenAI Dup", base_url="https://api.openai.com/v1", api_key="sk-2", protocol="openai", models=["gpt-5.6-sol"]),
    ])
    with pytest.raises(ValueError) as exc:
        await ms.patch_admin_routing_settings(db_session, body)
    assert "openai" in str(exc.value)


# ---- I-1: seed provider từ env đúng một lần, không gửi key TokenFree sang BytePlus ----

from app.config import Settings  # noqa: E402
from app.models_settings import AppSettings  # noqa: E402


def _tokenfree_era_settings() -> Settings:
    """Env thời TokenFree: ARK_API_KEY là key TokenFree (không có ARK_BASE_URL), OPENAI_BASE_URL trỏ tokenfree.com."""
    return Settings(ark_api_key="tf-key", openai_api_key="tf-key", openai_base_url="https://www.tokenfree.com/v1",
                    volc_tts_api_key="", volc_tts_app_id="", volc_tts_access_key="",
                    model_llm="kimi-k2.6", model_image="seedream-5.0", model_video="seedance-2.5")


def _fresh_settings() -> Settings:
    """Env sạch của bản mới: key OpenAI + BytePlus thật."""
    return Settings(openai_api_key="sk-real", openai_base_url="https://api.openai.com/v1", ark_api_key="ak-real", volc_tts_api_key="", volc_tts_app_id="",
                    volc_tts_access_key="", model_llm="gpt-5.6-sol", model_image="dola-seedream-5-0-pro-260628",
                    model_video="dreamina-seedance-2-5-260628", model_audio="gpt-4o-mini-tts")


async def _channel_ids(db_session) -> list[str]:
    """Id các provider đang có trong DB."""
    return list((await db_session.execute(select(SystemModelChannelRow.id))).scalars().all())


async def test_upgrade_from_tokenfree_does_not_seed_env_keys(db_session, monkeypatch):
    """DB cũ có kênh tokenfree + env thời TokenFree: xoá kênh cũ, không seed byteplus/openai bằng key TokenFree."""
    fake = _tokenfree_era_settings()
    monkeypatch.setattr(ms, "get_settings", lambda: fake)
    db_session.add(AppSettings(id="default", config_json={"flat": {"openai_base_url": "https://www.tokenfree.com/v1"},
                                                          "logical_models": [{"id": "x"}]}))
    db_session.add(SystemModelChannelRow(id="tokenfree", name="TokenFree", base_url="https://www.tokenfree.com/v1",
                                         protocol="auto", models=["kimi-k2.6"], enabled=True))
    await db_session.flush()
    await ms.load_model_settings_cache(db_session)
    assert await _channel_ids(db_session) == []
    await ms.load_model_settings_cache(db_session)          # lần nạp sau cũng không seed lại
    assert await _channel_ids(db_session) == []
    row = await db_session.get(AppSettings, "default")
    assert row.config_json.get("providers_seeded") is True


async def test_seed_skips_tokenfree_base_url_and_seeds_once(db_session, monkeypatch):
    """DB trống: seed một lần; admin xoá hết provider thì lần nạp sau không seed lại từ env."""
    fake = _fresh_settings()
    monkeypatch.setattr(ms, "get_settings", lambda: fake)
    await ms.load_model_settings_cache(db_session)
    assert set(await _channel_ids(db_session)) == {"openai", "byteplus"}
    await ms.patch_admin_routing_settings(db_session, AdminRoutingSettingsPatch(providers=[], function_bindings=FunctionBindings()))
    await ms.load_model_settings_cache(db_session)
    assert await _channel_ids(db_session) == []


async def test_existing_provider_rows_count_as_seeded(db_session, monkeypatch):
    """DB đã có provider (chưa có cờ) được coi là đã seed: xoá hết rồi nạp lại cũng không seed từ env."""
    fake = _fresh_settings()
    monkeypatch.setattr(ms, "get_settings", lambda: fake)
    db_session.add(AppSettings(id="default", config_json={"flat": {}}))
    db_session.add(SystemModelChannelRow(id="mine", name="Mine", base_url="https://api.openai.com/v1", protocol="openai",
                                         models=["gpt-5.6-sol"], enabled=True))
    await db_session.flush()
    await ms.load_model_settings_cache(db_session)
    await ms.patch_admin_routing_settings(db_session, AdminRoutingSettingsPatch(providers=[], function_bindings=FunctionBindings()))
    await ms.load_model_settings_cache(db_session)
    assert await _channel_ids(db_session) == []


async def test_new_app_row_encrypts_env_secrets(db_session, monkeypatch):
    """I-6: tạo mới app_settings từ env thì các khoá bí mật trong flat phải được mã hoá, không lưu plaintext."""
    fake = _fresh_settings()
    monkeypatch.setattr(ms, "get_settings", lambda: fake)
    row = await ms._get_or_create_app_row(db_session)
    flat = row.config_json["flat"]
    assert flat["openai_api_key"].startswith(ms.ENCRYPTED_PREFIX)
    assert flat["ark_api_key"].startswith(ms.ENCRYPTED_PREFIX)
    assert ms._decrypt_flat_config(row.config_json)["ark_api_key"] == "ak-real"
