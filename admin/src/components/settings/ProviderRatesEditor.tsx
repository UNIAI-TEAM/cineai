import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { ProviderRateRow, RateUnit, RateUnitOption, UnpricedModel } from "@/api/providerRates";
import { AdminConfirmDialog } from "@/components/admin/AdminConfirmDialog";
import { Button } from "@/components/ui/button";
import { useCurrency } from "@/lib/currency";
import { emptyRateRow, moveRow, pendingUnpriced, rateFenPreview, rowForUnpriced, unitSuffix, withUnit } from "@/lib/providerRates";

type ProviderRatesEditorProps = {
  rows: ProviderRateRow[];
  units: RateUnitOption[];
  unpriced: UnpricedModel[];
  usdCny: number;
  loading: boolean;
  loadError: string;
  saveError: string;
  onChange: (rows: ProviderRateRow[]) => void;
  onReset: () => void;
  onReload: () => void;
};

// Đọc số từ ô nhập; rỗng hoặc sai → 0
function toNumber(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** Bảng giá model theo USD: sửa, đổi thứ tự ưu tiên, xem trước giá quy đổi, cảnh báo model chưa có giá */
export function ProviderRatesEditor({
  rows,
  units,
  unpriced,
  usdCny,
  loading,
  loadError,
  saveError,
  onChange,
  onReset,
  onReload,
}: ProviderRatesEditorProps) {
  const { format } = useCurrency();
  /* confirmReset: hộp xác nhận khôi phục bảng mặc định */
  const [confirmReset, setConfirmReset] = useState(false);

  if (loading) return <p className="settings-field-hint">Đang tải bảng giá…</p>;
  if (loadError) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-red-600">{loadError}</p>
        <Button size="sm" variant="outline" onClick={onReload}>
          Thử lại
        </Button>
      </div>
    );
  }

  const pending = pendingUnpriced(unpriced, rows);

  // Sửa một ô của dòng i
  function patchRow(i: number, patch: Partial<ProviderRateRow>) {
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="settings-field-hint">
        Dòng trên cùng khớp trước. Mẫu tên model dùng * và ?, không phân biệt hoa thường. Model không khớp dòng nào
        sẽ tính theo đơn giá token dự phòng ở mục 3.
      </p>

      {pending.length > 0 ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">
            {pending.length} model đã gán nhưng chưa có giá — đang tính theo đơn giá token dự phòng.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {pending.map((m) => (
              <Button
                key={`${m.channel_id}:${m.model}`}
                size="sm"
                variant="outline"
                type="button"
                title={`Thêm giá cho ${m.model}`}
                onClick={() => onChange([...rows, rowForUnpriced(m)])}
              >
                <Plus className="h-3.5 w-3.5" />
                Thêm giá <span className="font-mono">{m.model}</span>
              </Button>
            ))}
          </div>
          <p className="mt-2 text-xs text-amber-700">
            Nếu thêm dòng bằng mẫu có ký tự đại diện (ví dụ <span className="font-mono">ep-*</span>), danh sách này
            chỉ cập nhật sau khi bấm Lưu.
          </p>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left">
              <th className="p-2">#</th>
              <th className="p-2">Mẫu tên model</th>
              <th className="p-2">Đơn vị</th>
              <th className="p-2">Giá USD</th>
              <th className="p-2">Quy đổi</th>
              <th className="p-2">Ghi chú</th>
              <th className="p-2" aria-label="Thao tác" />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-3 text-center text-muted-foreground">
                  Bảng giá trống — mọi model tính theo đơn giá token dự phòng ở mục 3.
                </td>
              </tr>
            ) : null}
            {rows.map((row, i) => (
              <tr key={i} className="border-b last:border-0 align-top">
                <td className="p-2 text-xs text-muted-foreground">{i + 1}</td>
                <td className="p-2">
                  <input
                    className="settings-input font-mono"
                    value={row.pattern}
                    placeholder="vd. dreamina-seedance-2-0*"
                    onChange={(e) => patchRow(i, { pattern: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <select
                    className="settings-select"
                    value={row.unit}
                    onChange={(e) => onChange(rows.map((r, idx) => (idx === i ? withUnit(r, e.target.value as RateUnit) : r)))}
                  >
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <input
                      className="settings-input w-24"
                      type="number"
                      min={0}
                      step="0.001"
                      aria-label={row.unit === "per_m_input_output" ? "Giá token vào" : "Giá USD"}
                      value={row.usd}
                      onChange={(e) => patchRow(i, { usd: toNumber(e.target.value) })}
                    />
                    {row.unit === "per_m_input_output" ? (
                      <input
                        className="settings-input w-24"
                        type="number"
                        min={0}
                        step="0.001"
                        aria-label="Giá token ra"
                        value={row.usd_out ?? 0}
                        onChange={(e) => patchRow(i, { usd_out: toNumber(e.target.value) })}
                      />
                    ) : null}
                  </div>
                  {row.usd === 0 && (row.usd_out ?? 0) === 0 ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Dòng này vẫn khớp trước các dòng bên dưới nhưng giá 0 nên không được dùng; model sẽ tính theo
                      đơn giá token dự phòng ở mục 3.
                    </p>
                  ) : null}
                </td>
                <td className="p-2 whitespace-nowrap text-xs">
                  {format(rateFenPreview(row.usd, usdCny))}
                  {row.unit === "per_m_input_output" ? ` | ${format(rateFenPreview(row.usd_out ?? 0, usdCny))}` : ""}{" "}
                  <span className="text-muted-foreground">{unitSuffix(units, row.unit)}</span>
                </td>
                <td className="p-2">
                  <input
                    className="settings-input"
                    value={row.note}
                    onChange={(e) => patchRow(i, { note: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <Button size="icon" variant="ghost" aria-label="Lên" disabled={i === 0} onClick={() => onChange(moveRow(rows, i, -1))}>
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Xuống"
                      disabled={i === rows.length - 1}
                      onClick={() => onChange(moveRow(rows, i, 1))}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Xoá dòng"
                      onClick={() => onChange(rows.filter((_, idx) => idx !== i))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {saveError ? (
        <p className="text-sm text-red-600" role="alert">
          {saveError}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => onChange([...rows, emptyRateRow()])}>
          <Plus className="h-3.5 w-3.5" />
          Thêm dòng
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => setConfirmReset(true)}>
          <RotateCcw className="h-3.5 w-3.5" />
          Khôi phục mặc định
        </Button>
      </div>

      <AdminConfirmDialog
        open={confirmReset}
        title="Khôi phục bảng giá mặc định?"
        description="Bảng nháp sẽ được thay bằng giá chính thức mặc định. Chỉ áp dụng sau khi bấm Lưu."
        confirmLabel="Khôi phục"
        cancelLabel="Huỷ"
        onOpenChange={setConfirmReset}
        onConfirm={() => {
          onReset();
          setConfirmReset(false);
        }}
      />
    </div>
  );
}
