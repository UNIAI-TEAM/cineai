/**
 * Lỗi đã lưu (dự án / tác vụ / phim ngắn) → câu hiển thị ở trang quản trị（纯函数，供 node --test 直接导入）。
 * 有已登记错误码：主文案为越南语翻译，detail 附「mã · nguyên văn」供运维排查；无码或码未登记：主文案为原文。
 */
import { translateErrorCode } from "./apiErrors.ts";

export type StoredErrorView = {
  /** Câu chính hiển thị cho vận hành */
  text: string;
  /** Lỗi gốc (mã + nguyên văn) — chỉ có khi câu chính là bản dịch hoặc có mã chưa dịch được */
  detail: string;
  /** Câu chính có phải bản dịch theo mã không */
  translated: boolean;
};

/**
 * 参数 message：落库原文（可能是中文模板 / 上游原文）；code：错误码；params：错误参数；formatFen：金额格式化。
 * 返回：原文与错误码都为空时返回 null。
 */
export function describeStoredError(
  message: string | null | undefined,
  code: string | null | undefined,
  params: unknown,
  formatFen: (fen: number) => string,
): StoredErrorView | null {
  const raw = (message ?? "").trim();
  const errCode = (code ?? "").trim();
  if (!raw && !errCode) return null;
  const text = translateErrorCode(errCode, params, formatFen);
  if (text) {
    return { text, detail: [errCode, raw].filter(Boolean).join(" · "), translated: true };
  }
  if (raw) return { text: raw, detail: errCode, translated: false };
  return { text: errCode, detail: "", translated: false };
}
