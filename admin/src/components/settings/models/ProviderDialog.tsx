import { useState } from "react";
import { CircleCheck, CircleX, Loader2, PlugZap } from "lucide-react";
import { toast } from "sonner";
import {
  testProviderConnection,
  type FunctionBindings,
  type FunctionInfo,
  type ProviderPreset,
  type ProviderProtocol,
  type ProviderTestResult,
} from "@/api/routing";
import { AdminConfirmDialog } from "@/components/admin/AdminConfirmDialog";
import { AdminModal } from "@/components/admin/AdminModal";
import { LabeledControl } from "@/components/settings/SettingsPanel";
import { ProviderModelsSection } from "@/components/settings/models/ProviderModelsSection";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  CONNECTION_TEST_HINTS,
  connectionTestLabel,
  draftFromPreset,
  providerDeleteBlocker,
  providerSaveBlockers,
  staticCatalogFor,
  urlOrigin,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

const PROTOCOL_LABELS: Record<ProviderProtocol, string> = {
  openai: "OpenAI (và tương thích OpenAI)",
  ark: "BytePlus ModelArk / Volcengine Ark",
  volc_tts: "BytePlus Seed Speech",
};

type ProviderDialogProps = {
  initial: ProviderDraft;
  presets: ProviderPreset[];
  providers: ProviderDraft[];
  bindingSets: FunctionBindings[];
  catalog: FunctionInfo[];
  onClose: () => void;
  onSave: (draft: ProviderDraft) => Promise<string | null>;
  onDelete: (id: string) => Promise<string | null>;
};

/** Hộp thoại tạo/sửa nhà cung cấp: preset, key, kiểm tra kết nối, model bật, lưu ngay, xoá (có xác nhận) */
export function ProviderDialog({
  initial,
  presets,
  providers,
  bindingSets,
  catalog,
  onClose,
  onSave,
  onDelete,
}: ProviderDialogProps) {
  /*
   * draft: form đang sửa; error: lỗi chặn lưu/xoá hoặc lỗi backend
   * busy: đang lưu/xoá; testing/test: kiểm tra kết nối; confirmDelete: hộp xác nhận xoá
   */
  const [draft, setDraft] = useState<ProviderDraft>(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"save" | "delete" | null>(null);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<ProviderTestResult | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const others = providers.filter((p) => p.id !== initial.id);
  const keySaved = draft.has_api_key && !draft.clear_api_key;

  // Cập nhật một phần form, xoá lỗi và kết quả kiểm tra cũ
  function patch(next: Partial<ProviderDraft>) {
    setDraft((prev) => ({ ...prev, ...next }));
    setError("");
    setTest(null);
  }

  // Đổi preset (chỉ khi tạo mới): điền lại tên / protocol / base URL, giữ key đang nhập
  function applyPreset(presetId: string) {
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;
    const next = draftFromPreset(preset, others.map((o) => o.id));
    setDraft((prev) => ({ ...next, api_key_input: prev.api_key_input }));
    setError("");
    setTest(null);
  }

  // Kiểm tra kết nối bằng key đang nhập, hoặc key đã lưu
  async function runTest() {
    setTesting(true);
    try {
      setTest(
        await testProviderConnection({
          channel_id: draft.is_new || draft.clear_api_key ? null : draft.id,
          protocol: draft.protocol,
          base_url: draft.base_url,
          api_key: draft.api_key_input.trim() || null,
        }),
      );
    } catch (err) {
      setTest({ ok: false, message: err instanceof Error ? err.message : "Không kiểm tra được" });
    } finally {
      setTesting(false);
    }
  }

  // Lưu ngay provider (PATCH toàn bộ danh sách provider)
  async function handleSave() {
    const blockers = providerSaveBlockers(initial, draft, others, bindingSets, catalog);
    if (blockers.length) {
      setError(blockers.join(" "));
      return;
    }
    setBusy("save");
    const err = await onSave(draft);
    setBusy(null);
    if (err) {
      setError(err);
      return;
    }
    toast.success(`Đã lưu nhà cung cấp ${draft.name.trim()}`);
    onClose();
  }

  // Bấm Xoá: chặn nếu đang được gán, không thì hỏi xác nhận
  function askDelete() {
    const blocker = providerDeleteBlocker(initial.id, bindingSets, catalog);
    if (blocker) {
      setError(blocker);
      return;
    }
    setConfirmDelete(true);
  }

  // Xoá sau khi xác nhận
  async function handleDelete() {
    setBusy("delete");
    const err = await onDelete(initial.id);
    setBusy(null);
    setConfirmDelete(false);
    if (err) {
      setError(err);
      return;
    }
    toast.success(`Đã xoá nhà cung cấp ${initial.name}`);
    onClose();
  }

  const hostChanged = !draft.is_new && urlOrigin(initial.base_url) !== urlOrigin(draft.base_url);
  const keyHint = draft.clear_api_key
    ? "Key sẽ bị xoá khi lưu"
    : keySaved && hostChanged && !draft.api_key_input.trim()
      ? "Đã đổi host Base URL: key đã lưu sẽ không được dùng lại, hãy nhập lại API key"
      : keySaved
        ? "Đã lưu key; để trống khi lưu thì giữ nguyên"
        : draft.protocol === "volc_tts"
          ? "Seed Speech: API key mới; để trống nếu đang dùng cặp app id / access key trong .env"
          : undefined;

  return (
    <>
      <AdminModal
        open
        onOpenChange={(open) => {
          if (!open && !busy) onClose();
        }}
        size="lg"
        title={draft.is_new ? "Thêm nhà cung cấp" : `Nhà cung cấp: ${initial.name}`}
        subtitle="Nhà cung cấp lưu ngay khi bấm Lưu. Key được mã hoá khi lưu vào DB."
        footer={
          <>
            {!draft.is_new ? (
              <Button variant="destructive" className="mr-auto" disabled={Boolean(busy)} onClick={askDelete}>
                Xoá nhà cung cấp
              </Button>
            ) : null}
            <Button variant="outline" disabled={Boolean(busy)} onClick={onClose}>
              Huỷ
            </Button>
            <Button disabled={Boolean(busy)} onClick={() => void handleSave()}>
              {busy === "save" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Lưu
            </Button>
          </>
        }
      >
        <div className="settings-field-grid">
          {draft.is_new ? (
            <LabeledControl label="Mẫu nhà cung cấp" className="settings-field-span-full">
              <select
                className="settings-select"
                value={draft.preset_id}
                onChange={(e) => applyPreset(e.target.value)}
              >
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </LabeledControl>
          ) : null}
          <LabeledControl label="Tên hiển thị">
            <input className="settings-input" value={draft.name} onChange={(e) => patch({ name: e.target.value })} />
          </LabeledControl>
          <LabeledControl
            label="ID"
            hint={draft.is_new ? "Chữ thường, số, - hoặc _; không đổi được sau khi lưu" : "Không đổi được"}
          >
            <input
              className="settings-input font-mono"
              value={draft.id}
              readOnly={!draft.is_new}
              onChange={(e) => patch({ id: e.target.value })}
            />
          </LabeledControl>
          <LabeledControl label="Protocol">
            <select
              className="settings-select"
              value={draft.protocol}
              disabled={!draft.is_new}
              onChange={(e) => patch({ protocol: e.target.value as ProviderProtocol, models: [] })}
            >
              {(Object.keys(PROTOCOL_LABELS) as ProviderProtocol[]).map((p) => (
                <option key={p} value={p}>
                  {PROTOCOL_LABELS[p]}
                </option>
              ))}
            </select>
          </LabeledControl>
          <LabeledControl label="Base URL">
            <input
              className="settings-input font-mono"
              value={draft.base_url}
              placeholder="https://…"
              onChange={(e) => patch({ base_url: e.target.value })}
            />
          </LabeledControl>
          <LabeledControl label="API key" hint={keyHint} className="settings-field-span-full">
            <div className="settings-secret-row">
              <input
                type="password"
                className="settings-input"
                autoComplete="new-password"
                placeholder={keySaved ? "Để trống = giữ key đã lưu" : "Dán API key"}
                value={draft.api_key_input}
                onChange={(e) => patch({ api_key_input: e.target.value, clear_api_key: false })}
              />
              {keySaved ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => patch({ clear_api_key: true, api_key_input: "" })}
                >
                  Xoá key
                </Button>
              ) : null}
            </div>
          </LabeledControl>
        </div>

        <div className="settings-toggle-row mt-3">
          <div>
            <strong>Bật nhà cung cấp</strong>
            <span>Tắt thì mọi model của nhà cung cấp này tạm không được dùng; phần gán chức năng vẫn giữ nguyên</span>
          </div>
          <Switch checked={draft.enabled} onCheckedChange={(v) => patch({ enabled: v })} />
        </div>

        <div className="settings-provider-test">
          <Button type="button" size="sm" variant="outline" disabled={testing} onClick={() => void runTest()}>
            {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlugZap className="h-3.5 w-3.5" />}
            Kiểm tra kết nối
          </Button>
          {test ? (
            <span className={cn("settings-provider-test-result", test.ok ? "is-ok" : "is-fail")}>
              {test.ok ? <CircleCheck className="h-3.5 w-3.5" /> : <CircleX className="h-3.5 w-3.5" />}
              {connectionTestLabel(draft.protocol, test)}
            </span>
          ) : null}
        </div>
        <p className="settings-field-hint">{CONNECTION_TEST_HINTS[draft.protocol]}</p>

        <ProviderModelsSection
          draft={draft}
          staticModels={staticCatalogFor(presets, draft)}
          onModelsChange={(models) => patch({ models })}
        />

        {error ? (
          <p className="settings-provider-dialog-error" role="alert">
            {error}
          </p>
        ) : null}
      </AdminModal>

      <AdminConfirmDialog
        open={confirmDelete}
        title={`Xoá nhà cung cấp ${initial.name}?`}
        description="Key và danh sách model của nhà cung cấp sẽ bị xoá. Thao tác này không hoàn tác được."
        confirmLabel="Xoá"
        cancelLabel="Huỷ"
        destructive
        loading={busy === "delete"}
        onOpenChange={setConfirmDelete}
        onConfirm={() => void handleDelete()}
      />
    </>
  );
}
