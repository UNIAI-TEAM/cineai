import { useState } from "react";
import { ChevronRight, FileText, Film, Image as ImageIcon, Mic, type LucideIcon } from "lucide-react";
import type { Capability, FunctionBindings, FunctionInfo, ModelBinding } from "@/api/routing";
import { Button } from "@/components/ui/button";
import {
  CAPABILITIES,
  CAPABILITY_HINTS,
  CAPABILITY_LABELS,
  assignedSlotCount,
  bindingKey,
  withOverride,
  withSlot,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";
import { BindingRow } from "@/components/settings/models/BindingRow";
import { ModelPickerDialog } from "@/components/settings/models/ModelPickerDialog";

const CAP_ICONS: Record<Capability, LucideIcon> = { text: FileText, image: ImageIcon, video: Film, audio: Mic };

/** Hàng đang mở hộp chọn model: một slot năng lực hoặc một chức năng ghi đè */
type PickerTarget = { kind: "slot"; capability: Capability } | { kind: "override"; fn: FunctionInfo };

type FunctionBindingsPanelProps = {
  providers: ProviderDraft[];
  bindings: FunctionBindings;
  catalog: FunctionInfo[];
  dirty: boolean;
  errors: string[];
  onChange: (next: FunctionBindings) => void;
};

/** Cột phải tab "Mô hình": 4 slot năng lực + nhóm ghi đè theo chức năng */
export function FunctionBindingsPanel({ providers, bindings, catalog, dirty, errors, onChange }: FunctionBindingsPanelProps) {
  /*
   * picker: hàng đang chọn model (null = đóng)
   * overridesOpen: nhóm "Ghi đè theo chức năng" đang mở (mặc định mở nếu đã có ghi đè)
   */
  const [picker, setPicker] = useState<PickerTarget | null>(null);
  const [overridesOpen, setOverridesOpen] = useState(() => Object.keys(bindings.overrides).length > 0);
  const assigned = assignedSlotCount(bindings);

  // Danh sách binding hiện tại của một hàng
  function listOf(t: PickerTarget): ModelBinding[] {
    return t.kind === "slot" ? bindings.slots[t.capability] ?? [] : bindings.overrides[t.fn.id] ?? [];
  }

  // Ghi danh sách mới cho một hàng
  function apply(t: PickerTarget, list: ModelBinding[]) {
    onChange(t.kind === "slot" ? withSlot(bindings, t.capability, list) : withOverride(bindings, t.fn.id, list));
  }

  // Gỡ một chip khỏi hàng
  function removeFrom(t: PickerTarget, key: string) {
    apply(t, listOf(t).filter((b) => bindingKey(b) !== key));
  }

  return (
    <section className="settings-bindings-panel">
      <header className="settings-bindings-header">
        <div className="min-w-0">
          <h3 className="settings-panel-title">Gán chức năng AI</h3>
          <p className="settings-panel-desc">
            Mỗi chức năng chạy bằng model bạn chọn ở đây. Chọn nhiều model thì các yêu cầu được chia luân phiên.
          </p>
        </div>
        <div className="settings-bindings-progress">
          <span>
            {assigned}/{CAPABILITIES.length} slot đã gán
          </span>
          <div className="settings-progress-track">
            <div
              className="settings-progress-fill"
              style={{ width: `${(assigned / CAPABILITIES.length) * 100}%` }}
            />
          </div>
          {dirty ? <em>Có thay đổi chưa lưu</em> : null}
        </div>
      </header>

      {errors.length > 0 ? (
        <ul className="settings-bindings-errors" role="alert">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}

      <div className="settings-binding-list">
        {CAPABILITIES.map((cap) => {
          const Icon = CAP_ICONS[cap];
          const target: PickerTarget = { kind: "slot", capability: cap };
          const list = listOf(target);
          return (
            <BindingRow
              key={cap}
              icon={<Icon className="h-4 w-4" />}
              title={CAPABILITY_LABELS[cap]}
              description={CAPABILITY_HINTS[cap]}
              capability={cap}
              bindings={list}
              providers={providers}
              emptyLabel="Chưa gán"
              emptyTone="warn"
              onRemove={(key) => removeFrom(target, key)}
              actions={
                <Button size="sm" variant="outline" onClick={() => setPicker(target)}>
                  {list.length ? "Đổi model" : "Chọn model"}
                </Button>
              }
            />
          );
        })}
      </div>

      <div className="settings-overrides">
        <button
          type="button"
          className="settings-overrides-toggle"
          aria-expanded={overridesOpen}
          onClick={() => setOverridesOpen((v) => !v)}
        >
          <ChevronRight className={cn("h-4 w-4 transition-transform", overridesOpen && "rotate-90")} />
          Ghi đè theo chức năng
          <span className="settings-overrides-count">
            {Object.keys(bindings.overrides).length}/{catalog.length}
          </span>
        </button>
        {overridesOpen ? (
          <div className="settings-binding-list">
            {catalog.map((fn) => {
              const Icon = CAP_ICONS[fn.capability];
              const target: PickerTarget = { kind: "override", fn };
              const list = listOf(target);
              return (
                <BindingRow
                  key={fn.id}
                  icon={<Icon className="h-4 w-4" />}
                  title={fn.label}
                  description={fn.description}
                  capability={fn.capability}
                  bindings={list}
                  providers={providers}
                  emptyLabel={`Dùng slot ${CAPABILITY_LABELS[fn.capability]}`}
                  emptyTone="muted"
                  onRemove={(key) => removeFrom(target, key)}
                  actions={
                    <>
                      <Button size="sm" variant="outline" onClick={() => setPicker(target)}>
                        {list.length ? "Đổi" : "Chọn"}
                      </Button>
                      {list.length ? (
                        <Button size="sm" variant="ghost" onClick={() => apply(target, [])}>
                          Bỏ ghi đè
                        </Button>
                      ) : null}
                    </>
                  }
                />
              );
            })}
          </div>
        ) : null}
      </div>

      {picker ? (
        <ModelPickerDialog
          title={
            picker.kind === "slot"
              ? `Chọn model cho slot ${CAPABILITY_LABELS[picker.capability]}`
              : `Ghi đè: ${picker.fn.label}`
          }
          capability={picker.kind === "slot" ? picker.capability : picker.fn.capability}
          providers={providers}
          value={listOf(picker)}
          onApply={(list) => apply(picker, list)}
          onClose={() => setPicker(null)}
        />
      ) : null}
    </section>
  );
}
