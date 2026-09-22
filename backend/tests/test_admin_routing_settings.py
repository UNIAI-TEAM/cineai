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
