import { Crown, ImageOff, Pencil, Trash2 } from "lucide-react";
import type { AdminTemplate } from "@/api/client";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

type TemplateCardProps = {
  template: AdminTemplate;
  /** 分类键 → 展示名 */
  categoryLabels?: Record<string, string>;
  onEdit: (tpl: AdminTemplate) => void;
  onDelete: (id: string) => void;
  onToggleActive: (id: string, value: boolean) => void;
  onTogglePremium: (id: string, value: boolean) => void;
};

// 解析封面 URL（相对 /static 走 Vite 代理）
function coverSrc(url: string): string {
  const trimmed = (url || "").trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

// 模板卡片：封面 + 元信息 + 快捷开关
export function TemplateCard({
  template,
  categoryLabels = {},
  onEdit,
  onDelete,
  onToggleActive,
  onTogglePremium,
}: TemplateCardProps) {
  const src = coverSrc(template.preview_cover);
  const categories = template.category?.length ? template.category : [];
  const vi = template.i18n?.vi;
  const viName = vi?.name?.trim() || "";
  const displayName = viName || template.name;
  const displayDesc = vi?.description?.trim() || template.description;

  return (
    <article
      className={cn(
        "template-card group",
        !template.is_active && "template-card--inactive",
      )}
    >
      <button
        type="button"
        className="template-card-cover"
        onClick={() => onEdit(template)}
        aria-label={`Sửa mẫu ${displayName}`}
      >
        {src ? (
          <img src={src} alt={displayName} loading="lazy" className="template-card-cover-img" />
        ) : (
          <div className="template-card-cover-fallback">
            <ImageOff className="h-8 w-8 text-white/70" />
          </div>
        )}
        <div className="template-card-cover-gradient" />
        <div className="template-card-cover-meta">
          <span className="template-card-sort">#{template.sort_order}</span>
          {template.is_premium ? (
            <span className="template-card-badge template-card-badge--premium">
              <Crown className="h-3 w-3" />
              Premium
            </span>
          ) : null}
          {!template.is_active ? (
            <span className="template-card-badge template-card-badge--off">Đã ẩn</span>
          ) : null}
        </div>
      </button>

      <div className="template-card-body">
        <div className="template-card-head">
          <div className="min-w-0 flex-1">
            <h3 className="template-card-title" title={viName && viName !== template.name ? template.name : undefined}>
              {displayName}
            </h3>
            {viName && viName !== template.name ? (
              <p className="template-card-id">{template.name}</p>
            ) : null}
            <p className="template-card-id">{template.id}</p>
          </div>
          <div className="template-card-actions">
            <button type="button" className="template-card-icon-btn" onClick={() => onEdit(template)} title="Sửa">
              <Pencil className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="template-card-icon-btn template-card-icon-btn--danger"
              onClick={() => onDelete(template.id)}
              title="Xoá"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {displayDesc ? (
          <p className="template-card-desc" title={displayDesc !== template.description ? template.description : undefined}>
            {displayDesc}
          </p>
        ) : (
          <p className="template-card-desc template-card-desc--empty">Chưa có mô tả</p>
        )}

        <div className="template-card-tags">
          {categories.length === 0 ? (
            <span className="template-card-tag">Chưa phân loại</span>
          ) : null}
          {categories.slice(0, 3).map((tag) => (
            <span key={tag} className="template-card-tag" title={tag}>
              {categoryLabels[tag] ?? tag}
            </span>
          ))}
          <span className="template-card-tag template-card-tag--muted">{template.default_ratio}</span>
        </div>

        <div className="template-card-foot">
          <label className="template-card-toggle">
            <span>Hiển thị</span>
            <Switch
              checked={template.is_active}
              onCheckedChange={(v) => onToggleActive(template.id, v)}
            />
          </label>
          <label className="template-card-toggle">
            <span>Premium</span>
            <Switch
              checked={template.is_premium}
              onCheckedChange={(v) => onTogglePremium(template.id, v)}
            />
          </label>
        </div>
      </div>
    </article>
  );
}
