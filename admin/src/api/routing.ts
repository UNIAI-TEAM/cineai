import { api, type ModelCapabilityReadiness } from "@/api/client";

/** Năng lực AI của một slot / model */
export type Capability = "text" | "image" | "video" | "audio";

/** Protocol provider backend hỗ trợ */
export type ProviderProtocol = "openai" | "ark" | "volc_tts";

/** Provider đã lưu (key bị che, chỉ còn cờ has_api_key) */
export type AdminProvider = {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  has_api_key: boolean;
  protocol: ProviderProtocol | "auto" | "kie";
  models: string[];
  enabled: boolean;
  sort_order: number;
};

/** Một (provider, model) được gán cho slot/override, kèm tỉ lệ chia luân phiên */
export type ModelBinding = { channel_id: string; model: string; weight: number };

/** Gán chức năng: 4 slot năng lực + ghi đè theo chức năng */
export type FunctionBindings = {
  slots: Partial<Record<Capability, ModelBinding[]>>;
  overrides: Record<string, ModelBinding[]>;
};

/** Một chức năng AI cố định trong danh mục backend */
export type FunctionInfo = { id: string; capability: Capability; label: string; description: string };

/** Một model trong danh mục (tĩnh của preset hoặc tải từ provider) */
export type CatalogModel = { id: string; label?: string; capability?: string };

/** Preset provider backend gợi ý khi thêm mới */
export type ProviderPreset = {
  id: string;
  name: string;
  protocol: ProviderProtocol;
  base_url: string;
  catalog: "remote" | "static" | "none";
  models: CatalogModel[];
};

/** GET /api/admin/settings/routing */
export type AdminRoutingSettings = {
  providers: AdminProvider[];
  function_bindings: FunctionBindings;
  readiness: ModelCapabilityReadiness[];
  function_catalog: FunctionInfo[];
  presets: ProviderPreset[];
  validation_errors: string[];
  updated_at?: string | null;
};

/** Một provider trong body PATCH (api_key null = giữ key đã lưu) */
export type ProviderPatchItem = {
  id: string;
  name: string;
  base_url: string;
  api_key: string | null;
  clear_api_key: boolean;
  protocol: ProviderProtocol;
  models: string[];
  enabled: boolean;
  sort_order: number;
};

/** PATCH /api/admin/settings/routing → 200 */
export type AdminRoutingSaveOut = { ok: boolean; settings: AdminRoutingSettings; applied: string[] };

/** Thông tin kết nối dùng cho kiểm tra / tải danh sách model (key trống + channel_id = dùng key đã lưu) */
export type ProviderConnectionInput = {
  channel_id?: string | null;
  protocol: ProviderProtocol;
  base_url: string;
  api_key?: string | null;
};

/** POST /api/admin/settings/providers/test */
export type ProviderTestResult = { ok: boolean; message: string; models_count?: number };

// Đọc toàn bộ cấu hình routing (provider, gán chức năng, danh mục, preset)
export function fetchRoutingSettings(): Promise<AdminRoutingSettings> {
  return api<AdminRoutingSettings>("/api/admin/settings/routing");
}

// Lưu danh sách provider (thay toàn bộ) và/hoặc gán chức năng; 400 trả câu lỗi tiếng Việt
export function saveRoutingSettings(body: {
  providers?: ProviderPatchItem[];
  function_bindings?: FunctionBindings;
}): Promise<AdminRoutingSaveOut> {
  return api<AdminRoutingSaveOut>("/api/admin/settings/routing", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// Kiểm tra kết nối provider trước/sau khi lưu
export function testProviderConnection(input: ProviderConnectionInput): Promise<ProviderTestResult> {
  return api<ProviderTestResult>("/api/admin/settings/providers/test", {
    method: "POST",
    body: JSON.stringify({ ...input, api_key: input.api_key || null, channel_id: input.channel_id || null }),
  });
}

// Tải danh mục model của provider (openai: GET /models; ark/volc_tts: danh sách tĩnh)
export async function listProviderModels(
  input: ProviderConnectionInput & { capability?: string },
): Promise<CatalogModel[]> {
  const res = await api<{ models: CatalogModel[] }>("/api/admin/settings/upstream/models", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      api_key: input.api_key || null,
      channel_id: input.channel_id || null,
      capability: input.capability ?? "all",
    }),
  });
  return res.models ?? [];
}
