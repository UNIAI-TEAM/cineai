"""Adapter cho BytePlus ModelArk / Volcengine Ark: Seedream (ảnh, đồng bộ) + Seedance (video, task + poll)."""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, NoReturn
from urllib.parse import urlparse

import httpx

from app.services.billing.pricing import parse_usage_dict
from app.services.providers.base import (
    IMAGE_GEN_READ_SEC,
    VIDEO_CREATE_READ_SEC,
    VIDEO_FETCH_READ_SEC,
    ImageOutput,
    ImageRequest,
    ProviderNotSupported,
    TaskResult,
    TransientUpstreamError,
    TtsRequest,
    VideoRequest,
    bearer_headers,
    is_failover_safe_error,
    is_transient_http_status,
    join_url,
    reraise_upstream_timeout,
    upstream_timeout,
)

logger = logging.getLogger(__name__)

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

# Làm dịu tên thương hiệu / IP mà Seedream hay từ chối vì bản quyền
SEEDREAM_SANITIZE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bspacex\b"), "民营商业航天公司"),
    (re.compile(r"(?i)\bspace\s*x\b"), "民营商业航天公司"),
    (re.compile(r"(?i)\bfalcon\s*heavy\b"), "重型运载火箭"),
    (re.compile(r"(?i)\bfalcon\s*1\b"), "首枚试验运载火箭"),
    (re.compile(r"(?i)\bfalcon\s*9\b"), "可回收运载火箭"),
    (re.compile(r"(?i)\bfalcon\b"), "试验运载火箭"),
    (re.compile(r"(?i)\bstarship\b"), "巨型运载飞船"),
    (re.compile(r"(?i)\belon\s*musk\b"), "航天企业家"),
    (re.compile(r"(?i)\btesla\b"), "电动车企业"),
    (re.compile(r"猎鹰一号"), "首枚试验运载火箭"),
    (re.compile(r"猎鹰\s*9"), "可回收运载火箭"),
    (re.compile(r"猎鹰重型"), "重型运载火箭"),
    (re.compile(r"猎鹰"), "试验运载火箭"),
    (re.compile(r"马斯克"), "航天企业家"),
    (re.compile(r"埃隆"), "航天企业家"),
    (re.compile(r"Space\s*X"), "民营商业航天公司"),
]

# Phong cách CG bồi dày đắp thêm sau khi bị chặn vì ảnh người thật, giảm khả năng bị kiểm duyệt lần sau
SEEDREAM_CG_STYLE = (
    "用CG厚涂、游戏CG的风格打造的画面，色彩层次丰富，质感细腻逼真，"
    "真实的光影效果赋予画面生动感"
)

# Trạng thái tác vụ video thành công (Ark)
VIDEO_SUCCESS_STATUSES = {"succeeded", "success", "completed", "complete"}
# Trạng thái tác vụ video thất bại (Ark)
VIDEO_FAILED_STATUSES = {"failed", "cancelled", "canceled", "expired", "failure"}


def is_ark_host(base_url: str) -> bool:
    """Base URL thuộc BytePlus ModelArk / Volcengine Ark."""
    host = (urlparse(base_url or "").hostname or "").lower()
    return any(host.endswith(h) for h in ARK_HOSTS)


def resolve_seedance_i2v_image_role(ratio: str | None) -> tuple[str, str | None]:
    """Có mục tiêu khung hình thì dùng reference_image để được gửi kèm ratio."""
    target = (ratio or "").strip() or None
    if target:
        return "reference_image", target
    return "first_frame", None


def raise_seedream_http_error(status_code: int, body: str, *, model: str = "") -> NoReturn:
    """Chuyển lỗi HTTP khi tạo ảnh thành RuntimeError dễ đọc."""
    snippet = (body or "")[:800]
    if status_code == 403 and "AccountOverdueError" in snippet:
        logger.error("Seedream AccountOverdueError — upstream Ark account overdue: %s", snippet[:200])
        raise RuntimeError(
            "上游 Seedream 账户欠费（AccountOverdueError），生图暂不可用，请联系管理员"
        )
    logger.warning(
        "出图上游失败 model=%s status=%s body=%s",
        (model or "").strip() or "-",
        status_code,
        snippet[:200],
    )
    if "InputTextSensitive" in snippet or "InputTextSensitiveContentDetected" in snippet:
        raise RuntimeError(
            "生图文案未通过内容审核（可能含敏感或历史名人相关表述），"
            "请修改提示词后重试。"
            f" 详情：{snippet[:240]}"
        )
    raise RuntimeError(f"Seedream error {status_code}: {snippet}")


def sanitize_seedream_prompt(prompt: str) -> str:
    """Làm dịu tên thương hiệu/IP (tùy chọn cho phía gọi; luồng sinh ảnh chính không tự sửa)."""
    out = prompt or ""
    for pat, repl in SEEDREAM_SANITIZE:
        out = pat.sub(repl, out)
    return out


def extract_image_url(data: dict[str, Any]) -> str | None:
    """Lấy URL ảnh từ response tạo ảnh Ark (data[0].url/b64_json hoặc url)."""
    if "data" in data and data["data"]:
        item = data["data"][0]
        return item.get("url") or item.get("b64_json")
    if "url" in data:
        return data["url"]
    return None


def is_seedream_input_text_sensitive(msg: str) -> bool:
    """Seedream chặn văn bản đầu vào (có thể nén lại prompt rồi thử lại)."""
    text = msg or ""
    return (
        "InputTextSensitive" in text
        or "InputTextSensitiveContentDetected" in text
        or "生图文案未通过内容审核" in text
    )


def is_seedream_input_privacy_error(msg: str) -> bool:
    """Ảnh tham chiếu / đầu vào bị chặn vì nghi ảnh người thật (đổi văn bản không có tác dụng)."""
    text = msg or ""
    return any(k in text for k in ("PrivacyInformation", "InputImageSensitive"))


def is_seedream_policy_error(msg: str) -> bool:
    """Văn bản hoặc nội dung đầu ra bị chặn vì chính sách (sinh ảnh fail thẳng, không fallback prompt)."""
    text = msg or ""
    if is_seedream_input_privacy_error(text):
        return False
    if is_seedream_input_text_sensitive(text):
        return True
    return (
        "PolicyViolation" in text
        or "SensitiveContent" in text
        or "OutputImageSensitive" in text
    )


def is_seedance_input_privacy_error(msg: str) -> bool:
    """Ảnh tham chiếu Seedance bị chặn vì nghi người thật (đổi văn bản video không có tác dụng)."""
    text = msg or ""
    return any(
        k in text
        for k in (
            "PrivacyInformation",
            "InputImageSensitive",
            "参考图疑似真人",
            "may contain real person",
        )
    )


def is_seedance_text_policy_error(msg: str) -> bool:
    """Seedance bị chặn vì văn bản/chính sách (có thể thêm phong cách CG rồi thử lại một lần)."""
    text = msg or ""
    if is_seedance_input_privacy_error(text):
        return False
    lowered = text.lower()
    if "分镜文案未通过内容审核" in text:
        return True
    return any(
        k in lowered
        for k in (
            "inputtextsensitive",
            "text sensitive",
            "policyviolation",
            "outputimagesensitive",
            "sensitivecontentdetected",
            "sensitivecontent",
        )
    )


def with_seedance_cg_style(prompt: str) -> str:
    """Thêm phong cách CG bồi dày vào cuối prompt (đã có thì trả nguyên)."""
    base = (prompt or "").strip()
    if not base:
        return SEEDREAM_CG_STYLE
    if SEEDREAM_CG_STYLE in base:
        return base
    return f"{base}。{SEEDREAM_CG_STYLE}"


def seedance_content_with_cg_style(content: list[Any] | None) -> list[dict[str, Any]] | None:
    """Thêm CG vào mọi mục text trong content[]; không đổi gì thì trả None."""
    if not isinstance(content, list):
        return None
    changed = False
    out: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            out.append(item)
            continue
        if item.get("type") != "text":
            out.append(dict(item))
            continue
        text = str(item.get("text") or "")
        cg = with_seedance_cg_style(text)
        if cg != text:
            changed = True
            out.append({**item, "text": cg})
        else:
            out.append(dict(item))
    return out if changed else None


def seedance_content_slot_label(text: str, content_labels: list[str] | None = None) -> tuple[int, str]:
    """Đọc chỉ số content[n] và nhãn tùy chọn từ văn bản lỗi."""
    m = re.search(r"content\[(\d+)\]", text or "", re.I)
    idx = int(m.group(1)) if m else -1
    label = ""
    if idx >= 0 and content_labels and idx < len(content_labels):
        label = str(content_labels[idx] or "").strip()
    return idx, label


def format_seedance_create_error(status_code: int, text: str, *, content_labels: list[str] | None = None) -> str:
    """Chuyển lỗi tạo tác vụ Seedance thành tiếng Trung dễ đọc (vẫn giữ code gốc để đối chiếu)."""
    body = (text or "")[:800]
    if any(
        k in body
        for k in ("PrivacyInformation", "InputImageSensitive", "SensitiveContentDetected", "real person")
    ):
        idx, label = seedance_content_slot_label(body, content_labels)
        if label:
            return (
                f"参考图疑似真人：{label}（content[{idx}]，PrivacyInformation），"
                "请更换该形象为动漫或插画后重试"
            )
        if idx >= 0:
            return (
                f"参考图疑似真人（提交内容第 {idx + 1} 项 / content[{idx}]，PrivacyInformation），"
                "请更换对应角色/场景形象为动漫或插画后重试"
            )
        return "参考图疑似真人（PrivacyInformation），请更换角色/场景形象为动漫或插画后重试"
    if "InputTextSensitive" in body or "text sensitive" in body.lower():
        return "分镜文案未通过内容审核，请修改敏感表述后重试"
    if "resource download failed" in body and "audio" in body.lower():
        return "参考音频无法下载，请检查角色音色绑定后重试"
    # Seedance r2v：reference_audio 时长须 ≥ 1.8 秒
    if re.search(r"audio duration.*(?:1\.8|greater than or equal)", body, re.I) or (
        "audio duration" in body.lower() and "content[" in body.lower()
    ):
        idx, label = seedance_content_slot_label(body, content_labels)
        who = label or (f"提交内容第 {idx + 1} 项 / content[{idx}]" if idx >= 0 else "某条参考音频")
        return (
            f"参考音频过短：{who}，Seedance 要求时长 ≥ 1.8 秒。"
            "请打开对应角色/旁白，重新生成或上传更长的试听音频后再生成该分镜。"
        )
    return f"Seedance create error {status_code}: {body}"


def seedance_prompt_text(prompt: str) -> str:
    """Seedance 2.0 có thể cần văn bản JSON kèm summary_caption (BodyFormat)."""
    clean = (prompt or "").strip() or "画面轻微动态，保持主体外形稳定"
    clean = re.sub(r"\s+", " ", clean).strip()
    if clean.startswith("{"):
        try:
            obj = json.loads(clean)
            if isinstance(obj, dict):
                if not str(obj.get("summary_caption") or "").strip():
                    obj["summary_caption"] = str(obj.get("prompt") or obj.get("text") or clean)[:500]
                return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    return json.dumps({"summary_caption": clean[:500]}, ensure_ascii=False)


def seedance_duration(duration: int | float) -> int:
    """Kẹp thời lượng Seedance về khoảng cho phép (mặc định 4-30s)."""
    from app.config import get_settings

    s = get_settings()
    lo = int(getattr(s, "seedance_duration_min", 4) or 4)
    hi = int(getattr(s, "seedance_duration_max", 30) or 30)
    return int(max(lo, min(int(round(float(duration))), hi)))


def _scalar_task_id(value: Any) -> str | None:
    """Chuẩn hóa một giá trị task id vô hướng về chuỗi khác rỗng; loại các từ trạng thái."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int)) and str(value).strip():
        text = str(value).strip()
        if text.lower() in {"success", "ok", "true", "none", "null", "0"}:
            return None
        return text
    return None


def extract_video_task_id(data: dict[str, Any] | None) -> str | None:
    """Lấy task id từ response tạo tác vụ Ark (task_id/taskId/id, không unwrap kiểu New API)."""
    if not isinstance(data, dict):
        return None
    for key in ("task_id", "taskId", "id"):
        found = _scalar_task_id(data.get(key))
        if found:
            return found
    return None


def format_video_task_error(err: Any) -> str:
    """Rút gọn object error của upstream thành một câu ngắn dễ đọc."""
    if isinstance(err, dict):
        for key in ("message", "msg", "error"):
            value = err.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested = format_video_task_error(value)
                if nested:
                    return nested
        return "视频生成失败"
    text = str(err or "").strip()
    return text or "视频生成失败"


def extract_video_result_url(data: dict[str, Any]) -> str | None:
    """Lấy URL video từ response tác vụ thành công (top-level url/video_url hoặc content.video_url)."""
    for key in ("url", "video_url"):
        value = data.get(key)
        if isinstance(value, str) and value.strip().startswith(("http://", "https://", "/")):
            return value.strip()
    content = data.get("content")
    if isinstance(content, dict):
        for key in ("video_url", "url"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def extract_seedance_last_frame_url(data: dict[str, Any]) -> str | None:
    """Lấy URL khung hình cuối từ response tác vụ Seedance thành công."""
    content = data.get("content")
    if isinstance(content, dict):
        for key in ("last_frame_url", "last_frame_image_url", "lastFrameUrl"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = content.get("last_frame")
        if isinstance(nested, dict):
            nested_url = nested.get("url")
            if isinstance(nested_url, str) and nested_url.strip():
                return nested_url.strip()
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    for key in ("last_frame_url", "last_frame_image_url", "lastFrameUrl"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_video_task_status(status: str) -> str:
    """Chuẩn hóa trạng thái upstream thành running/succeeded/failed."""
    raw = (status or "").strip().lower()
    if raw in VIDEO_SUCCESS_STATUSES:
        return "succeeded"
    if raw in VIDEO_FAILED_STATUSES:
        return "failed"
    return "running"


def build_task_result_from_payload(data: dict[str, Any]) -> TaskResult:
    """Đọc trực tiếp response truy vấn tác vụ Ark thành TaskResult (giữ cả model để tính giá)."""
    status = normalize_video_task_status(str(data.get("status", "") or "running"))
    usage_parsed = parse_usage_dict(data)
    common: dict[str, Any] = {
        "total_tokens": int(usage_parsed.get("total_tokens") or 0),
        "completion_tokens": int(usage_parsed.get("completion_tokens") or 0),
        "raw_usage": data.get("usage") if isinstance(data.get("usage"), dict) else None,
        "model": str(data.get("model") or ""),
    }
    if status == "succeeded":
        return TaskResult(
            status="succeeded",
            url=extract_video_result_url(data),
            last_frame_url=extract_seedance_last_frame_url(data),
            **common,
        )
    if status == "failed":
        err = data.get("error") or data.get("message") or data.get("fail_reason") or "failed"
        return TaskResult(status="failed", error=format_video_task_error(err), **common)
    return TaskResult(status="running", **common)


class ArkAdapter:
    """BytePlus ModelArk / Volcengine Ark: Seedream (đồng bộ) + Seedance (task + poll)."""

    protocol = "ark"

    async def list_models(self, route, capability: str = "all") -> list[dict[str, str]]:
        """Danh sách model tĩnh khả dụng cho capability này (Ark không có GET /models)."""
        return [m for m in ARK_STATIC_MODELS if capability in ("all", m["capability"])]

    async def gen_image(self, route, req: ImageRequest) -> ImageOutput:
        """Sinh ảnh Seedream đồng bộ; ảnh tham chiếu (refs + style_refs) gộp vào field `image`."""
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

    async def create_video(self, route, req: VideoRequest) -> str:
        """Tạo tác vụ Seedance; retry 4 tầng khi lỗi (plain-text fallback → CG style → bỏ ratio → adaptive).

        Mỗi tầng dựng một bản `body` mới (không sửa tại chỗ) để giữ nguyên payload đã gửi ở tầng trước.
        """
        body = copy.deepcopy(req.body)
        body["model"] = route.upstream_model
        url = join_url(route.base_url, VIDEO_TASK_PATH)
        headers = bearer_headers(route.api_key)
        try:
            async with httpx.AsyncClient(timeout=upstream_timeout(VIDEO_CREATE_READ_SEC)) as client:
                resp = await client.post(url, headers=headers, json=body)
                if is_transient_http_status(resp.status_code):
                    raise TransientUpstreamError(f"Seedance HTTP {resp.status_code}")
                if resp.status_code >= 400 and req.plain_text is not None:
                    body = copy.deepcopy(body)
                    body["content"][0]["text"] = req.plain_text
                    resp = await client.post(url, headers=headers, json=body)
                if resp.status_code >= 400:
                    raw_err = resp.text or ""
                    if is_seedance_input_privacy_error(raw_err):
                        raise RuntimeError(format_seedance_create_error(resp.status_code, raw_err))
                    if is_seedance_text_policy_error(raw_err):
                        cg_content = seedance_content_with_cg_style(body.get("content"))
                        if cg_content is not None:
                            body = {**body, "content": cg_content}
                            resp = await client.post(url, headers=headers, json=body)
                        if resp.status_code >= 400:
                            raise RuntimeError(format_seedance_create_error(resp.status_code, resp.text))
                allow_fallback = req.allow_structure_fallback and not req.target_ratio
                if resp.status_code >= 400 and allow_fallback:
                    err_text = resp.text or ""
                    if "ratio" in err_text.lower() and "ratio" in body:
                        body = {k: v for k, v in body.items() if k != "ratio"}
                        resp = await client.post(url, headers=headers, json=body)
                if resp.status_code >= 400 and allow_fallback:
                    body = copy.deepcopy(body)
                    body["content"][1].pop("role", None)
                    body["ratio"] = "adaptive"
                    resp = await client.post(url, headers=headers, json=body)
                if resp.status_code >= 400:
                    raise RuntimeError(format_seedance_create_error(resp.status_code, resp.text, content_labels=req.content_labels))
                data = resp.json()
        except httpx.TimeoutException as exc:
            reraise_upstream_timeout(exc, kind="生视频", read_sec=VIDEO_CREATE_READ_SEC)
        task_id = extract_video_task_id(data)
        if not task_id:
            raise RuntimeError(f"Seedance missing task id: {data}")
        return task_id

    async def fetch_video(self, route, task_id: str) -> TaskResult:
        """Truy vấn tác vụ Seedance một lần, không lặp poll; lỗi mạng/transient → running."""
        url = join_url(route.base_url, f"{VIDEO_TASK_PATH}/{task_id}")
        try:
            async with httpx.AsyncClient(timeout=upstream_timeout(VIDEO_FETCH_READ_SEC, connect=15.0)) as client:
                resp = await client.get(url, headers=bearer_headers(route.api_key))
        except httpx.HTTPError as exc:
            logger.warning("Seedance fetch network error task=%s: %s", task_id, exc)
            return TaskResult(status="running", provider_task_id=task_id, channel_id=route.channel_id)
        if resp.status_code >= 400:
            if is_transient_http_status(resp.status_code):
                return TaskResult(status="running", provider_task_id=task_id, channel_id=route.channel_id)
            return TaskResult(status="failed", error=resp.text[:500], provider_task_id=task_id, channel_id=route.channel_id)
        result = build_task_result_from_payload(resp.json())
        result.provider_task_id = task_id
        result.channel_id = route.channel_id
        return result

    async def tts(self, route, req: TtsRequest) -> bytes:
        """ModelArk không có TTS."""
        raise ProviderNotSupported("ModelArk không có TTS")

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates từ usage thật (Seedream: generated_images, Seedance: total_tokens)."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)

    def url_needs_auth(self, url: str) -> bool:
        """URL trả về từ Ark là public, không cần Bearer khi tải."""
        return False

    def is_transient_error(self, exc: BaseException) -> bool:
        """Lỗi tạm thời (được phép failover sang model kế tiếp)."""
        return is_failover_safe_error(exc)
