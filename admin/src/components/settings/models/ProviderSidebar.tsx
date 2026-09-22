import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProviderIcon } from "@/components/settings/models/ProviderIcon";
import { PROVIDER_STATUS_LABELS, draftHasKey, providerStatus, type ProviderDraft } from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ProviderSidebarProps = {
  providers: ProviderDraft[];
  onOpen: (p: ProviderDraft) => void;
  onCreate: () => void;
};

/** Cột trái: danh sách nhà cung cấp (icon, tên, "1 key"/"Chưa có key", chấm trạng thái) và nút thêm */
export function ProviderSidebar({ providers, onOpen, onCreate }: ProviderSidebarProps) {
  return (
    <aside className="settings-provider-sidebar">
      <div className="settings-provider-sidebar-head">
        <h3 className="settings-panel-title">Nhà cung cấp</h3>
        <span className="settings-panel-desc">{providers.length} nhà cung cấp</span>
      </div>
      {providers.length === 0 ? (
        <p className="settings-empty-hint">Chưa có nhà cung cấp nào. Thêm OpenAI hoặc BytePlus để bắt đầu.</p>
      ) : null}
      <ul className="settings-provider-list">
        {providers.map((p) => {
          const status = providerStatus(p);
          return (
            <li key={p.id}>
              <button type="button" className="settings-provider-item" onClick={() => onOpen(p)}>
                <span className="settings-provider-icon">
                  <ProviderIcon provider={p} className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-[13px]">{p.name}</strong>
                  <span className="settings-provider-sub">
                    {draftHasKey(p) ? "1 key" : "Chưa có key"} · {p.models.length} model
                  </span>
                </span>
                <span
                  className={cn("settings-provider-dot", `is-${status}`)}
                  title={PROVIDER_STATUS_LABELS[status]}
                  aria-label={PROVIDER_STATUS_LABELS[status]}
                />
              </button>
            </li>
          );
        })}
      </ul>
      <Button variant="outline" size="sm" className="w-full" onClick={onCreate}>
        <Plus className="h-4 w-4" />
        Thêm nhà cung cấp
      </Button>
    </aside>
  );
}
