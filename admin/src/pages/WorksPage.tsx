import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AdminWork, type PageMeta } from "@/api/client";
import { AdminDetailMeta, AdminDetailSection } from "@/components/admin/AdminDetailLayout";
import { AdminEntityLink } from "@/components/admin/AdminEntityLink";
import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminModal } from "@/components/admin/AdminModal";
import { AdminSearchInput } from "@/components/admin/AdminSearchInput";
import { AdminUserSearchSelect } from "@/components/admin/AdminUserSearchSelect";
import { PaginationBar } from "@/components/PaginationBar";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/ui/page";
import { useAdminDetailQuery } from "@/hooks/useAdminDetailQuery";
import { auditStatusLabel, visibilityLabel } from "@/lib/statusLabels";

type ListRes = { items: AdminWork[]; meta: PageMeta };

function coverSrc(url: string | null | undefined): string {
  const trimmed = (url || "").trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

// 作品审核：搜索、预览与只读详情
export function WorksPage() {
  const [auditStatus, setAuditStatus] = useState("");
  const [visibility, setVisibility] = useState("");
  const [q, setQ] = useState("");
  const [userId, setUserId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListRes | null>(null);
  const [detail, setDetail] = useState<AdminWork | null>(null);
  const workDetail = useAdminDetailQuery("work");

  async function load(nextPage = page) {
    try {
      const params = new URLSearchParams({ page: String(nextPage), page_size: String(DEFAULT_PAGE_SIZE) });
      if (auditStatus) params.set("audit_status", auditStatus);
      if (visibility) params.set("visibility", visibility);
      if (q.trim()) params.set("q", q.trim());
      if (userId) params.set("user_id", String(userId));
      setData(await api<ListRes>(`/api/admin/works?${params}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được danh sách");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => {
    if (!workDetail.id || !data?.items) return;
    const hit = data.items.find((w) => w.id === workDetail.id);
    if (hit) setDetail(hit);
  }, [workDetail.id, data?.items]);

  async function patchWork(id: number, body: { visibility?: string; audit_status?: string }) {
    try {
      await api(`/api/admin/works/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      toast.success("Đã cập nhật");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không cập nhật được");
    }
  }

  function openWork(work: AdminWork) {
    setDetail(work);
    workDetail.open(work.id);
  }

  return (
    <div className="admin-list-page">
      <PageHeader description="Chỉnh chế độ hiển thị và trạng thái duyệt" />
      <AdminFilterBar>
        <AdminSearchInput
          value={q}
          onChange={setQ}
          placeholder="Tìm theo tiêu đề"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setPage(1);
              void load(1);
            }
          }}
        />
        <AdminUserSearchSelect value={userId} onChange={(id) => setUserId(id)} />
        <Select value={auditStatus} onChange={(e) => setAuditStatus(e.target.value)}>
          <option value="">Tất cả trạng thái duyệt</option>
          <option value="pending">Chờ duyệt</option>
          <option value="passed">Đã duyệt</option>
          <option value="rejected">Bị từ chối</option>
        </Select>
        <Select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
          <option value="">Tất cả chế độ hiển thị</option>
          <option value="public">Công khai</option>
          <option value="private">Riêng tư</option>
          <option value="unlisted">Không công khai (ai có link xem được)</option>
        </Select>
        <Button
          size="sm"
          variant="secondary"
          className="admin-filter-action"
          onClick={() => {
            setPage(1);
            void load(1);
          }}
        >
          Lọc
        </Button>
      </AdminFilterBar>
      <div className="rounded-lg border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ảnh bìa</TableHead>
              <TableHead>ID</TableHead>
              <TableHead>Tiêu đề</TableHead>
              <TableHead>Người dùng</TableHead>
              <TableHead>Hiển thị</TableHead>
              <TableHead>Duyệt</TableHead>
              <TableHead>Đăng lúc</TableHead>
              <TableHead>Thao tác</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.items ?? []).map((w) => (
              <TableRow key={w.id}>
                <TableCell>
                  {w.cover_url ? (
                    <button type="button" onClick={() => openWork(w)} className="block">
                      <img src={coverSrc(w.cover_url)} alt={w.title} className="admin-thumb" loading="lazy" />
                    </button>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>{w.id}</TableCell>
                <TableCell className="max-w-[200px] truncate">
                  <button type="button" className="admin-link text-left" onClick={() => openWork(w)}>
                    {w.title}
                  </button>
                </TableCell>
                <TableCell>
                  <AdminEntityLink kind="user" id={w.user_id} label={w.user_email ?? undefined} />
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{visibilityLabel(w.visibility)}</Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      w.audit_status === "rejected"
                        ? "destructive"
                        : w.audit_status === "passed"
                          ? "success"
                          : "warning"
                    }
                  >
                    {auditStatusLabel(w.audit_status)}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(w.published_at).toLocaleString("vi-VN")}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <Button size="sm" variant="outline" onClick={() => openWork(w)}>
                      Chi tiết
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void patchWork(w.id, { audit_status: "passed" })}>
                      Duyệt
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void patchWork(w.id, { audit_status: "rejected" })}
                    >
                      Từ chối
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        void patchWork(w.id, {
                          visibility: w.visibility === "public" ? "private" : "public",
                        })
                      }
                    >
                      {w.visibility === "public" ? "Chuyển riêng tư" : "Chuyển công khai"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {data && (
        <PaginationBar
          page={data.meta.page}
          pageSize={data.meta.page_size}
          total={data.meta.total}
          onPageChange={setPage}
        />
      )}

      <AdminModal
        open={workDetail.isOpen && !!detail}
        onOpenChange={(open) => {
          if (!open) {
            setDetail(null);
            workDetail.close();
          }
        }}
        size="lg"
        title={detail?.title ?? "Chi tiết tác phẩm"}
        subtitle={detail ? `Tác phẩm #${detail.id}` : undefined}
      >
        {detail ? (
          <>
            {(detail.cover_url || detail.video_url) ? (
              <AdminDetailSection title="Xem trước media">
                <div className="admin-detail-media">
                  {detail.cover_url ? (
                    <img src={coverSrc(detail.cover_url)} alt={detail.title} />
                  ) : null}
                  {detail.video_url ? (
                    <video src={detail.video_url} controls className="max-w-full" />
                  ) : null}
                </div>
              </AdminDetailSection>
            ) : null}
            <AdminDetailSection title="Thông tin chung">
              <AdminDetailMeta
                items={[
                  {
                    label: "Người dùng",
                    value: (
                      <AdminEntityLink
                        kind="user"
                        id={detail.user_id}
                        label={detail.user_email ?? undefined}
                      />
                    ),
                  },
                  {
                    label: "Dự án liên quan",
                    value: detail.project_id ? (
                      <AdminEntityLink kind="project" id={detail.project_id} />
                    ) : (
                      "—"
                    ),
                  },
                  { label: "Hiển thị", value: visibilityLabel(detail.visibility) },
                  { label: "Duyệt", value: auditStatusLabel(detail.audit_status) },
                  {
                    label: "Đăng lúc",
                    value: new Date(detail.published_at).toLocaleString("vi-VN"),
                    full: true,
                  },
                ]}
              />
            </AdminDetailSection>
            {detail.video_url ? (
              <Button size="sm" variant="outline" asChild>
                <a href={detail.video_url} target="_blank" rel="noreferrer">
                  Mở video trong tab mới
                </a>
              </Button>
            ) : null}
          </>
        ) : null}
      </AdminModal>
    </div>
  );
}
