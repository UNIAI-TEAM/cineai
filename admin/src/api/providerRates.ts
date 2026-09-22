import { api } from "@/api/client";

/** Đơn vị tính giá trong provider_rates */
export type RateUnit = "per_image" | "per_m_tokens" | "per_m_output_tokens" | "per_m_input_output" | "per_m_chars";

/** Một dòng bảng giá (USD); usd_out chỉ dùng cho per_m_input_output */
export type ProviderRateRow = { pattern: string; unit: RateUnit; usd: number; usd_out: number | null; note: string };

export type RateUnitOption = { id: RateUnit; label: string };

/** Model đã gán nhưng chưa khớp dòng giá nào */
export type UnpricedModel = { channel_id: string; model: string; capability: string };

/** GET/PUT /api/admin/settings/billing/model-rates */
export type ProviderRatesOut = {
  items: ProviderRateRow[];
  defaults: ProviderRateRow[];
  units: RateUnitOption[];
  unpriced_models: UnpricedModel[];
  usd_cny: number;
  updated_at?: string | null;
};

// Đọc bảng giá hiện hành + bảng mặc định + model chưa có giá
export function fetchProviderRates(): Promise<ProviderRatesOut> {
  return api<ProviderRatesOut>("/api/admin/settings/billing/model-rates");
}

// Thay toàn bộ bảng giá; 400 trả câu lỗi tiếng Việt theo từng dòng
export function saveProviderRates(items: ProviderRateRow[]): Promise<ProviderRatesOut> {
  return api<ProviderRatesOut>("/api/admin/settings/billing/model-rates", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}
