import { useMemo, useState } from "react";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { listProviderModels, type Capability, type CatalogModel } from "@/api/routing";
import { Button } from "@/components/ui/button";
import {
  CAPABILITIES,
  CAPABILITY_LABELS,
  mergeModelIds,
  modelCapability,
  normalizeModelName,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ProviderModelsSectionProps = {
  draft: ProviderDraft;
  staticModels: CatalogModel[];
  onModelsChange: (models: string[]) => void;
};

/** Phần "Model bật": openai tải danh sách từ provider, ark/volc_tts dùng danh sách tĩnh; luôn thêm ID thủ công được */
export function ProviderModelsSection({ draft, staticModels, onModelsChange }: ProviderModelsSectionProps) {
  /*
   * remote: danh sách tải từ provider (openai); loading/error: trạng thái tải
   * query/capFilter: lọc theo tên và năng lực; manual: ô nhập ID thủ công
   */
  const [remote, setRemote] = useState<CatalogModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [capFilter, setCapFilter] = useState<Capability | "all">("all");
  const [manual, setManual] = useState("");

  const enabled = useMemo(() => new Set(draft.models.map(normalizeModelName)), [draft.models]);

  // Gộp danh mục (tải về hoặc tĩnh) với model đã bật nhưng không có trong danh mục (ID thủ công)
  const items = useMemo(() => {
    const base = draft.protocol === "openai" ? remote : staticModels;
    const known = new Set(base.map((m) => normalizeModelName(m.id)));
    const extra = draft.models.filter((m) => !known.has(normalizeModelName(m))).map((id) => ({ id, label: id }));
    return [...base, ...extra];
  }, [draft.protocol, draft.models, remote, staticModels]);

  const q = query.trim().toLowerCase();
  const visible = items.filter((m) => {
    const cap = modelCapability(draft.protocol, m.id);
    if (capFilter !== "all" && cap !== capFilter) return false;
    return !q || `${m.id} ${m.label ?? ""}`.toLowerCase().includes(q);
  });

  // Tải danh sách model từ provider (dùng key đang nhập, hoặc key đã lưu nếu provider đã có)
  async function fetchRemote() {
    setLoading(true);
    setError("");
    try {
      const models = await listProviderModels({
        channel_id: draft.is_new || draft.clear_api_key ? null : draft.id,
        protocol: draft.protocol,
        base_url: draft.base_url,
        api_key: draft.api_key_input.trim() || null,
      });
      setRemote(models);
      if (models.length === 0) setError("Nhà cung cấp không trả model nào");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách model");
    } finally {
      setLoading(false);
    }
  }

  // Bật/tắt một model
  function toggle(id: string) {
    const key = normalizeModelName(id);
    onModelsChange(
      enabled.has(key) ? draft.models.filter((m) => normalizeModelName(m) !== key) : mergeModelIds(draft.models, [id]),
    );
  }

  // Thêm ID thủ công (vd. endpoint ep-…)
  function addManual() {
    const id = manual.trim();
    if (!id) return;
    onModelsChange(mergeModelIds(draft.models, [id]));
    setManual("");
  }

  return (
    <div className="settings-provider-models">
      <div className="settings-provider-models-head">
        <strong>Model bật</strong>
        <span className="settings-model-count">Đã bật {draft.models.length} model</span>
        {draft.protocol === "openai" ? (
          <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void fetchRemote()}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Tải danh sách
          </Button>
        ) : null}
      </div>
      {error ? <p className="settings-provider-models-error">{error}</p> : null}

      <div className="settings-model-cap-row">
        {(["all", ...CAPABILITIES] as const).map((cap) => (
          <button
            key={cap}
            type="button"
            className={cn("settings-model-cap-chip", capFilter === cap && "is-active")}
            onClick={() => setCapFilter(cap)}
          >
            {cap === "all" ? "Tất cả" : CAPABILITY_LABELS[cap]}
          </button>
        ))}
      </div>
      <div className="settings-model-search">
        <input
          className="settings-input"
          placeholder="Tìm model"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="settings-model-catalog">
        {visible.length === 0 ? (
          <p className="settings-empty-hint">
            {draft.protocol === "openai" && remote.length === 0
              ? "Bấm “Tải danh sách” để lấy model từ nhà cung cấp, hoặc thêm ID thủ công bên dưới."
              : "Không có model khớp bộ lọc."}
          </p>
        ) : null}
        {visible.map((m) => {
          const cap = modelCapability(draft.protocol, m.id);
          const checked = enabled.has(normalizeModelName(m.id));
          return (
            <label key={m.id} className={cn("settings-model-option", checked && "is-checked")}>
              <input type="checkbox" checked={checked} onChange={() => toggle(m.id)} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-xs">{m.id}</span>
                {m.label && m.label !== m.id ? <span className="settings-picker-provider">{m.label}</span> : null}
              </span>
              <span className={cn("settings-cap-tag", `is-${cap}`)}>{CAPABILITY_LABELS[cap]}</span>
            </label>
          );
        })}
      </div>

      <div className="settings-model-manual">
        <input
          className="settings-input"
          placeholder="Thêm ID thủ công, vd. ep-20260923-abc"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addManual();
            }
          }}
        />
        <Button type="button" size="sm" variant="outline" onClick={addManual}>
          <Plus className="h-3.5 w-3.5" />
          Thêm
        </Button>
      </div>
    </div>
  );
}
