import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, type AdminDramaEpisode } from "@/api/client";
import {
  AdminDetailMeta,
  AdminDetailSection,
  AdminDetailTableWrap,
} from "@/components/admin/AdminDetailLayout";
import { AdminEntityLink } from "@/components/admin/AdminEntityLink";
import { StoredErrorText } from "@/components/admin/StoredErrorText";
import { Button } from "@/components/ui/button";
import { formatDramaGenerationStatus } from "@/lib/dramaLabels";

/** 漫剧分集详情：含分镜列表 */
export function DramaEpisodeDetailPage() {
  const { episodeId } = useParams<{ episodeId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AdminDramaEpisode | null>(null);
  const [loading, setLoading] = useState(true);
  const id = Number(episodeId);

  useEffect(() => {
    if (!id || Number.isNaN(id)) {
      navigate("/drama-episodes", { replace: true });
      return;
    }
    setLoading(true);
    void api<AdminDramaEpisode>(`/api/admin/drama-episodes/${id}`)
      .then(setDetail)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Không tải được dữ liệu");
        navigate("/drama-episodes", { replace: true });
      })
      .finally(() => setLoading(false));
  }, [id, navigate]);

  if (loading && !detail) {
    return <div className="admin-detail-page-loading">Đang tải…</div>;
  }
  if (!detail) return null;

  return (
    <div className="admin-detail-page">
      <div className="admin-detail-page-toolbar">
        <Button variant="ghost" size="sm" className="admin-detail-back" asChild>
          <Link to="/drama-episodes">
            <ArrowLeft className="h-4 w-4" />
            Về danh sách tập
          </Link>
        </Button>
        <div className="admin-detail-page-heading">
          <h2 className="admin-detail-page-title">
            Tập #{detail.id} · {detail.name}
          </h2>
          <p className="admin-detail-page-sub">
            <AdminEntityLink kind="drama" id={detail.project_id} label={detail.project_title ?? undefined} />
          </p>
        </div>
        <div className="admin-detail-page-actions">
          <Button size="sm" variant="outline" asChild>
            <Link to={`/drama-projects/${detail.project_id}?tab=episodes`}>Mở dự án</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to={`/drama-fragments?episode_id=${detail.id}`}>Tất cả phân cảnh</Link>
          </Button>
        </div>
      </div>

      <AdminDetailSection title="Thông tin cơ bản">
        <AdminDetailMeta
          items={[
            {
              label: "Người dùng",
              value: detail.user_id ? (
                <AdminEntityLink kind="user" id={detail.user_id} label={detail.user_email ?? undefined} />
              ) : (
                "—"
              ),
            },
            {
              label: "Thuộc dự án",
              value: <AdminEntityLink kind="drama" id={detail.project_id} label={detail.project_title ?? undefined} />,
            },
            { label: "Số phân cảnh", value: detail.fragment_count },
            { label: "Kế hoạch phân cảnh", value: detail.fragment_plan_status || "—" },
            ...(detail.fragment_plan_error
              ? [
                  {
                    label: "Lỗi chia phân cảnh",
                    value: <StoredErrorText error={detail.fragment_plan_error} className="text-[#f56c6c]" />,
                    full: true,
                  },
                ]
              : []),
            ...(detail.episode_optimize_error
              ? [
                  {
                    label: "Lỗi AI chỉnh kịch bản",
                    value: <StoredErrorText error={detail.episode_optimize_error} className="text-[#f56c6c]" />,
                    full: true,
                  },
                ]
              : []),
            {
              label: "Cập nhật lúc",
              value: detail.updated_at ? new Date(detail.updated_at).toLocaleString("vi-VN") : "—",
            },
          ]}
        />
      </AdminDetailSection>

      <AdminDetailSection title={`Danh sách phân cảnh (${(detail.fragments ?? []).length})`}>
        <AdminDetailTableWrap>
          <table>
            <thead>
              <tr>
                <th>Thứ tự</th>
                <th>ID</th>
                <th>Nội dung</th>
                <th>Thời lượng</th>
                <th>Trạng thái tạo</th>
                <th>Tư liệu dùng</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(detail.fragments ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="!text-center text-[var(--admin-muted)]">
                    Chưa có phân cảnh
                  </td>
                </tr>
              ) : (
                (detail.fragments ?? []).map((f) => (
                  <tr key={f.id}>
                    <td>{f.sort_order}</td>
                    <td>{f.id}</td>
                    <td className="max-w-[240px] truncate">{f.content || "—"}</td>
                    <td>{f.duration_sec != null ? `${f.duration_sec}s` : "—"}</td>
                    <td className="text-xs text-[var(--admin-muted)]">
                      {formatDramaGenerationStatus(f.generation_status)}
                      <StoredErrorText compact className="mt-1" error={f.generation_error} />
                    </td>
                    <td>{f.asset_ref_count}</td>
                    <td>
                      <Button size="sm" variant="outline" asChild>
                        <Link to={`/drama-fragments/${f.id}`}>Xem</Link>
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </AdminDetailTableWrap>
      </AdminDetailSection>
    </div>
  );
}
