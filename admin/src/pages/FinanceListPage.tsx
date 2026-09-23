import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AdminChipFilter } from "@/components/admin/AdminChipFilter";
import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { PageSection } from "@/components/admin/PageSection";
import { PageHeader } from "@/components/ui/page";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type AdminFinanceDaily } from "@/api/client";
import { useCurrency } from "@/lib/currency";

type FinanceDays = "7" | "14" | "30" | "90";

const DAY_OPTIONS = [
  { value: "7", label: "7 ngày qua" },
  { value: "14", label: "14 ngày qua" },
  { value: "30", label: "30 ngày qua" },
  { value: "90", label: "90 ngày qua" },
];

function profitClass(profitFen: number): string {
  if (profitFen > 0) return "text-[var(--admin-forest)] font-semibold";
  if (profitFen < 0) return "text-red-600 font-semibold";
  return "";
}

/** 管理端财务列表：按日展示扣费、成本、token 与利润 */
export function FinanceListPage() {
  const { format } = useCurrency();
  const [days, setDays] = useState<FinanceDays>("30");
  const [data, setData] = useState<AdminFinanceDaily | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<AdminFinanceDaily>(`/api/admin/finance/daily?days=${days}`);
      setData(res);
    } catch (err) {
      setData(null);
      toast.error(err instanceof Error ? err.message : "Không tải được dữ liệu tài chính");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const rows = [...(data?.series ?? [])].reverse();
  const totals = data?.totals;
  const rangeMismatch = data != null && String(data.days) !== days;

  return (
    <div className="admin-page">
      <PageHeader description="Tổng hợp theo ngày: tiền đã trừ, chi phí (tính theo bảng giá mô hình) và lợi nhuận" />

      <AdminFilterBar>
        <AdminChipFilter
          label="Khoảng thời gian"
          value={days}
          options={DAY_OPTIONS}
          onChange={(v) => setDays(v as FinanceDays)}
          className="admin-chip-filter--segment"
        />
      </AdminFilterBar>

      <PageSection
        title="Tài chính theo ngày"
        description={
          rangeMismatch ? "Dữ liệu không khớp khoảng thời gian đang chọn, hãy tải lại" : `${days} ngày qua · Chi phí = giá gốc nhà cung cấp tính theo bảng giá mô hình`
        }
        bodyClassName="!pt-0"
      >
        <div className="admin-table-wrap">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ngày</TableHead>
                <TableHead>Đã trừ</TableHead>
                <TableHead>Chi phí</TableHead>
                <TableHead>Token</TableHead>
                <TableHead>Lợi nhuận</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="!text-center text-[var(--admin-muted)]">
                    Đang tải…
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="!text-center text-[var(--admin-muted)]">
                    Chưa có dữ liệu
                  </TableCell>
                </TableRow>
              ) : (
                <>
                  {rows.map((row) => (
                    <TableRow key={row.date}>
                      <TableCell className="font-mono text-xs">{row.date}</TableCell>
                      <TableCell>{format(row.charge_fen)}</TableCell>
                      <TableCell>{format(row.cost_fen)}</TableCell>
                      <TableCell>{row.tokens.toLocaleString("vi-VN")}</TableCell>
                      <TableCell className={profitClass(row.profit_fen)}>
                        {format(row.profit_fen)}
                        {row.profit_pct != null ? ` (${row.profit_pct}%)` : ""}
                      </TableCell>
                    </TableRow>
                  ))}
                  {totals ? (
                    <TableRow className="bg-[rgba(15,45,32,0.04)] font-medium">
                      <TableCell>Tổng</TableCell>
                      <TableCell>{format(totals.charge_fen)}</TableCell>
                      <TableCell>{format(totals.cost_fen)}</TableCell>
                      <TableCell>{totals.tokens.toLocaleString("vi-VN")}</TableCell>
                      <TableCell className={profitClass(totals.profit_fen)}>
                        {format(totals.profit_fen)}
                        {totals.profit_pct != null ? ` (${totals.profit_pct}%)` : ""}
                      </TableCell>
                    </TableRow>
                  ) : null}
                </>
              )}
            </TableBody>
          </Table>
        </div>
      </PageSection>
    </div>
  );
}
