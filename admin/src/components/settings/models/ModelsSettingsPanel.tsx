import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { SettingsLoading, SettingsTabShell } from "@/components/settings/SettingsPanel";
import { FunctionBindingsPanel } from "@/components/settings/models/FunctionBindingsPanel";
import { ProviderDialog } from "@/components/settings/models/ProviderDialog";
import { ProviderSidebar } from "@/components/settings/models/ProviderSidebar";
import { useRoutingSettings } from "@/hooks/useRoutingSettings";
import {
  BLANK_PRESET,
  draftFromPreset,
  draftFromProvider,
  validateBindingsDraft,
  type ProviderDraft,
} from "@/lib/providerRouting";

/** Tab "Mô hình": cột trái nhà cung cấp (lưu ngay trong hộp thoại), cột phải gán chức năng (lưu bằng nút của trang) */
export function ModelsSettingsPanel() {
  const routing = useRoutingSettings();
  /* dialogDraft: provider đang mở trong hộp thoại (null = đóng) */
  const [dialogDraft, setDialogDraft] = useState<ProviderDraft | null>(null);

  const providers = useMemo(() => (routing.data?.providers ?? []).map(draftFromProvider), [routing.data]);
  const catalog = useMemo(() => routing.data?.function_catalog ?? [], [routing.data]);
  const draftErrors = useMemo(
    () => validateBindingsDraft(routing.bindings, providers, catalog),
    [routing.bindings, providers, catalog],
  );

  if (!routing.loading && routing.loadError) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-red-600">{routing.loadError}</p>
        <Button size="sm" variant="outline" onClick={() => void routing.load()}>
          Thử lại
        </Button>
      </div>
    );
  }

  if (routing.loading || !routing.data) {
    return <SettingsLoading label="Đang tải cấu hình mô hình…" />;
  }

  const presets = routing.data.presets.length ? routing.data.presets : [BLANK_PRESET];
  const savedBindings = routing.data.function_bindings;
  const errors = Array.from(new Set([...draftErrors, ...(routing.saveError ? [routing.saveError] : [])]));

  // Lưu một provider: hook áp thay đổi lên danh sách mới nhất rồi PATCH toàn bộ
  function handleSaveProvider(draft: ProviderDraft): Promise<string | null> {
    return routing.saveProviders({ kind: "save", draft });
  }

  // Xoá một provider: hook bỏ provider khỏi danh sách mới nhất rồi PATCH
  function handleDeleteProvider(id: string): Promise<string | null> {
    return routing.saveProviders({ kind: "delete", id });
  }

  // Nút Lưu của trang: chỉ lưu gán chức năng, chặn khi nháp còn lỗi
  function handleSave() {
    if (draftErrors.length) {
      toast.error("Còn lỗi trong phần gán chức năng, hãy sửa trước khi lưu");
      return;
    }
    void routing.saveBindings();
  }

  return (
    <SettingsTabShell onSave={handleSave} saving={routing.saving} saveLabel="Lưu gán chức năng">
      <div className="settings-providers-layout">
        <ProviderSidebar
          providers={providers}
          onOpen={setDialogDraft}
          onCreate={() => setDialogDraft(draftFromPreset(presets[0], providers.map((p) => p.id)))}
        />
        <FunctionBindingsPanel
          providers={providers}
          bindings={routing.bindings}
          catalog={catalog}
          dirty={routing.dirty}
          errors={errors}
          onChange={routing.setBindings}
        />
      </div>
      {dialogDraft ? (
        <ProviderDialog
          key={`${dialogDraft.id}:${dialogDraft.is_new ? "new" : "edit"}`}
          initial={dialogDraft}
          presets={presets}
          providers={providers}
          bindingSets={[savedBindings, routing.bindings]}
          catalog={catalog}
          onClose={() => setDialogDraft(null)}
          onSave={handleSaveProvider}
          onDelete={handleDeleteProvider}
        />
      ) : null}
    </SettingsTabShell>
  );
}
