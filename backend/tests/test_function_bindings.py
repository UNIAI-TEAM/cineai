"""function_bindings: parse chịu lỗi, override kế thừa slot, validate tiếng Việt."""
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import function_bindings as fb


def _ch(cid="byteplus", models=("dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"), enabled=True, key=True, protocol="ark"):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key="k" if key else "", has_api_key=key,
                              protocol=protocol, models=list(models), enabled=enabled)


def test_parse_tolerates_garbage():
    assert fb.parse_function_bindings(None) == FunctionBindings()
    out = fb.parse_function_bindings({"slots": {"image": [{"channel_id": "a", "model": "m"}], "nope": []}, "overrides": {"zzz": []}})
    assert out.slots["image"][0].weight == 1 and "nope" not in out.slots and "zzz" not in out.overrides


def test_effective_override_then_slot():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="a", model="s")]},
                         overrides={"tools.image": [ModelBinding(channel_id="o", model="g")]})
    assert [x.model for x in fb.effective_bindings(b, "tools.image")] == ["g"]
    assert [x.model for x in fb.effective_bindings(b, "kepu.image")] == ["s"]
    assert fb.effective_bindings(b, "kepu.video") == []


def test_validate_ok():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]})
    assert fb.validate_function_bindings(b, [_ch()]) == []


def test_validate_reports_unknown_channel_model_and_capability():
    b = FunctionBindings(slots={
        "image": [ModelBinding(channel_id="ghost", model="x")],
        "video": [ModelBinding(channel_id="byteplus", model="not-enabled")],
        "text": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")],
    })
    errs = fb.validate_function_bindings(b, [_ch()])
    assert any("ghost" in e for e in errs)
    assert any("not-enabled" in e for e in errs)
    assert any("Văn bản" in e and "dola-seedream" in e for e in errs)


def test_validate_unknown_override_function():
    b = FunctionBindings(overrides={"foo.bar": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]})
    assert any("foo.bar" in e for e in fb.validate_function_bindings(b, [_ch()]))


def test_slot_assigned():
    b = FunctionBindings(slots={"audio": [ModelBinding(channel_id="a", model="m")]})
    assert fb.slot_assigned(b, "audio") and not fb.slot_assigned(b, "image")


def test_parse_tolerates_wrong_typed_slots_and_overrides():
    assert fb.parse_function_bindings({"slots": "garbage", "overrides": ["a", "b"]}) == FunctionBindings()


def test_validate_reports_unknown_slot_key_without_raising():
    b = FunctionBindings(slots={"junk": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]})
    errs = fb.validate_function_bindings(b, [_ch()])
    assert any("junk" in e for e in errs)


def test_validate_messages_match_admin_mirror_wording():
    """Câu lỗi hiện nguyên văn ở tab Mô hình: dùng "nhà cung cấp", khớp validateBindingsDraft của admin."""
    b = FunctionBindings(slots={
        "image": [ModelBinding(channel_id="ghost", model="x")],
        "video": [ModelBinding(channel_id="byteplus", model="not-enabled")],
    })
    errs = fb.validate_function_bindings(b, [_ch()])
    assert "Slot Ảnh: nhà cung cấp 'ghost' không tồn tại" in errs
    assert "Slot Video: model 'not-enabled' chưa được bật ở nhà cung cấp byteplus" in errs
    assert not any("provider" in e for e in errs)
