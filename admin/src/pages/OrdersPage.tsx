import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  api,
  closeAdminOrder,
  confirmAdminOrder,
  type AdminLedger,
  type AdminOrder,
  type AdminUsageEventListRes,
  type PageMeta,
} from "@/api/client";
import { AdminConfirmDialog } from "@/components/admin/AdminConfirmDialog";
import { AdminField } from "@/components/admin/AdminField";
import { AdminDateRangeFilter } from "@/components/admin/AdminDateRangeFilter";
import { AdminDetailMeta, AdminDetailSection } from "@/components/admin/AdminDetailLayout";
import { AdminEntityLink } from "@/components/admin/AdminEntityLink";
import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminModal } from "@/components/admin/AdminModal";
import { AdminUserSearchSelect } from "@/components/admin/AdminUserSearchSelect";
import { PaginationBar } from "@/components/PaginationBar";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/ui/page";
import { useAdminDetailQuery } from "@/hooks/useAdminDetailQuery";
import { useCurrency } from "@/lib/currency";
import { billingBasisLabel, ledgerKindLabel, orderStatusLabel, payTypeLabel, taskDomainLabel } from "@/lib/statusLabels";

type OrderRes = { items: AdminOrder[]; meta: PageMeta };
type LedgerRes = { items: AdminLedger[]; meta: PageMeta };

const ORDER_TABS = new Set(["orders", "ledger", "usage"]);

function tabFromSearch(raw: string | null): string {
  return raw && ORDER_TABS.has(raw) ? raw : "orders";
}

function ledgerRefLink(row: AdminLedger) {
  if (row.ref_type === "order" && row.ref_id) {
    const id = Number(row.ref_id);
    if (Number.isFinite(id) && id > 0) {
      return <AdminEntityLink kind="order" id={id} label={`Đơn #${id}`} />;
    }
    return (
      <Link
        to={`/orders?tab=orders&trade=${encodeURIComponent(row.ref_id)}`}
        className="admin-link font-mono text-xs"
      >
        {row.ref_id}
      </Link>
    );
  }
  if (!row.ref_type && !row.ref_id) return "—";
  return (
    <span className="font-mono text-xs">
      {row.ref_type}/{row.ref_id}
    </span>
  );
}

// 充值订单、钱包流水与用量明细
export function OrdersPage() {
  const { format, formatAmount } = useCurrency();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(() => tabFromSearch(searchParams.get("tab")));
  const [orderStatus, setOrderStatus] = useState("");
  const [orderUserId, setOrderUserId] = useState<number | null>(null);
  const [ledgerKind, setLedgerKind] = useState("");
  const [ledgerUserId, setLedgerUserId] = useState<number | null>(null);
  const [orderPage, setOrderPage] = useState(1);
  const [ledgerPage, setLedgerPage] = useState(1);
  const [usagePage, setUsagePage] = useState(1);
  const [usageUserId, setUsageUserId] = useState<number | null>(null);
  const [usageTaskId, setUsageTaskId] = useState("");
  const [usageDomain, setUsageDomain] = useState("");
  const [usageBillingKey, setUsageBillingKey] = useState("");
  const [usageCapability, setUsageCapability] = useState("");
  const [usageBasis, setUsageBasis] = useState("");
  const [usageDateFrom, setUsageDateFrom] = useState("");
  const [usageDateTo, setUsageDateTo] = useState("");
  const [orders, setOrders] = useState<OrderRes | null>(null);
  const [ledger, setLedger] = useState<LedgerRes | null>(null);
  const [usage, setUsage] = useState<AdminUsageEventListRes | null>(null);
  const [orderDetail, setOrderDetail] = useState<AdminOrder | null>(null);
  const [ledgerDetail, setLedgerDetail] = useState<AdminLedger | null>(null);
  /*
   * confirmTarget 待「确认到账」的订单
   * confirmNote 确认到账备注
   * closeTarget 待「关闭」的订单
   * actionBusy 确认 / 关闭请求进行中
   */
  const [confirmTarget, setConfirmTarget] = useState<AdminOrder | null>(null);
  const [confirmNote, setConfirmNote] = useState("");
  const [closeTarget, setCloseTarget] = useState<AdminOrder | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const orderQuery = useAdminDetailQuery("order");

  // 应付金额：按下单时记录的币种展示
  function payAmountLabel(order: AdminOrder): string {
    if (order.pay_amount == null) return "—";
    return formatAmount(order.pay_amount, order.pay_currency || "VND");
  }

  // 订单操作完成后：刷新列表并同步详情弹窗
  function applyOrderResult(updated: AdminOrder) {
    setOrderDetail((prev) => (prev && prev.id === updated.id ? updated : prev));
    void loadOrders();
  }

  // 确认银行转账到账
  async function handleConfirmOrder() {
    if (!confirmTarget) return;
    setActionBusy(true);
    try {
      const updated = await confirmAdminOrder(confirmTarget.out_trade_no, confirmNote);
      toast.success("Đã xác nhận nhận tiền, số dư đã được cộng");
      setConfirmTarget(null);
      setConfirmNote("");
      applyOrderResult(updated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không xác nhận được");
    } finally {
      setActionBusy(false);
    }
  }

  // 关闭待支付订单
  async function handleCloseOrder() {
    if (!closeTarget) return;
    setActionBusy(true);
    try {
      const updated = await closeAdminOrder(closeTarget.out_trade_no);
      toast.success("Đã đóng đơn");
      setCloseTarget(null);
      applyOrderResult(updated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không đóng được đơn");
    } finally {
      setActionBusy(false);
    }
  }

  // 待支付订单的操作按钮（确认到账 / 关闭）
  function renderOrderActions(order: AdminOrder, size: "sm" | "default" = "sm") {
    if (order.status !== "pending") return null;
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <Button
          size={size}
          variant="default"
          disabled={actionBusy}
          onClick={(e) => {
            e.stopPropagation();
            setConfirmNote("");
            setConfirmTarget(order);
          }}
        >
          Xác nhận đã nhận tiền
        </Button>
        <Button
          size={size}
          variant="outline"
          disabled={actionBusy}
          onClick={(e) => {
            e.stopPropagation();
            setCloseTarget(order);
          }}
        >
          Đóng đơn
        </Button>
      </div>
    );
  }

  async function loadOrders(page = orderPage) {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(DEFAULT_PAGE_SIZE) });
      if (orderStatus) params.set("status", orderStatus);
      if (orderUserId) params.set("user_id", String(orderUserId));
      setOrders(await api<OrderRes>(`/api/admin/orders?${params}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được danh sách đơn");
    }
  }

  async function loadLedger(page = ledgerPage) {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(DEFAULT_PAGE_SIZE) });
      if (ledgerKind) params.set("kind", ledgerKind);
      if (ledgerUserId) params.set("user_id", String(ledgerUserId));
      setLedger(await api<LedgerRes>(`/api/admin/ledger?${params}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được biến động số dư");
    }
  }

  async function loadUsage(
    page = usagePage,
    overrides?: { billing_key?: string; capability?: string },
  ) {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(DEFAULT_PAGE_SIZE) });
      if (usageUserId) params.set("user_id", String(usageUserId));
      if (usageTaskId.trim()) params.set("task_run_id", usageTaskId.trim());
      if (usageDomain) params.set("domain", usageDomain);
      const billingKey = overrides?.billing_key ?? usageBillingKey.trim();
      const capability = overrides?.capability ?? usageCapability.trim();
      if (billingKey) params.set("billing_key", billingKey);
      if (capability) params.set("capability", capability);
      if (usageBasis) params.set("billing_basis", usageBasis);
      if (usageDateFrom) params.set("created_from", `${usageDateFrom}T00:00:00`);
      if (usageDateTo) params.set("created_to", `${usageDateTo}T23:59:59`);
      setUsage(await api<AdminUsageEventListRes>(`/api/admin/usage-events?${params}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được lượng sử dụng");
    }
  }

  useEffect(() => {
    const next = tabFromSearch(searchParams.get("tab"));
    setTab((prev) => (prev === next ? prev : next));
  }, [searchParams]);

  useEffect(() => {
    void loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderPage]);

  useEffect(() => {
    void loadLedger();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ledgerPage]);

  useEffect(() => {
    void loadUsage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usagePage]);

  useEffect(() => {
    if (!orderQuery.id || !orders?.items) return;
    const hit = orders.items.find((o) => o.id === orderQuery.id);
    if (hit) setOrderDetail(hit);
  }, [orderQuery.id, orders?.items]);

  useEffect(() => {
    const tradeNo = searchParams.get("trade");
    if (!tradeNo) return;
    void (async () => {
      try {
        const res = await api<OrderRes>(
          `/api/admin/orders?page=1&page_size=1&out_trade_no=${encodeURIComponent(tradeNo)}`,
        );
        const hit = res.items[0];
        if (hit) {
          setOrderDetail(hit);
          orderQuery.open(hit.id);
        }
      } catch {
        /* 深链失败时静默，用户仍可手动筛选 */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  function onTabChange(next: string) {
    setTab(next);
    const params = new URLSearchParams(searchParams);
    if (next === "orders") params.delete("tab");
    else params.set("tab", next);
    setSearchParams(params, { replace: true });
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Đã sao chép");
    } catch {
      toast.error("Không sao chép được");
    }
  }

  return (
    <div className="admin-list-page">
      <PageHeader description="Xem đơn nạp tiền, biến động số dư ví và chi tiết lượng sử dụng AI" />
      <Tabs value={tab} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="orders">Đơn nạp tiền</TabsTrigger>
          <TabsTrigger value="ledger">Biến động số dư</TabsTrigger>
          <TabsTrigger value="usage">Lượng sử dụng</TabsTrigger>
        </TabsList>
        <TabsContent value="orders" className="space-y-4">
          <AdminFilterBar>
            <Select value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
              <option value="">Tất cả trạng thái</option>
              <option value="pending">Chờ thanh toán</option>
              <option value="paid">Đã thanh toán</option>
              <option value="closed">Đã đóng</option>
            </Select>
            <AdminUserSearchSelect value={orderUserId} onChange={(id) => setOrderUserId(id)} />
            <Button
              size="sm"
              variant="secondary"
              className="admin-filter-action"
              onClick={() => {
                setOrderPage(1);
                void loadOrders(1);
              }}
            >
              Lọc
            </Button>
          </AdminFilterBar>
          <div className="rounded-lg border bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Mã đơn</TableHead>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead className="whitespace-nowrap">Cần trả</TableHead>
                  <TableHead className="whitespace-nowrap">Cộng số dư</TableHead>
                  <TableHead className="whitespace-nowrap">Phương thức thanh toán</TableHead>
                  <TableHead className="whitespace-nowrap">Trạng thái</TableHead>
                  <TableHead className="whitespace-nowrap">Thao tác</TableHead>
                  <TableHead className="whitespace-nowrap">Mã giao dịch</TableHead>
                  <TableHead>Ghi chú</TableHead>
                  <TableHead className="whitespace-nowrap">Thanh toán lúc</TableHead>
                  <TableHead className="whitespace-nowrap">Tạo lúc</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(orders?.items ?? []).map((o) => (
                  <TableRow
                    key={o.id}
                    className="cursor-pointer"
                    onClick={() => {
                      setOrderDetail(o);
                      orderQuery.open(o.id);
                    }}
                  >
                    <TableCell>{o.id}</TableCell>
                    <TableCell className="font-mono text-xs">{o.out_trade_no}</TableCell>
                    <TableCell>
                      <AdminEntityLink kind="user" id={o.user_id} label={o.user_email ?? undefined} />
                    </TableCell>
                    <TableCell>{o.sku_id}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">{payAmountLabel(o)}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">{format(o.credit_fen)}</TableCell>
                    <TableCell className="whitespace-nowrap">{payTypeLabel(o.pay_type)}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge variant={o.status === "paid" ? "success" : "secondary"}>
                        {orderStatusLabel(o.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>{renderOrderActions(o) ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{o.trade_no || "—"}</TableCell>
                    <TableCell className="max-w-[160px] truncate text-xs" title={o.note ?? undefined}>
                      {o.note || "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {o.paid_at ? new Date(o.paid_at).toLocaleString("vi-VN") : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(o.created_at).toLocaleString("vi-VN")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {orders && (
            <PaginationBar
              page={orders.meta.page}
              pageSize={orders.meta.page_size}
              total={orders.meta.total}
              onPageChange={setOrderPage}
            />
          )}
        </TabsContent>
        <TabsContent value="ledger" className="space-y-4">
          <AdminFilterBar>
            <Select value={ledgerKind} onChange={(e) => setLedgerKind(e.target.value)}>
              <option value="">Tất cả loại</option>
              <option value="topup">Nạp tiền</option>
              <option value="grant">Tặng</option>
              <option value="adjust">Điều chỉnh số dư</option>
              <option value="freeze">Tạm giữ</option>
              <option value="unfreeze">Hoàn tạm giữ</option>
              <option value="settle">Quyết toán</option>
              <option value="refund">Hoàn tiền</option>
            </Select>
            <AdminUserSearchSelect value={ledgerUserId} onChange={(id) => setLedgerUserId(id)} />
            <Button
              size="sm"
              variant="secondary"
              className="admin-filter-action"
              onClick={() => {
                setLedgerPage(1);
                void loadLedger(1);
              }}
            >
              Lọc
            </Button>
          </AdminFilterBar>
          <div className="rounded-lg border bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>Biến động</TableHead>
                  <TableHead>Số dư sau</TableHead>
                  <TableHead>Loại</TableHead>
                  <TableHead>Liên kết</TableHead>
                  <TableHead>Ghi chú</TableHead>
                  <TableHead>Thời gian</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(ledger?.items ?? []).map((e) => (
                  <TableRow key={e.id} className="cursor-pointer" onClick={() => setLedgerDetail(e)}>
                    <TableCell>{e.id}</TableCell>
                    <TableCell>
                      <AdminEntityLink kind="user" id={e.user_id} label={e.user_email ?? undefined} />
                    </TableCell>
                    <TableCell className={e.delta_fen >= 0 ? "text-emerald-700" : "text-red-600"}>
                      {e.delta_fen >= 0 ? "+" : ""}
                      {format(e.delta_fen)}
                    </TableCell>
                    <TableCell>{format(e.balance_after)}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{ledgerKindLabel(e.kind)}</Badge>
                    </TableCell>
                    <TableCell>{ledgerRefLink(e)}</TableCell>
                    <TableCell className="max-w-[200px] truncate">{e.note}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(e.created_at).toLocaleString("vi-VN")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {ledger && (
            <PaginationBar
              page={ledger.meta.page}
              pageSize={ledger.meta.page_size}
              total={ledger.meta.total}
              onPageChange={setLedgerPage}
            />
          )}
        </TabsContent>
        <TabsContent value="usage" className="space-y-4">
          <AdminFilterBar>
            <AdminUserSearchSelect value={usageUserId} onChange={(id) => setUsageUserId(id)} />
            <Input placeholder="ID tác vụ" value={usageTaskId} onChange={(e) => setUsageTaskId(e.target.value)} />
            <Select value={usageDomain} onChange={(e) => setUsageDomain(e.target.value)}>
              <option value="">Tất cả mảng</option>
              <option value="kepu">Video ngắn AI</option>
              <option value="drama">Phim ngắn AI</option>
              <option value="studio">Studio</option>
              <option value="api">API mở</option>
            </Select>
            <Input
              placeholder="billing_key"
              value={usageBillingKey}
              onChange={(e) => setUsageBillingKey(e.target.value)}
            />
            <Select value={usageCapability} onChange={(e) => setUsageCapability(e.target.value)}>
              <option value="">Tất cả loại tạo</option>
              <option value="llm">LLM văn bản</option>
              <option value="image">Tạo ảnh</option>
              <option value="video">Tạo video</option>
              <option value="tts">Giọng đọc</option>
            </Select>
            <Select value={usageBasis} onChange={(e) => setUsageBasis(e.target.value)}>
              <option value="">Tất cả cơ sở tính phí</option>
              <option value="estimate">Ước tính</option>
              <option value="upstream">Thực tế (nhà cung cấp)</option>
              <option value="upstream_usage">Thực tế (token)</option>
              <option value="upstream_cost">Thực tế (chi phí)</option>
            </Select>
            <AdminDateRangeFilter
              from={usageDateFrom}
              to={usageDateTo}
              onChange={({ from, to }) => {
                setUsageDateFrom(from);
                setUsageDateTo(to);
              }}
            />
            <Button
              size="sm"
              variant="outline"
              className="admin-filter-action"
              onClick={() => {
                setUsageBillingKey("llm_chat");
                setUsageCapability("llm");
                setUsagePage(1);
                void loadUsage(1, { billing_key: "llm_chat", capability: "llm" });
              }}
            >
              Lượng sử dụng LLM
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="admin-filter-action"
              onClick={() => {
                setUsagePage(1);
                void loadUsage(1);
              }}
            >
              Lọc
            </Button>
          </AdminFilterBar>
          <div className="rounded-lg border bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Thời gian</TableHead>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>Tác vụ</TableHead>
                  <TableHead>Dự án</TableHead>
                  <TableHead>Mảng</TableHead>
                  <TableHead>Năng lực</TableHead>
                  <TableHead>Mô hình</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Đã trừ</TableHead>
                  <TableHead>Giá gốc nhà cung cấp</TableHead>
                  <TableHead>Cách tính phí</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(usage?.items ?? []).map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {row.created_at ? new Date(row.created_at).toLocaleString("vi-VN") : "—"}
                    </TableCell>
                    <TableCell>
                      <AdminEntityLink kind="user" id={row.user_id} label={row.user_email ?? undefined} />
                    </TableCell>
                    <TableCell>
                      {row.task_run_id ? (
                        <AdminEntityLink kind="task" id={row.task_run_id} />
                      ) : (
                        "Cũ / không liên kết"
                      )}
                    </TableCell>
                    <TableCell className="text-xs">
                      {row.project_id ? (
                        <AdminEntityLink kind="project" id={row.project_id} />
                      ) : row.drama_project_id ? (
                        <AdminEntityLink kind="drama" id={row.drama_project_id} />
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>{row.domain ? taskDomainLabel(row.domain) : "—"}</TableCell>
                    <TableCell>{row.capability ?? row.billing_key}</TableCell>
                    <TableCell className="max-w-[120px] truncate text-xs">{row.model || "—"}</TableCell>
                    <TableCell>{row.total_tokens ?? 0}</TableCell>
                    <TableCell>{format(row.charge_fen ?? 0)}</TableCell>
                    <TableCell>{format(row.cost_fen ?? 0)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          row.billing_basis === "estimate" || row.estimated
                            ? "secondary"
                            : "success"
                        }
                        title={
                          row.billing_basis === "upstream_cost"
                            ? "Trừ tiền theo chi phí tính từ bảng giá mô hình và lượng sử dụng thực tế"
                            : row.billing_basis === "upstream_usage"
                              ? "Trừ tiền theo số token (usage) nhà cung cấp trả về × đơn giá trong bảng giá"
                              : "Nhà cung cấp không trả usage, trừ tiền theo số token ước tính trong cấu hình"
                        }
                      >
                        {billingBasisLabel(row.billing_basis, row.estimated)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {usage && (
            <PaginationBar
              page={usage.meta.page}
              pageSize={usage.meta.page_size}
              total={usage.meta.total}
              onPageChange={setUsagePage}
            />
          )}
        </TabsContent>
      </Tabs>

      <AdminModal
        open={orderQuery.isOpen && !!orderDetail}
        onOpenChange={(open) => {
          if (!open) {
            setOrderDetail(null);
            orderQuery.close();
          }
        }}
        size="md"
        title={orderDetail ? `Chi tiết đơn #${orderDetail.id}` : "Chi tiết đơn"}
        subtitle={orderDetail?.out_trade_no}
        footer={
          orderDetail ? (
            <div className="flex w-full flex-wrap items-center justify-between gap-2">
              <Button size="sm" variant="outline" onClick={() => void copyText(orderDetail.out_trade_no)}>
                Sao chép mã đơn
              </Button>
              {renderOrderActions(orderDetail)}
            </div>
          ) : undefined
        }
      >
        {orderDetail ? (
          <AdminDetailSection>
            <AdminDetailMeta
              items={[
                {
                  label: "Người dùng",
                  value: (
                    <AdminEntityLink
                      kind="user"
                      id={orderDetail.user_id}
                      label={orderDetail.user_email ?? undefined}
                    />
                  ),
                },
                { label: "SKU", value: orderDetail.sku_id },
                { label: "Số tiền", value: format(orderDetail.amount_fen) },
                { label: "Cộng số dư", value: format(orderDetail.credit_fen) },
                {
                  label: "Cần trả",
                  value: orderDetail.pay_amount != null
                    ? `${payAmountLabel(orderDetail)}（${orderDetail.pay_currency || "VND"}）`
                    : "—",
                },
                { label: "Phương thức thanh toán", value: payTypeLabel(orderDetail.pay_type) },
                { label: "Trạng thái", value: orderStatusLabel(orderDetail.status) },
                { label: "Mã giao dịch", value: orderDetail.trade_no || "—" },
                { label: "Ghi chú", value: orderDetail.note || "—", full: true },
                {
                  label: "Thanh toán lúc",
                  value: orderDetail.paid_at ? new Date(orderDetail.paid_at).toLocaleString("vi-VN") : "—",
                },
                {
                  label: "Tạo lúc",
                  value: new Date(orderDetail.created_at).toLocaleString("vi-VN"),
                  full: true,
                },
              ]}
            />
          </AdminDetailSection>
        ) : null}
      </AdminModal>

      <AdminModal
        open={!!ledgerDetail}
        onOpenChange={(open) => !open && setLedgerDetail(null)}
        size="md"
        title={ledgerDetail ? `Chi tiết biến động #${ledgerDetail.id}` : "Chi tiết biến động"}
      >
        {ledgerDetail ? (
          <AdminDetailSection>
            <AdminDetailMeta
              items={[
                {
                  label: "Người dùng",
                  value: (
                    <AdminEntityLink
                      kind="user"
                      id={ledgerDetail.user_id}
                      label={ledgerDetail.user_email ?? undefined}
                    />
                  ),
                },
                { label: "Loại", value: ledgerKindLabel(ledgerDetail.kind) },
                { label: "Biến động", value: format(ledgerDetail.delta_fen) },
                { label: "Số dư sau", value: format(ledgerDetail.balance_after) },
                { label: "Liên kết", value: ledgerRefLink(ledgerDetail) },
                { label: "Ghi chú", value: ledgerDetail.note || "—" },
                {
                  label: "Thời gian",
                  value: new Date(ledgerDetail.created_at).toLocaleString("vi-VN"),
                  full: true,
                },
              ]}
            />
          </AdminDetailSection>
        ) : null}
      </AdminModal>

      <AdminModal
        open={!!confirmTarget}
        onOpenChange={(open) => {
          if (!open && !actionBusy) {
            setConfirmTarget(null);
            setConfirmNote("");
          }
        }}
        size="md"
        title="Xác nhận đã nhận tiền"
        subtitle={
          confirmTarget
            ? `Đơn ${confirmTarget.out_trade_no} · Cần trả ${payAmountLabel(confirmTarget)} · Cộng số dư ${format(confirmTarget.credit_fen)}`
            : undefined
        }
        footer={
          <>
            <Button variant="outline" disabled={actionBusy} onClick={() => setConfirmTarget(null)}>
              Huỷ
            </Button>
            <Button disabled={actionBusy} onClick={() => void handleConfirmOrder()}>
              {actionBusy ? "Đang xử lý…" : "Xác nhận và cộng số dư"}
            </Button>
          </>
        }
      >
        <div className="admin-form-grid">
          <p className="text-sm text-muted-foreground">
            Đối chiếu sao kê ngân hàng trước: nội dung chuyển khoản (mã đơn) và số tiền phải khớp. Sau khi xác nhận, tiền được cộng ngay vào số dư của người dùng. Thao tác này không hoàn tác được.
          </p>
          <AdminField label="Ghi chú" hint="Không bắt buộc, vd. mã giao dịch ngân hàng hoặc ghi chú đối chiếu">
            <Input
              value={confirmNote}
              maxLength={255}
              placeholder="Vd. VCB mã GD 123456"
              onChange={(e) => setConfirmNote(e.target.value)}
            />
          </AdminField>
        </div>
      </AdminModal>

      <AdminConfirmDialog
        open={!!closeTarget}
        title="Đóng đơn"
        description={
          closeTarget
            ? `Đơn ${closeTarget.out_trade_no} sẽ bị đóng. Người dùng không thể chuyển khoản theo đơn này để nạp tiền nữa.`
            : undefined
        }
        confirmLabel="Đóng đơn"
        destructive
        loading={actionBusy}
        onOpenChange={(open) => {
          if (!open && !actionBusy) setCloseTarget(null);
        }}
        onConfirm={() => void handleCloseOrder()}
      />
    </div>
  );
}
