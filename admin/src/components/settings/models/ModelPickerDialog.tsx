import { useMemo, useState } from "react";
import type { Capability, ModelBinding } from "@/api/routing";
import { AdminModal } from "@/components/admin/AdminModal";
import { Button } from "@/components/ui/button";
import {
  BINDING_WEIGHT_MAX,
  BINDING_WEIGHT_MIN,
  CAPABILITY_LABELS,
  PROVIDER_STATUS_LABELS,
  bindingKey,
  modelOptionsFor,
  setBindingWeight,
  toggleBinding,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ModelPickerDialogProps = {
  title: string;
  capability: Capability;
  providers: ProviderDraft[];
  value: ModelBinding[];
  onApply: (list: ModelBinding[]) => void;
  onClose: () => void;
};

/** Hộp chọn nhiều model đúng năng lực (từ mọi provider) và đặt tỉ lệ chia luân phiên */
export function ModelPickerDialog({ title, capability, providers, value, onApply, onClose }: ModelPickerDialogProps) {
  /*
   * selected: danh sách binding đang chọn (khởi tạo từ value lúc mở)
   * query: ô tìm theo provider / model
   */
  const [selected, setSelected] = useState<ModelBinding[]>(value);
  const [query, setQuery] = useState("");

  const options = useMemo(() => modelOptionsFor(providers, capability), [providers, capability]);
  const q = query.trim().toLowerCase();
  const visible = options.filter((o) => !q || `${o.channel_name} ${o.model}`.toLowerCase().includes(q));
  const selectedByKey = new Map(selected.map((b) => [bindingKey(b), b]));
  const optionKeys = new Set(options.map((o) => bindingKey(o)));
  const orphans = selected.filter((b) => !optionKeys.has(bindingKey(b)));
  const capLabel = CAPABILITY_LABELS[capability].toLowerCase();

  return (
    <AdminModal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      size="lg"
      title={title}
      subtitle="Tick một hoặc nhiều model. Chọn nhiều thì các yêu cầu được chia luân phiên theo tỉ lệ."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            onClick={() => {
              onApply(selected);
              onClose();
            }}
          >
            Áp dụng ({selected.length})
          </Button>
        </>
      }
    >
      <input
        className="settings-input"
        aria-label="Tìm theo provider hoặc model"
        placeholder="Tìm theo provider hoặc model"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {options.length === 0 ? (
        <p className="settings-empty-hint">
          Chưa có model {capLabel} nào được bật. Mở một provider ở cột trái và tick model trước.
        </p>
      ) : null}
      <div className="settings-model-catalog">
        {visible.map((o) => {
          const key = bindingKey(o);
          const current = selectedByKey.get(key);
          return (
            <div key={key} className={cn("settings-picker-row", current && "is-checked")}>
              <label className="settings-model-option min-w-0 flex-1">
                <input
                  type="checkbox"
                  checked={Boolean(current)}
                  onChange={() => setSelected((prev) => toggleBinding(prev, o))}
                />
                <span className="min-w-0">
                  <span className="block truncate font-mono text-xs">{o.model}</span>
                  <span className="settings-picker-provider">
                    {o.channel_name}
                    {o.status !== "ready" ? ` · ${PROVIDER_STATUS_LABELS[o.status]}` : ""}
                  </span>
                </span>
              </label>
              {current ? (
                <label className="settings-weight-field">
                  <span>Tỉ lệ</span>
                  <input
                    type="number"
                    min={BINDING_WEIGHT_MIN}
                    max={BINDING_WEIGHT_MAX}
                    aria-label={`Tỉ lệ chia luân phiên cho ${o.model}`}
                    className="settings-input settings-weight-input"
                    value={current.weight}
                    onChange={(e) => setSelected((prev) => setBindingWeight(prev, key, Number(e.target.value)))}
                  />
                </label>
              ) : null}
            </div>
          );
        })}
        {orphans.map((b) => (
          <div key={bindingKey(b)} className="settings-picker-row is-checked">
            <label className="settings-model-option min-w-0 flex-1">
              <input type="checkbox" checked onChange={() => setSelected((prev) => toggleBinding(prev, b))} />
              <span className="min-w-0">
                <span className="block truncate font-mono text-xs">{b.model}</span>
                <span className="settings-picker-provider">{b.channel_id} · không còn được bật, bỏ tick để gỡ</span>
              </span>
            </label>
          </div>
        ))}
      </div>
    </AdminModal>
  );
}
