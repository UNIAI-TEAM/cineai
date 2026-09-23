import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AdminProject, type PageMeta } from "@/api/client";
import {
  AdminDetailMeta,
  AdminDetailNote,
  AdminDetailSection,
  AdminDetailStatGrid,
  AdminDetailTableWrap,
} from "@/components/admin/AdminDetailLayout";
import { AdminEntityLink } from "@/components/admin/AdminEntityLink";
import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminModal } from "@/components/admin/AdminModal";
import { StoredErrorText } from "@/components/admin/StoredErrorText";
import { AdminUserSearchSelect } from "@/components/admin/AdminUserSearchSelect";
import { PaginationBar } from "@/components/PaginationBar";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/ui/page";
import { useAdminDetailQuery } from "@/hooks/useAdminDetailQuery";
import { PROJECT_STATUS_OPTIONS, projectStatusLabel, taskStatusLabel, taskTypeLabel } from "@/lib/statusLabels";
import { useCurrency } from "@/lib/currency";

type ListRes = { items: AdminProject[]; meta: PageMeta };

function statusBadgeVariant(status: string): "destructive" | "success" | "warning" | "info" | "secondary" {
  if (status === "FAILED" || status === "REJECTED") return "destructive";
  if (status === "DONE") return "success";
  if (status === "CANCELLED") return "secondary";
  if (status === "DRAFT") return "secondary";
  return "info";
}

function mediaSrc(url: string | null | undefined): string {
  const trimmed = (url || "").trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

// 科普项目列表与详情（镜头 / 任务 / 费用 / 媒体预览）
export function ProjectsPage() {
  const { format } = useCurrency();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [userId, setUserId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListRes | null>(null);
  const [detail, setDetail] = useState<AdminProject | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const projectDetail = useAdminDetailQuery("open");

  async function load(nextPage = page) {
    try {
      const params = new URLSearchParams({ page: String(nextPage), page_size: String(DEFAULT_PAGE_SIZE) });
      if (status) params.set("status", status);
      if (q.trim()) params.set("q", q.trim());
      if (userId) params.set("user_id", String(userId));
      setData(await api<ListRes>(`/api/admin/projects?${params}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được danh sách");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function openDetail(id: number) {
    setDetailLoading(true);
    projectDetail.open(id);
    try {
      setDetail(await api<AdminProject>(`/api/admin/projects/${id}`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được chi tiết");
      projectDetail.close();
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    if (!projectDetail.id) {
      setDetail(null);
      return;
    }
    if (detail?.id === projectDetail.id) return;
    void openDetail(projectDetail.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectDetail.id]);

  const usage = detail?.usage;

  return (
    <div className="admin-list-page">
      <PageHeader description="Dự án video ngắn: trạng thái, cảnh, tác vụ liên quan và chi phí" />
      <AdminFilterBar>
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {PROJECT_STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || "all"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
        <Input placeholder="Tiêu đề / thông báo lỗi" value={q} onChange={(e) => setQ(e.target.value)} />
        <AdminUserSearchSelect value={userId} onChange={(id) => setUserId(id)} />
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
              <TableHead>ID</TableHead>
              <TableHead>Tiêu đề</TableHead>
              <TableHead>Người dùng</TableHead>
              <TableHead>Mẫu</TableHead>
              <TableHead>Chế độ</TableHead>
              <TableHead>Trạng thái</TableHead>
              <TableHead>Tiến độ</TableHead>
              <TableHead>Cảnh</TableHead>
              <TableHead>Chi phí</TableHead>
              <TableHead>Tạo lúc</TableHead>
              <TableHead>Cập nhật lúc</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.items ?? []).map((p) => (
              <TableRow key={p.id}>
                <TableCell>{p.id}</TableCell>
                <TableCell className="max-w-[180px] truncate">{p.title}</TableCell>
                <TableCell className="text-sm">
                  <AdminEntityLink kind="user" id={p.user_id} label={p.user_email ?? undefined} />
                </TableCell>
                <TableCell className="font-mono text-xs">{p.template_id}</TableCell>
                <TableCell className="text-xs">{p.pipeline_mode}</TableCell>
                <TableCell>
                  <Badge variant={statusBadgeVariant(p.status)}>{projectStatusLabel(p.status)}</Badge>
                </TableCell>
                <TableCell>{p.progress}%</TableCell>
                <TableCell>{p.shot_count}</TableCell>
                <TableCell>{format(p.charge_fen ?? 0)}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(p.created_at).toLocaleString("vi-VN")}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(p.updated_at).toLocaleString("vi-VN")}
                </TableCell>
                <TableCell>
                  <Button size="sm" variant="outline" onClick={() => void openDetail(p.id)}>
                    Chi tiết
                  </Button>
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
        open={projectDetail.isOpen}
        onOpenChange={(open) => {
          if (!open) {
            setDetail(null);
            projectDetail.close();
          }
        }}
        size="full"
        title={detail ? `Dự án #${detail.id} · ${detail.title}` : "Chi tiết dự án"}
        subtitle={detail ? projectStatusLabel(detail.status) : detailLoading ? "Đang tải…" : undefined}
        bodyClassName="space-y-3"
      >
        {detailLoading && !detail ? (
          <div className="py-10 text-center text-sm text-[var(--admin-muted)]">Đang tải…</div>
        ) : null}
        {detail ? (
          <>
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
                    label: "Trạng thái / tiến độ",
                    value: `${projectStatusLabel(detail.status)} · ${detail.progress}% · ${detail.shot_count} cảnh`,
                  },
                  { label: "Mẫu", value: detail.template_id },
                  { label: "Chế độ", value: detail.pipeline_mode },
                  { label: "Nguồn", value: detail.source_type || "—" },
                  {
                    label: "Độ phân giải / tỉ lệ",
                    value: `${detail.resolution_mode || "—"} · ${detail.output_ratio || "—"}`,
                  },
                  { label: "Giọng đọc", value: detail.voice_id || "—", full: true },
                ]}
              />
              <AdminDetailNote empty={!detail.error_msg && !detail.error_code} className="mt-3">
                <StoredErrorText
                  message={detail.error_msg}
                  code={detail.error_code}
                  params={detail.error_params}
                  emptyText="Không có lỗi"
                />
              </AdminDetailNote>
            </AdminDetailSection>

            {(detail.cover_url || detail.final_video_url) ? (
              <AdminDetailSection title="Xem trước media">
                <div className="admin-detail-media">
                  {detail.cover_url ? (
                    <img src={mediaSrc(detail.cover_url)} alt="Ảnh bìa" />
                  ) : null}
                  {detail.final_video_url ? (
                    <video src={mediaSrc(detail.final_video_url)} controls className="max-w-full" />
                  ) : null}
                </div>
              </AdminDetailSection>
            ) : null}

            <AdminDetailSection title="Tổng chi phí">
              <AdminDetailStatGrid
                items={[
                  { label: "Đã trừ", value: format(usage?.charge_fen ?? detail.charge_fen ?? 0) },
                  { label: "Giá vốn", value: format(usage?.cost_fen ?? 0) },
                  { label: "Tokens", value: usage?.tokens ?? 0 },
                  {
                    label: "Ảnh/Video/LLM/TTS",
                    value: `${usage?.image_gens ?? 0}/${usage?.video_gens ?? 0}/${usage?.llm_calls ?? 0}/${usage?.tts_gens ?? 0}`,
                  },
                ]}
              />
            </AdminDetailSection>

            <AdminDetailSection title={`Cảnh (${(detail.shots ?? []).length})`}>
              <AdminDetailTableWrap>
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Trạng thái</th>
                      <th>Thời lượng</th>
                      <th>Ảnh</th>
                      <th>Video</th>
                      <th>Âm thanh</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.shots ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={6} className="!text-center text-[var(--admin-muted)]">
                          Chưa có cảnh
                        </td>
                      </tr>
                    ) : (
                      (detail.shots ?? []).map((s) => (
                        <tr key={s.id}>
                          <td>{s.shot_no}</td>
                          <td>{s.status}</td>
                          <td>{s.duration}s</td>
                          <td>{s.has_image ? "Có" : "—"}</td>
                          <td>{s.has_video ? "Có" : "—"}</td>
                          <td>{s.has_audio ? "Có" : "—"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </AdminDetailTableWrap>
            </AdminDetailSection>

            <AdminDetailSection title={`Tác vụ liên quan (${(detail.recent_tasks ?? []).length} gần nhất)`}>
              <AdminDetailTableWrap className="max-h-[200px]">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Loại</th>
                      <th>Trạng thái</th>
                      <th>Đã trừ / ước tính</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.recent_tasks ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={4} className="!text-center text-[var(--admin-muted)]">
                          Chưa có tác vụ
                        </td>
                      </tr>
                    ) : (
                      (detail.recent_tasks ?? []).map((t) => (
                        <tr key={t.id}>
                          <td>
                            <AdminEntityLink kind="task" id={t.id} />
                          </td>
                          <td>
                            {taskTypeLabel(t.task_type)}
                            {t.provider_channel_id ? (
                              <div className="font-mono text-[11px] text-[var(--admin-muted)]">
                                provider: {t.provider_channel_id}
                              </div>
                            ) : null}
                          </td>
                          <td>
                            {taskStatusLabel(t.status)}
                            <StoredErrorText
                              compact
                              className="mt-1"
                              message={t.error_message}
                              code={t.error_code}
                              params={t.error_params}
                            />
                          </td>
                          <td>
                            {format(t.billing_charged_fen)} / {format(t.billing_estimate_fen)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </AdminDetailTableWrap>
            </AdminDetailSection>

            {detail.source_text ? (
              <AdminDetailSection title="Văn bản nguồn">
                <AdminDetailNote>{detail.source_text}</AdminDetailNote>
              </AdminDetailSection>
            ) : null}
          </>
        ) : null}
      </AdminModal>
    </div>
  );
}
