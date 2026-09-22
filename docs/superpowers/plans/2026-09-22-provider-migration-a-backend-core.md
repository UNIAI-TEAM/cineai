# Bỏ TokenFree — Plan A: Backend core (adapter + function router + poll theo kênh)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend gọi thẳng OpenAI + BytePlus ModelArk qua lớp adapter theo protocol, cấu hình bằng `function_bindings` (4 slot năng lực + override theo chức năng), poll video đúng kênh đã tạo; mọi module `tokenfree_*` runtime bị xoá.

**Architecture:** `app/services/providers/` chứa `base.py` (dataclass request/response, Protocol, registry) + `ark_adapter.py` / `openai_adapter.py` / `volc_tts_adapter.py`. `ark.py` (2 427 dòng) tách thành `kepu_text.py`, `tts_service.py`, `media_gateway.py` (facade mỏng, giữ nguyên tên hàm public) và `ark.py` chỉ còn shim re-export. `function_router.py` thay `logical_model_router.py`; `model_settings.py` bỏ khoá TokenFree, lưu `function_bindings` trong `app_settings.config_json`. `TaskRun.provider_channel_id` mới để poll đúng kênh.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async (asyncpg), httpx, pydantic v2, pytest (`asyncio_mode=auto`, `pythonpath=.`).

**Spec:** `docs/superpowers/specs/2026-09-22-provider-migration-design.md` (mục 4, 5, 8, 9.1). Plan B (billing) và Plan C (admin UI + frontend + docs) viết sau khi Plan A xong.

## Global Constraints

- Chạy lệnh trong `backend/`; test: `pytest tests/<file>.py -v`. Test có fixture `db_session` cần PostgreSQL (`deploy/docker-compose.yml`); còn lại thuần unit.
- Mọi hàm/class mới có một dòng comment/docstring mô tả chức năng (quy ước `docs/STANDARDS.md`). File mới ≤ 500 dòng.
- Thông điệp lỗi trả về user (`AppError`, `RuntimeError` hiển thị) là câu ngắn, không stack trace. Mã lỗi `AppError` mới phải thêm vào cả 3 file `frontend/src/i18n/locales/{zh,en,vi}/errors.ts` (test `tests/test_app_errors.py` kiểm tra).
- Không đổi tên field cấu hình `ark_*` / `openai_*` / `model_*` / `volc_tts_*` trong `config.py` (chỉ đổi giá trị mặc định).
- **Không xoá** `tokenfree_pricing.py`, `tokenfree_usage.py`, `tests/test_tokenfree_pricing.py`, `tests/test_tokenfree_usage.py`, `tests/test_admin_upstream_usage.py` trong plan này (Plan B xử lý billing). Xoá: `tokenfree_gateway.py`, `tokenfree_image.py`, `tokenfree_video.py`, `tokenfree_audio.py`, `logical_model_router.py`.
- Commit message tiếng Việt, kết thúc bằng dòng `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Không commit `.env`.
- Sau plan này tab "Mô hình" của admin **tạm không dùng được** (payload API đổi; Plan C viết lại UI). Cấu hình vẫn seed được từ `.env` hoặc `PATCH /api/admin/settings/routing`.
- Hoàn thành mỗi task: chạy `pytest -q -x --ignore=tests/test_tokenfree_pricing.py --ignore=tests/test_tokenfree_usage.py` (bỏ PG nếu không có DB: thêm `-k "not db_session"` không dùng được — thay bằng chạy các file thuần unit liệt kê trong task).

---

## Sơ đồ file

| File | Trách nhiệm | Task |
|---|---|---|
| `app/services/kepu_text.py` (mới) | `chat_storyboard`, `expand_content`, parser, mock kịch bản khoa học | 1 |
| `app/services/providers/__init__.py`, `base.py` (mới) | dataclass request/response, `TaskResult`, Protocol `ProviderAdapter`, helper timeout/transient, `get_adapter()`, `url_needs_auth()` | 2 |
| `app/services/providers/ark_adapter.py` (mới) | Ark/BytePlus: `/images/generations`, `/contents/generations/tasks`, rule Seedance, danh sách model tĩnh | 3 |
| `app/services/providers/openai_adapter.py` (mới) | OpenAI: `/images/generations|edits`, `/audio/speech`, `GET /models` | 4 |
| `app/services/providers/volc_tts_adapter.py` (mới) | BytePlus Seed Speech / Volc openspeech | 5 |
| `app/services/functions.py` (mới) | danh mục 10 chức năng | 6 |
| `app/schemas_routing.py` (sửa) | `ModelBinding`, `FunctionBindings`, `FunctionInfo`, `ProviderPreset`, payload admin mới; bỏ LogicalModel/DefaultModels | 6 |
| `app/services/function_bindings.py` (mới) | parse/validate/effective bindings (thuần) | 6 |
| `app/services/function_router.py` (mới) | resolve route theo function, weight, failover | 6 |
| `app/services/providers/presets.py` (mới) | preset provider cho admin | 7 |
| `app/services/model_settings.py` (sửa lớn) | snapshot `channels + function_bindings`, gỡ khoá, migration, seed env, admin GET/PATCH | 7 |
| `app/services/upstream_model_catalog.py`, `app/api/admin/settings.py`, `app/config.py`, `.env.example` (sửa) | catalog theo adapter, bỏ endpoint quota, mặc định mới | 7 |
| `app/services/media_gateway.py` (mới) | facade ảnh/video/poll/mock/lưu file; `channel_for_task()` | 8 |
| `app/services/tts_service.py` (mới) | cascade TTS: slot audio → edge-tts | 9 |
| `app/services/ark.py` (thu gọn thành shim), xoá `tokenfree_image/video/audio/gateway.py`, sửa `kepu_continuity.py`, `llm_client.py`, `billing/pricing.py`, `drama/seedream_options.py`, `drama/build_seedance_generate_body.py`, `media_catalog.py`, call site `function_id` | 10 |
| `app/models_tasks.py`, `app/main.py`, `app/schemas_tasks.py`, `drama/jobs.py`, `billing/ephemeral.py`, `tasks/poller.py`, `studio_tools.py`, `api/tools.py`, `api/v1/generation.py`, `drama/billing_util.py` | `provider_channel_id` + poll theo kênh | 11 |
| `CLAUDE.md`, `docs/PROVIDERS.md` (mới) | tài liệu | 12 |

---

### Task 1: Tách `kepu_text.py` khỏi `ark.py` (không đổi hành vi)

**Files:**
- Create: `backend/app/services/kepu_text.py`
- Modify: `backend/app/services/ark.py` (xoá khối đã chuyển, thêm delegate)
- Test: `backend/tests/test_kepu_text_module.py`

**Interfaces:**
- Produces:
  ```python
  # app/services/kepu_text.py
  @dataclass class ShotPlan            # nguyên văn ark.py:270-281
  @dataclass class StoryboardResult    # nguyên văn ark.py:284-288
  def storyboard_name_policy(allow_source_names: bool) -> str
  async def chat_storyboard(*, mock: bool, source_text, source_type, style_prefix, llm_system_addon,
      duration_min, duration_max, max_shot_duration, pipeline_mode="full", character_hint="",
      extra_requirements="", consistency_mode="character", output_ratio="16:9",
      shot_range_override=None, allow_source_names=False) -> StoryboardResult
  async def expand_content(topic: str, mode: str = "theme", *, mock: bool) -> dict[str, str]
  def parse_storyboard(...)            # nguyên _parse_storyboard, bỏ self
  def parse_expand_content(raw, topic, mode) -> dict[str, str]
  def mock_storyboard(...)             # nguyên _mock_storyboard, bỏ self
  def mock_expand_content(topic, mode) -> dict[str, str]
  ```

- [ ] **Step 1: Viết test đảm bảo module mới tồn tại và parser hoạt động**

```python
# backend/tests/test_kepu_text_module.py
"""kepu_text tách khỏi ark.py: parser/mock chạy độc lập, ark.py vẫn delegate."""
import pytest

from app.services import kepu_text


def test_parse_expand_content_reads_json():
    out = kepu_text.parse_expand_content('{"title": "Tiêu đề", "content": "Nội dung"}', "chủ đề", "theme")
    assert out["title"] == "Tiêu đề"
    assert out["content"] == "Nội dung"


def test_mock_expand_content_returns_title_and_content():
    out = kepu_text.mock_expand_content("năng lượng mặt trời", "script")
    assert out["title"]
    assert out["content"]


async def test_expand_content_mock_shortcut():
    out = await kepu_text.expand_content("AI trong y tế", "theme", mock=True)
    assert set(out) >= {"title", "content"}


async def test_ark_gateway_delegates_expand_content(monkeypatch):
    from app.services.ark import ArkGateway

    called = {}

    async def fake(topic, mode="theme", *, mock):
        called["args"] = (topic, mode, mock)
        return {"title": "t", "content": "c"}

    monkeypatch.setattr(kepu_text, "expand_content", fake)
    monkeypatch.setattr(ArkGateway, "mock", property(lambda self: True))
    out = await ArkGateway().expand_content("chủ đề", "theme")
    assert out == {"title": "t", "content": "c"}
    assert called["args"] == ("chủ đề", "theme", True)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && pytest tests/test_kepu_text_module.py -v`
Expected: FAIL `ModuleNotFoundError: app.services.kepu_text`

- [ ] **Step 3: Tạo `kepu_text.py` bằng cách chuyển nguyên khối từ `ark.py`**

Chuyển các đoạn sau (số dòng theo `ark.py` hiện tại) sang `app/services/kepu_text.py`, giữ nguyên nội dung, chỉ đổi tên/bỏ `self`:

| Từ `ark.py` | Thành |
|---|---|
| 151–229 (`_fallback_overlay_title` … `_normalize_overlay_subtitle`) | giữ nguyên tên |
| 259–288 (`storyboard_name_policy`, `ShotPlan`, `StoryboardResult`) | giữ nguyên |
| 543–765 (`ArkGateway.chat_storyboard`) | `async def chat_storyboard(*, mock: bool, source_text, ...)`; thay `self.mock` → `mock`; `self._mock_storyboard(` → `mock_storyboard(`; `self._parse_storyboard(` → `parse_storyboard(` |
| 2177–2257 (`_mock_storyboard`) | `def mock_storyboard(...)` (bỏ `self`) |
| 2259–2334 (`_parse_storyboard`) | `def parse_storyboard(...)` (bỏ `self`) |
| 2336–2365 (`expand_content`) | `async def expand_content(topic, mode="theme", *, mock: bool)`; `self._mock_expand_content(` → `mock_expand_content(`; `self._parse_expand_content(` → `parse_expand_content(` |
| 2367–2387 (`_mock_expand_content`) | `def mock_expand_content(topic, mode)` |
| 2389–2412 (`_parse_expand_content`) | `def parse_expand_content(raw, topic, mode)` |

Đầu file:

```python
"""科普文字链路：拆镜（storyboard）与主题扩写，独立于图/视频 provider。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ark_mock import mock_expand_content as _vi_mock_expand_content
from app.services.ark_mock import mock_storyboard_items
from app.services.llm_client import chat_completions
from app.services.text_lang import cut_words, is_cjk_text

logger = logging.getLogger(__name__)
```

Lưu ý: trong `ark.py` mock đang gọi `mock_expand_content` của `ark_mock` bên trong `_mock_expand_content`; giữ nguyên logic, chỉ đổi alias import như trên để tránh trùng tên. `chat_storyboard` gọi `asyncio.to_thread(mock_storyboard, ...)` thay cho `self._mock_storyboard`.

- [ ] **Step 4: `ark.py` delegate sang module mới**

Xoá các khối đã chuyển khỏi `ark.py`; thay `chat_storyboard` / `expand_content` trên `ArkGateway` bằng:

```python
    async def chat_storyboard(self, *args: Any, **kwargs: Any) -> StoryboardResult:
        """科普拆镜：委托 kepu_text（保留旧调用签名）。"""
        from app.services import kepu_text

        return await kepu_text.chat_storyboard(mock=self.mock, *args, **kwargs)

    async def expand_content(self, topic: str, mode: str = "theme") -> dict[str, str]:
        """主题扩写：委托 kepu_text。"""
        from app.services import kepu_text

        return await kepu_text.expand_content(topic, mode, mock=self.mock)
```

Thêm re-export ở đầu `ark.py` (test và `pipeline.py` đang import từ `ark`): `from app.services.kepu_text import ShotPlan, StoryboardResult, storyboard_name_policy  # noqa: F401`. Kiểm tra `grep -rn "ark\.\(chat_storyboard\|expand_content\)\|_parse_storyboard\|_mock_storyboard" app tests` không còn tham chiếu vào symbol đã xoá (test `tests/test_vi_text_fallbacks.py` dùng gì thì đổi import sang `kepu_text`).

- [ ] **Step 5: Chạy test**

Run: `cd backend && pytest tests/test_kepu_text_module.py tests/test_vi_text_fallbacks.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/kepu_text.py backend/app/services/ark.py backend/tests/test_kepu_text_module.py backend/tests/test_vi_text_fallbacks.py
git commit -m "refactor: tách chuỗi văn bản khoa học ra kepu_text.py

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `providers/base.py` — kiểu dữ liệu, Protocol, registry

**Files:**
- Create: `backend/app/services/providers/__init__.py`, `backend/app/services/providers/base.py`, `backend/app/services/providers/registry.py`
- Test: `backend/tests/test_providers_base.py`

**Interfaces:**
- Produces (dùng ở mọi task sau):
  ```python
  # app/services/providers/base.py
  IMAGE_GEN_READ_SEC = 1200.0; VIDEO_CREATE_READ_SEC = 180.0; VIDEO_POLL_READ_SEC = 60.0; VIDEO_FETCH_READ_SEC = 30.0
  def upstream_timeout(read_sec: float, *, connect: float = 30.0) -> httpx.Timeout
  def reraise_upstream_timeout(exc: BaseException, *, kind: str, read_sec: float) -> NoReturn
  def is_transient_http_status(status_code: int) -> bool
  def retry_after_seconds(resp: httpx.Response, default: float) -> float
  class ProviderNotSupported(RuntimeError)
  class TransientUpstreamError(RuntimeError)
  @dataclass class TaskResult(status, url=None, last_frame_url=None, error=None, total_tokens=0,
      completion_tokens=0, raw_usage=None, provider_task_id=None, upstream_cost_fen=None, channel_id="")
  @dataclass class ImageRequest(prompt: str, size: str = "", aspect_ratio: str = "",
      refs: list[str] = [], style_refs: list[str] = [], output_format: str = "png")
  @dataclass class ImageOutput(url=None, data: bytes|None=None, size="", raw_usage=None,
      total_tokens=0, prompt_tokens=0, completion_tokens=0)
  @dataclass class VideoRequest(body: dict, plain_text: str|None=None, target_ratio: str|None=None,
      allow_structure_fallback: bool=False, content_labels: list[str]|None=None)
  @dataclass class TtsRequest(text: str, voice: str, emotion_hint: str|None=None)
  class ProviderAdapter(Protocol):
      protocol: str
      async def list_models(self, route, capability: str = "all") -> list[dict[str, str]]
      async def gen_image(self, route, req: ImageRequest) -> ImageOutput
      async def create_video(self, route, req: VideoRequest) -> str
      async def fetch_video(self, route, task_id: str) -> TaskResult
      async def tts(self, route, req: TtsRequest) -> bytes
      def cost_fen(self, model: str, raw_usage: dict | None) -> int | None
      def url_needs_auth(self, url: str) -> bool
      def is_transient_error(self, exc: BaseException) -> bool
  def bearer_headers(api_key: str) -> dict[str, str]
  def join_url(base_url: str, path: str) -> str
  # app/services/providers/registry.py
  def get_adapter(protocol: str) -> ProviderAdapter        # "auto"/"" → openai; lạ → ProviderNotSupported
  def url_needs_auth(url: str) -> bool                      # any() trên các adapter đã đăng ký
  ```

- [ ] **Step 1: Test**

```python
# backend/tests/test_providers_base.py
"""providers/base: helper chung + registry theo protocol."""
import httpx
import pytest

from app.services.providers import base, registry


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_status(code):
    assert base.is_transient_http_status(code)


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_terminal_status(code):
    assert not base.is_transient_http_status(code)


def test_retry_after_caps_at_60():
    resp = httpx.Response(429, headers={"Retry-After": "600"})
    assert base.retry_after_seconds(resp, 8.0) == 60.0
    assert base.retry_after_seconds(httpx.Response(429), 8.0) == 8.0


def test_join_url_strips_slashes():
    assert base.join_url("https://x/api/v3/", "/images/generations") == "https://x/api/v3/images/generations"
    assert base.join_url("https://x/api/v3", "images/generations") == "https://x/api/v3/images/generations"


def test_reraise_read_timeout_mentions_upstream():
    with pytest.raises(RuntimeError) as exc:
        base.reraise_upstream_timeout(httpx.ReadTimeout("t"), kind="生图", read_sec=12)
    assert "ReadTimeout" in str(exc.value)
    assert "TokenFree" not in str(exc.value)


def test_registry_unknown_protocol():
    with pytest.raises(base.ProviderNotSupported):
        registry.get_adapter("kie")


def test_registry_auto_is_openai():
    assert registry.get_adapter("auto").protocol == "openai"
    assert registry.get_adapter("").protocol == "openai"
    assert registry.get_adapter("ark").protocol == "ark"
    assert registry.get_adapter("volc_tts").protocol == "volc_tts"
```

- [ ] **Step 2: Chạy test → FAIL** (`ModuleNotFoundError`)

- [ ] **Step 3: Viết `base.py`**

Chuyển nguyên văn từ `ark.py`: hằng 83–89, `_upstream_timeout` (92–94) → `upstream_timeout`, `reraise_upstream_timeout` (97–110, thay chữ "TokenFree" bằng "上游"), `TaskResult` (291–302, thêm `channel_id: str = ""`), `_is_transient_http_status` (307–309) → `is_transient_http_status`, `_retry_after_seconds` (312–320) → `retry_after_seconds`. Thêm:

```python
class ProviderNotSupported(RuntimeError):
    """Provider/protocol không được hỗ trợ hoặc không có năng lực này."""


class TransientUpstreamError(RuntimeError):
    """Lỗi tạm thời lúc tạo tác vụ (429/5xx/mạng) — được phép failover sang model kế tiếp."""


@dataclass
class ImageRequest:
    prompt: str
    size: str = ""
    aspect_ratio: str = ""
    refs: list[str] = field(default_factory=list)
    style_refs: list[str] = field(default_factory=list)
    output_format: str = "png"


@dataclass
class ImageOutput:
    url: str | None = None
    data: bytes | None = None
    size: str = ""
    raw_usage: dict[str, Any] | None = None
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class VideoRequest:
    body: dict[str, Any]
    plain_text: str | None = None
    target_ratio: str | None = None
    allow_structure_fallback: bool = False
    content_labels: list[str] | None = None


@dataclass
class TtsRequest:
    text: str
    voice: str
    emotion_hint: str | None = None


class ProviderAdapter(Protocol):
    """Hợp đồng một provider: mỗi protocol một file, facade chỉ gọi qua đây."""

    protocol: str

    async def list_models(self, route: ResolvedModelRoute, capability: str = "all") -> list[dict[str, str]]: ...
    async def gen_image(self, route: ResolvedModelRoute, req: ImageRequest) -> ImageOutput: ...
    async def create_video(self, route: ResolvedModelRoute, req: VideoRequest) -> str: ...
    async def fetch_video(self, route: ResolvedModelRoute, task_id: str) -> TaskResult: ...
    async def tts(self, route: ResolvedModelRoute, req: TtsRequest) -> bytes: ...
    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None: ...
    def url_needs_auth(self, url: str) -> bool: ...
    def is_transient_error(self, exc: BaseException) -> bool: ...


def bearer_headers(api_key: str) -> dict[str, str]:
    """Header Bearer + JSON dùng chung cho OpenAI/Ark."""
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def join_url(base_url: str, path: str) -> str:
    """Ghép base + path, tránh `//`."""
    return f"{(base_url or '').rstrip('/')}/{(path or '').lstrip('/')}"
```

`registry.py`:

```python
"""Registry adapter theo protocol; import lười để tránh vòng import."""

from __future__ import annotations

from app.services.providers.base import ProviderAdapter, ProviderNotSupported

_CACHE: dict[str, ProviderAdapter] = {}


def get_adapter(protocol: str) -> ProviderAdapter:
    """Trả adapter singleton theo protocol; `auto`/rỗng coi là openai."""
    proto = (protocol or "openai").strip().lower()
    if proto == "auto":
        proto = "openai"
    if proto in _CACHE:
        return _CACHE[proto]
    if proto == "openai":
        from app.services.providers.openai_adapter import OpenAIAdapter as cls
    elif proto == "ark":
        from app.services.providers.ark_adapter import ArkAdapter as cls
    elif proto == "volc_tts":
        from app.services.providers.volc_tts_adapter import VolcTtsAdapter as cls
    else:
        raise ProviderNotSupported(f"protocol không hỗ trợ: {proto}")
    _CACHE[proto] = cls()
    return _CACHE[proto]


def url_needs_auth(url: str) -> bool:
    """URL có cần Bearer khi tải không (hỏi mọi adapter)."""
    return any(get_adapter(p).url_needs_auth(url) for p in ("openai", "ark", "volc_tts"))
```

`__init__.py` để trống ngoài docstring. Vì `registry` import lười các adapter chưa tồn tại ở task này, tạo tạm 3 file adapter tối thiểu chỉ có `class XAdapter: protocol = "..."` (Task 3–5 điền đầy đủ).

- [ ] **Step 4: Chạy test → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/providers backend/tests/test_providers_base.py
git commit -m "feat: thêm lớp providers/base với kiểu dữ liệu, Protocol và registry adapter

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `ark_adapter.py` — chuyển nhánh Ark/BytePlus từ `ark.py`

**Files:**
- Create: `backend/app/services/providers/ark_adapter.py`
- Modify: `backend/app/services/drama/seedance_i2v_role.py` (re-export), `backend/app/services/media_ref_limits.py` (hằng lấy từ adapter)
- Test: `backend/tests/test_ark_adapter.py`

**Interfaces:**
- Consumes: `base.*` (Task 2), `app.services.drama.seedream_options.is_seedream_pro_model / clamp_seedream_pixel_size` (đã có), `app.services.billing.pricing.parse_usage_dict` (đã có).
- Produces:
  ```python
  ARK_DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
  ARK_HOSTS = ("bytepluses.com", "volces.com", "volcengineapi.com")
  ARK_STATIC_MODELS: list[dict[str, str]]     # {id,label,capability} — danh sách mục 4.3 spec
  MAX_REFERENCE_IMAGES = 9
  SEEDREAM_CG_STYLE: str                       # nguyên _SEEDREAM_CG_STYLE ark.py:253-256
  def is_ark_host(base_url: str) -> bool
  def resolve_seedance_i2v_image_role(ratio: str | None) -> tuple[str, str | None]
  def seedance_prompt_text(prompt: str) -> str
  def seedance_duration(duration: int | float) -> int
  def is_seedance_input_privacy_error(msg: str) -> bool
  def is_seedance_text_policy_error(msg: str) -> bool
  def with_seedance_cg_style(prompt: str) -> str
  def seedance_content_with_cg_style(content) -> list[dict] | None
  def format_seedance_create_error(status_code, text, *, content_labels=None) -> str
  def raise_seedream_http_error(status_code: int, body: str, *, model: str = "") -> NoReturn
  def extract_image_url(data: dict) -> str | None
  def extract_video_task_id(data) -> str | None
  def extract_video_result_url(data) -> str | None
  def normalize_video_task_status(status: str) -> str
  def build_task_result_from_payload(data: dict) -> TaskResult
  class ArkAdapter:  protocol = "ark"  # implement ProviderAdapter; create_video không hỗ trợ tts → ProviderNotSupported
  ```

- [ ] **Step 1: Test (fake `httpx.AsyncClient` ghi lại request)**

```python
# backend/tests/test_ark_adapter.py
"""ArkAdapter: body ảnh/video đúng shape Ark, retry tạo task, parse GET task."""
from __future__ import annotations

import json

import httpx
import pytest

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import ark_adapter, base
from app.services.providers.ark_adapter import ArkAdapter


def _route(model="dreamina-seedance-2-5-260628", base_url="https://ark.ap-southeast.bytepluses.com/api/v3"):
    return ResolvedModelRoute(
        capability="video", logical_model_id="drama.video", upstream_model=model,
        channel_id="byteplus", channel_name="BytePlus", base_url=base_url,
        api_key="k", protocol="ark", api_format="ark",
    )


class _Recorder:
    """Ghi lại từng POST/GET và trả về câu trả lời theo kịch bản."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[tuple[str, str, dict | None]] = []

    def client(self):
        rec = self

        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append(("POST", url, json))
                return rec.script.pop(0)
            async def get(self, url, headers=None):
                rec.calls.append(("GET", url, None))
                return rec.script.pop(0)
        return _C


async def test_gen_image_body_and_url(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"url": "https://cdn/x.jpg"}], "usage": {"output_tokens": 4096, "total_tokens": 4096, "generated_images": 1}})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    out = await ArkAdapter().gen_image(
        _route("dola-seedream-5-0-pro-260628"),
        base.ImageRequest(prompt="một chú mèo", size="4K", refs=["https://a/1.png"], style_refs=["https://a/s.png"]),
    )
    method, url, body = rec.calls[0]
    assert url.endswith("/images/generations")
    assert body["model"] == "dola-seedream-5-0-pro-260628"
    assert body["size"] == "2K"                      # pro: 4K bị kẹp về 2K
    assert body["image"] == ["https://a/1.png", "https://a/s.png"]
    assert body["watermark"] is False and body["response_format"] == "url"
    assert out.url == "https://cdn/x.jpg"
    assert out.total_tokens == 4096
    assert out.raw_usage["generated_images"] == 1


async def test_gen_image_single_ref_is_scalar(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"url": "https://cdn/x.jpg"}]})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    await ArkAdapter().gen_image(_route("seedream-4-5-251128"), base.ImageRequest(prompt="p", size="2K", refs=["https://a/1.png"]))
    assert rec.calls[0][2]["image"] == "https://a/1.png"


async def test_gen_image_text_sensitive_raises_readable(monkeypatch):
    rec = _Recorder([httpx.Response(400, text='{"error":{"code":"InputTextSensitiveContentDetected"}}')])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError) as exc:
        await ArkAdapter().gen_image(_route("seedream-4-5-251128"), base.ImageRequest(prompt="p"))
    assert "内容审核" in str(exc.value)


async def test_create_video_first_frame_no_ratio(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"id": "cgt-1"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "t"}, {"type": "image_url", "image_url": {"url": "https://a/f.png"}, "role": "first_frame"}], "duration": 8, "resolution": "720p"}
    task_id = await ArkAdapter().create_video(_route(), base.VideoRequest(body=body))
    assert task_id == "cgt-1"
    assert rec.calls[0][1].endswith("/contents/generations/tasks")
    assert rec.calls[0][2]["model"] == "dreamina-seedance-2-5-260628"   # model lấy từ route
    assert "ratio" not in rec.calls[0][2]


async def test_create_video_json_prompt_falls_back_to_plain(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="BodyFormat"), httpx.Response(200, json={"id": "cgt-2"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": '{"summary_caption":"x"}'}, {"type": "image_url", "image_url": {"url": "u"}, "role": "first_frame"}], "duration": 5}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body, plain_text="x thuần", allow_structure_fallback=True))
    assert rec.calls[1][2]["content"][0]["text"] == "x thuần"


async def test_create_video_policy_hit_retries_with_cg(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="InputTextSensitive"), httpx.Response(200, json={"id": "cgt-3"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "cảnh"}], "duration": 5}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body))
    assert ark_adapter.SEEDREAM_CG_STYLE.strip() in rec.calls[1][2]["content"][0]["text"]


async def test_create_video_privacy_error_no_retry(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="InputImageSensitive")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError):
        await ArkAdapter().create_video(_route(), base.VideoRequest(body={"model": "m", "content": [{"type": "text", "text": "x"}]}))
    assert len(rec.calls) == 1


async def test_create_video_structure_fallback_drops_ratio_then_adaptive(monkeypatch):
    rec = _Recorder([httpx.Response(400, text="ratio invalid"), httpx.Response(400, text="ratio invalid"), httpx.Response(200, json={"id": "cgt-4"})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    body = {"model": "m", "content": [{"type": "text", "text": "x"}, {"type": "image_url", "image_url": {"url": "u"}, "role": "first_frame"}], "ratio": "9:16"}
    await ArkAdapter().create_video(_route(), base.VideoRequest(body=body, allow_structure_fallback=True))
    assert "ratio" not in rec.calls[1][2]
    assert rec.calls[2][2]["ratio"] == "adaptive" and "role" not in rec.calls[2][2]["content"][1]


async def test_create_video_transient_5xx_raises_transient(monkeypatch):
    rec = _Recorder([httpx.Response(503, text="busy")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(base.TransientUpstreamError):
        await ArkAdapter().create_video(_route(), base.VideoRequest(body={"model": "m", "content": [{"type": "text", "text": "x"}]}))


async def test_fetch_video_succeeded_parses_ark_shape(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"id": "cgt-1", "status": "succeeded", "content": {"video_url": "https://v/1.mp4", "last_frame_url": "https://v/l.jpg"}, "usage": {"completion_tokens": 123, "total_tokens": 123}})])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    out = await ArkAdapter().fetch_video(_route(), "cgt-1")
    assert rec.calls[0][1].endswith("/contents/generations/tasks/cgt-1")
    assert out.status == "succeeded" and out.url == "https://v/1.mp4" and out.last_frame_url == "https://v/l.jpg"
    assert out.completion_tokens == 123 and out.provider_task_id == "cgt-1" and out.channel_id == "byteplus"


@pytest.mark.parametrize("code", [429, 502])
async def test_fetch_video_transient_is_running(monkeypatch, code):
    rec = _Recorder([httpx.Response(code, text="x")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "running"


async def test_fetch_video_404_failed(monkeypatch):
    rec = _Recorder([httpx.Response(404, text="nope")])
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", rec.client())
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "failed"


async def test_fetch_video_network_error_is_running(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): raise httpx.ConnectError("x")
    monkeypatch.setattr(ark_adapter.httpx, "AsyncClient", _Boom)
    assert (await ArkAdapter().fetch_video(_route(), "cgt-1")).status == "running"


def test_static_models_have_capabilities():
    caps = {m["capability"] for m in ark_adapter.ARK_STATIC_MODELS}
    assert caps == {"text", "image", "video"}
    assert any(m["id"] == "dreamina-seedance-2-5-260628" for m in ark_adapter.ARK_STATIC_MODELS)


async def test_list_models_filters_by_capability():
    out = await ArkAdapter().list_models(_route(), "video")
    assert out and all(m["capability"] == "video" for m in out)


def test_is_ark_host():
    assert ark_adapter.is_ark_host("https://ark.ap-southeast.bytepluses.com/api/v3")
    assert ark_adapter.is_ark_host("https://ark.cn-beijing.volces.com/api/v3")
    assert not ark_adapter.is_ark_host("https://api.openai.com/v1")


async def test_tts_not_supported():
    with pytest.raises(base.ProviderNotSupported):
        await ArkAdapter().tts(_route(), base.TtsRequest(text="a", voice="v"))


def test_i2v_role_rule():
    assert ark_adapter.resolve_seedance_i2v_image_role("9:16") == ("reference_image", "9:16")
    assert ark_adapter.resolve_seedance_i2v_image_role(None) == ("first_frame", None)
```

- [ ] **Step 2: Chạy → FAIL** (`AttributeError`/`ImportError` vì adapter còn rỗng)

- [ ] **Step 3: Viết `ark_adapter.py`**

Chuyển nguyên văn từ `ark.py` (bỏ `self`/`@staticmethod`, đổi tên bỏ dấu `_`): `_raise_seedream_http_error` 113–148 (**bỏ** tham số `tokenfree` và nhánh `if tokenfree`), `_SEEDREAM_SANITIZE` 233–250, `_SEEDREAM_CG_STYLE` 253–256 → `SEEDREAM_CG_STYLE`, `_build_task_result_from_payload` 324–355, `_extract_seedance_last_frame_url` 359–377, `_seedance_content_slot_label` 381–390, `_format_seedance_create_error` 394–430, `_is_seedream_input_text_sensitive` 998–1006, `_is_seedream_input_privacy_error` 1008–1015, `_is_seedream_policy_error` 1017–1029, `_is_seedance_input_privacy_error` 1031–1043, `_is_seedance_text_policy_error` 1045–1064, `_with_seedream_cg_style` 1066–1074, `_seedance_content_with_cg_style` 1082–1104, `_sanitize_seedream_prompt` 1106–1112, `_extract_image_url` 1114–1120, `_seedance_prompt_text` 1122–1138, `_seedance_duration` 1140–1145. Từ `tokenfree_video.py`: `extract_video_task_id` (không còn `unwrap` New API — chỉ `payload.get("id")`/`task_id`), `format_video_task_error`, `extract_video_result_url`, `normalize_video_task_status`, hằng `VIDEO_SUCCESS_STATUSES`/`VIDEO_FAILED_STATUSES`. Từ `drama/seedance_i2v_role.py`: `resolve_seedance_i2v_image_role` (file cũ giữ lại chỉ `from app.services.providers.ark_adapter import resolve_seedance_i2v_image_role  # noqa: F401`).

Phần adapter:

```python
ARK_DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_HOSTS = ("bytepluses.com", "volces.com", "volcengineapi.com")
MAX_REFERENCE_IMAGES = 9
IMAGE_PATH = "/images/generations"
VIDEO_TASK_PATH = "/contents/generations/tasks"

# Danh sách model chính thức (BytePlus không có GET /models); cập nhật 2026-09-22
ARK_STATIC_MODELS: list[dict[str, str]] = [
    {"id": "dola-seedream-5-0-pro-260628", "label": "Seedream 5.0 Pro", "capability": "image"},
    {"id": "dola-seedream-5-0-flash-260915", "label": "Seedream 5.0 Flash", "capability": "image"},
    {"id": "seedream-5-0-260128", "label": "Seedream 5.0 Lite", "capability": "image"},
    {"id": "seedream-4-5-251128", "label": "Seedream 4.5", "capability": "image"},
    {"id": "seedream-4-0-250828", "label": "Seedream 4.0", "capability": "image"},
    {"id": "dreamina-seedance-2-5-260628", "label": "Seedance 2.5", "capability": "video"},
    {"id": "dreamina-seedance-2-0-260128", "label": "Seedance 2.0", "capability": "video"},
    {"id": "dreamina-seedance-2-0-fast-260128", "label": "Seedance 2.0 Fast", "capability": "video"},
    {"id": "dreamina-seedance-2-0-mini-260615", "label": "Seedance 2.0 Mini", "capability": "video"},
    {"id": "seedance-1-0-pro-250528", "label": "Seedance 1.0 Pro", "capability": "video"},
    {"id": "dola-seed-2-1-turbo-260628", "label": "Seed 2.1 Turbo", "capability": "text"},
    {"id": "seed-2-0-pro-260328", "label": "Seed 2.0 Pro", "capability": "text"},
    {"id": "seed-2-0-lite-260428", "label": "Seed 2.0 Lite", "capability": "text"},
    {"id": "deepseek-v4-pro-ga-260813", "label": "DeepSeek V4 Pro", "capability": "text"},
    {"id": "deepseek-v4-flash-ga-260731", "label": "DeepSeek V4 Flash", "capability": "text"},
]


def is_ark_host(base_url: str) -> bool:
    """Base URL thuộc BytePlus ModelArk / Volcengine Ark."""
    host = (urlparse(base_url or "").hostname or "").lower()
    return any(host.endswith(h) for h in ARK_HOSTS)


class ArkAdapter:
    """BytePlus ModelArk / Volcengine Ark: Seedream (đồng bộ) + Seedance (task + poll)."""

    protocol = "ark"

    async def list_models(self, route, capability: str = "all") -> list[dict[str, str]]:
        return [m for m in ARK_STATIC_MODELS if capability in ("all", m["capability"])]

    async def gen_image(self, route, req: ImageRequest) -> ImageOutput:
        from app.services.drama.seedream_options import clamp_seedream_pixel_size, is_seedream_pro_model

        model = route.upstream_model
        size = req.size or "2K"
        if is_seedream_pro_model(model):
            size = "2K" if size.strip().upper() in {"3K", "4K"} else clamp_seedream_pixel_size(size)
        refs = [*req.refs, *req.style_refs]
        body: dict[str, Any] = {"model": model, "prompt": req.prompt, "size": size, "response_format": "url", "watermark": False}
        if refs:
            body["image"] = refs if len(refs) > 1 else refs[0]
        try:
            async with httpx.AsyncClient(timeout=upstream_timeout(IMAGE_GEN_READ_SEC)) as client:
                resp = await client.post(join_url(route.base_url, IMAGE_PATH), headers=bearer_headers(route.api_key), json=body)
        except httpx.TimeoutException as exc:
            reraise_upstream_timeout(exc, kind="生图", read_sec=IMAGE_GEN_READ_SEC)
        if resp.status_code >= 400:
            if is_transient_http_status(resp.status_code):
                raise TransientUpstreamError(f"Seedream HTTP {resp.status_code}")
            raise_seedream_http_error(resp.status_code, resp.text, model=model)
        data = resp.json()
        usage = parse_usage_dict(data)
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        url = extract_image_url(data)
        if not url:
            raise RuntimeError("出图未返回图片地址，请稍后重试")
        return ImageOutput(url=url, size=size, raw_usage=raw_usage,
                           total_tokens=int(usage.get("total_tokens") or 0),
                           prompt_tokens=int(usage.get("prompt_tokens") or 0),
                           completion_tokens=int(usage.get("completion_tokens") or 0))
```

`create_video`: nhận `req.body`, ghi đè `body["model"] = route.upstream_model`, POST tới `join_url(route.base_url, VIDEO_TASK_PATH)`; sao chép nguyên 4 tầng retry từ `ark.py:1231-1289` với thay thế: `prompt_as_json` → `req.plain_text is not None`; `plain` → `req.plain_text`; `target_ratio` → `req.target_ratio`; tầng "bỏ ratio" và "adaptive" chỉ chạy khi `req.allow_structure_fallback and not req.target_ratio`; lỗi cuối `RuntimeError(format_seedance_create_error(status, text, content_labels=req.content_labels))`; **trước khi vào các tầng retry**, nếu `is_transient_http_status(resp.status_code)` → `raise TransientUpstreamError(...)`. Trả `extract_video_task_id(data)`; thiếu → `RuntimeError(f"Seedance missing task id: {data}")`.

`fetch_video`: nguyên `fetch_task_once` `ark.py:1557-1576` (bỏ mock), URL `join_url(route.base_url, f"{VIDEO_TASK_PATH}/{task_id}")`, headers `bearer_headers(route.api_key)`; mọi `TaskResult` trả về gán `provider_task_id=task_id, channel_id=route.channel_id`.

`tts` → `raise ProviderNotSupported("ModelArk không có TTS")`. `cost_fen` → `return None` (Plan B). `url_needs_auth` → `False`. `is_transient_error(exc)` → `isinstance(exc, (TransientUpstreamError, httpx.TransportError))`.

- [ ] **Step 4: `media_ref_limits.py`** đổi `MAX_REFERENCE_IMAGES = 9` thành `from app.services.providers.ark_adapter import MAX_REFERENCE_IMAGES`.

- [ ] **Step 5: Chạy → PASS**: `pytest tests/test_ark_adapter.py tests/test_seedance_i2v_role.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/providers/ark_adapter.py backend/app/services/drama/seedance_i2v_role.py backend/app/services/media_ref_limits.py backend/tests/test_ark_adapter.py
git commit -m "feat: adapter BytePlus ModelArk (Seedream/Seedance) tách khỏi ark.py

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `openai_adapter.py` — ảnh (generations/edits), TTS, GET /models

**Files:**
- Create: `backend/app/services/providers/openai_adapter.py`
- Test: `backend/tests/test_openai_adapter.py`

**Interfaces:**
- Consumes: `base.*`, `app.services.voices.infer_speaker_gender` (đã có), `app.services.billing.pricing.parse_usage_dict`.
- Produces:
  ```python
  OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
  def is_official_openai(base_url: str) -> bool               # host api.openai.com
  def openai_image_size(size: str, aspect_ratio: str, model: str) -> tuple[str, str]  # (size, quality)
  def openai_voice_for_speaker(speaker: str) -> str            # nữ → "marin", nam → "cedar", không rõ → "alloy"
  class OpenAIAdapter: protocol = "openai"
  ```

- [ ] **Step 1: Test**

```python
# backend/tests/test_openai_adapter.py
"""OpenAIAdapter: map size/quality, generations vs edits, base64, TTS, /models."""
from __future__ import annotations

import base64

import httpx
import pytest

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import base, openai_adapter
from app.services.providers.openai_adapter import OpenAIAdapter, openai_image_size, openai_voice_for_speaker


def _route(model="gpt-image-2.5-sunburst", capability="image", base_url="https://api.openai.com/v1"):
    return ResolvedModelRoute(capability=capability, logical_model_id="tools.image", upstream_model=model,
                              channel_id="openai", channel_name="OpenAI", base_url=base_url, api_key="sk",
                              protocol="openai", api_format="openai")


class _Recorder:
    def __init__(self, script):
        self.script = list(script); self.calls = []
    def client(self):
        rec = self
        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append(("POST", url, json)); return rec.script.pop(0)
            async def get(self, url, headers=None):
                rec.calls.append(("GET", url, None)); return rec.script.pop(0)
        return _C


@pytest.mark.parametrize("size,ratio,model,expect", [
    ("1K", "", "gpt-image-1", ("1024x1024", "low")),
    ("2K", "9:16", "gpt-image-1", ("1024x1536", "medium")),
    ("2K", "16:9", "gpt-image-1", ("1536x1024", "medium")),
    ("4K", "1:1", "gpt-image-1", ("1024x1024", "high")),
    ("2816x1584", "", "gpt-image-2.5-sunburst", ("2816x1584", "medium")),   # 2.x: WxH giữ, chia hết 16
    ("2816x1584", "", "gpt-image-1", ("1536x1024", "medium")),              # 1.x: WxH không hỗ trợ → tier
    ("5000x1000", "", "gpt-image-2", ("3840x1280", "medium")),              # kẹp cạnh dài 3840, tỉ lệ ≤ 3:1
])
def test_openai_image_size(size, ratio, model, expect):
    assert openai_image_size(size, ratio, model) == expect


def test_voice_map():
    assert openai_voice_for_speaker("zh_female_cancan_uranus_bigtts") == "marin"
    assert openai_voice_for_speaker("zh_male_shaonianzixin_uranus_bigtts") == "cedar"
    assert openai_voice_for_speaker("") == "alloy"


async def test_gen_image_without_refs_uses_generations(monkeypatch):
    png = base64.b64encode(b"\x89PNG-fake").decode()
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": png}], "usage": {"input_tokens": 10, "output_tokens": 1000, "total_tokens": 1010}})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    out = await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="mèo", size="2K", aspect_ratio="9:16"))
    _, url, body = rec.calls[0]
    assert url.endswith("/images/generations")
    assert body == {"model": "gpt-image-2.5-sunburst", "prompt": "mèo", "n": 1, "size": "1024x1536", "quality": "medium", "output_format": "png"}
    assert out.data == b"\x89PNG-fake" and out.url is None
    assert out.total_tokens == 1010 and out.completion_tokens == 1000 and out.prompt_tokens == 10
    assert out.raw_usage["output_tokens"] == 1000


async def test_gen_image_with_refs_uses_edits(monkeypatch):
    png = base64.b64encode(b"x").decode()
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": png}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p", size="1K", refs=["https://a/1.png"], style_refs=["data:image/png;base64,AAA"]))
    _, url, body = rec.calls[0]
    assert url.endswith("/images/edits")
    assert body["images"] == [{"image_url": "https://a/1.png"}, {"image_url": "data:image/png;base64,AAA"}]
    assert "n" in body and body["size"] == "1024x1024"


async def test_gen_image_caps_refs_at_16(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"x").decode()}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p", refs=[f"https://a/{i}.png" for i in range(20)]))
    assert len(rec.calls[0][2]["images"]) == 16


async def test_gen_image_http_error_readable(monkeypatch):
    rec = _Recorder([httpx.Response(400, json={"error": {"message": "safety system rejected"}})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(RuntimeError) as exc:
        await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p"))
    assert "safety system rejected" in str(exc.value)


async def test_gen_image_transient(monkeypatch):
    rec = _Recorder([httpx.Response(429, json={})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    with pytest.raises(base.TransientUpstreamError):
        await OpenAIAdapter().gen_image(_route(), base.ImageRequest(prompt="p"))


async def test_tts_body(monkeypatch):
    rec = _Recorder([httpx.Response(200, content=b"ID3" + b"\x00" * 2000)])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    audio = await OpenAIAdapter().tts(_route("gpt-4o-mini-tts", "audio"), base.TtsRequest(text="xin chào", voice="zh_female_cancan_uranus_bigtts", emotion_hint="vui vẻ"))
    _, url, body = rec.calls[0]
    assert url.endswith("/audio/speech")
    assert body["model"] == "gpt-4o-mini-tts" and body["voice"] == "marin" and body["response_format"] == "mp3"
    assert body["instructions"] == "vui vẻ"
    assert audio.startswith(b"ID3")


async def test_tts_no_instructions_for_tts1(monkeypatch):
    rec = _Recorder([httpx.Response(200, content=b"\xff\xfb" + b"\x00" * 2000)])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    await OpenAIAdapter().tts(_route("tts-1", "audio"), base.TtsRequest(text="a", voice="v", emotion_hint="x"))
    assert "instructions" not in rec.calls[0][2]


async def test_list_models_infers_capability(monkeypatch):
    rec = _Recorder([httpx.Response(200, json={"data": [{"id": "gpt-5.6-sol"}, {"id": "gpt-image-2"}, {"id": "gpt-4o-mini-tts"}, {"id": "sora-2"}]})])
    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", rec.client())
    out = await OpenAIAdapter().list_models(_route(), "all")
    caps = {m["id"]: m["capability"] for m in out}
    assert caps["gpt-5.6-sol"] == "text" and caps["gpt-image-2"] == "image" and caps["gpt-4o-mini-tts"] == "audio"
    assert "sora-2" not in caps                      # video OpenAI bị loại (đã gỡ 2026-09-24)


async def test_create_video_not_supported():
    with pytest.raises(base.ProviderNotSupported):
        await OpenAIAdapter().create_video(_route(), base.VideoRequest(body={}))
```

- [ ] **Step 2: Chạy → FAIL**

- [ ] **Step 3: Viết `openai_adapter.py`**

```python
"""OpenAI (và OpenAI-compatible: OpenRouter, tuỳ chỉnh): ảnh base64, TTS, danh sách model."""

from __future__ import annotations

import base64
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.billing.pricing import parse_usage_dict
from app.services.providers.base import (
    IMAGE_GEN_READ_SEC, ImageOutput, ImageRequest, ProviderNotSupported, TaskResult,
    TransientUpstreamError, TtsRequest, VideoRequest, bearer_headers, is_transient_http_status,
    join_url, reraise_upstream_timeout, upstream_timeout,
)

logger = logging.getLogger(__name__)

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_EDIT_REFS = 16
# gpt-image-2 / 2.5: WxH tuỳ ý chia hết 16, cạnh ≤ 3840x2160, tỉ lệ trong [1:3, 3:1]
_ARBITRARY_SIZE_MODELS = re.compile(r"^gpt-image-2(\.|-|$)")
_TIER_QUALITY = {"1K": "low", "2K": "medium", "3K": "high", "4K": "high"}


def is_official_openai(base_url: str) -> bool:
    """Base URL là api.openai.com (dùng để chọn max_completion_tokens)."""
    return (urlparse(base_url or "").hostname or "").lower() == "api.openai.com"


def _ratio_of(aspect_ratio: str) -> float | None:
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", aspect_ratio or "")
    return (int(m.group(1)) / int(m.group(2))) if m and int(m.group(2)) else None


def openai_image_size(size: str, aspect_ratio: str, model: str) -> tuple[str, str]:
    """Map size nội bộ (1K/2K/3K/4K hoặc WxH) + tỉ lệ sang (size, quality) của OpenAI."""
    raw = (size or "2K").strip()
    tier = raw.upper()
    ratio = _ratio_of(aspect_ratio)
    m = re.match(r"^(\d+)\s*[xX×]\s*(\d+)$", raw)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        ratio = w / h if h else ratio
        if _ARBITRARY_SIZE_MODELS.match((model or "").lower()):
            scale = min(1.0, 3840 / max(w, 1), 2160 / max(h, 1))
            w, h = int(w * scale), int(h * scale)
            r = w / max(h, 1)
            if r > 3:
                h = w // 3
            elif r < 1 / 3:
                w = h // 3
            w, h = max(16, w - w % 16), max(16, h - h % 16)
            return f"{w}x{h}", "medium"
        tier = "2K"
    quality = _TIER_QUALITY.get(tier, "medium")
    if ratio is None or abs(ratio - 1) < 0.15:
        return "1024x1024", quality
    return ("1536x1024", quality) if ratio > 1 else ("1024x1536", quality)


def openai_voice_for_speaker(speaker: str) -> str:
    """Speaker nội bộ (zh_female_*, S_*, preset) → voice OpenAI theo giới tính suy ra."""
    from app.services.voices import infer_speaker_gender

    g = infer_speaker_gender(speaker or "")
    if g == "female":
        return "marin"
    if g == "male":
        return "cedar"
    return "alloy"


def _error_text(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
    except Exception:  # noqa: BLE001
        pass
    return (resp.text or "")[:300]


class OpenAIAdapter:
    """OpenAI-compatible: /images/generations|edits (base64), /audio/speech, GET /models."""

    protocol = "openai"

    async def list_models(self, route: ResolvedModelRoute, capability: str = "all") -> list[dict[str, str]]:
        from app.services.model_routing_config import infer_model_capability

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(join_url(route.base_url, "/models"), headers=bearer_headers(route.api_key))
        if resp.status_code >= 400:
            raise RuntimeError(f"Không tải được danh sách model (HTTP {resp.status_code}): {_error_text(resp)}")
        out: list[dict[str, str]] = []
        for item in resp.json().get("data") or []:
            mid = str(item.get("id") or "").strip()
            if not mid:
                continue
            cap = infer_model_capability(mid)
            if cap == "video":
                continue  # OpenAI không còn video; OpenRouter chưa có
            if capability in ("all", cap):
                out.append({"id": mid, "label": mid, "capability": cap})
        return sorted(out, key=lambda m: m["id"])

    async def gen_image(self, route: ResolvedModelRoute, req: ImageRequest) -> ImageOutput:
        model = route.upstream_model
        size, quality = openai_image_size(req.size, req.aspect_ratio, model)
        refs = [*req.refs, *req.style_refs][:MAX_EDIT_REFS]
        body: dict[str, Any] = {"model": model, "prompt": req.prompt, "n": 1, "size": size, "quality": quality, "output_format": req.output_format or "png"}
        path = "/images/generations"
        if refs:
            path = "/images/edits"
            body["images"] = [{"image_url": u} for u in refs]
        try:
            async with httpx.AsyncClient(timeout=upstream_timeout(IMAGE_GEN_READ_SEC)) as client:
                resp = await client.post(join_url(route.base_url, path), headers=bearer_headers(route.api_key), json=body)
        except httpx.TimeoutException as exc:
            reraise_upstream_timeout(exc, kind="生图", read_sec=IMAGE_GEN_READ_SEC)
        if resp.status_code >= 400:
            if is_transient_http_status(resp.status_code):
                raise TransientUpstreamError(f"OpenAI image HTTP {resp.status_code}")
            raise RuntimeError(f"生图失败（{resp.status_code}）：{_error_text(resp)}")
        data = resp.json()
        first = (data.get("data") or [{}])[0]
        usage = parse_usage_dict(data)
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        b64 = first.get("b64_json")
        if not b64 and not first.get("url"):
            raise RuntimeError("出图未返回图片数据，请稍后重试")
        return ImageOutput(url=first.get("url"), data=base64.b64decode(b64) if b64 else None, size=size, raw_usage=raw_usage,
                           total_tokens=int(usage.get("total_tokens") or 0), prompt_tokens=int(usage.get("prompt_tokens") or 0),
                           completion_tokens=int(usage.get("completion_tokens") or 0))

    async def create_video(self, route: ResolvedModelRoute, req: VideoRequest) -> str:
        raise ProviderNotSupported("OpenAI không hỗ trợ tạo video")

    async def fetch_video(self, route: ResolvedModelRoute, task_id: str) -> TaskResult:
        raise ProviderNotSupported("OpenAI không hỗ trợ tạo video")

    async def tts(self, route: ResolvedModelRoute, req: TtsRequest) -> bytes:
        model = route.upstream_model or "gpt-4o-mini-tts"
        body: dict[str, Any] = {"model": model, "input": req.text, "voice": openai_voice_for_speaker(req.voice), "response_format": "mp3"}
        if req.emotion_hint and not model.startswith("tts-1"):
            body["instructions"] = req.emotion_hint[:400]
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(join_url(route.base_url, "/audio/speech"), headers=bearer_headers(route.api_key), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"TTS HTTP {resp.status_code}: {_error_text(resp)}")
        if len(resp.content) < 1000:
            raise RuntimeError("TTS trả về âm thanh rỗng")
        return resp.content

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        return None  # Plan B: bảng giá provider_rates

    def url_needs_auth(self, url: str) -> bool:
        return False

    def is_transient_error(self, exc: BaseException) -> bool:
        return isinstance(exc, (TransientUpstreamError, httpx.TransportError))
```

`parse_usage_dict` hiện đọc `input_tokens`/`output_tokens` (`pricing.py:234-248`) — xác nhận bằng test; nếu không, bổ sung hai khoá đó vào `parse_usage_dict`.

- [ ] **Step 4: Chạy → PASS**: `pytest tests/test_openai_adapter.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/providers/openai_adapter.py backend/tests/test_openai_adapter.py
git commit -m "feat: adapter OpenAI cho ảnh (base64/edits), TTS và danh sách model

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `volc_tts_adapter.py` — chuyển openspeech

**Files:**
- Create: `backend/app/services/providers/volc_tts_adapter.py`
- Test: `backend/tests/test_volc_tts_adapter.py`

**Interfaces:**
- Produces:
  ```python
  VOLC_TTS_DEFAULT_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
  BYTEPLUS_TTS_URL = "https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/unidirectional"
  SPEAKER_ALIASES: dict[str, str]                       # nguyên voice_map ark.py:1837-1844
  def resolve_volc_speaker(voice: str, default: str) -> str
  def resource_id_for_speaker(speaker: str, default: str) -> str   # nguyên _tts_resource_id
  def build_tts_additions(speaker: str, emotion_hint: str | None) -> str | None  # nguyên _build_tts_additions
  def parse_openspeech_ndjson(raw: bytes) -> bytes
  class VolcTtsAdapter: protocol = "volc_tts"
  ```

- [ ] **Step 1: Test**

```python
# backend/tests/test_volc_tts_adapter.py
"""VolcTtsAdapter: header theo kiểu key, body openspeech, NDJSON → bytes."""
from __future__ import annotations

import base64
import json

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.providers import base, volc_tts_adapter
from app.services.providers.volc_tts_adapter import VolcTtsAdapter


def _route(api_key="vk", base_url=""):
    return ResolvedModelRoute(capability="audio", logical_model_id="kepu.tts", upstream_model="seed-tts-2.0",
                              channel_id="volc", channel_name="Volc", base_url=base_url, api_key=api_key,
                              protocol="volc_tts", api_format="openai")


def _ndjson(chunks):
    lines = [json.dumps({"code": 0, "data": base64.b64encode(c).decode()}) for c in chunks]
    lines.append(json.dumps({"code": 20000000}))
    return ("\n".join(lines)).encode()


class _Recorder:
    def __init__(self, resp): self.resp = resp; self.calls = []
    def client(self):
        rec = self
        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.calls.append((url, headers, json)); return rec.resp
        return _C


def test_parse_ndjson_concatenates():
    assert volc_tts_adapter.parse_openspeech_ndjson(_ndjson([b"ab", b"cd"])) == b"abcd"


def test_speaker_alias_and_resource():
    assert volc_tts_adapter.resolve_volc_speaker("narrator_calm", "x") == "zh_female_cancan_uranus_bigtts"
    assert volc_tts_adapter.resolve_volc_speaker("", "zh_x") == "zh_x"
    assert volc_tts_adapter.resource_id_for_speaker("S_abc", "seed-tts-2.0") == "seed-icl-2.0"
    assert volc_tts_adapter.resource_id_for_speaker("zh_female_cancan_uranus_bigtts", "seed-tts-2.0") == "seed-tts-2.0"


async def test_tts_uses_api_key_header_and_default_url(monkeypatch):
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\xff" * 1500])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    audio = await VolcTtsAdapter().tts(_route(), base.TtsRequest(text="xin chào", voice="narrator_calm", emotion_hint="ấm áp"))
    url, headers, body = rec.calls[0]
    assert url == volc_tts_adapter.VOLC_TTS_DEFAULT_URL
    assert headers["X-Api-Key"] == "vk" and headers["X-Api-Resource-Id"] == "seed-tts-2.0"
    assert body["req_params"]["speaker"] == "zh_female_cancan_uranus_bigtts"
    assert body["req_params"]["audio_params"] == {"format": "mp3", "sample_rate": 24000}
    assert "additions" in body["req_params"]
    assert len(audio) == 1500


async def test_tts_legacy_app_id_headers(monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "volc_tts_app_id", "app"); monkeypatch.setattr(s, "volc_tts_access_key", "ak")
    rec = _Recorder(httpx.Response(200, content=_ndjson([b"\x00" * 1200])))
    monkeypatch.setattr(volc_tts_adapter.httpx, "AsyncClient", rec.client())
    await VolcTtsAdapter().tts(_route(api_key=""), base.TtsRequest(text="a", voice="v"))
    _, headers, _ = rec.calls[0]
    assert headers["X-Api-App-Id"] == "app" and headers["X-Api-Access-Key"] == "ak" and "X-Api-Key" not in headers
```

- [ ] **Step 2: Chạy → FAIL**

- [ ] **Step 3: Viết adapter**: chuyển nguyên `voice_map` (→ `SPEAKER_ALIASES`), `_tts_resource_id` (→ `resource_id_for_speaker(speaker, default)`), `_build_tts_additions` (1813–1824), `_tts_openspeech` (1935–1977, thành `tts()` trả bytes thay vì ghi file: `resp.status >= 400` → `RuntimeError`, audio rỗng → `RuntimeError`), `_parse_openspeech_ndjson` (1979–1998). Header: `route.api_key` → `X-Api-Key`; rỗng → `settings.volc_tts_app_id/access_key` (legacy); URL = `route.base_url or settings.volc_tts_url or VOLC_TTS_DEFAULT_URL`; resource mặc định `settings.volc_tts_resource_id or "seed-tts-2.0"`. `list_models` trả `[{"id": "seed-tts-2.0", "label": "Seed TTS 2.0", "capability": "audio"}, {"id": "seed-tts-1.0", ...}, {"id": "seed-icl-2.0", "label": "Voice clone (S_*)", ...}]`. `gen_image/create_video/fetch_video` → `ProviderNotSupported`. `is_transient_error` → `isinstance(exc, httpx.TransportError)`.

- [ ] **Step 4: Chạy → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/providers/volc_tts_adapter.py backend/tests/test_volc_tts_adapter.py
git commit -m "feat: adapter Volc/BytePlus Seed Speech tách khỏi ark.py

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Danh mục chức năng + `function_bindings` + `function_router`

**Files:**
- Create: `backend/app/services/functions.py`, `backend/app/services/function_bindings.py`, `backend/app/services/function_router.py`
- Modify: `backend/app/schemas_routing.py`
- Test: `backend/tests/test_functions_catalog.py`, `backend/tests/test_function_bindings.py`, `backend/tests/test_function_router.py`

**Interfaces:**
- Consumes: `model_settings.get_routing_snapshot()` — ở task này snapshot **chưa có** `function_bindings`; router nhận snapshot qua tham số `snapshot=None` (mặc định gọi `get_routing_snapshot()`), nên test truyền snapshot giả. Task 7 bổ sung field thật.
- Produces:
  ```python
  # app/services/functions.py
  @dataclass(frozen=True) class AiFunction(id: str, capability: LogicalModelCapability, label_vi: str, label_en: str, description_vi: str)
  FUNCTIONS: tuple[AiFunction, ...]           # 10 mục theo spec 5.2, thứ tự bảng
  FUNCTION_BY_ID: dict[str, AiFunction]
  CAPABILITIES: tuple[str, ...] = ("text", "image", "video", "audio")
  def function_capability(function_id: str) -> LogicalModelCapability   # KeyError nếu lạ
  def function_catalog_payload() -> list[dict]                            # cho admin API

  # app/schemas_routing.py (thêm)
  class ModelBinding(BaseModel): channel_id: str; model: str; weight: int = Field(default=1, ge=1, le=100)
  class FunctionBindings(BaseModel):
      slots: dict[str, list[ModelBinding]] = {}      # key ∈ CAPABILITIES
      overrides: dict[str, list[ModelBinding]] = {}  # key ∈ FUNCTION_BY_ID
  class FunctionInfo(BaseModel): id, capability, label, description
  class ProviderPreset(BaseModel): id, name, protocol, base_url, catalog: Literal["remote","static","none"], models: list[dict] = []
  class AdminRoutingSettingsOut(BaseModel): providers: list[SystemModelChannel]; function_bindings: FunctionBindings;
      readiness: list[ModelCapabilityReadiness]; function_catalog: list[FunctionInfo]; presets: list[ProviderPreset];
      validation_errors: list[str]; updated_at: datetime | None
  class AdminRoutingSettingsPatch(BaseModel): providers: list[SystemModelChannelIn] | None = None; function_bindings: FunctionBindings | None = None
  # (xoá LogicalModelBinding, LogicalModel, DefaultModels, default_models_to_dict/from_dict)

  # app/services/function_bindings.py
  def parse_function_bindings(raw: Any) -> FunctionBindings              # dict lỗi/None → rỗng, bỏ khoá lạ
  def bindings_to_dict(b: FunctionBindings) -> dict
  def effective_bindings(b: FunctionBindings, function_id: str) -> list[ModelBinding]   # override → slot
  def validate_function_bindings(b: FunctionBindings, channels: list[SystemModelChannel]) -> list[str]  # tiếng Việt
  def slot_assigned(b: FunctionBindings, capability: str) -> bool

  # app/services/function_router.py
  def allowed_bindings(function_id, *, snapshot=None) -> list[ModelBinding]     # đã lọc provider tắt/thiếu key
  def is_model_allowed(function_id, model_id, *, snapshot=None) -> bool
  def resolve_function_candidates(function_id, requested_model=None, *, snapshot=None, rng=None) -> list[ResolvedModelRoute]
  def resolve_function_route(function_id, requested_model=None, *, snapshot=None, rng=None) -> ResolvedModelRoute | None
  def route_for_channel(channel_id: str, model: str, capability: str, *, snapshot=None) -> ResolvedModelRoute | None
  class ModelNotAllowed(ValueError)   # requested_model không trong danh sách hiệu lực
  ```
  `ResolvedModelRoute.logical_model_id` = function_id; `protocol` = `channel.protocol` (`auto`/rỗng → `openai`); `api_format` = `"ark"` nếu protocol ark, còn lại `"openai"`.

- [ ] **Step 1: Test danh mục + bindings**

```python
# backend/tests/test_functions_catalog.py
"""Danh mục chức năng cố định: 10 mục, đúng năng lực."""
from app.services import functions


def test_catalog_has_ten_functions_in_spec_order():
    ids = [f.id for f in functions.FUNCTIONS]
    assert ids == ["kepu.script", "drama.script", "kepu.image", "drama.asset_image", "tools.image",
                   "kepu.video", "drama.video", "tools.video", "kepu.tts", "drama.tts"]


def test_capabilities():
    assert functions.function_capability("kepu.image") == "image"
    assert functions.function_capability("drama.tts") == "audio"
    assert functions.function_capability("tools.video") == "video"
    assert functions.function_capability("drama.script") == "text"


def test_payload_has_labels():
    row = functions.function_catalog_payload()[0]
    assert row["id"] == "kepu.script" and row["label"] and row["capability"] == "text"
```

```python
# backend/tests/test_function_bindings.py
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
```

- [ ] **Step 2: Test router**

```python
# backend/tests/test_function_router.py
"""function_router: lọc provider hỏng, weight ngẫu nhiên, validate model user chọn, failover."""
import random
from types import SimpleNamespace

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import function_router as fr


def _ch(cid, protocol, models, key="k", enabled=True):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key=key, has_api_key=bool(key),
                              protocol=protocol, models=list(models), enabled=enabled)


def _snap(bindings, channels):
    return SimpleNamespace(channels=channels, function_bindings=bindings)


BYTE = _ch("byteplus", "ark", ["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"])
OAI = _ch("openai", "openai", ["gpt-image-2.5-sunburst", "gpt-5.6-sol"])


def test_route_fields():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]}), [BYTE])
    r = fr.resolve_function_route("kepu.image", snapshot=snap)
    assert r and r.channel_id == "byteplus" and r.protocol == "ark" and r.api_format == "ark"
    assert r.upstream_model == "dola-seedream-5-0-pro-260628" and r.logical_model_id == "kepu.image" and r.api_key == "k"


def test_disabled_or_keyless_provider_filtered():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]}),
                 [_ch("openai", "openai", ["gpt-image-2.5-sunburst"], key="")])
    assert fr.allowed_bindings("kepu.image", snapshot=snap) == []
    assert fr.resolve_function_route("kepu.image", snapshot=snap) is None


def test_model_not_in_provider_list_filtered():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="removed")]}), [BYTE])
    assert fr.allowed_bindings("kepu.image", snapshot=snap) == []


def test_requested_model_must_be_allowed():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]}), [BYTE, OAI])
    assert fr.is_model_allowed("kepu.image", "DOLA-Seedream-5-0-Pro-260628", snapshot=snap)
    assert not fr.is_model_allowed("kepu.image", "gpt-image-2.5-sunburst", snapshot=snap)
    with pytest.raises(fr.ModelNotAllowed):
        fr.resolve_function_candidates("kepu.image", "gpt-image-2.5-sunburst", snapshot=snap)


def test_requested_model_goes_first_then_others():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628"),
                                          ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]})
    cands = fr.resolve_function_candidates("kepu.image", "gpt-image-2.5-sunburst", snapshot=_snap(b, [BYTE, OAI]))
    assert [c.upstream_model for c in cands] == ["gpt-image-2.5-sunburst", "dola-seedream-5-0-pro-260628"]


def test_weighted_pick_is_random_but_seeded():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628", weight=1),
                                          ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst", weight=99)]})
    snap = _snap(b, [BYTE, OAI])
    firsts = {fr.resolve_function_route("kepu.image", snapshot=snap, rng=random.Random(i)).upstream_model for i in range(30)}
    assert "gpt-image-2.5-sunburst" in firsts          # weight 99 thắng đa số
    counts = sum(1 for i in range(200) if fr.resolve_function_route("kepu.image", snapshot=snap, rng=random.Random(i)).upstream_model == "gpt-image-2.5-sunburst")
    assert counts > 150


def test_override_beats_slot():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]},
                         overrides={"tools.image": [ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]})
    snap = _snap(b, [BYTE, OAI])
    assert fr.resolve_function_route("tools.image", snapshot=snap).channel_id == "openai"
    assert fr.resolve_function_route("kepu.image", snapshot=snap).channel_id == "byteplus"


def test_route_for_channel():
    snap = _snap(FunctionBindings(), [BYTE])
    r = fr.route_for_channel("byteplus", "dreamina-seedance-2-5-260628", "video", snapshot=snap)
    assert r and r.protocol == "ark"
    assert fr.route_for_channel("nope", "m", "video", snapshot=snap) is None
```

- [ ] **Step 3: Chạy 3 file → FAIL**

- [ ] **Step 4: Viết `functions.py`**

```python
"""Danh mục chức năng AI cố định (id → năng lực) dùng cho gán model theo chức năng."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas_routing import LogicalModelCapability

CAPABILITIES: tuple[str, ...] = ("text", "image", "video", "audio")


@dataclass(frozen=True)
class AiFunction:
    id: str
    capability: LogicalModelCapability
    label_vi: str
    label_en: str
    description_vi: str


FUNCTIONS: tuple[AiFunction, ...] = (
    AiFunction("kepu.script", "text", "Kịch bản khoa học", "Science script", "Mở rộng chủ đề và tách phân cảnh video khoa học"),
    AiFunction("drama.script", "text", "Kịch bản phim ngắn", "Drama script", "Tóm tắt, chia tập, tách phân cảnh, viết prompt phim ngắn"),
    AiFunction("kepu.image", "image", "Ảnh phân cảnh khoa học", "Science storyboard image", "Ảnh tĩnh từng phân cảnh video khoa học"),
    AiFunction("drama.asset_image", "image", "Ảnh tài sản phim ngắn", "Drama asset image", "Nhân vật, bối cảnh, đạo cụ và ảnh tĩnh phân cảnh"),
    AiFunction("tools.image", "image", "Ảnh công cụ & Open API", "Tools & API image", "Công cụ t2i/i2p và /api/v1/images"),
    AiFunction("kepu.video", "video", "Video khoa học", "Science video", "Video từng phân cảnh video khoa học"),
    AiFunction("drama.video", "video", "Video phim ngắn", "Drama video", "Video phân cảnh và video tài sản phim ngắn"),
    AiFunction("tools.video", "video", "Video công cụ & Open API", "Tools & API video", "Công cụ t2v/i2v và /api/v1/videos"),
    AiFunction("kepu.tts", "audio", "Lời bình khoa học", "Science narration", "Giọng đọc lời bình video khoa học"),
    AiFunction("drama.tts", "audio", "Lồng tiếng phim ngắn", "Drama voice", "Giọng nhân vật và mẫu giọng phim ngắn"),
)
FUNCTION_BY_ID: dict[str, AiFunction] = {f.id: f for f in FUNCTIONS}


def function_capability(function_id: str) -> LogicalModelCapability:
    """Năng lực của chức năng; KeyError nếu id lạ."""
    return FUNCTION_BY_ID[function_id].capability


def function_catalog_payload() -> list[dict[str, str]]:
    """Danh mục cho admin API (nhãn tiếng Việt)."""
    return [{"id": f.id, "capability": f.capability, "label": f.label_vi, "description": f.description_vi} for f in FUNCTIONS]
```

- [ ] **Step 5: Sửa `schemas_routing.py`**: xoá `LogicalModelBinding`, `LogicalModel`, `DefaultModels`, `default_models_to_dict`, `default_models_from_dict`; thêm `ModelBinding`, `FunctionBindings`, `FunctionInfo`, `ProviderPreset`; thay `AdminRoutingSettingsOut`/`AdminRoutingSettingsPatch` theo Interfaces (import `ModelCapabilityReadiness` từ `app.schemas_settings` — kiểm tra không vòng import; nếu vòng, chuyển `ModelCapabilityReadiness` sang `schemas_routing` và `schemas_settings` import lại). `AdminRoutingSettingsSaveOut` giữ nguyên.

- [ ] **Step 6: Viết `function_bindings.py`**

```python
"""Gán model theo chức năng: parse/validate/hợp nhất override → slot (thuần, không DB)."""

from __future__ import annotations

from typing import Any

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.functions import CAPABILITIES, FUNCTION_BY_ID, function_capability
from app.services.model_routing_config import infer_model_capability, normalize_model_name

_CAP_LABEL = {"text": "Văn bản", "image": "Ảnh", "video": "Video", "audio": "Giọng đọc"}


def _parse_list(raw: Any) -> list[ModelBinding]:
    out: list[ModelBinding] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            b = ModelBinding.model_validate(item)
        except Exception:  # noqa: BLE001
            continue
        if b.channel_id.strip() and b.model.strip():
            out.append(b)
    return out


def parse_function_bindings(raw: Any) -> FunctionBindings:
    """Đọc từ config_json; bỏ khoá lạ và phần tử hỏng."""
    if not isinstance(raw, dict):
        return FunctionBindings()
    slots = {k: _parse_list(v) for k, v in (raw.get("slots") or {}).items() if k in CAPABILITIES}
    overrides = {k: _parse_list(v) for k, v in (raw.get("overrides") or {}).items() if k in FUNCTION_BY_ID}
    return FunctionBindings(slots=slots, overrides=overrides)


def bindings_to_dict(b: FunctionBindings) -> dict[str, Any]:
    """Dạng lưu DB."""
    return b.model_dump()


def effective_bindings(b: FunctionBindings, function_id: str) -> list[ModelBinding]:
    """Override của chức năng nếu có, không thì slot năng lực."""
    override = b.overrides.get(function_id) or []
    if override:
        return list(override)
    return list(b.slots.get(function_capability(function_id)) or [])


def slot_assigned(b: FunctionBindings, capability: str) -> bool:
    """Slot năng lực đã có ít nhất một model."""
    return bool(b.slots.get(capability))


def _check(label: str, capability: str, items: list[ModelBinding], channels: dict[str, SystemModelChannel]) -> list[str]:
    errs: list[str] = []
    for item in items:
        ch = channels.get(item.channel_id)
        if ch is None:
            errs.append(f"{label}: provider '{item.channel_id}' không tồn tại")
            continue
        if not any(normalize_model_name(m) == normalize_model_name(item.model) for m in ch.models):
            errs.append(f"{label}: model '{item.model}' chưa được bật ở provider {ch.name}")
            continue
        if ch.protocol == "volc_tts":
            cap = "audio"
        else:
            cap = infer_model_capability(item.model)
        if cap != capability:
            errs.append(f"{label}: model '{item.model}' không phải model {_CAP_LABEL[capability].lower()}")
    return errs


def validate_function_bindings(b: FunctionBindings, channels: list[SystemModelChannel]) -> list[str]:
    """Danh sách lỗi (tiếng Việt); rỗng = hợp lệ."""
    by_id = {c.id: c for c in channels}
    errs: list[str] = []
    for cap, items in b.slots.items():
        errs.extend(_check(f"Slot {_CAP_LABEL.get(cap, cap)}", cap, items, by_id))
    for fid, items in b.overrides.items():
        fn = FUNCTION_BY_ID.get(fid)
        if fn is None:
            errs.append(f"Chức năng '{fid}' không tồn tại")
            continue
        errs.extend(_check(fn.label_vi, fn.capability, items, by_id))
    return list(dict.fromkeys(errs))
```

- [ ] **Step 7: Viết `function_router.py`**

```python
"""Resolve route theo chức năng: override → slot, lọc provider hỏng, chọn theo weight, failover."""

from __future__ import annotations

import random
from typing import Any

from app.schemas_routing import ModelBinding, ResolvedModelRoute, SystemModelChannel
from app.services.function_bindings import effective_bindings
from app.services.functions import function_capability
from app.services.model_routing_config import channel_connection_ready, normalize_model_name


class ModelNotAllowed(ValueError):
    """Model user chọn không nằm trong danh sách admin đã gán cho chức năng."""


def _snapshot(snapshot: Any | None):
    if snapshot is not None:
        return snapshot
    from app.services.model_settings import get_routing_snapshot

    return get_routing_snapshot()


def _channel_ok(ch: SystemModelChannel) -> bool:
    return ch.enabled and (channel_connection_ready(ch) or bool((ch.api_key or "").strip()))


def _protocol(ch: SystemModelChannel) -> str:
    proto = (ch.protocol or "openai").lower()
    return "openai" if proto in ("", "auto") else proto


def _build_route(ch: SystemModelChannel, model: str, capability: str, function_id: str) -> ResolvedModelRoute:
    proto = _protocol(ch)
    return ResolvedModelRoute(
        capability=capability, logical_model_id=function_id, upstream_model=model,
        channel_id=ch.id, channel_name=ch.name, base_url=(ch.base_url or "").rstrip("/"),
        api_key=(ch.api_key or "").strip(), protocol=proto, api_format="ark" if proto == "ark" else "openai",
    )


def allowed_bindings(function_id: str, *, snapshot: Any | None = None) -> list[ModelBinding]:
    """Binding hiệu lực đã loại provider tắt/thiếu key/model không còn bật."""
    snap = _snapshot(snapshot)
    by_id = {c.id: c for c in snap.channels}
    out: list[ModelBinding] = []
    for b in effective_bindings(snap.function_bindings, function_id):
        ch = by_id.get(b.channel_id)
        if ch is None or not _channel_ok(ch):
            continue
        if not any(normalize_model_name(m) == normalize_model_name(b.model) for m in ch.models):
            continue
        out.append(b)
    return out


def is_model_allowed(function_id: str, model_id: str | None, *, snapshot: Any | None = None) -> bool:
    """User chọn model này cho chức năng được không (rỗng = tự động → True)."""
    mid = normalize_model_name(model_id or "")
    if not mid:
        return True
    return any(normalize_model_name(b.model) == mid for b in allowed_bindings(function_id, snapshot=snapshot))


def _weighted_order(items: list[ModelBinding], rng: random.Random) -> list[ModelBinding]:
    pool = list(items)
    out: list[ModelBinding] = []
    while pool:
        pick = rng.choices(pool, weights=[max(1, b.weight) for b in pool], k=1)[0]
        out.append(pick)
        pool.remove(pick)
    return out


def resolve_function_candidates(function_id: str, requested_model: str | None = None, *, snapshot: Any | None = None,
                                rng: random.Random | None = None) -> list[ResolvedModelRoute]:
    """Thứ tự thử: model user chọn trước, còn lại xáo trộn theo weight (failover)."""
    snap = _snapshot(snapshot)
    by_id = {c.id: c for c in snap.channels}
    capability = function_capability(function_id)
    allowed = allowed_bindings(function_id, snapshot=snap)
    mid = normalize_model_name(requested_model or "")
    head: list[ModelBinding] = []
    if mid:
        head = [b for b in allowed if normalize_model_name(b.model) == mid]
        if not head:
            raise ModelNotAllowed(requested_model or "")
    rest = [b for b in allowed if b not in head]
    ordered = head + _weighted_order(rest, rng or random)
    return [_build_route(by_id[b.channel_id], b.model, capability, function_id) for b in ordered]


def resolve_function_route(function_id: str, requested_model: str | None = None, *, snapshot: Any | None = None,
                           rng: random.Random | None = None) -> ResolvedModelRoute | None:
    """Route đầu tiên hoặc None khi chưa gán."""
    cands = resolve_function_candidates(function_id, requested_model, snapshot=snapshot, rng=rng)
    return cands[0] if cands else None


def route_for_channel(channel_id: str, model: str, capability: str, *, snapshot: Any | None = None) -> ResolvedModelRoute | None:
    """Route cố định theo kênh (poll tác vụ đã tạo), không qua bindings."""
    snap = _snapshot(snapshot)
    ch = next((c for c in snap.channels if c.id == channel_id), None)
    if ch is None:
        return None
    return _build_route(ch, model, capability, f"{capability}.poll")
```

`channel_connection_ready` trong `model_routing_config.py`: bỏ nhánh `kie`, giữ `volc_tts` và mặc định `base_url and (has_api_key or api_key)`.

- [ ] **Step 8: Chạy → PASS**: `pytest tests/test_functions_catalog.py tests/test_function_bindings.py tests/test_function_router.py -v`. Các test cũ import `LogicalModel`/`DefaultModels` (`test_generic_text_model_routing.py`, `test_logical_image_route.py`, `test_seedance_model_routing.py`, `test_media_catalog_validation.py`) sẽ vỡ import — xoá `test_generic_text_model_routing.py` ngay (logic sync bị bỏ); 3 file còn lại xoá/viết lại ở Task 10.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/functions.py backend/app/services/function_bindings.py backend/app/services/function_router.py backend/app/schemas_routing.py backend/app/services/model_routing_config.py backend/tests/test_functions_catalog.py backend/tests/test_function_bindings.py backend/tests/test_function_router.py
git rm backend/tests/test_generic_text_model_routing.py
git commit -m "feat: danh mục chức năng, function_bindings và function_router thay logical model

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Gỡ khoá `model_settings.py`, snapshot mới, migration, seed env, admin API

**Files:**
- Create: `backend/app/services/providers/presets.py`
- Modify: `backend/app/services/model_settings.py`, `backend/app/services/upstream_model_catalog.py`, `backend/app/api/admin/settings.py`, `backend/app/config.py`, `backend/app/schemas_settings.py`, `backend/.env.example`
- Test: `backend/tests/test_model_settings_bootstrap.py` (unit), `backend/tests/test_admin_routing_settings.py` (PG)

**Interfaces:**
- Consumes: Task 6 (`FunctionBindings`, `parse_function_bindings`, `validate_function_bindings`, `slot_assigned`), Task 3/4 (`ARK_STATIC_MODELS`, `ARK_DEFAULT_BASE_URL`, `OPENAI_DEFAULT_BASE_URL`, `registry.get_adapter`).
- Produces:
  ```python
  # providers/presets.py
  PROVIDER_PRESETS: list[ProviderPreset]   # openai (remote), byteplus (static: ARK_STATIC_MODELS), openrouter (remote, base https://openrouter.ai/api/v1), volc_tts (static 3 model), custom_openai (remote, base "")
  def preset_by_id(pid: str) -> ProviderPreset | None
  # model_settings.py
  @dataclass class RoutingSnapshot: channels: list[SystemModelChannel]; function_bindings: FunctionBindings
  def get_routing_snapshot() -> RoutingSnapshot
  def _refresh_routing_snapshot(channels, function_bindings) -> None
  def _bootstrap_channels_from_env(settings=None) -> list[SystemModelChannel]      # 0..3 kênh theo key có trong env
  async def _compose_runtime_state(db) -> tuple[list[SystemModelChannel], FunctionBindings, dict, AppSettings]
  async def load_model_settings_cache(db) -> None                                   # + migration legacy
  def _build_readiness(bindings: FunctionBindings, channels) -> list[ModelCapabilityReadiness]
  async def get_admin_routing_settings(db) -> AdminRoutingSettingsOut
  async def patch_admin_routing_settings(db, body: AdminRoutingSettingsPatch) -> tuple[AdminRoutingSettingsOut, list[str]]
  ```

- [ ] **Step 1: Test unit bootstrap/readiness**

```python
# backend/tests/test_model_settings_bootstrap.py
"""Seed provider từ env, readiness theo slot, migration bỏ tokenfree/logical_models."""
from app.config import Settings
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import model_settings as ms


def test_bootstrap_from_env_creates_openai_and_byteplus():
    s = Settings(openai_api_key="sk", openai_base_url="https://api.openai.com/v1", ark_api_key="ak",
                 ark_base_url="https://ark.ap-southeast.bytepluses.com/api/v3", model_llm="gpt-5.6-sol",
                 model_image="dola-seedream-5-0-pro-260628", model_video="dreamina-seedance-2-5-260628",
                 model_audio="gpt-4o-mini-tts", volc_tts_api_key="")
    chans = {c.id: c for c in ms._bootstrap_channels_from_env(s)}
    assert set(chans) == {"openai", "byteplus"}
    assert chans["openai"].protocol == "openai" and "gpt-5.6-sol" in chans["openai"].models and "gpt-4o-mini-tts" in chans["openai"].models
    assert chans["byteplus"].protocol == "ark" and chans["byteplus"].base_url.endswith("/api/v3")
    assert {"dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"} <= set(chans["byteplus"].models)


def test_bootstrap_from_env_without_keys_is_empty():
    assert ms._bootstrap_channels_from_env(Settings(openai_api_key="", ark_api_key="", volc_tts_api_key="", volc_tts_app_id="")) == []


def test_bootstrap_bindings_from_env_channels():
    s = Settings(openai_api_key="sk", ark_api_key="ak", model_llm="gpt-5.6-sol", model_image="dola-seedream-5-0-pro-260628",
                 model_video="dreamina-seedance-2-5-260628", model_audio="gpt-4o-mini-tts")
    b = ms._bootstrap_bindings_from_env(s, ms._bootstrap_channels_from_env(s))
    assert b.slots["text"][0].channel_id == "openai" and b.slots["image"][0].channel_id == "byteplus"
    assert b.slots["video"][0].model == "dreamina-seedance-2-5-260628" and b.slots["audio"][0].model == "gpt-4o-mini-tts"


def test_readiness_marks_unassigned_slots():
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                            protocol="openai", models=["gpt-5.6-sol"], enabled=True)
    b = FunctionBindings(slots={"text": [ModelBinding(channel_id="openai", model="gpt-5.6-sol")]})
    rows = {r.capability: r for r in ms._build_readiness(b, [ch])}
    assert rows["text"].ready and rows["text"].model == "gpt-5.6-sol"
    assert not rows["image"].ready and "Chưa gán" in rows["image"].message


def test_migrate_legacy_config_drops_logical_models():
    cfg = {"flat": {}, "logical_models": [{"id": "x"}], "default_models": {"imageModel": "seedream-5.0"}}
    out, changed = ms._migrate_legacy_config(cfg)
    assert changed and "logical_models" not in out and "default_models" not in out and out["function_bindings"] == {"slots": {}, "overrides": {}}
```

- [ ] **Step 2: Test PG admin PATCH**

```python
# backend/tests/test_admin_routing_settings.py
"""PATCH /settings/routing: thêm provider, gán slot, lỗi validation; kênh tokenfree cũ bị xoá."""
import pytest
from sqlalchemy import select

from app.models_settings import SystemModelChannelRow
from app.schemas_routing import AdminRoutingSettingsPatch, FunctionBindings, ModelBinding, SystemModelChannelIn
from app.services import model_settings as ms


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
```

- [ ] **Step 3: Chạy → FAIL**

- [ ] **Step 4: `presets.py`**

```python
"""Preset provider cho admin: điền sẵn protocol/base URL và cách lấy danh sách model."""

from __future__ import annotations

from app.schemas_routing import ProviderPreset
from app.services.providers.ark_adapter import ARK_DEFAULT_BASE_URL, ARK_STATIC_MODELS
from app.services.providers.openai_adapter import OPENAI_DEFAULT_BASE_URL
from app.services.providers.volc_tts_adapter import BYTEPLUS_TTS_URL, VOLC_TTS_STATIC_MODELS

PROVIDER_PRESETS: list[ProviderPreset] = [
    ProviderPreset(id="openai", name="OpenAI", protocol="openai", base_url=OPENAI_DEFAULT_BASE_URL, catalog="remote"),
    ProviderPreset(id="byteplus", name="BytePlus ModelArk", protocol="ark", base_url=ARK_DEFAULT_BASE_URL, catalog="static", models=ARK_STATIC_MODELS),
    ProviderPreset(id="openrouter", name="OpenRouter", protocol="openai", base_url="https://openrouter.ai/api/v1", catalog="remote"),
    ProviderPreset(id="volc_tts", name="BytePlus Seed Speech", protocol="volc_tts", base_url=BYTEPLUS_TTS_URL, catalog="static", models=VOLC_TTS_STATIC_MODELS),
    ProviderPreset(id="custom_openai", name="OpenAI-compatible tuỳ chỉnh", protocol="openai", base_url="", catalog="remote"),
]


def preset_by_id(pid: str) -> ProviderPreset | None:
    """Tra preset theo id."""
    return next((p for p in PROVIDER_PRESETS if p.id == pid), None)
```

(`VOLC_TTS_STATIC_MODELS` = danh sách 3 model trong `volc_tts_adapter.list_models`, tách thành hằng.)

- [ ] **Step 5: Sửa `config.py` mặc định + `.env.example`**

`config.py`: `ark_base_url = "https://ark.ap-southeast.bytepluses.com/api/v3"`, `openai_base_url = "https://api.openai.com/v1"`, `model_llm = "gpt-5.6-sol"`, `model_image = "dola-seedream-5-0-pro-260628"`, `model_video = "dreamina-seedance-2-5-260628"`, `model_audio = "gpt-4o-mini-tts"`, `volc_tts_url = "https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/unidirectional"`; xoá `tokenfree_image_concurrency` (và khỏi `schemas_settings.model_config_field_names` / `AdminModelSettingsOut` / `AdminModelSettingsPatch` nếu có — `grep -rn tokenfree_image_concurrency app admin/src`). Sửa comment TokenFree → "provider". `.env.example`: cập nhật các dòng `OPENAI_BASE_URL`, `MODEL_*`, thêm `ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3`, ghi chú "chỉ seed lần đầu; sau đó cấu hình trong admin".

- [ ] **Step 6: Viết lại `model_settings.py`**

Giữ: mã hoá Fernet, `_overlay`, `_refresh_overlay`, `_channel_row_to_admin/_runtime`, `_get_or_create_app_row`, `_load_channels`, `_settings_to_dict`, `_decrypt/_encrypt_flat_config`, `_effective_flat`, `get_admin_model_settings`, `patch_admin_model_settings`, `import_admin_model_settings_from_env`, `_to_admin_flat_out`. Xoá: mọi import `tokenfree_*`, `LogicalModel/DefaultModels`, `_seedance_logical_meta`, `_append_seedance_alias`, `_merge_friendly_alias_models`, `_bootstrap_logical_from_channels`, `_bindings_for_upstream`, `_ensure_tokenfree_channel`, mọi `synchronize_*`/`normalize_default_models`/`model_routing_validation_errors`. Viết mới:

```python
@dataclass
class RoutingSnapshot:
    channels: list[SystemModelChannel]
    function_bindings: FunctionBindings


_routing_snapshot = RoutingSnapshot(channels=[], function_bindings=FunctionBindings())


def _refresh_routing_snapshot(channels: list[SystemModelChannel], function_bindings: FunctionBindings) -> None:
    global _routing_snapshot
    _routing_snapshot = RoutingSnapshot(channels=channels, function_bindings=function_bindings)


# Seed provider từ .env lần đầu (chỉ khi DB chưa có provider nào)
def _bootstrap_channels_from_env(settings: Settings | None = None) -> list[SystemModelChannel]:
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
```

`get_admin_model_settings` gọi `_build_readiness(bindings, admin_channels)` (sửa `_to_admin_flat_out` nhận `bindings` thay `logical_models/defaults`).

```python
async def get_admin_routing_settings(db: AsyncSession) -> AdminRoutingSettingsOut:
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


async def patch_admin_routing_settings(db: AsyncSession, body: AdminRoutingSettingsPatch) -> tuple[AdminRoutingSettingsOut, list[str]]:
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
```

Lưu ý `validate_function_bindings` với `admin_channels` (key che): kiểm tra model/protocol không cần key nên dùng được.

- [ ] **Step 7: `upstream_model_catalog.py`** viết lại:

```python
"""Danh sách model khả dụng của một provider: openai → GET /models qua adapter; ark/volc_tts → tĩnh."""
async def list_upstream_models(db, *, channel_id=None, protocol="auto", base_url="", api_key_override=None, capability="all") -> list[dict]:
    # 1) lấy kênh runtime theo channel_id (nếu có) để bù key/base/protocol thiếu
    # 2) route = ResolvedModelRoute(capability="text", logical_model_id="catalog", upstream_model="", channel_id=channel_id or "", channel_name="", base_url=base, api_key=key, protocol=proto, api_format=...)
    # 3) return await get_adapter(proto).list_models(route, capability)
    # openai thiếu base → RuntimeError("Cần Base URL"), thiếu key → RuntimeError("Cần API key")
```

- [ ] **Step 8: `api/admin/settings.py`**: xoá route `/settings/tokenfree/quota`; thêm

```python
class AdminProviderTestRequest(BaseModel):
    """Kiểm tra kết nối provider trước khi lưu."""
    channel_id: str | None = Field(default=None, max_length=64)
    protocol: str = Field(default="openai", max_length=32)
    base_url: str = Field(default="", max_length=512)
    api_key: str | None = Field(default=None, max_length=512)


@router.post("/settings/providers/test")
async def admin_test_provider(body: AdminProviderTestRequest, _admin=Depends(get_current_admin), db=Depends(get_db)) -> dict:
    """openai: GET /models; ark/volc_tts: chỉ kiểm tra có key (không có endpoint rẻ)."""
    try:
        models = await list_upstream_models(db, channel_id=body.channel_id, protocol=body.protocol, base_url=body.base_url, api_key_override=body.api_key)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": f"Kết nối thành công, {len(models)} model", "models_count": len(models)}
```

- [ ] **Step 8b: `/api/health`**: `grep -n "models" app/main.py app/api/*.py | grep -i health` — nếu phần `models` của health đang đọc logical model/default, đổi sang `_build_readiness(snapshot.function_bindings, snapshot.channels)` và trả `"models": "ok" | "not_configured"` (+ danh sách slot chưa gán).

- [ ] **Step 9: Sửa `tests/conftest.py`** không đổi (vẫn stub `tokenfree_pricing`). Chạy: `pytest tests/test_model_settings_bootstrap.py tests/test_model_settings_overlay.py tests/test_admin_routing_settings.py -v` → PASS (file thứ ba cần PostgreSQL).

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/model_settings.py backend/app/services/providers/presets.py backend/app/services/upstream_model_catalog.py backend/app/api/admin/settings.py backend/app/config.py backend/app/schemas_settings.py backend/.env.example backend/tests/test_model_settings_bootstrap.py backend/tests/test_admin_routing_settings.py
git commit -m "feat: gỡ khoá TokenFree ở model_settings, lưu function_bindings, seed provider từ env

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: `media_gateway.py` — facade ảnh/video/poll gọi adapter theo route

**Files:**
- Create: `backend/app/services/media_gateway.py`
- Test: `backend/tests/test_media_gateway.py`

**Interfaces:**
- Consumes: Task 2–7 (`get_adapter`, `resolve_function_candidates`, `route_for_channel`, `ModelNotAllowed`, `ImageRequest/Output`, `VideoRequest`, `TaskResult`, `ark_adapter.seedance_prompt_text / seedance_duration / resolve_seedance_i2v_image_role`), `app.services.storage`, `app.services.style_lock.split_seedream_subject_style_refs`, `app.services.seedream_text_soften`, `app.errors.AppError`.
- Produces:
  ```python
  @dataclass class ImageResult(local_url, remote_url=None, total_tokens=0, prompt_tokens=0, completion_tokens=0,
      raw_usage=None, upstream_cost_fen=None, channel_id="", model="")
  class MediaGateway:
      def __init__(self, settings: Settings | None = None)
      settings: Settings                        # property
      mock: bool                                # property: settings.ark_mock or không provider nào có key
      def channel_for_task(self, task_id: str) -> str | None       # map in-memory task_id → channel_id
      async def gen_image(self, prompt, negative="", ref_urls=None, *, function_id="tools.image", project_id=None,
          shot_no=None, size=None, model=None, aspect_ratio=None, style_ref_urls=None) -> ImageResult
      async def gen_video_i2v(self, image_url, prompt, duration, *, function_id="tools.video", model=None,
          character_consistency=True, resolution="480p", ratio=None, prompt_as_json=True, return_last_frame=True,
          generate_audio=False, extra_image_urls=None) -> str
      async def gen_video_seedance_body(self, body, *, function_id="drama.video", project_id=0, content_labels=None) -> str
      async def gen_and_wait_seedance_body(self, body, *, function_id="drama.video", project_id, shot_no, content_labels=None) -> tuple[str, str|None, TaskResult]
      async def poll_task(self, task_id, *, channel_id=None) -> TaskResult
      async def fetch_task_once(self, task_id, *, channel_id=None) -> TaskResult
      async def save_video_assets_from_result(self, result, *, project_id, shot_no) -> tuple[str, str|None]
      async def wait_video_assets(self, task_id, *, project_id, shot_no, channel_id=None)
      async def wait_video(self, task_id, *, project_id, shot_no, channel_id=None) -> tuple[str, TaskResult]
      async def gen_and_wait_video(self, image_url, prompt, duration, *, function_id="kepu.video", project_id, shot_no,
          character_consistency=True, resolution="480p", ratio=None, max_attempts=3, generate_audio=False, model=None,
          extra_image_urls=None) -> tuple[str, TaskResult]
      async def download_result_media(self, url, dest) -> None
      async def tts(self, text, voice, *, function_id="kepu.tts", project_id=None, shot_no=None, duration_hint=4.0, emotion_hint=None) -> str   # Task 9
      async def chat_storyboard(...); async def expand_content(...)     # delegate kepu_text (Task 1)
      async def _resolve_image_ref(self, image_url, *, prefer_https=False) -> str   # nguyên ark.py:2104-2135
  def get_media_gateway() -> MediaGateway; def reset_media_gateway() -> None
  ```
  Mã lỗi mới trong `app/errors.py`: `"model.slot_not_configured": (503, "该功能尚未配置模型，请联系管理员")`, `"model.not_available": (400, "所选模型当前不可用，请重新选择")` + 3 file locale frontend (`errors.ts`) thêm khoá tương ứng (vi: "Chức năng này chưa được cấu hình mô hình, vui lòng liên hệ quản trị viên" / "Mô hình đã chọn hiện không khả dụng, vui lòng chọn lại"; en tương đương).

- [ ] **Step 1: Test**

```python
# backend/tests/test_media_gateway.py
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


async def test_gen_and_wait_video_passes_model(monkeypatch, snapshot):
    ark = _FakeAdapter("ark", task_id="cgt-2", fetch=base.TaskResult(status="succeeded", url="/static/mock/v.mp4"))
    g = _gateway(monkeypatch, {"ark": ark})
    async def _ref(url, *, prefer_https=False): return "https://pub/f.png"
    monkeypatch.setattr(g, "_resolve_image_ref", _ref)
    local, result = await g.gen_and_wait_video("u", "p", 5, function_id="kepu.video", project_id=1, shot_no=1, model="dreamina-seedance-2-5-260628")
    assert local == "/static/mock/v.mp4" and ark.calls[0][1] == "dreamina-seedance-2-5-260628" and result.channel_id == "byteplus"
```

- [ ] **Step 2: Chạy → FAIL**

- [ ] **Step 3: Viết `media_gateway.py`**

Khung:

```python
"""Facade sinh ảnh/video: resolve route theo chức năng → gọi adapter → lưu file local/OSS. Không chứa HTTP."""

from __future__ import annotations

import asyncio, hashlib, json, logging, time, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.errors import AppError
from app.services import storage
from app.services.function_router import ModelNotAllowed, resolve_function_candidates, route_for_channel
from app.services.providers.ark_adapter import resolve_seedance_i2v_image_role, seedance_duration, seedance_prompt_text
from app.services.providers.base import ImageOutput, ImageRequest, TaskResult, VideoRequest
from app.services.providers.registry import get_adapter, url_needs_auth

logger = logging.getLogger(__name__)


@dataclass
class ImageResult:
    local_url: str
    remote_url: str | None = None
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    upstream_cost_fen: int | None = None
    channel_id: str = ""
    model: str = ""


class MediaGateway:
    """Cổng duy nhất mà pipeline/drama/tools gọi để sinh ảnh, video, TTS."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._task_channels: dict[str, str] = {}

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    @property
    def mock(self) -> bool:
        """ARK_MOCK hoặc chưa có provider nào có key → chạy mock."""
        if self.settings.ark_mock:
            return True
        from app.services.model_settings import get_routing_snapshot

        return not any(c.enabled and (c.api_key or "").strip() for c in get_routing_snapshot().channels)

    def channel_for_task(self, task_id: str) -> str | None:
        return self._task_channels.get(task_id)

    def _candidates(self, function_id: str, model: str | None):
        try:
            cands = resolve_function_candidates(function_id, model)
        except ModelNotAllowed as exc:
            raise AppError("model.not_available") from exc
        if not cands:
            raise AppError("model.slot_not_configured")
        return cands

    async def _try_candidates(self, function_id, model, call):
        """Gọi `call(route, adapter)` lần lượt; chỉ chuyển model kế tiếp khi adapter báo lỗi tạm thời."""
        last: Exception | None = None
        for route in self._candidates(function_id, model):
            adapter = get_adapter(route.protocol)
            try:
                return route, await call(route, adapter)
            except Exception as exc:  # noqa: BLE001
                if not adapter.is_transient_error(exc):
                    raise
                logger.warning("provider %s tạm lỗi (%s), thử model kế tiếp", route.channel_id, exc)
                last = exc
        raise RuntimeError(str(last) if last else "không có provider khả dụng")
```

`gen_image`: nguyên khối soften/3 tầng prompt từ `ark.py:785-863` (mock branch giữ `_write_mock_image` chuyển nguyên 2137–2175); mỗi tầng gọi `self._image_once(full_prompt, ...)`:

```python
    async def _image_once(self, full_prompt, ref_urls, *, function_id, project_id, shot_no, size, model, aspect_ratio, style_ref_urls) -> ImageResult:
        from app.services.style_lock import split_seedream_subject_style_refs

        subject_refs, style_refs = split_seedream_subject_style_refs(ref_urls, style_ref_urls)
        req = ImageRequest(prompt=full_prompt, size=str(size or self.settings.ark_image_size or "2K"), aspect_ratio=aspect_ratio or "",
                           refs=list(subject_refs), style_refs=list(style_refs))
        route, out = await self._try_candidates(function_id, model, lambda r, a: a.gen_image(r, req))
        dest = storage.project_dir(project_id or 0) / f"shot_{(shot_no or 0):03d}_{uuid.uuid4().hex[:12]}.png"
        if out.data:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(out.data)
        else:
            await storage.download_to(out.url, dest, headers=self._auth_headers_for(route, out.url))
        merged = dict(out.raw_usage or {})
        if out.size:
            merged.setdefault("size", out.size)
        return ImageResult(local_url=storage.publish_local(dest, sync=True), remote_url=out.url, total_tokens=out.total_tokens,
                           prompt_tokens=out.prompt_tokens, completion_tokens=out.completion_tokens, raw_usage=merged or None,
                           upstream_cost_fen=get_adapter(route.protocol).cost_fen(route.upstream_model, merged),
                           channel_id=route.channel_id, model=route.upstream_model)
```

`gen_video_i2v`: nguyên phần dựng `content[]` từ `ark.py:1165-1219` (dùng `resolve_seedance_i2v_image_role`, `seedance_prompt_text`, `seedance_duration`), rồi:

```python
        req = VideoRequest(body=body, plain_text=None if not prompt_as_json else plain, target_ratio=target_ratio,
                           allow_structure_fallback=True)
        route, task_id = await self._try_candidates(function_id, model, lambda r, a: a.create_video(r, req))
        self._task_channels[task_id] = route.channel_id
        return task_id
```

`gen_video_seedance_body`: mock → `mock-task-{md5}`; `payload["content"] = await self._resolve_seedance_content_items(...)` (nguyên 1303–1323), `payload["duration"] = seedance_duration(...)`; `VideoRequest(body=payload, target_ratio=payload.get("ratio"), allow_structure_fallback=False, content_labels=content_labels)`; route theo `function_id` với `model=payload.get("model")` (**chỉ** truyền khi model đó nằm trong danh sách hiệu lực — dùng `is_model_allowed`; không thì để `None` để slot quyết định); ghi `_task_channels`.

`fetch_task_once(task_id, *, channel_id=None)`: mock/`mock-task-` → như cũ; `cid = channel_id or self._task_channels.get(task_id)`; `route = route_for_channel(cid, "", "video")` nếu `cid` else `resolve_function_candidates("kepu.video")[0]` (log warning "poll không có channel_id, dùng slot video"); không route → `TaskResult(status="failed", error="Không tìm thấy provider của tác vụ", provider_task_id=task_id)`; `return await get_adapter(route.protocol).fetch_video(route, task_id)` rồi gán `upstream_cost_fen = adapter.cost_fen(...)` khi `raw_usage`. `poll_task`: vòng lặp `deadline = time.monotonic() + ark_video_poll_timeout`, mỗi vòng `fetch_task_once`, `succeeded/failed` → return, ngược lại `await asyncio.sleep(ark_video_poll_interval)`; hết hạn → `TaskResult(status="failed", error="poll timeout", provider_task_id=task_id)`.

`save_video_assets_from_result`, `wait_video_assets`, `wait_video`, `gen_and_wait_video`: nguyên 1578–1705, thêm `channel_id` truyền xuống và **truyền `model=model, function_id=function_id` vào `gen_video_i2v`** (sửa bug). `download_result_media`: header Bearer khi `url_needs_auth(url)` (registry) — lấy key từ route hiện tại của task nếu có, còn lại không header. `gen_and_wait_seedance_body`: nguyên 1408–1499 với `function_id`. `_resolve_image_ref`, `_resolve_media_ref`, `_resolve_seedance_content_items`, `_write_mock_image`, `_is_portrait_size`: nguyên. `chat_storyboard`/`expand_content`: delegate `kepu_text` (như Task 1). `tts`: điền ở Task 9 (tạm `raise NotImplementedError`). Cuối file: `get_media_gateway()`/`reset_media_gateway()` singleton.

- [ ] **Step 4: Thêm 2 mã lỗi vào `app/errors.py` và 3 file `errors.ts`; chạy `pytest tests/test_app_errors.py tests/test_media_gateway.py -v` → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/media_gateway.py backend/app/errors.py frontend/src/i18n/locales backend/tests/test_media_gateway.py
git commit -m "feat: facade media_gateway gọi adapter theo function route, failover và poll theo kênh

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `tts_service.py` — cascade slot Giọng đọc → edge-tts

**Files:**
- Create: `backend/app/services/tts_service.py`
- Modify: `backend/app/services/media_gateway.py` (`tts()` delegate)
- Test: `backend/tests/test_tts_fallback.py` (thay `test_tts_tokenfree_fallback.py`)

**Interfaces:**
- Consumes: `resolve_function_candidates`, `get_adapter`, `TtsRequest`, `ffmpeg_compose.is_near_silent_audio`, `voices.edge_tts_voice_for_text`.
- Produces:
  ```python
  class TtsService:
      def __init__(self, settings: Settings, *, mock: bool)
      async def synthesize(self, text, voice, *, function_id="kepu.tts", project_id=None, shot_no=None, emotion_hint=None) -> str  # trả /static url
      async def _tts_edge(self, text: str, dest: Path, voice_hint: str = "") -> None     # nguyên ark.py:2000-2025
      def _persist_mp3(self, dest: Path, audio: bytes) -> bool                            # nguyên _persist_tts_mp3 2027-2073
  MediaGateway.tts(...) -> TtsService(self.settings, mock=self.mock).synthesize(...)
  ```

- [ ] **Step 1: Test**

```python
# backend/tests/test_tts_fallback.py
"""TTS: slot audio lỗi → edge-tts; adapter đầu OK thì dừng; tất cả hỏng → raise, không ghi im lặng."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import tts_service as ts
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot
from app.services.providers import base

MP3 = b"ID3" + b"\x00" * 3000


@pytest.fixture
def audio_snapshot():
    prev = get_routing_snapshot()
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                            protocol="openai", models=["gpt-4o-mini-tts"], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"audio": [ModelBinding(channel_id="openai", model="gpt-4o-mini-tts")]}))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def _svc(monkeypatch, tmp_path, adapter):
    monkeypatch.setattr(ts, "get_adapter", lambda proto: adapter)
    monkeypatch.setattr(ts.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(ts.storage, "publish_local", lambda p, sync=False: f"/static/{p.name}")
    monkeypatch.setattr(ts, "is_near_silent_audio", lambda p: False)
    return ts.TtsService(SimpleNamespace(ffmpeg_path="ffmpeg", volc_tts_speaker="zh_female_cancan_uranus_bigtts"), mock=False)


async def test_slot_adapter_ok_no_edge(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    edge = AsyncMock(); monkeypatch.setattr(svc, "_tts_edge", edge)
    url = await svc.synthesize("xin chào", "narrator_calm", function_id="kepu.tts", project_id=1, shot_no=3)
    assert url == "/static/shot_003_tts.mp3" and edge.await_count == 0
    req = adapter.tts.await_args.args[1]
    assert isinstance(req, base.TtsRequest) and req.voice == "narrator_calm"


async def test_adapter_error_falls_back_to_edge(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("boom")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    async def edge(text, dest: Path, voice_hint=""): dest.write_bytes(MP3)
    monkeypatch.setattr(svc, "_tts_edge", edge)
    assert (await svc.synthesize("a", "v", project_id=1, shot_no=1)).endswith("shot_001_tts.mp3")


async def test_no_audio_slot_goes_straight_to_edge(monkeypatch, tmp_path):
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        svc = _svc(monkeypatch, tmp_path, SimpleNamespace(tts=AsyncMock()))
        async def edge(text, dest: Path, voice_hint=""): dest.write_bytes(MP3)
        monkeypatch.setattr(svc, "_tts_edge", edge)
        assert await svc.synthesize("a", "v", project_id=1, shot_no=1)
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_all_fail_raises_and_no_file(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("x")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    monkeypatch.setattr(svc, "_tts_edge", AsyncMock(side_effect=RuntimeError("edge down")))
    with pytest.raises(RuntimeError):
        await svc.synthesize("a", "v", project_id=1, shot_no=2)
    assert not (tmp_path / "shot_002_tts.mp3").exists()


async def test_near_silent_output_rejected(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    monkeypatch.setattr(ts, "is_near_silent_audio", lambda p: True)
    monkeypatch.setattr(svc, "_tts_edge", AsyncMock(side_effect=RuntimeError("edge down")))
    with pytest.raises(RuntimeError):
        await svc.synthesize("a", "v", project_id=1, shot_no=2)
```

- [ ] **Step 2: Chạy → FAIL**

- [ ] **Step 3: Viết `tts_service.py`**

```python
"""Giọng đọc: mock → model trong slot Giọng đọc (theo function) → edge-tts; thất bại thì raise, không ghi im lặng."""

from __future__ import annotations

import asyncio, hashlib, logging
from pathlib import Path

from app.config import Settings
from app.services import storage
from app.services.ffmpeg_compose import is_near_silent_audio
from app.services.function_router import resolve_function_candidates
from app.services.providers.base import TtsRequest
from app.services.providers.registry import get_adapter
from app.services.voices import edge_tts_voice_for_text

logger = logging.getLogger(__name__)


class TtsService:
    """Cascade TTS cho khoa học và phim ngắn."""

    def __init__(self, settings: Settings, *, mock: bool) -> None:
        self.settings = settings
        self.mock = mock

    async def synthesize(self, text, voice, *, function_id="kepu.tts", project_id=None, shot_no=None, emotion_hint=None) -> str:
        clean = (text or "").strip() or "这一幕。"
        speaker = (voice or "").strip() or (self.settings.volc_tts_speaker or "")
        if self.mock:
            digest = hashlib.md5(f"{speaker}:{clean}".encode()).hexdigest()[:8]
            dest = Path(__file__).resolve().parents[2] / "static" / "mock" / f"audio_{digest}.mp3"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or dest.stat().st_size < 1000:
                await self._tts_edge(clean, dest, voice_hint=speaker)
            return f"/static/mock/audio_{digest}.mp3"

        dest = storage.project_dir(project_id or 0) / f"shot_{(shot_no or 0):03d}_tts.mp3"
        req = TtsRequest(text=clean, voice=speaker, emotion_hint=emotion_hint)
        for route in resolve_function_candidates(function_id):
            adapter = get_adapter(route.protocol)
            try:
                audio = await adapter.tts(route, req)
            except Exception as exc:  # noqa: BLE001
                logger.warning("TTS %s/%s lỗi: %s", route.channel_id, route.upstream_model, exc)
                continue
            if self._persist_mp3(dest, audio):
                url = await self._accept_if_audible(dest, f"{route.channel_id}")
                if url:
                    return url
        try:
            await self._tts_edge(clean, dest, voice_hint=speaker)
            url = await self._accept_if_audible(dest, "edge-tts")
            if url:
                return url
        except Exception as exc:  # noqa: BLE001
            logger.warning("edge-tts failed: %s", exc)
        dest.unlink(missing_ok=True)
        raise RuntimeError("配音失败：语音服务暂不可用，请稍后重试")

    async def _accept_if_audible(self, dest: Path, label: str) -> str | None:
        """Từ chối file quá nhỏ hoặc gần im lặng."""
        if not dest.exists() or dest.stat().st_size < 2000:
            return None
        if await asyncio.to_thread(is_near_silent_audio, dest):
            logger.warning("%s produced near-silence", label)
            dest.unlink(missing_ok=True)
            return None
        return storage.publish_local(dest)
```

+ `_tts_edge` (nguyên 2000–2025) + `_persist_mp3` (nguyên 2027–2073, đổi tên). `MediaGateway.tts(...)`: `return await TtsService(self.settings, mock=self.mock).synthesize(text, voice, function_id=function_id, project_id=project_id, shot_no=shot_no, emotion_hint=emotion_hint)`.

- [ ] **Step 4: `git rm backend/tests/test_tts_tokenfree_fallback.py`; chạy `pytest tests/test_tts_fallback.py -v` → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts_service.py backend/app/services/media_gateway.py backend/tests/test_tts_fallback.py
git rm -q backend/tests/test_tts_tokenfree_fallback.py
git commit -m "feat: tts_service theo slot Giọng đọc với edge-tts dự phòng

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: `ark.py` thành shim, xoá module TokenFree, cập nhật call site + resolver + catalog

**Files:**
- Modify: `backend/app/services/ark.py` (shim), `backend/app/services/kepu_continuity.py`, `backend/app/services/llm_client.py`, `backend/app/services/billing/pricing.py`, `backend/app/services/drama/seedream_options.py`, `backend/app/services/drama/build_seedance_generate_body.py`, `backend/app/services/media_catalog.py`, `backend/app/api/projects.py`, `backend/app/schemas.py`, `backend/app/models.py`, `backend/app/main.py`, `backend/app/services/exc_format.py`, call site: `pipeline.py`, `drama/generation.py`, `drama/asset_video.py`, `drama/voice_synthesis.py`, `drama/llm.py`, `studio_tools.py`, `api/v1/generation.py`, `api/projects.py`
- Delete: `backend/app/services/tokenfree_gateway.py`, `tokenfree_image.py`, `tokenfree_video.py`, `tokenfree_audio.py`, `logical_model_router.py`, `tests/test_tokenfree_image.py`, `tests/test_tokenfree_video.py`, `tests/test_tokenfree_audio.py`, `tests/test_logical_image_route.py`, `tests/test_seedance_model_routing.py`
- Test: `backend/tests/test_media_catalog_validation.py` (viết lại), `backend/tests/test_kepu_continuity.py` (sửa 4 test), `backend/tests/test_llm_client_tokens.py` (mới), `backend/tests/test_ark_poll_resilience.py` (sửa fixture)

**Interfaces:**
- Produces:
  ```python
  # app/services/ark.py — shim, giữ mọi tên test/caller đang dùng
  from app.services.media_gateway import ImageResult, MediaGateway, get_media_gateway, reset_media_gateway
  from app.services.providers.base import TaskResult, IMAGE_GEN_READ_SEC, VIDEO_CREATE_READ_SEC, upstream_timeout as _upstream_timeout, reraise_upstream_timeout, is_transient_http_status as _is_transient_http_status, retry_after_seconds as _retry_after_seconds
  from app.services.providers.ark_adapter import SEEDREAM_CG_STYLE as _SEEDREAM_CG_STYLE, build_task_result_from_payload as _build_task_result_from_payload, format_seedance_create_error as _format_seedance_create_error, raise_seedream_http_error as _raise_seedream_http_error
  from app.services.kepu_text import ShotPlan, StoryboardResult, storyboard_name_policy
  ArkGateway = MediaGateway; get_ark = get_media_gateway; reset_ark = reset_media_gateway
  # MediaGateway có thêm staticmethod delegate: _is_seedance_text_policy_error, _is_seedance_input_privacy_error, _seedance_content_with_cg_style (→ ark_adapter), _build_tts_additions (→ volc_tts_adapter)
  # llm_client
  async def chat_completions(system, user, *, function_id: str = "drama.script", temperature=0.6, max_tokens=..., timeout=300.0, response_format=None) -> str
  # media_catalog
  def build_media_catalog(*, image_function: str, video_function: str, snapshot=None) -> dict
  def catalog_payload(scope: str | None = None) -> dict      # scope kepu|drama|tools|None(union)
  def is_valid_project_media_model(model_id, capability) -> bool   # kepu.image / kepu.video
  # drama/seedream_options.resolve_seedream_model_endpoint(model_id) / build_seedance_generate_body.resolve_seedance_model_endpoint(model_id)
  #   → route.upstream_model của drama.asset_image / drama.video (model được phép) hoặc raw/ settings.model_*
  ```

- [ ] **Step 1: Test mới/sửa**

```python
# backend/tests/test_llm_client_tokens.py
"""llm_client: OpenAI chính thức dùng max_completion_tokens; provider khác dùng max_tokens; route theo function."""
import httpx
import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import llm_client
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot


def _snap(base_url):
    ch = SystemModelChannel(id="c", name="c", base_url=base_url, api_key="k", has_api_key=True, protocol="openai", models=["m"], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"text": [ModelBinding(channel_id="c", model="m")]}))


class _Rec:
    def __init__(self): self.body = None
    def client(self):
        rec = self
        class _C:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, headers=None, json=None):
                rec.body = json; return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        return _C


@pytest.mark.parametrize("base,key", [("https://api.openai.com/v1", "max_completion_tokens"), ("https://ark.ap-southeast.bytepluses.com/api/v3", "max_tokens")])
async def test_token_param_by_host(monkeypatch, base, key):
    prev = get_routing_snapshot(); _snap(base)
    try:
        rec = _Rec(); monkeypatch.setattr(llm_client.httpx, "AsyncClient", rec.client())
        assert await llm_client.chat_completions("s", "u", function_id="kepu.script", max_tokens=100) == "ok"
        assert rec.body[key] == 100 and ("max_tokens" in rec.body) != ("max_completion_tokens" in rec.body)
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_unconfigured_text_slot_raises(monkeypatch):
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        with pytest.raises(llm_client.LlmUnavailableError):
            await llm_client.chat_completions("s", "u", function_id="drama.script")
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
```

```python
# backend/tests/test_media_catalog_validation.py (viết lại toàn bộ)
"""Catalog phía user lấy từ slot/override; scope kepu/drama/tools; validate model dự án."""
import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import media_catalog
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot


@pytest.fixture
def snap():
    prev = get_routing_snapshot()
    byte = SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://x", api_key="k", has_api_key=True, protocol="ark",
                              models=["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"], enabled=True)
    oai = SystemModelChannel(id="openai", name="OpenAI", base_url="https://x", api_key="k", has_api_key=True, protocol="openai", models=["gpt-image-2"], enabled=True)
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")],
                                "video": [ModelBinding(channel_id="byteplus", model="dreamina-seedance-2-5-260628")]},
                         overrides={"tools.image": [ModelBinding(channel_id="openai", model="gpt-image-2")]})
    _refresh_routing_snapshot([byte, oai], b)
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_scope_kepu_lists_slot_models(snap):
    cat = media_catalog.catalog_payload("kepu")
    assert [m["id"] for m in cat["image_models"]] == ["dola-seedream-5-0-pro-260628"]
    assert cat["image_models"][0]["provider"] == "byteplus" and cat["image_models"][0]["recommended"]
    assert cat["defaults"] == {"image_model": "dola-seedream-5-0-pro-260628", "video_model": "dreamina-seedance-2-5-260628"}


def test_scope_tools_uses_override(snap):
    cat = media_catalog.catalog_payload("tools")
    assert [m["id"] for m in cat["image_models"]] == ["gpt-image-2"]


def test_no_scope_is_union(snap):
    ids = {m["id"] for m in media_catalog.catalog_payload()["image_models"]}
    assert ids == {"dola-seedream-5-0-pro-260628", "gpt-image-2"}


def test_project_model_validation(snap):
    assert media_catalog.is_valid_project_media_model("", "image")
    assert media_catalog.is_valid_project_media_model("dola-seedream-5-0-pro-260628", "image")
    assert not media_catalog.is_valid_project_media_model("gpt-image-2", "image")     # chỉ override tools
    assert not media_catalog.is_valid_project_media_model("garbage", "video")


def test_empty_config_gives_empty_lists():
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        cat = media_catalog.catalog_payload("drama")
        assert cat["image_models"] == [] and cat["defaults"]["image_model"] == ""
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
```

`tests/test_kepu_continuity.py`: 4 test có "tokenfree" trong tên đổi thành kiểm tra URL cần auth qua `monkeypatch.setattr("app.services.kepu_continuity.url_needs_auth", lambda u: "private.example" in u)` với URL `https://private.example/x.jpg` thay cho URL tokenfree; hành vi mong đợi giữ nguyên (bị bỏ qua).

`tests/test_ark_poll_resilience.py`: fixture `ark_client` → tạo `ArkAdapter()` và route giả; các test `fetch_once_*`/`poll_*` gọi `adapter.fetch_video(route, "t")` (transient → `running`, 404 → `failed`, network → `running`); test `poll_*` chuyển sang `MediaGateway.poll_task` với `monkeypatch.setattr(gateway, "fetch_task_once", ...)` theo kịch bản; nhóm `seedance_*` giữ nguyên qua `MediaGateway` (patch `gen_video_seedance_body`/`wait_video_assets` như cũ, `get_ark` vẫn trả `MediaGateway`).

- [ ] **Step 2: Chạy các test trên → FAIL**

- [ ] **Step 3: `ark.py` → shim** theo Interfaces (xoá toàn bộ phần còn lại). Thêm vào `MediaGateway`:

```python
    # Giữ tương thích test/caller cũ: các classifier Seedance/TTS nay nằm ở adapter
    _is_seedance_text_policy_error = staticmethod(ark_adapter.is_seedance_text_policy_error)
    _is_seedance_input_privacy_error = staticmethod(ark_adapter.is_seedance_input_privacy_error)
    _seedance_content_with_cg_style = staticmethod(ark_adapter.seedance_content_with_cg_style)
    _build_tts_additions = staticmethod(volc_tts_adapter.build_tts_additions)
```

- [ ] **Step 4: `git rm` 5 module + 5 test** như liệt kê ở Files.

- [ ] **Step 5: `kepu_continuity.py`**: thay hai import tokenfree bằng `from app.services.providers.registry import url_needs_auth`; `_usable_seedream_url`: `if url_needs_auth(url): return None` (cả sau republish); `_usable_video_ref`: `return None if url_needs_auth(url) else url`. Sửa docstring.

- [ ] **Step 6: `llm_client.py`**

```python
from app.services.function_router import resolve_function_route
from app.services.providers.openai_adapter import is_official_openai

async def chat_completions(system, user, *, function_id: str = "drama.script", temperature=0.6, max_tokens=DEFAULT_MAX_TOKENS, timeout=300.0, response_format=None) -> str:
    route = resolve_function_route(function_id)
    if route is None or not route.upstream_model:
        raise LlmUnavailableError("Chưa gán model văn bản. Vào Admin → Cài đặt → Mô hình để cấu hình.")
    api_key, model, base = route.api_key, route.upstream_model, route.base_url
    # kimi 系列仅允许 temperature=0.6，其它值会 400
    effective_temperature = 0.6 if model.lower().startswith("kimi") else temperature
    payload: dict[str, Any] = {
        "model": model,
        "temperature": effective_temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    payload["max_completion_tokens" if is_official_openai(base) else "max_tokens"] = max_tokens
    extra = _llm_extra_body(model)
    if extra:
        payload.update(extra)
    if response_format:
        payload["response_format"] = response_format
    # phần POST + kiểm tra HTML/JSON giữ nguyên llm_client.py:108-142
```

Xoá `resolve_llm_api_key`, `resolve_llm_base_url`, chuỗi "TokenFree". `chat_storyboard`/`expand_content` trong `kepu_text.py` truyền `function_id="kepu.script"`; `drama/llm.py` (`drama_chat_json`, `drama_chat_text`) truyền `function_id="drama.script"` (mặc định).

- [ ] **Step 7: Resolver drama**

```python
# drama/seedream_options.py
def resolve_seedream_model_endpoint(model_id: str | None) -> str:
    """Model ảnh cho phim ngắn: model user chọn (nếu admin cho phép) hoặc model đầu của slot; rỗng → settings.model_image."""
    from app.services.function_router import ModelNotAllowed, resolve_function_route
    try:
        route = resolve_function_route("drama.asset_image", (model_id or "").strip() or None)
    except ModelNotAllowed:
        route = resolve_function_route("drama.asset_image")
    return route.upstream_model if route else ((model_id or "").strip() or get_settings().model_image)
```

`build_seedance_generate_body.resolve_seedance_model_endpoint` tương tự với `"drama.video"` và `settings.model_video`. Xoá import `logical_model_router` ở cả hai file (và mọi nơi: `grep -rn logical_model_router app tests`).

- [ ] **Step 8: `media_catalog.py`** viết lại:

```python
"""Catalog ảnh/video phía user: lấy từ slot/override đã gán, theo scope sản phẩm."""
_SCOPE_FUNCTIONS = {"kepu": ("kepu.image", "kepu.video"), "drama": ("drama.asset_image", "drama.video"), "tools": ("tools.image", "tools.video")}

def _rows(function_id, snapshot=None) -> list[dict]:
    from app.services.function_router import allowed_bindings
    seen, out = set(), []
    for b in allowed_bindings(function_id, snapshot=snapshot):
        key = normalize_model_name(b.model)
        if key in seen: continue
        seen.add(key)
        out.append({"id": b.model, "label": b.model, "description": "", "provider": b.channel_id, "recommended": not out})
    return out

def build_media_catalog(*, image_function, video_function, snapshot=None) -> dict:
    images, videos = _rows(image_function, snapshot), _rows(video_function, snapshot)
    return {"image_models": images, "video_models": videos,
            "defaults": {"image_model": images[0]["id"] if images else "", "video_model": videos[0]["id"] if videos else ""}}

def catalog_payload(scope: str | None = None) -> dict:
    if scope in _SCOPE_FUNCTIONS:
        return build_media_catalog(image_function=_SCOPE_FUNCTIONS[scope][0], video_function=_SCOPE_FUNCTIONS[scope][1])
    # không scope (client cũ): hợp nhất 3 scope theo thứ tự kepu → drama → tools, không trùng id
    merged = {"image_models": [], "video_models": []}
    seen = {"image_models": set(), "video_models": set()}
    for key in ("kepu", "drama", "tools"):
        part = build_media_catalog(image_function=_SCOPE_FUNCTIONS[key][0], video_function=_SCOPE_FUNCTIONS[key][1])
        for bucket in ("image_models", "video_models"):
            for row in part[bucket]:
                norm = normalize_model_name(row["id"])
                if norm in seen[bucket]:
                    continue
                seen[bucket].add(norm)
                merged[bucket].append({**row, "recommended": not merged[bucket]})
    merged["defaults"] = {"image_model": merged["image_models"][0]["id"] if merged["image_models"] else "",
                          "video_model": merged["video_models"][0]["id"] if merged["video_models"] else ""}
    return merged

def is_valid_project_media_model(model_id, capability) -> bool:
    from app.services.function_router import is_model_allowed
    return is_model_allowed("kepu.image" if capability == "image" else "kepu.video", model_id)
```

`api/projects.py` `GET /media-models`: thêm `scope: str | None = Query(default=None)` → `catalog_payload(scope)`. `schemas.py` `image_model/video_model` `max_length=128`; `models.py` `String(128)`; `main.py` `_apply_schema_patches` thêm `ALTER TABLE projects ALTER COLUMN image_model TYPE VARCHAR(128)` và `video_model` (idempotent).

- [ ] **Step 9: `billing/pricing.py`** `_catalog_image_fen_if_per_call`: bỏ import `tokenfree_image`; `is_seedream_family` chuyển thành hàm nhỏ trong `drama/seedream_options.py` (`"seedream" in mid.lower()`), `tokenfree_working_image_model(raw)` → dùng `raw` nguyên. `parse_upstream_cost_fen`: giữ nhánh quota (import `tokenfree_usage` vẫn tồn tại) — Plan B dọn.

- [ ] **Step 10: Call site truyền `function_id` + model thật cho usage**

| File | Thay đổi |
|---|---|
| `pipeline.py:970`, `:1512` | `ark.gen_image(..., function_id="kepu.image", ...)`; `_record_seedream_usage(..., model=img.model or s.model_image)` |
| `pipeline.py:1198`, `:1596` | `gen_and_wait_video(..., function_id="kepu.video", model=video_model)` |
| `pipeline.py:304` | `ark.tts(..., function_id="kepu.tts")` |
| `drama/generation.py:1311`, `:1616` | `function_id="drama.asset_image"` |
| `drama/generation.py:1646`, `:1652` | `gen_video_seedance_body(..., function_id="drama.video")`, `gen_video_i2v(..., function_id="drama.video", model=prepared.model_id)`; thông báo kie → "Kênh video cũ không còn, hãy tạo lại phân cảnh này" |
| `drama/asset_video.py:119` | `function_id="drama.video"` |
| `drama/voice_synthesis.py:191` | `function_id="drama.tts"` |
| `studio_tools.py:193`, `:384`, `:425` | `function_id="tools.image"` / `"tools.video"`; `record_seedream_image_usage(model=result.model or settings.model_image)` |
| `api/v1/generation.py:64`, `:120`, `:180` | `tools.image` / `tools.video`; `/seedance/tasks` payload bỏ `"model": settings.model_video` (slot quyết định) |
| `api/projects.py:126` | không đổi (delegate) |
| `exc_format.py:38` | "TokenFree" → "nhà cung cấp mô hình" |

- [ ] **Step 11: Chạy toàn bộ unit** `pytest -q --ignore=tests/test_tokenfree_pricing.py --ignore=tests/test_tokenfree_usage.py` (PG có thì chạy cả); sửa cho xanh. `grep -rn --include='*.py' -i tokenfree app | grep -v "tokenfree_pricing\|tokenfree_usage\|billing/\|admin/upstream_usage\|admin/finance\|api/admin/settings.py:12[0-9]"` phải rỗng.

- [ ] **Step 12: Commit**

```bash
git add -A backend/app backend/tests
git commit -m "refactor: ark.py thành shim, xoá module TokenFree, call site đi qua function route

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: `TaskRun.provider_channel_id` — poll đúng kênh ở drama / api / studio

**Files:**
- Modify: `backend/app/models_tasks.py`, `backend/app/main.py` (`_apply_schema_patches`), `backend/app/schemas_tasks.py`, `backend/app/services/drama/jobs.py`, `backend/app/services/billing/ephemeral.py`, `backend/app/services/tasks/poller.py`, `backend/app/services/studio_tools.py`, `backend/app/api/tools.py`, `backend/app/api/v1/generation.py`, `backend/app/services/drama/billing_util.py`
- Test: `backend/tests/test_provider_channel_binding.py` (PG)

**Interfaces:**
- Produces: `TaskRun.provider_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)`; `TaskRunOut.provider_channel_id: str | None`; `studio_tools.poll_video_task(user, task_id, *, channel_id: str | None = None)`; `record_seedance_video_usage(..., channel_id: str | None = None)`; `record_seedream_image_usage` ghi `provider=image_result.channel_id or "ark"`.

- [ ] **Step 1: Test**

```python
# backend/tests/test_provider_channel_binding.py
"""Submit ghi provider_channel_id; poll drama/ephemeral truyền kênh đó vào fetch_task_once."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from app.services import ark as ark_module
from app.services.providers.base import TaskResult


async def test_column_exists(db_session):
    cols = (await db_session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='task_runs'"))).scalars().all()
    assert "provider_channel_id" in cols


async def test_ephemeral_deferred_stores_channel(db_session, monkeypatch):
    from app.models import User
    from app.services.billing.ephemeral import run_billed_ephemeral_deferred

    # tạo user theo cách tests/test_billing_integration.py đang làm (cùng helper/field)
    user = User(email="c@x.vn", password_hash="x", balance_fen=100000); db_session.add(user); await db_session.flush()
    gw = ark_module.get_ark(); gw._task_channels["cgt-77"] = "byteplus"
    async def exec_(): return {"task_id": "cgt-77"}
    task, _ = await run_billed_ephemeral_deferred(db_session, user, domain="studio", task_type="tool_video", executor=exec_, payload={"duration": 5}, commit=False)
    assert task.provider_task_id == "cgt-77" and task.provider_channel_id == "byteplus"


async def test_ephemeral_poll_passes_channel(db_session, monkeypatch):
    from app.models import User
    from app.services.tasks import poller
    from app.models_tasks import TaskRun

    user = User(email="p@x.vn", password_hash="x"); db_session.add(user); await db_session.flush()
    task = TaskRun(domain="studio", task_type="tool_video", status="awaiting_poll", requested_by=user.id, provider_task_id="cgt-1", provider_channel_id="byteplus", billing_status="frozen")
    db_session.add(task); await db_session.flush()
    seen = {}
    async def fake_poll(u, tid, *, channel_id=None):
        seen["channel"] = channel_id; return {"status": "running", "kind": "video", "urls": [], "usage": {}}
    monkeypatch.setattr("app.services.studio_tools.poll_video_task", fake_poll)
    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: db_session)   # xem ghi chú fixture trong file
    from datetime import UTC, datetime
    await poller._poll_one_ephemeral_task(task.id, now=datetime.now(UTC), timeout_sec=900)
    assert seen["channel"] == "byteplus"


async def test_fetch_task_once_receives_channel(monkeypatch):
    gw = ark_module.get_ark()
    spy = AsyncMock(return_value=TaskResult(status="running"))
    monkeypatch.setattr(gw, "fetch_task_once", spy)
    from app.services.studio_tools import poll_video_task
    from types import SimpleNamespace
    await poll_video_task(SimpleNamespace(id=1), "cgt-5", channel_id="byteplus")
    assert spy.await_args.kwargs["channel_id"] == "byteplus"
```

(Nếu `poller.AsyncSessionLocal` khó thay bằng session test, gọi trực tiếp đoạn xử lý sau khi tách thành `_poll_ephemeral_with_session(db, task, user, now, timeout_sec)` — refactor nhỏ hợp lệ trong task này.)

- [ ] **Step 2: Chạy → FAIL**

- [ ] **Step 3: Thực hiện**

1. `models_tasks.py`: thêm cột sau `provider_task_id`. `main.py` `_apply_schema_patches`: `tcols = await _pg_columns(conn, "task_runs"); if "provider_channel_id" not in tcols: ALTER TABLE task_runs ADD COLUMN provider_channel_id VARCHAR(64)`. `schemas_tasks.py`: thêm `provider_channel_id: str | None = None` vào `TaskRunOut` và `AdminTaskRunOut`.
2. `drama/jobs.py:1201-1202` (sau `task_row.provider_task_id = provider_task_id`): `task_row.provider_channel_id = get_ark().channel_for_task(provider_task_id)`; `:1411`: `fetch_task_once(task.provider_task_id, channel_id=task.provider_channel_id)`; `:1474` không đổi; `apply_fragment_video_assets(...)` → `record_seedance_video_usage(..., channel_id=task.provider_channel_id)` (thêm tham số xuyên suốt).
3. `billing/ephemeral.py` `run_billed_ephemeral_deferred`: sau `task.provider_task_id = provider_id` thêm `task.provider_channel_id = get_ark().channel_for_task(provider_id)` (import trong hàm).
4. `tasks/poller.py:286`: `poll_video_task(user, provider_id, channel_id=task.provider_channel_id)`.
5. `studio_tools.poll_video_task(user, task_id, *, channel_id=None)`: `ark.fetch_task_once(task_id, channel_id=channel_id)`.
6. `api/tools.py:163` và `api/v1/generation.py:223`: tra `TaskRun.provider_channel_id` theo `provider_task_id` (v1 đã query `TaskRun`; đổi `select(TaskRun.id, TaskRun.provider_channel_id)`), truyền vào `poll_video_task`.
7. `drama/billing_util.py`: `record_seedance_video_usage(..., channel_id=None)` → re-fetch `get_ark().fetch_task_once(provider_id, channel_id=channel_id)`; `provider = channel_id or getattr(task_result, "channel_id", "") or "ark"`; `record_seedream_image_usage`: `provider = getattr(image_result, "channel_id", "") or "ark"`. Xoá dò chuỗi "kie".

- [ ] **Step 4: Chạy** `pytest tests/test_provider_channel_binding.py tests/test_task_poller_dispatch.py tests/test_seedance_billing_usage.py tests/test_record_seedream_image_usage.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add -A backend/app backend/tests
git commit -m "feat: lưu provider_channel_id trên TaskRun và poll video đúng kênh đã tạo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Tài liệu, kiểm tra toàn bộ, mock e2e

**Files:**
- Create: `docs/PROVIDERS.md`
- Modify: `CLAUDE.md` (mục "模型路由"), `README.md` (đoạn TokenFree), `backend/.env.example` (đã sửa Task 7 — rà lại)

- [ ] **Step 1: `docs/PROVIDERS.md`** (tiếng Việt): kiến trúc adapter (interface Task 2), cách thêm provider mới (tạo file adapter, đăng ký trong `registry.get_adapter`, thêm preset), danh sách model tĩnh BytePlus và cách cập nhật, `function_bindings` JSON mẫu, lệnh `PATCH /api/admin/settings/routing` mẫu bằng curl để cấu hình khi chưa có UI, giới hạn (OpenAI không video; URL kết quả BytePlus 24 h).

- [ ] **Step 2: `CLAUDE.md`**: thay mục "模型路由：上游被锁定为 TokenFree" bằng mô tả mới (providers/adapters, `function_bindings`, `function_router`, `media_gateway`, `TaskRun.provider_channel_id`, mock khi không key), giữ ngôn ngữ tiếng Trung như phần còn lại của file. `README.md`: thay các câu "统一走 TokenFree New API" bằng "trực tiếp OpenAI + BytePlus ModelArk (xem docs/PROVIDERS.md)".

- [ ] **Step 3: Chạy toàn bộ**

```bash
cd backend && pytest -q                  # cần PostgreSQL cho nhóm db_session
cd ../frontend && npm run lint && npm run build
cd ../admin && npm run build             # tab Mô hình vỡ về payload là chấp nhận được, nhưng phải build được (sửa type AdminRoutingSettings tối thiểu để tsc qua)
```

- [ ] **Step 4: Mock e2e** — `ARK_MOCK=true uvicorn app.main:app --port 8000`, `GET /api/health` phải `ok`; `GET /api/media-models?scope=kepu` trả JSON; tạo dự án khoa học từ chủ đề qua UI hoặc curl và chạy tới `DONE`; drama: tạo project → tạo ảnh tài sản → video phân cảnh (mock) hoàn tất; tools t2i/t2v mock. Ghi kết quả vào commit message.

- [ ] **Step 5: Commit**

```bash
git add docs/PROVIDERS.md CLAUDE.md README.md backend/.env.example admin/src
git commit -m "docs: tài liệu lớp provider và cập nhật CLAUDE.md/README sau khi bỏ TokenFree

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Sau Plan A

- **Plan B (billing)**: `provider_rates` + `adapter.cost_fen` + `estimates.py` + xoá `tokenfree_pricing/usage`, upstream-usage compare, endpoint model-rates.
- **Plan C (admin UI + frontend + docs)**: màn hình 2 cột, `PaymentSettingsPanel`/`RuntimeSettingsPanel`/Dashboard/Finance, i18n frontend bỏ chữ TokenFree, `docs/BILLING.md`, `docs/releases/`.
