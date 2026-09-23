import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AdminModelSettings } from "@/api/client";

// 加载 / 保存管理端 flat 配置（DB 覆盖 env）
export function useAdminModelSettings() {
  const [form, setForm] = useState<AdminModelSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setForm(await api<AdminModelSettings>("/api/admin/settings/models"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được cấu hình");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function patchField<K extends keyof AdminModelSettings>(key: K, value: AdminModelSettings[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function save(body: Record<string, unknown>, successMessage = "Đã lưu cấu hình") {
    setSaving(true);
    try {
      await api("/api/admin/settings/models", { method: "PATCH", body: JSON.stringify(body) });
      await load();
      toast.success(successMessage);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không lưu được");
    } finally {
      setSaving(false);
    }
  }

  return { form, loading, saving, load, patchField, save };
}
