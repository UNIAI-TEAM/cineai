"""MediaGateway: chọn adapter theo route, failover lúc tạo, lưu ảnh base64/URL, poll đúng kênh, mock."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.errors import AppError
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import media_gateway as mg
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot
from app.services.providers import base


def _ch(cid, protocol, models):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key="k", has_api_key=True, protocol=protocol, models=models, enabled=True)


@pytest.fixture
def snapshot():
    prev = get_routing_snapshot()
    b = FunctionBindings(slots={
        "image": [ModelBinding(channel_id="byteplus", model="seedream-4-5-251128"), ModelBinding(channel_id="openai", model="gpt-image-2")],
        "video": [ModelBinding(channel_id="byteplus", model="dreamina-seedance-2-5-260628")],
    })
    _refresh_routing_snapshot([_ch("byteplus", "ark", ["seedream-4-5-251128", "dreamina-seedance-2-5-260628"]), _ch("openai", "openai", ["gpt-image-2"])], b)
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


class _FakeAdapter:
    def __init__(self, protocol, *, image=None, image_exc=None, task_id="cgt-1", fetch=None):
        self.protocol, self.image, self.image_exc, self.task_id, self.fetch = protocol, image, image_exc, task_id, fetch
        self.calls = []
    async def gen_image(self, route, req):
        self.calls.append(("image", route.upstream_model, req))
        if self.image_exc: raise self.image_exc
        return self.image
    async def create_video(self, route, req):
        self.calls.append(("video", route.upstream_model, req)); return self.task_id
    async def fetch_video(self, route, task_id):
        self.calls.append(("fetch", route.channel_id, task_id)); return self.fetch
    def is_transient_error(self, exc): return isinstance(exc, base.TransientUpstreamError)
    def url_needs_auth(self, url): return False
    def cost_fen(self, model, raw): return None


def _gateway(monkeypatch, adapters):
    monkeypatch.setattr(mg, "get_adapter", lambda proto: adapters[proto])
    g = mg.MediaGateway(SimpleNamespace(ark_mock=False, ark_image_size="2k", ark_video_poll_timeout=5.0, ark_video_poll_interval=0.0,
                                        seedance_duration_min=4, seedance_duration_max=30, ffmpeg_path="ffmpeg"))
    monkeypatch.setattr(mg.MediaGateway, "mock", property(lambda self: False))
    return g


async def test_gen_image_saves_bytes_and_records_channel(monkeypatch, snapshot, tmp_path):
    ark = _FakeAdapter("ark", image=base.ImageOutput(url="https://cdn/a.jpg", size="2K", raw_usage={"total_tokens": 5}, total_tokens=5))
    oai = _FakeAdapter("openai", image=base.ImageOutput(data=b"\x89PNG", size="1024x1024"))
    g = _gateway(monkeypatch, {"ark": ark, "openai": oai})
    monkeypatch.setattr(mg.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(mg.storage, "publish_local", lambda p, sync=False: f"/static/{p.name}")
    async def _dl(url, dest, headers=None, timeout=None): dest.write_bytes(b"jpg")
    monkeypatch.setattr(mg.storage, "download_to", _dl)

    out = await g.gen_image("mèo", function_id="kepu.image", model="gpt-image-2", project_id=1, shot_no=2)
    assert out.channel_id == "openai" and out.model == "gpt-image-2" and out.local_url.startswith("/static/shot_002_")
    assert (tmp_path / out.local_url.split("/")[-1]).read_bytes() == b"\x89PNG"
    out2 = await g.gen_image("mèo", function_id="kepu.image", model="seedream-4-5-251128", project_id=1, shot_no=3)
    assert out2.channel_id == "byteplus" and out2.remote_url == "https://cdn/a.jpg" and out2.total_tokens == 5


async def test_gen_image_failover_on_transient(monkeypatch, snapshot, tmp_path):
    ark = _FakeAdapter("ark", image_exc=base.TransientUpstreamError("503"))
    oai = _FakeAdapter("openai", image=base.ImageOutput(data=b"x", size="1024x1024"))
    g = _gateway(monkeypatch, {"ark": ark, "openai": oai})
    monkeypatch.setattr(mg.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(mg.storage, "publish_local", lambda p, sync=False: f"/static/{p.name}")
    out = await g.gen_image("p", function_id="kepu.image", model="seedream-4-5-251128")
    assert out.channel_id == "openai" and len(ark.calls) == 1 and len(oai.calls) == 1


async def test_gen_image_no_failover_on_policy_error(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", image_exc=RuntimeError("InputTextSensitive"))
    oai = _FakeAdapter("openai")
    g = _gateway(monkeypatch, {"ark": ark, "openai": oai})
    with pytest.raises(RuntimeError):
        await g.gen_image("p", function_id="kepu.image", model="seedream-4-5-251128")
    assert oai.calls == []


async def test_gen_image_unconfigured_slot_raises_app_error(monkeypatch):
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([], FunctionBindings())        # chưa gán gì
    try:
        g = _gateway(monkeypatch, {})
        with pytest.raises(AppError) as exc:
            await g.gen_image("p", function_id="kepu.image")
        assert exc.value.code == "model.slot_not_configured"
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_gen_image_disallowed_model_raises(monkeypatch, snapshot):
    g = _gateway(monkeypatch, {})
    with pytest.raises(AppError) as exc:
        await g.gen_image("p", function_id="kepu.image", model="not-listed")
    assert exc.value.code == "model.not_available"


async def test_gen_video_i2v_builds_ark_body_and_remembers_channel(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", task_id="cgt-9")
    g = _gateway(monkeypatch, {"ark": ark})
    async def _ref(url, *, prefer_https=False): return "https://pub/f.png"
    monkeypatch.setattr(g, "_resolve_image_ref", _ref)
    task_id = await g.gen_video_i2v("/static/f.png", "cảnh", 8, function_id="kepu.video", ratio="9:16", resolution="720p", generate_audio=True)
    assert task_id == "cgt-9" and g.channel_for_task("cgt-9") == "byteplus"
    kind, model, req = ark.calls[0]
    assert model == "dreamina-seedance-2-5-260628"
    assert req.body["content"][1] == {"type": "image_url", "image_url": {"url": "https://pub/f.png"}, "role": "reference_image"}
    assert req.body["ratio"] == "9:16" and req.target_ratio == "9:16" and req.allow_structure_fallback is True
    assert req.body["duration"] == 8 and req.body["resolution"] == "720p" and req.body["generate_audio"] is True
    assert req.plain_text == "cảnh" and req.body["content"][0]["text"].startswith("{")


async def test_gen_video_i2v_uses_requested_model(monkeypatch, snapshot):
    ark = _FakeAdapter("ark")
    g = _gateway(monkeypatch, {"ark": ark})
    async def _ref(url, *, prefer_https=False): return "https://pub/f.png"
    monkeypatch.setattr(g, "_resolve_image_ref", _ref)
    with pytest.raises(AppError):
        await g.gen_video_i2v("u", "p", 5, function_id="kepu.video", model="not-listed")
    await g.gen_video_i2v("u", "p", 5, function_id="kepu.video", model="dreamina-seedance-2-5-260628")
    assert ark.calls[0][1] == "dreamina-seedance-2-5-260628"


async def test_fetch_task_once_uses_channel_id(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", fetch=base.TaskResult(status="running"))
    g = _gateway(monkeypatch, {"ark": ark})
    r = await g.fetch_task_once("cgt-1", channel_id="byteplus")
    assert r.status == "running" and ark.calls[0] == ("fetch", "byteplus", "cgt-1")


async def test_fetch_task_once_falls_back_to_video_slot(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", fetch=base.TaskResult(status="succeeded", url="https://v/1.mp4"))
    g = _gateway(monkeypatch, {"ark": ark})
    r = await g.fetch_task_once("cgt-old")
    assert r.status == "succeeded" and ark.calls[0][1] == "byteplus"


async def test_fetch_task_once_mock_id(monkeypatch, snapshot):
    g = _gateway(monkeypatch, {})
    r = await g.fetch_task_once("mock-task-abc12345")
    assert r.status == "succeeded" and r.url.startswith("/static/mock/video_")


@pytest.fixture
def two_video_channels():
    """Slot video có 2 binding trên 2 provider → bộc lộ mọi lựa chọn provider ngẫu nhiên."""
    prev = get_routing_snapshot()
    b = FunctionBindings(slots={"video": [
        ModelBinding(channel_id="ark-a", model="dreamina-seedance-2-5-260628"),
        ModelBinding(channel_id="ark-b", model="dreamina-seedance-2-0-260128"),
    ]})
    _refresh_routing_snapshot(
        [_ch("ark-a", "ark", ["dreamina-seedance-2-5-260628"]), _ch("ark-b", "ark", ["dreamina-seedance-2-0-260128"])], b)
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_fetch_task_once_fallback_picks_same_channel_every_time(monkeypatch, two_video_channels):
    """Không biết kênh: luôn hỏi binding đầu của slot, không xáo theo weight."""
    ark = _FakeAdapter("ark", fetch=base.TaskResult(status="running"))
    g = _gateway(monkeypatch, {"ark": ark})
    for _ in range(8):
        await g.fetch_task_once("cgt-x")
    assert [c[1] for c in ark.calls] == ["ark-a"] * 8


async def test_poll_task_keeps_one_channel_across_iterations(monkeypatch, two_video_channels):
    """poll_task chốt provider một lần: mọi vòng lặp đều hỏi đúng kênh đó."""
    seq = [base.TaskResult(status="running"), base.TaskResult(status="running"),
           base.TaskResult(status="succeeded", url="/static/mock/v.mp4")]
    ark = _FakeAdapter("ark")
    async def _fetch(route, task_id):
        ark.calls.append(("fetch", route.channel_id, task_id))
        return seq.pop(0)
    ark.fetch_video = _fetch
    g = _gateway(monkeypatch, {"ark": ark})
    result = await g.poll_task("cgt-y")
    assert result.status == "succeeded"
    assert [c[1] for c in ark.calls] == ["ark-a", "ark-a", "ark-a"]


async def test_gen_video_seedance_body_gates_requested_model(monkeypatch, snapshot):
    """model trong body chỉ là gợi ý: không được gán thì slot quyết định, được gán thì dùng đúng."""
    ark = _FakeAdapter("ark", task_id="cgt-s1")
    g = _gateway(monkeypatch, {"ark": ark})
    task_id = await g.gen_video_seedance_body({"model": "not-listed", "duration": 8, "content": []},
                                              function_id="drama.video")
    assert task_id == "cgt-s1" and ark.calls[0][1] == "dreamina-seedance-2-5-260628"
    assert g.channel_for_task("cgt-s1") == "byteplus"

    ark.task_id = "cgt-s2"
    await g.gen_video_seedance_body({"model": "dreamina-seedance-2-5-260628", "duration": 8, "content": []},
                                    function_id="drama.video")
    _kind, model, req = ark.calls[1]
    assert model == "dreamina-seedance-2-5-260628"
    assert req.allow_structure_fallback is False and req.body["duration"] == 8


async def test_gen_and_wait_seedance_body_retries_once_without_audio(monkeypatch, snapshot):
    """Lỗi tải reference_audio: bỏ audio gửi lại đúng một lần, không có lần thứ ba."""
    audio_err = "upstream failure: audio_url resource download failed at task start"
    body = {"content": [
        {"type": "text", "text": "镜头画面：星空\n参考音频：素材一\n角色音色：旁白A"},
        {"type": "audio_url", "role": "reference_audio", "audio_url": {"url": "https://x/a.mp3"}},
    ]}
    g = _gateway(monkeypatch, {})
    submitted: list[dict] = []
    waited: list[str] = []

    async def _submit(payload, **kwargs):
        submitted.append(payload)
        return f"t{len(submitted)}"

    async def _wait(task_id, **kwargs):
        waited.append(task_id)
        if len(waited) == 1:
            raise RuntimeError(audio_err)
        return "/static/x.mp4", None, base.TaskResult(status="succeeded", url="https://x/v.mp4")

    monkeypatch.setattr(g, "gen_video_seedance_body", _submit)
    monkeypatch.setattr(g, "wait_video_assets", _wait)
    video_url, _last, result = await g.gen_and_wait_seedance_body(body, project_id=1, shot_no=2)
    assert video_url == "/static/x.mp4" and result.status == "succeeded"
    assert len(submitted) == 2 and waited == ["t1", "t2"]
    assert not any(item.get("type") == "audio_url" for item in submitted[1]["content"])


async def test_gen_and_wait_seedance_body_never_submits_a_third_time(monkeypatch, snapshot):
    """Bỏ audio rồi vẫn lỗi: tối đa hai lần gửi, tuyệt đối không có lần thứ ba (tránh tính phí lặp)."""
    audio_err = "upstream failure: audio_url resource download failed at task start"
    body = {"content": [
        {"type": "text", "text": "镜头画面：星空"},
        {"type": "audio_url", "role": "reference_audio", "audio_url": {"url": "https://x/a.mp3"}},
    ]}
    g = _gateway(monkeypatch, {})
    submitted: list[dict] = []

    async def _submit(payload, **kwargs):
        submitted.append(payload)
        return f"t{len(submitted)}"

    async def _wait(task_id, **kwargs):
        raise RuntimeError(audio_err)

    monkeypatch.setattr(g, "gen_video_seedance_body", _submit)
    monkeypatch.setattr(g, "wait_video_assets", _wait)
    with pytest.raises(RuntimeError, match="resource download failed"):
        await g.gen_and_wait_seedance_body(body, project_id=1, shot_no=2)
    assert len(submitted) == 2


async def test_gen_and_wait_video_passes_model(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", task_id="cgt-2", fetch=base.TaskResult(status="succeeded", url="/static/mock/v.mp4"))
    g = _gateway(monkeypatch, {"ark": ark})
    async def _ref(url, *, prefer_https=False): return "https://pub/f.png"
    monkeypatch.setattr(g, "_resolve_image_ref", _ref)
    local, result = await g.gen_and_wait_video("u", "p", 5, function_id="kepu.video", project_id=1, shot_no=1, model="dreamina-seedance-2-5-260628")
    assert local == "/static/mock/v.mp4" and ark.calls[0][1] == "dreamina-seedance-2-5-260628" and result.channel_id == "byteplus"


def _mock_gateway(monkeypatch):
    """Gateway chạy mock (ARK_MOCK) nhưng vẫn có snapshot routing: không ghi file ảnh giả."""
    g = mg.MediaGateway(SimpleNamespace(ark_mock=True, ark_image_size="2k", ark_video_poll_timeout=5.0, ark_video_poll_interval=0.0,
                                        seedance_duration_min=4, seedance_duration_max=30, ffmpeg_path="ffmpeg"))
    monkeypatch.setattr(mg.MediaGateway, "mock", property(lambda self: True))
    monkeypatch.setattr(g, "_write_mock_image", lambda prompt, size: "/static/mock/none.png")
    return g


async def test_mock_image_result_carries_bound_model(monkeypatch, snapshot):
    """B1: kết quả mock ghi model/kênh theo binding để dòng usage có nhãn model đúng."""
    g = _mock_gateway(monkeypatch)
    r = await g.gen_image("p", function_id="kepu.image")
    assert (r.channel_id, r.model) == ("byteplus", "seedream-4-5-251128")
    r2 = await g.gen_image("p", function_id="kepu.image", model="gpt-image-2")
    assert (r2.channel_id, r2.model) == ("openai", "gpt-image-2")


async def test_mock_image_without_binding_keeps_empty_model(monkeypatch):
    """Chưa gán slot (mock vì thiếu key): vẫn trả ảnh giả, model để trống."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([], FunctionBindings())
    try:
        r = await _mock_gateway(monkeypatch).gen_image("p", function_id="kepu.image")
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
    assert r.model == "" and r.local_url


async def test_mock_video_task_result_carries_bound_model(monkeypatch, snapshot):
    """B1: tác vụ video mock nhớ model lúc tạo, kết quả poll trả đúng model/kênh."""
    g = _mock_gateway(monkeypatch)
    task_id = await g.gen_video_i2v("https://x/a.jpg", "move", 5, function_id="kepu.video")
    r = await g.fetch_task_once(task_id)
    assert r.status == "succeeded" and (r.channel_id, r.model) == ("byteplus", "dreamina-seedance-2-5-260628")
    task2 = await g.gen_video_seedance_body({"content": [], "duration": 5}, function_id="drama.video")
    r2 = await g.poll_task(task2)
    assert r2.model == "dreamina-seedance-2-5-260628"


async def test_resolve_image_ref_seedance_uses_https_site_url_without_oss(monkeypatch, tmp_path):
    """Tắt OSS nhưng PUBLIC_BASE_URL là https công khai: Seedance nhận link site /static thay vì báo lỗi."""
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    g = _gateway(monkeypatch, {})
    monkeypatch.setattr(mg.storage, "local_path_from_url", lambda url: img)
    monkeypatch.setattr(mg.storage, "republish_url", lambda url, sync=True: url)
    monkeypatch.setattr(mg.storage, "to_public_url", lambda url: "https://cineai.vn" + url)
    assert await g._resolve_image_ref("/static/generated/p7/a.png", prefer_https=True) == "https://cineai.vn/static/generated/p7/a.png"


async def test_resolve_image_ref_seedance_still_fails_on_local_site_without_oss(monkeypatch, tmp_path):
    """Tắt OSS và PUBLIC_BASE_URL là localhost: vẫn báo lỗi rõ ràng, không gửi link Ark không tải được."""
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    g = _gateway(monkeypatch, {})
    monkeypatch.setattr(mg.storage, "local_path_from_url", lambda url: img)
    monkeypatch.setattr(mg.storage, "republish_url", lambda url, sync=True: url)
    monkeypatch.setattr(mg.storage, "to_public_url", lambda url: "http://127.0.0.1:8000" + url)
    with pytest.raises(mg.UpstreamError):
        await g._resolve_image_ref("/static/generated/p7/a.png", prefer_https=True)
