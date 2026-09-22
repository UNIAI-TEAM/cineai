import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { Capability, ModelBinding } from "@/api/routing";
import {
  BINDING_PROBLEM_LABELS,
  bindingKey,
  bindingProblem,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";
import { ProviderIcon } from "@/components/settings/models/ProviderIcon";

type BindingRowProps = {
  icon: ReactNode;
  title: string;
  description: string;
  capability: Capability;
  bindings: ModelBinding[];
  providers: ProviderDraft[];
  emptyLabel: string;
  emptyTone: "warn" | "muted";
  actions: ReactNode;
  onRemove: (key: string) => void;
};

/** Một hàng slot/override: tiêu đề, chip "provider · model · ×", badge Chưa gán / N tạm không dùng được */
export function BindingRow({
  icon,
  title,
  description,
  capability,
  bindings,
  providers,
  emptyLabel,
  emptyTone,
  actions,
  onRemove,
}: BindingRowProps) {
  const problems = bindings.map((b) => bindingProblem(b, capability, providers));
  const broken = problems.filter(Boolean).length;
  return (
    <div className="settings-binding-row">
      <div className="settings-binding-icon">{icon}</div>
      <div className="min-w-0">
        <div className="settings-binding-head">
          <strong>{title}</strong>
          {bindings.length === 0 ? (
            <span className={cn("settings-binding-badge", emptyTone === "warn" ? "is-warn" : "is-muted")}>
              {emptyLabel}
            </span>
          ) : null}
          {broken > 0 ? <span className="settings-binding-badge is-muted">{broken} tạm không dùng được</span> : null}
        </div>
        <p className="settings-binding-desc">{description}</p>
        {bindings.length > 0 ? (
          <div className="settings-binding-chips">
            {bindings.map((b, i) => {
              const problem = problems[i];
              const provider = providers.find((p) => p.id === b.channel_id);
              return (
                <span
                  key={bindingKey(b)}
                  className={cn("settings-binding-chip", problem && "is-broken")}
                  title={problem ? BINDING_PROBLEM_LABELS[problem] : undefined}
                >
                  <ProviderIcon provider={provider} className="h-3.5 w-3.5 shrink-0" />
                  <span className="shrink-0">{provider?.name ?? b.channel_id}</span>
                  <span aria-hidden>·</span>
                  <span className="font-mono">{b.model}</span>
                  {b.weight > 1 ? <span className="settings-binding-chip-weight">×{b.weight}</span> : null}
                  <button type="button" aria-label={`Bỏ ${b.model}`} onClick={() => onRemove(bindingKey(b))}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
      <div className="settings-binding-actions">{actions}</div>
    </div>
  );
}
