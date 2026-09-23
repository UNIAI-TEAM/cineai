/**
 * Hàm thuần cho tab "Mô hình": suy luận năng lực model, trạng thái provider, lỗi binding,
 * sửa bản nháp function_bindings, chặn lưu/xoá provider đang được gán.
 * Chỉ `import type` để chạy được bằng `node --test`.
 */
import type {
  AdminProvider,
  CatalogModel,
  Capability,
  FunctionBindings,
  FunctionInfo,
  ModelBinding,
  ProviderPatchItem,
  ProviderPreset,
  ProviderProtocol,
  ProviderTestResult,
} from "@/api/routing";

export const CAPABILITIES: readonly Capability[] = ["text", "image", "video", "audio"];

export const CAPABILITY_LABELS: Record<Capability, string> = {
  text: "Văn bản",
  image: "Ảnh",
  video: "Video",
  audio: "Giọng đọc",
};

export const CAPABILITY_HINTS: Record<Capability, string> = {
  text: "Kịch bản, tách phân cảnh, viết prompt",
  image: "Ảnh phân cảnh, ảnh tư liệu, công cụ tạo ảnh",
  video: "Video phân cảnh, video tư liệu, công cụ tạo video",
  audio: "Lời dẫn, lồng tiếng, nghe thử giọng",
};

/** Cận dưới/trên hợp lệ của weight — khớp `Field(ge=1, le=100)` của `ModelBinding` (backend/app/schemas_routing.py) */
export const BINDING_WEIGHT_MIN = 1;
export const BINDING_WEIGHT_MAX = 100;

/** Bản nháp provider trên UI: key mới nhập tách khỏi cờ "đã lưu key" */
export type ProviderDraft = {
  id: string;
  name: string;
  base_url: string;
  protocol: ProviderProtocol;
  models: string[];
  enabled: boolean;
  has_api_key: boolean;
  api_key_input: string;
  clear_api_key: boolean;
  is_new: boolean;
  preset_id: string;
};

export type ProviderStatus = "ready" | "incomplete" | "disabled";

export const PROVIDER_STATUS_LABELS: Record<ProviderStatus, string> = {
  ready: "Sẵn sàng",
  incomplete: "Thiếu key",
  disabled: "Đang tắt",
};

export type BindingProblem =
  | "missing_provider"
  | "model_not_enabled"
  | "wrong_capability"
  | "provider_disabled"
  | "provider_incomplete";

export const BINDING_PROBLEM_LABELS: Record<BindingProblem, string> = {
  missing_provider: "Nhà cung cấp đã bị xoá",
  model_not_enabled: "Model chưa được bật ở nhà cung cấp",
  wrong_capability: "Model không đúng năng lực của hàng này",
  provider_disabled: "Nhà cung cấp đang tắt",
  provider_incomplete: "Nhà cung cấp thiếu key hoặc Base URL",
};

/** Một model đã bật ở một provider (dùng cho hộp chọn model) */
export type ModelOption = { channel_id: string; channel_name: string; model: string; status: ProviderStatus };

/** Preset trống dự phòng khi backend không trả preset nào */
export const BLANK_PRESET: ProviderPreset = {
  id: "custom_openai",
  name: "OpenAI-compatible",
  protocol: "openai",
  base_url: "",
  catalog: "remote",
  models: [],
};

/** Chuẩn hoá tên model để so khớp — bản sao `normalize_model_name` (backend/app/services/model_routing_config.py) */
export function normalizeModelName(value: string): string {
  return (value || "").trim().replace(/\s+/g, "").toLowerCase();
}

/** Suy luận năng lực từ tên model — bản sao `infer_model_capability` (backend/app/services/model_routing_config.py) */
export function inferModelCapability(model: string): Capability {
  const mid = normalizeModelName(model);
  if (!mid) return "text";
  if (
    mid.includes("tts") ||
    mid.includes("text-to-speech") ||
    mid.includes("text-to-dialogue") ||
    mid.includes("elevenlabs") ||
    mid.startsWith("zh_") ||
    mid.includes("speaker") ||
    mid.startsWith("s_")
  ) {
    return "audio";
  }
  if (
    mid.includes("seedance") ||
    mid.includes("veo") ||
    mid.includes("video") ||
    mid.includes("i2v") ||
    mid.includes("sora") ||
    mid.startsWith("kie-veo") ||
    mid.startsWith("kie-seedance")
  ) {
    return "video";
  }
  if (
    mid.includes("seedream") ||
    mid.includes("nano-banana") ||
    mid.includes("banana") ||
    mid.includes("dream") ||
    mid.startsWith("gpt-image") ||
    mid.includes("grok-imagine") ||
    mid.includes("image") ||
    mid.startsWith("kie-")
  ) {
    return "image";
  }
  return "text";
}

/** Năng lực model trong một provider (volc_tts luôn là giọng đọc, như validation backend) */
export function modelCapability(protocol: string, model: string): Capability {
  return protocol === "volc_tts" ? "audio" : inferModelCapability(model);
}

/** Protocol cũ (auto/kie/rỗng) coi là openai */
export function normalizeProtocol(protocol: string): ProviderProtocol {
  return protocol === "ark" || protocol === "volc_tts" ? protocol : "openai";
}

/** Provider đã lưu → bản nháp */
export function draftFromProvider(p: AdminProvider): ProviderDraft {
  return {
    id: p.id,
    name: p.name,
    base_url: p.base_url || "",
    protocol: normalizeProtocol(p.protocol),
    models: [...(p.models ?? [])],
    enabled: p.enabled,
    has_api_key: p.has_api_key,
    api_key_input: "",
    clear_api_key: false,
    is_new: false,
    preset_id: p.id,
  };
}

/** Sinh id provider dạng slug chưa bị dùng (openai, openai-2, …) */
export function uniqueProviderId(base: string, existingIds: string[]): string {
  const slug =
    (base || "")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "provider";
  if (!existingIds.includes(slug)) return slug;
  let n = 2;
  while (existingIds.includes(`${slug}-${n}`)) n += 1;
  return `${slug}-${n}`;
}

/** Preset → bản nháp provider mới */
export function draftFromPreset(preset: ProviderPreset, existingIds: string[]): ProviderDraft {
  return {
    id: uniqueProviderId(preset.id, existingIds),
    name: preset.name,
    base_url: preset.base_url,
    protocol: normalizeProtocol(preset.protocol),
    models: [],
    enabled: true,
    has_api_key: false,
    api_key_input: "",
    clear_api_key: false,
    is_new: true,
    preset_id: preset.id,
  };
}

/** Provider có key (đã lưu và chưa bị xoá, hoặc vừa nhập) */
export function draftHasKey(d: ProviderDraft): boolean {
  return (d.has_api_key && !d.clear_api_key) || d.api_key_input.trim().length > 0;
}

/** Trạng thái chấm màu: bật + đủ kết nối / thiếu key / tắt — bản sao `channel_connection_ready` (backend/app/services/model_routing_config.py) */
export function providerStatus(d: ProviderDraft): ProviderStatus {
  if (!d.enabled) return "disabled";
  if (d.protocol === "volc_tts") return draftHasKey(d) || d.base_url.trim() ? "ready" : "incomplete";
  return d.base_url.trim() && draftHasKey(d) ? "ready" : "incomplete";
}

/** Danh sách model tĩnh của preset (ark / volc_tts); openai trả rỗng vì tải từ provider */
export function staticCatalogFor(
  presets: ProviderPreset[],
  d: Pick<ProviderDraft, "preset_id" | "protocol">,
): CatalogModel[] {
  const own = presets.find((p) => p.id === d.preset_id && p.protocol === d.protocol && p.catalog === "static");
  const byProtocol = presets.find((p) => p.protocol === d.protocol && p.catalog === "static");
  return (own ?? byProtocol)?.models ?? [];
}

/** Khoá duy nhất của một binding (provider + model đã chuẩn hoá) */
export function bindingKey(b: { channel_id: string; model: string }): string {
  return `${b.channel_id}::${normalizeModelName(b.model)}`;
}

/** Lý do binding tạm không dùng được; null = dùng được */
export function bindingProblem(
  b: ModelBinding,
  capability: Capability,
  providers: ProviderDraft[],
): BindingProblem | null {
  const p = providers.find((x) => x.id === b.channel_id);
  if (!p) return "missing_provider";
  if (!p.models.some((m) => normalizeModelName(m) === normalizeModelName(b.model))) return "model_not_enabled";
  if (modelCapability(p.protocol, b.model) !== capability) return "wrong_capability";
  const status = providerStatus(p);
  if (status === "disabled") return "provider_disabled";
  if (status === "incomplete") return "provider_incomplete";
  return null;
}

/** Model đã bật ở mọi provider, đúng năng lực */
export function modelOptionsFor(providers: ProviderDraft[], capability: Capability): ModelOption[] {
  const out: ModelOption[] = [];
  for (const p of providers) {
    const status = providerStatus(p);
    const seen = new Set<string>();
    for (const m of p.models) {
      const key = normalizeModelName(m);
      if (!key || seen.has(key) || modelCapability(p.protocol, m) !== capability) continue;
      seen.add(key);
      out.push({ channel_id: p.id, channel_name: p.name, model: m, status });
    }
  }
  return out;
}

/** Bật/tắt một model trong danh sách binding (mặc định weight 1) */
export function toggleBinding(
  list: ModelBinding[],
  option: { channel_id: string; model: string },
): ModelBinding[] {
  const key = bindingKey(option);
  if (list.some((b) => bindingKey(b) === key)) return list.filter((b) => bindingKey(b) !== key);
  return [...list, { channel_id: option.channel_id, model: option.model, weight: BINDING_WEIGHT_MIN }];
}

/** Đặt weight (số nguyên BINDING_WEIGHT_MIN..BINDING_WEIGHT_MAX) cho binding có khoá `key` */
export function setBindingWeight(list: ModelBinding[], key: string, weight: number): ModelBinding[] {
  const w = Number.isFinite(weight)
    ? Math.min(BINDING_WEIGHT_MAX, Math.max(BINDING_WEIGHT_MIN, Math.round(weight)))
    : BINDING_WEIGHT_MIN;
  return list.map((b) => (bindingKey(b) === key ? { ...b, weight: w } : b));
}

/** Thay danh sách của một slot; rỗng thì xoá khoá */
export function withSlot(b: FunctionBindings, cap: Capability, list: ModelBinding[]): FunctionBindings {
  const slots = { ...b.slots };
  if (list.length) slots[cap] = list;
  else delete slots[cap];
  return { ...b, slots };
}

/** Thay danh sách ghi đè của một chức năng; rỗng thì xoá khoá (= dùng slot) */
export function withOverride(b: FunctionBindings, functionId: string, list: ModelBinding[]): FunctionBindings {
  const overrides = { ...b.overrides };
  if (list.length) overrides[functionId] = list;
  else delete overrides[functionId];
  return { ...b, overrides };
}

/** Số slot năng lực đã gán ít nhất một model (dùng CAPABILITIES.length, không ghim 4) */
export function assignedSlotCount(b: FunctionBindings): number {
  return CAPABILITIES.filter((c) => (b.slots[c]?.length ?? 0) > 0).length;
}

/** Nhãn các nơi có binding thoả `match` ("Slot Ảnh", nhãn chức năng) */
function bindingUsages(
  b: FunctionBindings,
  catalog: FunctionInfo[],
  match: (x: ModelBinding) => boolean,
): string[] {
  const out: string[] = [];
  for (const cap of CAPABILITIES) {
    if ((b.slots[cap] ?? []).some(match)) out.push(`Slot ${CAPABILITY_LABELS[cap]}`);
  }
  for (const fn of catalog) {
    if ((b.overrides[fn.id] ?? []).some(match)) out.push(fn.label);
  }
  return out;
}

/** Nơi đang dùng provider */
export function providerUsages(b: FunctionBindings, catalog: FunctionInfo[], channelId: string): string[] {
  return bindingUsages(b, catalog, (x) => x.channel_id === channelId);
}

/** Nơi đang dùng một model của provider */
export function modelUsages(
  b: FunctionBindings,
  catalog: FunctionInfo[],
  channelId: string,
  model: string,
): string[] {
  const target = normalizeModelName(model);
  return bindingUsages(b, catalog, (x) => x.channel_id === channelId && normalizeModelName(x.model) === target);
}

/** Gộp id model, bỏ trống và trùng (không phân biệt hoa/thường), giữ thứ tự */
export function mergeModelIds(current: string[], added: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of [...current, ...added]) {
    const id = (raw || "").trim();
    const key = normalizeModelName(id);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(id);
  }
  return out;
}

/** Kiểm tra nháp gán chức năng — câu lỗi phải trùng từng chữ với `_check`/`validate_function_bindings` (backend/app/services/function_bindings.py), đều dùng "nhà cung cấp" */
export function validateBindingsDraft(
  b: FunctionBindings,
  providers: ProviderDraft[],
  catalog: FunctionInfo[],
): string[] {
  const errs: string[] = [];
  const check = (label: string, capability: Capability, items: ModelBinding[]) => {
    for (const item of items) {
      const p = providers.find((x) => x.id === item.channel_id);
      if (!p) {
        errs.push(`${label}: nhà cung cấp '${item.channel_id}' không tồn tại`);
        continue;
      }
      if (!p.models.some((m) => normalizeModelName(m) === normalizeModelName(item.model))) {
        errs.push(`${label}: model '${item.model}' chưa được bật ở nhà cung cấp ${p.name}`);
        continue;
      }
      if (modelCapability(p.protocol, item.model) !== capability) {
        errs.push(`${label}: model '${item.model}' không phải model ${CAPABILITY_LABELS[capability].toLowerCase()}`);
      }
    }
  };
  for (const cap of CAPABILITIES) check(`Slot ${CAPABILITY_LABELS[cap]}`, cap, b.slots[cap] ?? []);
  for (const [fid, items] of Object.entries(b.overrides)) {
    const fn = catalog.find((f) => f.id === fid);
    if (!fn) {
      errs.push(`Chức năng '${fid}' không tồn tại`);
      continue;
    }
    check(fn.label, fn.capability, items);
  }
  return [...new Set(errs)];
}

/** Kiểm tra form provider: id mới hợp lệ và chưa trùng, có tên, có Base URL (trừ volc_tts) */
export function validateProviderDraft(d: ProviderDraft, others: ProviderDraft[]): string[] {
  const errs: string[] = [];
  const id = d.id.trim();
  if (d.is_new) {
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(id)) {
      errs.push("ID chỉ gồm chữ thường, số, '-' hoặc '_' (tối đa 64 ký tự)");
    } else if (others.some((o) => o.id === id)) {
      errs.push(`ID '${id}' đã tồn tại`);
    }
  }
  if (!d.name.trim()) errs.push("Cần nhập tên nhà cung cấp");
  if (d.protocol !== "volc_tts" && !d.base_url.trim()) errs.push("Cần nhập Base URL");
  return errs;
}

/**
 * Origin (scheme + host + port, chữ thường) của Base URL — bản sao `host_guard.same_host`
 * (backend/app/services/providers/host_guard.py); chuỗi không phải URL tuyệt đối → ""
 * (backend cũng coi mọi URL hỏng là cùng một origin rỗng)
 */
export function urlOrigin(value: string): string {
  try {
    return new URL((value || "").trim()).origin.toLowerCase();
  } catch {
    return "";
  }
}

/** Câu giải thích nút "Kiểm tra kết nối" theo protocol (ark / volc_tts chỉ kiểm tra có key) — theo `admin_test_provider` (backend/app/api/admin/settings.py) */
export const CONNECTION_TEST_HINTS: Record<ProviderProtocol, string> = {
  openai: "Gọi thử GET /models của nhà cung cấp bằng key này.",
  ark: "BytePlus ModelArk không có endpoint kiểm tra miễn phí: nút này chỉ xác nhận đã có key, chưa gọi thử nhà cung cấp.",
  volc_tts: "Seed Speech không có endpoint kiểm tra miễn phí: nút này chỉ xác nhận đã có key, chưa gọi thử nhà cung cấp.",
};

/** Câu hiển thị kết quả kiểm tra; ark / volc_tts thành công thì không nói "kết nối thành công" */
export function connectionTestLabel(protocol: ProviderProtocol, result: ProviderTestResult): string {
  if (!result.ok || protocol === "openai") return result.message;
  return "Đã có key (chưa gọi thử nhà cung cấp)";
}

/**
 * Lý do không cho lưu provider: lỗi form; model bị bỏ tick nhưng đang được gán (bản lưu hoặc bản nháp);
 * đổi host Base URL mà không nhập key mới (backend không dùng lại key đã lưu cho host khác, `host_guard.same_host`).
 */
export function providerSaveBlockers(
  initial: ProviderDraft,
  draft: ProviderDraft,
  others: ProviderDraft[],
  bindingSets: FunctionBindings[],
  catalog: FunctionInfo[],
): string[] {
  const errs = validateProviderDraft(draft, others);
  if (!initial.is_new) {
    const kept = new Set(draft.models.map(normalizeModelName));
    for (const m of initial.models) {
      if (kept.has(normalizeModelName(m))) continue;
      const uses = [...new Set(bindingSets.flatMap((b) => modelUsages(b, catalog, initial.id, m)))];
      if (uses.length) {
        errs.push(`Model '${m}' đang được gán cho: ${uses.join(", ")}. Hãy đổi gán trước khi bỏ tick.`);
      }
    }
    const hostChanged = urlOrigin(initial.base_url) !== urlOrigin(draft.base_url);
    if (hostChanged && initial.has_api_key && !draft.clear_api_key && !draft.api_key_input.trim()) {
      errs.push("Đổi địa chỉ máy chủ (Base URL) thì phải nhập lại API key.");
    }
  }
  return errs;
}

/** Lý do không cho xoá provider (đang được gán ở bản lưu hoặc bản nháp); null = xoá được */
export function providerDeleteBlocker(
  id: string,
  bindingSets: FunctionBindings[],
  catalog: FunctionInfo[],
): string | null {
  const uses = [...new Set(bindingSets.flatMap((b) => providerUsages(b, catalog, id)))];
  return uses.length ? `Nhà cung cấp đang được gán cho: ${uses.join(", ")}. Hãy đổi gán trước khi xoá.` : null;
}

/** Danh sách nháp → body PATCH (key trống = giữ key cũ; nhập key mới thì bỏ cờ xoá) */
export function toProviderPatch(drafts: ProviderDraft[]): ProviderPatchItem[] {
  return drafts.map((d, idx) => {
    const key = d.api_key_input.trim();
    return {
      id: d.id.trim(),
      name: d.name.trim(),
      base_url: d.base_url.trim().replace(/\/+$/, ""),
      api_key: key || null,
      clear_api_key: d.clear_api_key && !key,
      protocol: d.protocol,
      models: mergeModelIds([], d.models),
      enabled: d.enabled,
      sort_order: idx,
    };
  });
}

/** Một thao tác lưu/xoá provider từ hộp thoại */
export type ProviderEditOp = { kind: "save"; draft: ProviderDraft } | { kind: "delete"; id: string };

/**
 * Áp thao tác lên danh sách provider vừa tải lại (tránh ghi đè/xoá provider phiên khác vừa sửa).
 * Trả danh sách mới, hoặc câu lỗi khi id mới bị trùng / provider đang sửa đã bị xoá.
 */
export function mergeProviderEdit(fresh: ProviderDraft[], op: ProviderEditOp): ProviderDraft[] | string {
  if (op.kind === "delete") return fresh.filter((p) => p.id !== op.id);
  const exists = fresh.some((p) => p.id === op.draft.id);
  if (op.draft.is_new) return exists ? `ID '${op.draft.id}' đã tồn tại, hãy chọn ID khác` : [...fresh, op.draft];
  if (!exists) return "Nhà cung cấp này vừa bị xoá ở phiên khác, hãy tải lại trang";
  return fresh.map((p) => (p.id === op.draft.id ? op.draft : p));
}
