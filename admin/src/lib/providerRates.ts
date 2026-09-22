/** Hàm thuần cho bảng giá provider_rates (chỉ `import type` để chạy được bằng `node --test`). */
import type { ProviderRateRow, RateUnit, RateUnitOption, UnpricedModel } from "@/api/providerRates";

/** USD → fen giống backend: ceil(round(usd × usd_cny × 100, 6)), usd > 0 thì tối thiểu 1 fen */
export function rateFenPreview(usd: number, usdCny: number): number {
  if (!(usd > 0) || !(usdCny > 0)) return 0;
  const raw = Math.round(usd * usdCny * 100 * 1e6) / 1e6;
  return Math.max(1, Math.ceil(raw));
}

/** Đổi đơn vị; chỉ per_m_input_output giữ usd_out (mặc định 0), còn lại null */
export function withUnit(row: ProviderRateRow, unit: RateUnit): ProviderRateRow {
  return { ...row, unit, usd_out: unit === "per_m_input_output" ? (row.usd_out ?? 0) : null };
}

/** Đổi chỗ dòng với dòng kề trên/dưới (thứ tự = ưu tiên khớp) */
export function moveRow<T>(rows: T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (index < 0 || index >= rows.length || target < 0 || target >= rows.length) return rows;
  const next = [...rows];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Dòng trống để thêm mới */
export function emptyRateRow(): ProviderRateRow {
  return { pattern: "", unit: "per_image", usd: 0, usd_out: null, note: "" };
}

/** Dòng gợi ý cho một model chưa có giá (đơn vị đoán theo năng lực) */
export function rowForUnpriced(m: UnpricedModel): ProviderRateRow {
  const unit: RateUnit =
    m.capability === "image"
      ? "per_image"
      : m.capability === "video"
        ? "per_m_tokens"
        : m.capability === "audio"
          ? "per_m_chars"
          : "per_m_input_output";
  return { pattern: m.model, unit, usd: 0, usd_out: unit === "per_m_input_output" ? 0 : null, note: m.channel_id };
}

/** Model chưa có giá mà bảng nháp cũng chưa có dòng trùng tên (không phân biệt hoa/thường) */
export function pendingUnpriced(unpriced: UnpricedModel[], rows: ProviderRateRow[]): UnpricedModel[] {
  const patterns = new Set(rows.map((r) => r.pattern.trim().toLowerCase()));
  return unpriced.filter((m) => !patterns.has(m.model.trim().toLowerCase()));
}

/**
 * Hậu tố hiển thị sau giá xem trước, lấy từ nhãn `units[]` của API (không hard-code danh sách đơn vị) —
 * bỏ tiền tố "USD " của nhãn, ví dụ "USD / ảnh" → "/ ảnh". Không tìm thấy thì trả về mã đơn vị thô.
 */
export function unitSuffix(units: RateUnitOption[], unit: RateUnit): string {
  const found = units.find((u) => u.id === unit);
  if (!found) return unit;
  return found.label.replace(/^USD\s*/i, "");
}
