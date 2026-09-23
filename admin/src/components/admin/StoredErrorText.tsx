import type { AdminStoredError } from "@/api/client";
import { useCurrency } from "@/lib/currency";
import { describeStoredError } from "@/lib/storedError";
import { cn } from "@/lib/utils";

type StoredErrorTextProps = {
  /** Lỗi phim ngắn dạng object (thay cho message/code/params) */
  error?: AdminStoredError | null;
  /** Nguyên văn lỗi đã lưu (error_msg / error_message / params.*_error) */
  message?: string | null;
  /** Mã lỗi AppError đã lưu kèm */
  code?: string | null;
  /** Tham số của mã lỗi */
  params?: unknown;
  /** Dạng gọn cho ô bảng: một dòng, cắt bớt, xem đủ khi rê chuột */
  compact?: boolean;
  /** Hiện khi không có lỗi (mặc định không hiện gì) */
  emptyText?: string;
  className?: string;
};

/**
 * Hiện lỗi đã lưu: có mã → câu tiếng Việt, bên dưới chữ nhỏ mờ "Lỗi gốc: mã · nguyên văn" để vận hành tra cứu;
 * không có mã → hiện nguyên văn như cũ.
 */
export function StoredErrorText({
  error,
  message,
  code,
  params,
  compact = false,
  emptyText,
  className,
}: StoredErrorTextProps) {
  const { format } = useCurrency();
  const view = error
    ? describeStoredError(error.message, error.code, error.params, format)
    : describeStoredError(message, code, params, format);
  if (!view) {
    return emptyText ? <span className={cn("text-[var(--admin-muted)]", className)}>{emptyText}</span> : null;
  }
  const detailLabel = view.translated ? "Lỗi gốc" : "Mã lỗi";
  const detail = view.detail ? `${detailLabel}: ${view.detail}` : "";

  if (compact) {
    return (
      <div
        className={cn("max-w-[200px] text-[11px]", className)}
        title={detail ? `${view.text}\n${detail}` : view.text}
      >
        <div className="truncate text-[#f56c6c]">{view.text}</div>
        {detail ? <div className="truncate text-[var(--admin-muted)]">{detail}</div> : null}
      </div>
    );
  }
  return (
    <div className={className}>
      <div className="whitespace-pre-wrap break-words">{view.text}</div>
      {detail ? (
        <div className="mt-1 whitespace-pre-wrap break-all text-[11px] text-[var(--admin-muted)]">{detail}</div>
      ) : null}
    </div>
  );
}
