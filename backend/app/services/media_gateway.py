"""Facade sinh ảnh/video: resolve route theo chức năng → gọi adapter → lưu file local/OSS. Không chứa HTTP."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings
from app.errors import AppError
from app.schemas_routing import ResolvedModelRoute
from app.services import storage
from app.services.ark_mock import mock_image_caption
from app.services import kepu_text
from app.services.function_router import (
    ModelNotAllowed,
    allowed_bindings,
    is_model_allowed,
    resolve_function_candidates,
    route_for_channel,
)
from app.services.providers import ark_adapter, volc_tts_adapter
from app.services.providers.ark_adapter import (
    resolve_seedance_i2v_image_role,
    seedance_duration,
    seedance_prompt_text,
)
from app.services.providers.base import ImageRequest, TaskResult, VideoRequest
from app.services.providers.registry import get_adapter, url_needs_auth

logger = logging.getLogger(__name__)

# Tiền tố task id giả lập khi chạy mock (không có key upstream)
MOCK_TASK_PREFIX = "mock-task-"
# Prompt tối thiểu khi người dùng không mô tả chuyển động
DEFAULT_MOTION_PROMPT = "画面轻微动态，保持主体外形稳定"
# Lỗi tạo video đáng thử lại ở tầng gen_and_wait_video (đổi kiểu prompt)
RETRYABLE_VIDEO_ERRORS = ("summary_caption", "BodyFormat", "InvalidParameter", "poll timeout")


@dataclass
class ImageResult:
    """Kết quả sinh ảnh: đường dẫn local đã publish + usage + kênh/model thực tế đã dùng."""

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

    # Giữ tương thích test/caller cũ: các classifier Seedance/TTS nay nằm ở adapter
    _is_seedance_text_policy_error = staticmethod(ark_adapter.is_seedance_text_policy_error)
    _is_seedance_input_privacy_error = staticmethod(ark_adapter.is_seedance_input_privacy_error)
    _seedance_content_with_cg_style = staticmethod(ark_adapter.seedance_content_with_cg_style)
    _sanitize_seedream_prompt = staticmethod(ark_adapter.sanitize_seedream_prompt)
    _build_tts_additions = staticmethod(volc_tts_adapter.build_tts_additions)

    def __init__(self, settings: Settings | None = None) -> None:
        """Khởi tạo facade; `settings=None` nghĩa là luôn đọc cấu hình hiện hành."""
        self._settings = settings
        self._task_channels: dict[str, str] = {}

    @property
    def settings(self) -> Settings:
        """Cấu hình đang dùng (đã phủ overlay từ DB nếu lấy qua get_settings)."""
        return self._settings or get_settings()

    @property
    def mock(self) -> bool:
        """ARK_MOCK hoặc chưa có provider nào có key → chạy mock."""
        if self.settings.ark_mock:
            return True
        from app.services.model_settings import get_routing_snapshot

        return not any(c.enabled and (c.api_key or "").strip() for c in get_routing_snapshot().channels)

    def channel_for_task(self, task_id: str) -> str | None:
        """Kênh đã tạo tác vụ này (nhớ trong tiến trình, dùng để poll đúng provider)."""
        return self._task_channels.get(task_id)

    # ---- Route & failover -------------------------------------------------

    def _candidates(self, function_id: str, model: str | None) -> list[ResolvedModelRoute]:
        """Danh sách route ứng viên cho chức năng; lỗi rõ ràng khi model bị cấm hoặc slot chưa gán."""
        try:
            cands = resolve_function_candidates(function_id, model)
        except ModelNotAllowed as exc:
            raise AppError("model.not_available") from exc
        if not cands:
            raise AppError("model.slot_not_configured")
        return cands

    async def _try_candidates(
        self,
        function_id: str,
        model: str | None,
        call: Callable[[ResolvedModelRoute, Any], Awaitable[Any]],
    ) -> tuple[ResolvedModelRoute, Any]:
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

    def _auth_headers_for(self, route: ResolvedModelRoute | None, url: str | None) -> dict[str, str] | None:
        """Header Bearer khi URL kết quả của provider cần xác thực mới tải được."""
        if route and route.api_key and url_needs_auth(url or ""):
            return {"Authorization": f"Bearer {route.api_key}"}
        return None

    # ---- Ảnh ---------------------------------------------------------------

    async def gen_image(
        self,
        prompt: str,
        negative: str = "",
        ref_urls: list[str] | None = None,
        *,
        function_id: str = "tools.image",
        project_id: int | None = None,
        shot_no: int | None = None,
        size: str | None = None,
        model: str | None = None,
        aspect_ratio: str | None = None,
        style_ref_urls: list[str] | None = None,
    ) -> ImageResult:
        """Sinh ảnh theo route của chức năng.

        Chỉ làm dịu phần văn bản của người dùng và giữ nguyên tiền tố cấu trúc (ba hình chiếu…);
        khi upstream chặn vì InputTextSensitive thì rút gọn prompt rồi thử lại, tầng cuối chỉ còn
        «ba hình chiếu + phong cách trang phục». Không bịa nội dung thay thế.
        """
        requested_model = (model or "").strip() or None

        if self.mock:
            local = await asyncio.to_thread(self._write_mock_image, prompt, size)
            # _write_mock_image trả /static/...; bật OSS thì publish tiếp lên public
            path = storage.local_path_from_url(local)
            url = storage.publish_local(path) if path and path.exists() else local
            return ImageResult(local_url=url, remote_url=None)

        from app.services.seedream_text_soften import (
            compact_seedream_prompt_for_retry,
            soften_seedream_input_text,
            style_only_seedream_prompt_for_retry,
        )
        from app.services.providers.ark_adapter import (
            is_seedream_input_text_sensitive,
            is_seedream_policy_error,
        )

        original = (prompt or "").strip()
        current = soften_seedream_input_text(original)
        if current != original:
            logger.info("Seedream input softened shot=%s before=%s after=%s", shot_no, len(original), len(current))

        attempts = [current]
        for builder in (compact_seedream_prompt_for_retry, style_only_seedream_prompt_for_retry):
            candidate = builder(current)
            if candidate and candidate not in attempts:
                attempts.append(candidate)

        last_err: Exception | None = None
        labels = ("softened", "compact", "style_only")
        for idx, candidate in enumerate(attempts):
            full_prompt = f"{candidate}。避免：{negative}" if negative else candidate
            try:
                return await self._image_once(
                    full_prompt,
                    ref_urls,
                    function_id=function_id,
                    project_id=project_id,
                    shot_no=shot_no,
                    size=size,
                    model=requested_model,
                    aspect_ratio=aspect_ratio,
                    style_ref_urls=style_ref_urls,
                )
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                msg = str(exc)
                # Chỉ lỗi kiểm duyệt văn bản mới được rút gọn thử lại; lỗi khác trả thẳng
                if not is_seedream_input_text_sensitive(msg):
                    if is_seedream_policy_error(msg):
                        logger.warning("Seedream policy hit shot=%s; failing without fallback", shot_no)
                    raise
                if idx + 1 < len(attempts):
                    nxt = labels[idx + 1] if idx + 1 < len(labels) else "next"
                    logger.warning("Seedream InputTextSensitive shot=%s; retrying %s prompt", shot_no, nxt)
                    continue
                logger.warning("Seedream InputTextSensitive shot=%s; retries exhausted", shot_no)
                raise
        raise RuntimeError(str(last_err) if last_err else "Seedream failed")

    async def _image_once(
        self,
        full_prompt: str,
        ref_urls: list[str] | None,
        *,
        function_id: str,
        project_id: int | None,
        shot_no: int | None,
        size: str | None,
        model: str | None,
        aspect_ratio: str | None,
        style_ref_urls: list[str] | None,
    ) -> ImageResult:
        """Một lượt gọi adapter sinh ảnh rồi lưu kết quả (bytes hoặc URL) về đĩa."""
        from app.services.style_lock import split_seedream_subject_style_refs

        subject_refs, style_refs = split_seedream_subject_style_refs(ref_urls, style_ref_urls)
        req = ImageRequest(
            prompt=full_prompt,
            size=str(size or self.settings.ark_image_size or "2K"),
            aspect_ratio=aspect_ratio or "",
            refs=list(subject_refs),
            style_refs=list(style_refs),
        )
        route, out = await self._try_candidates(function_id, model, lambda r, a: a.gen_image(r, req))
        dest = storage.project_dir(project_id or 0) / f"shot_{(shot_no or 0):03d}_{uuid.uuid4().hex[:12]}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if out.data:
            dest.write_bytes(out.data)
        else:
            await storage.download_to(out.url, dest, headers=self._auth_headers_for(route, out.url))
        merged = dict(out.raw_usage or {})
        if out.size:
            merged.setdefault("size", out.size)
        return ImageResult(
            local_url=storage.publish_local(dest, sync=True),
            remote_url=out.url,
            total_tokens=out.total_tokens,
            prompt_tokens=out.prompt_tokens,
            completion_tokens=out.completion_tokens,
            raw_usage=merged or None,
            upstream_cost_fen=get_adapter(route.protocol).cost_fen(route.upstream_model, merged or None),
            channel_id=route.channel_id,
            model=route.upstream_model,
        )

    # ---- Video: tạo tác vụ -------------------------------------------------

    async def gen_video_i2v(
        self,
        image_url: str,
        prompt: str,
        duration: int,
        *,
        function_id: str = "tools.video",
        model: str | None = None,
        character_consistency: bool = True,
        resolution: str = "480p",
        ratio: str | None = None,
        prompt_as_json: bool = True,
        return_last_frame: bool = True,
        generate_audio: bool = False,
        extra_image_urls: list[str] | None = None,
    ) -> str:
        """Tạo tác vụ ảnh → video theo route của chức năng; trả task id của provider.

        `character_consistency` giữ lại cho tương thích chữ ký cũ: trường lạ từng làm upstream
        báo BodyFormat nên không được gửi lên.
        """
        if self.mock:
            digest = hashlib.md5(f"{image_url}:{prompt}".encode()).hexdigest()[:10]
            return f"{MOCK_TASK_PREFIX}{digest}"

        # Seedance cần ảnh https công khai (data URI hay bị từ chối với lỗi khó hiểu)
        image_ref = await self._resolve_image_ref(image_url, prefer_https=True)
        plain = (prompt or "").strip() or DEFAULT_MOTION_PROMPT
        text = plain if not prompt_as_json else seedance_prompt_text(prompt)
        # Kịch bản kiểu phân cảnh theo mốc thời gian thì luôn gửi văn bản thuần
        if "@duration:" in plain or "00:" in plain or plain.startswith("【"):
            text = plain
            prompt_as_json = False
        # Có khung hình mục tiêu thì dùng reference_image + ratio; first_frame thuần không được gửi ratio
        image_role, target_ratio = resolve_seedance_i2v_image_role(ratio)
        extra_refs: list[str] = []
        for raw in extra_image_urls or []:
            text_url = str(raw or "").strip()
            if not text_url:
                continue
            try:
                extra_refs.append(await self._resolve_image_ref(text_url, prefer_https=True))
            except Exception:  # noqa: BLE001
                logger.warning("Seedance extra ref resolve failed url=%s", text_url[:120])
        if extra_refs:
            # Nhiều ảnh chỉ đi được đường reference_image, không trộn với first_frame
            image_role = "reference_image"
            if not target_ratio:
                target_ratio = (ratio or "").strip() or "16:9"
        content: list[dict[str, Any]] = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_ref}, "role": image_role},
        ]
        for extra in extra_refs[:2]:
            content.append({"type": "image_url", "image_url": {"url": extra}, "role": "reference_image"})
        body: dict[str, Any] = {
            "content": content,
            "duration": seedance_duration(duration),
            "resolution": resolution,
            "watermark": False,
            "generate_audio": bool(generate_audio),
            "return_last_frame": bool(return_last_frame),
        }
        if target_ratio:
            body["ratio"] = target_ratio
        req = VideoRequest(
            body=body,
            plain_text=plain if prompt_as_json else None,
            target_ratio=target_ratio,
            allow_structure_fallback=True,
        )
        route, task_id = await self._try_candidates(function_id, model, lambda r, a: a.create_video(r, req))
        self._task_channels[task_id] = route.channel_id
        logger.info(
            "i2v create channel=%s model=%s duration=%s resolution=%s ratio=%s role=%s generate_audio=%s task=%s",
            route.channel_id,
            route.upstream_model,
            body["duration"],
            resolution,
            body.get("ratio") or "(omit)",
            image_role,
            body["generate_audio"],
            task_id,
        )
        return task_id

    async def gen_video_seedance_body(
        self,
        body: dict[str, Any],
        *,
        function_id: str = "drama.video",
        project_id: int = 0,
        content_labels: list[str] | None = None,
    ) -> str:
        """Gửi body Seedance đa phương thức (ảnh tham chiếu + reference_audio) theo route của chức năng."""
        if self.mock:
            digest = hashlib.md5(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:10]
            return f"{MOCK_TASK_PREFIX}{digest}"

        payload = dict(body)
        content = payload.get("content")
        if isinstance(content, list):
            payload["content"] = await self._resolve_seedance_content_items(content, project_id=project_id)
        payload["duration"] = seedance_duration(payload.get("duration", 8))
        # Model trong body chỉ là gợi ý: không nằm trong danh sách admin gán thì để slot tự chọn
        requested = str(payload.get("model") or "").strip() or None
        if requested and not is_model_allowed(function_id, requested):
            logger.warning("model %s không thuộc chức năng %s, dùng model của slot", requested, function_id)
            requested = None
        req = VideoRequest(
            body=payload,
            target_ratio=payload.get("ratio"),
            allow_structure_fallback=False,
            content_labels=content_labels,
        )
        route, task_id = await self._try_candidates(function_id, requested, lambda r, a: a.create_video(r, req))
        self._task_channels[task_id] = route.channel_id
        logger.info(
            "Seedance multimodal create channel=%s model=%s duration=%s items=%s task=%s",
            route.channel_id,
            route.upstream_model,
            payload.get("duration"),
            len(payload.get("content") or []),
            task_id,
        )
        return task_id

    async def gen_and_wait_seedance_body(
        self,
        body: dict[str, Any],
        *,
        function_id: str = "drama.video",
        project_id: int,
        shot_no: int,
        max_attempts: int = 2,
        content_labels: list[str] | None = None,
    ) -> tuple[str, str | None, TaskResult]:
        """Tạo tác vụ Seedance đa phương thức rồi chờ xong; trả (video local, ảnh khung cuối local, kết quả)."""

        def _is_audio_download_error(err: Exception) -> bool:
            """Lỗi upstream báo không tải được reference_audio."""
            msg = str(err)
            return "audio_url" in msg and "resource download failed" in msg

        def _strip_reference_audio(src: dict[str, Any]) -> dict[str, Any] | None:
            """Bỏ mọi reference_audio và dòng mô tả âm sắc; không có gì để bỏ thì trả None."""
            content = src.get("content")
            if not isinstance(content, list):
                return None
            filtered: list[dict[str, Any]] = []
            removed = False
            for item in content:
                if not isinstance(item, dict):
                    filtered.append(item)
                    continue
                if item.get("type") == "audio_url" and item.get("role") == "reference_audio":
                    removed = True
                    continue
                if item.get("type") == "text":
                    text = str(item.get("text") or "")
                    cleaned_lines = [
                        line
                        for line in text.splitlines()
                        if "参考音频" not in line and "角色音色" not in line and "旁白音色" not in line
                    ]
                    filtered.append({**item, "text": "\n".join(cleaned_lines).strip()})
                    continue
                filtered.append(item)
            if not removed:
                return None
            return {**src, "content": filtered}

        last_err: Exception | None = None
        fallback_body = body
        audio_fallback_used = False

        def _audio_fallback(exc: Exception, *, accepted: bool) -> bool:
            """Chỉ «tải tham chiếu âm thanh lỗi» mới được bỏ audio và gửi lại một lần.

            Gửi lại sau khi upstream đã nhận tác vụ sẽ sinh tác vụ tính phí thứ hai, nên danh
            sách cho phép phải hẹp: chặn riêng tư / thất bại / hết hạn chờ đều phải trả thẳng.
            """
            nonlocal fallback_body, audio_fallback_used, last_err
            last_err = exc
            if audio_fallback_used or not _is_audio_download_error(exc):
                return False
            stripped = _strip_reference_audio(fallback_body)
            if not stripped:
                return False
            logger.warning(
                "Seedance reference_audio download failed (%s); retry once without audio refs project=%s shot=%s",
                "after accept" if accepted else "at submit",
                project_id,
                shot_no,
            )
            fallback_body = stripped
            audio_fallback_used = True
            return True

        for _attempt in range(max_attempts):
            # Giai đoạn gửi: trừ lỗi âm thanh tham chiếu, mọi lỗi khác trả thẳng, không tạo lại đơn
            try:
                task_id = await self.gen_video_seedance_body(
                    fallback_body,
                    function_id=function_id,
                    project_id=project_id,
                    content_labels=content_labels,
                )
            except Exception as exc:  # noqa: BLE001
                if _audio_fallback(exc, accepted=False):
                    continue
                raise
            # Giai đoạn chờ: chặn riêng tư / thất bại / quá hạn trả thẳng, chỉ lỗi âm thanh gửi lại
            try:
                return await self.wait_video_assets(
                    task_id,
                    project_id=project_id,
                    shot_no=shot_no,
                    channel_id=self.channel_for_task(task_id),
                )
            except Exception as exc:  # noqa: BLE001
                if _audio_fallback(exc, accepted=True):
                    continue
                raise
        raise RuntimeError(str(last_err) if last_err else "Seedance multimodal failed")

    # ---- Video: truy vấn tác vụ -------------------------------------------

    def _mock_task_result(self, task_id: str) -> TaskResult:
        """Kết quả giả lập cho task id mock (không gọi upstream)."""
        return TaskResult(
            status="succeeded",
            url=f"/static/mock/video_{task_id[-8:]}.mp4",
            last_frame_url=f"/static/mock/last_{task_id[-8:]}.jpg",
            provider_task_id=task_id,
        )

    def _poll_route(self, task_id: str, channel_id: str | None) -> ResolvedModelRoute | None:
        """Route để truy vấn tác vụ: ưu tiên kênh đã ghi nhớ, không có thì dùng binding đầu của slot video.

        Tuyệt đối không dùng `resolve_function_candidates` ở đây: hàm đó xáo trộn theo weight nên
        hai lần poll cùng một tác vụ có thể rơi vào hai provider khác nhau (provider sai trả 404 →
        tác vụ bị hiểu nhầm là hỏng). Binding đầu tiên admin gán là lựa chọn cố định.
        """
        cid = (channel_id or self._task_channels.get(task_id) or "").strip()
        if cid:
            return route_for_channel(cid, "", "video")
        logger.warning("poll không có channel_id task=%s, dùng provider đầu của slot video", task_id)
        bindings = allowed_bindings("kepu.video")
        if not bindings:
            return None
        first = bindings[0]
        return route_for_channel(first.channel_id, first.model, "video")

    async def fetch_task_once(self, task_id: str, *, channel_id: str | None = None) -> TaskResult:
        """Truy vấn tác vụ video một lần theo đúng kênh đã tạo, không chờ vòng lặp."""
        if self.mock or task_id.startswith(MOCK_TASK_PREFIX):
            return self._mock_task_result(task_id)
        route = self._poll_route(task_id, channel_id)
        if route is None:
            return TaskResult(
                status="failed",
                error="Không tìm thấy provider của tác vụ",
                provider_task_id=task_id,
            )
        adapter = get_adapter(route.protocol)
        result = await adapter.fetch_video(route, task_id)
        result.provider_task_id = result.provider_task_id or task_id
        result.channel_id = result.channel_id or route.channel_id
        if result.raw_usage:
            result.upstream_cost_fen = adapter.cost_fen(route.upstream_model, result.raw_usage)
        return result

    async def poll_task(self, task_id: str, *, channel_id: str | None = None) -> TaskResult:
        """Lặp truy vấn tác vụ đến khi xong/hỏng hoặc hết hạn chờ cấu hình."""
        if self.mock or task_id.startswith(MOCK_TASK_PREFIX):
            return self._mock_task_result(task_id)
        # Chốt provider một lần trước vòng lặp: đổi kênh giữa chừng sẽ hỏi nhầm provider
        cid = (channel_id or self._task_channels.get(task_id) or "").strip()
        if not cid:
            route = self._poll_route(task_id, None)
            if route is None:
                return TaskResult(
                    status="failed",
                    error="Không tìm thấy provider của tác vụ",
                    provider_task_id=task_id,
                )
            cid = route.channel_id
        deadline = time.monotonic() + float(self.settings.ark_video_poll_timeout)
        interval = float(self.settings.ark_video_poll_interval)
        while time.monotonic() < deadline:
            result = await self.fetch_task_once(task_id, channel_id=cid)
            if result.status in ("succeeded", "failed"):
                return result
            await asyncio.sleep(interval)
        return TaskResult(status="failed", error="poll timeout", provider_task_id=task_id)

    # ---- Video: lưu kết quả ------------------------------------------------

    async def download_result_media(self, url: str, dest: Path, *, channel_id: str | None = None) -> None:
        """Tải media kết quả về đĩa; chỉ gắn Bearer khi provider yêu cầu xác thực cho URL đó."""
        headers: dict[str, str] | None = None
        timeout: float | httpx.Timeout = 300.0
        if url_needs_auth(url or ""):
            route = route_for_channel(channel_id, "", "video") if channel_id else None
            headers = self._auth_headers_for(route, url)
            timeout = httpx.Timeout(connect=30.0, read=600.0, write=60.0, pool=30.0)
        await storage.download_to(url, dest, headers=headers, timeout=timeout)

    async def save_video_assets_from_result(
        self,
        result: TaskResult,
        *,
        project_id: int,
        shot_no: int,
    ) -> tuple[str, str | None]:
        """Lưu kết quả poll thành công thành video local và ảnh khung cuối (nếu có)."""
        if result.status != "succeeded" or not result.url:
            raise RuntimeError(result.error or "video generation failed")

        channel_id = result.channel_id or None
        if result.url.startswith("/static/"):
            video_local = result.url
        else:
            # Mỗi lần sinh một tên file riêng, tránh đè mất bản cũ
            stamp = int(time.time())
            dest = storage.project_dir(project_id) / f"shot_{shot_no:03d}_{stamp}.mp4"
            await self.download_result_media(result.url, dest, channel_id=channel_id)
            video_local = storage.publish_local(dest)

        last_local: str | None = None
        if result.last_frame_url:
            try:
                if result.last_frame_url.startswith("/static/"):
                    last_local = result.last_frame_url
                else:
                    stamp = int(time.time())
                    frame_dest = storage.project_dir(project_id) / f"shot_{shot_no:03d}_{stamp}_last.jpg"
                    await self.download_result_media(result.last_frame_url, frame_dest, channel_id=channel_id)
                    last_local = storage.publish_local(frame_dest)
            except Exception:  # noqa: BLE001
                logger.warning("failed to save last frame project=%s shot=%s", project_id, shot_no)
        return video_local, last_local

    async def wait_video_assets(
        self,
        task_id: str,
        *,
        project_id: int,
        shot_no: int,
        channel_id: str | None = None,
    ) -> tuple[str, str | None, TaskResult]:
        """Chờ tác vụ xong rồi lưu video (kèm ảnh khung cuối nếu upstream trả về)."""
        result = await self.poll_task(task_id, channel_id=channel_id)
        video_local, last_local = await self.save_video_assets_from_result(
            result,
            project_id=project_id,
            shot_no=shot_no,
        )
        return video_local, last_local, result

    async def wait_video(
        self,
        task_id: str,
        *,
        project_id: int,
        shot_no: int,
        channel_id: str | None = None,
    ) -> tuple[str, TaskResult]:
        """Chờ thành phẩm và ghi ảnh khung cuối đã lưu ngược vào result cho phân cảnh sau tham chiếu."""
        video_local, last_local, result = await self.wait_video_assets(
            task_id, project_id=project_id, shot_no=shot_no, channel_id=channel_id
        )
        if last_local:
            result.last_frame_url = last_local
        return video_local, result

    async def gen_and_wait_video(
        self,
        image_url: str,
        prompt: str,
        duration: int,
        *,
        function_id: str = "kepu.video",
        project_id: int,
        shot_no: int,
        character_consistency: bool = True,
        resolution: str = "480p",
        ratio: str | None = None,
        max_attempts: int = 3,
        generate_audio: bool = False,
        model: str | None = None,
        extra_image_urls: list[str] | None = None,
    ) -> tuple[str, TaskResult]:
        """Tạo tác vụ i2v rồi chờ thành phẩm; lỗi định dạng prompt thì đổi kiểu prompt thử lại."""
        last_err: Exception | None = None
        for attempt in range(max_attempts):
            use_json = attempt != 1  # lượt 0 JSON, lượt 1 văn bản thuần, lượt 2 lại JSON
            try:
                task_id = await self.gen_video_i2v(
                    image_url,
                    prompt,
                    duration,
                    function_id=function_id,
                    model=model,
                    character_consistency=character_consistency,
                    resolution=resolution,
                    ratio=ratio,
                    prompt_as_json=use_json,
                    generate_audio=generate_audio,
                    extra_image_urls=extra_image_urls,
                )
                return await self.wait_video(
                    task_id,
                    project_id=project_id,
                    shot_no=shot_no,
                    channel_id=self.channel_for_task(task_id),
                )
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                msg = str(exc)
                retryable = any(k in msg for k in RETRYABLE_VIDEO_ERRORS)
                logger.warning(
                    "Seedance attempt %s/%s shot=%s failed: %s", attempt + 1, max_attempts, shot_no, msg[:300]
                )
                if not retryable or attempt >= max_attempts - 1:
                    break
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(str(last_err) if last_err else "video generation failed")

    # ---- Tiếng nói & văn bản ----------------------------------------------

    async def tts(
        self,
        text: str,
        voice: str,
        *,
        function_id: str = "kepu.tts",
        project_id: int | None = None,
        shot_no: int | None = None,
        duration_hint: float = 4.0,
        emotion_hint: str | None = None,
    ) -> str:
        """Sinh lời bình theo route của chức năng: uỷ quyền cho TtsService (cascade slot → edge-tts)."""
        from app.services.tts_service import TtsService

        return await TtsService(self.settings, mock=self.mock).synthesize(
            text,
            voice,
            function_id=function_id,
            project_id=project_id,
            shot_no=shot_no,
            emotion_hint=emotion_hint,
        )

    async def chat_storyboard(self, *args: Any, **kwargs: Any) -> kepu_text.StoryboardResult:
        """Tách phân cảnh khoa học: uỷ quyền cho kepu_text (giữ nguyên chữ ký cũ)."""
        return await kepu_text.chat_storyboard(*args, mock=self.mock, **kwargs)

    async def expand_content(self, topic: str, mode: str = "theme") -> dict[str, str]:
        """Mở rộng chủ đề: uỷ quyền cho kepu_text."""
        return await kepu_text.expand_content(topic, mode, mock=self.mock)

    # ---- Tham chiếu media & mock ------------------------------------------

    async def _resolve_image_ref(self, image_url: str, *, prefer_https: bool = False) -> str:
        """Đổi URL ảnh thành dạng upstream tải được (https công khai / data URI)."""
        raw = (image_url or "").strip()
        if raw.startswith("https://"):
            return raw
        if raw.startswith("http://"):
            # Upstream trên cloud không tải được LAN/localhost; chỉ giữ khi host công khai
            host = (urlparse(raw).hostname or "").lower()
            if host and host not in {"localhost", "127.0.0.1", "::1"} and not host.startswith(("192.168.", "10.")):
                return raw
        if prefer_https:
            # Seedance cần https công khai; ảnh /static nội bộ phải đẩy lên OSS trước
            local = storage.local_path_from_url(raw)
            if local and local.exists():
                public = storage.republish_url(raw, sync=True)
                if public and str(public).startswith("https://"):
                    return str(public)
                raise RuntimeError(
                    "Seedance 需要公网可访问的图片 URL（请启用 OSS 并确保参考图已上传），"
                    "本地 /static 图无法被方舟拉取"
                )
            if raw.startswith("data:"):
                raise RuntimeError("Seedance 不支持 data URI 图片，请使用 Ark CDN https 链接")
        if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("data:"):
            return raw
        local = storage.local_path_from_url(raw)
        if local and local.exists():
            # Ưu tiên data URI để upstream đọc được mà không cần CDN công khai
            return storage.file_to_data_uri(local)
        # Phương án cuối: URL public tuyệt đối (chỉ chạy nếu upstream với tới được máy bạn)
        return storage.to_public_url(raw)

    async def _resolve_media_ref(self, media_url: str, *, prefer_https: bool = False) -> str:
        """Đổi URL ảnh/âm thanh thành dạng upstream tải được."""
        return await self._resolve_image_ref(media_url, prefer_https=prefer_https)

    async def _resolve_seedance_content_items(
        self,
        items: list[dict[str, Any]],
        *,
        project_id: int = 0,
    ) -> list[dict[str, Any]]:
        """Đổi mọi image_url/audio_url trong content[] sang URL upstream tải được."""
        resolved: list[dict[str, Any]] = []
        for item in items:
            copy = dict(item)
            if item.get("type") == "image_url":
                raw_url = (item.get("image_url") or {}).get("url") or ""
                copy["image_url"] = {"url": await self._resolve_media_ref(str(raw_url), prefer_https=True)}
            elif item.get("type") == "audio_url":
                raw_url = (item.get("audio_url") or {}).get("url") or ""
                copy["audio_url"] = {"url": await self._resolve_media_ref(str(raw_url), prefer_https=True)}
            resolved.append(copy)
        return resolved

    def _write_mock_image(self, prompt: str, size: str | None = None) -> str:
        """Ghi ảnh mock SVG; mỗi lần một tên file riêng để retry không đè lên nhau."""
        digest = uuid.uuid4().hex[:12]
        root = Path(__file__).resolve().parents[2] / "static" / "mock"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"image_{digest}.svg"
        hue = int(digest[:2], 16)
        heading, label = mock_image_caption(prompt)
        safe = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        # Ảnh mock dọc cho chế độ image_text / 9:16
        portrait = bool(size and ("x" in size.lower()) and self._is_portrait_size(size))
        w, h = (720, 1280) if portrait else (960, 540)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="hsl({hue},28%,22%)"/>
      <stop offset="100%" stop-color="hsl({(hue + 40) % 360},22%,38%)"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#g)"/>
  <rect x="{int(w*0.08)}" y="{int(h*0.28)}" width="{int(w*0.4)}" height="{int(h*0.28)}" rx="10" fill="hsl({(hue + 20) % 360},35%,72%)" opacity="0.9"/>
  <circle cx="{int(w*0.72)}" cy="{int(h*0.38)}" r="{int(w*0.14)}" fill="hsl({(hue + 80) % 360},30%,65%)" opacity="0.55"/>
  <text x="{int(w*0.08)}" y="{int(h*0.78)}" fill="#f2ebe0" font-family="Georgia, serif" font-size="28">{heading}</text>
  <text x="{int(w*0.08)}" y="{int(h*0.84)}" fill="#d7cfc3" font-family="sans-serif" font-size="18">{safe}</text>
</svg>"""
        path.write_text(svg, encoding="utf-8")
        return f"/static/mock/image_{digest}.svg"

    @staticmethod
    def _is_portrait_size(size: str) -> bool:
        """Chuỗi kích thước WxH có phải khung dọc không."""
        m = re.match(r"^(\d+)x(\d+)$", size.strip().lower())
        if not m:
            return False
        return int(m.group(2)) > int(m.group(1))


_gateway: MediaGateway | None = None


def get_media_gateway() -> MediaGateway:
    """Singleton MediaGateway dùng chung trong tiến trình."""
    global _gateway
    if _gateway is None:
        _gateway = MediaGateway()
    return _gateway


def reset_media_gateway() -> None:
    """Xoá singleton (dùng khi đổi cấu hình model hoặc trong test)."""
    global _gateway
    _gateway = None
