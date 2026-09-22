import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  fetchRoutingSettings,
  saveRoutingSettings,
  type AdminRoutingSettings,
  type FunctionBindings,
  type ProviderPatchItem,
} from "@/api/routing";

/** Tải cấu hình routing; giữ bản nháp gán chức năng; lưu provider và gán chức năng tách riêng */
export function useRoutingSettings() {
  /*
   * data: cấu hình đã lưu; bindings: bản nháp gán chức năng; dirty: nháp khác bản đã lưu
   * loading / saving: trạng thái tải / lưu gán chức năng; saveError: lỗi lưu gần nhất (tiếng Việt từ backend)
   */
  const [data, setData] = useState<AdminRoutingSettings | null>(null);
  const [bindings, setBindingsState] = useState<FunctionBindings>({ slots: {}, overrides: {} });
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchRoutingSettings();
      setData(res);
      setBindingsState(res.function_bindings);
      setDirty(false);
      setSaveError("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không tải được cấu hình mô hình");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Sửa nháp gán chức năng
  const setBindings = useCallback((next: FunctionBindings) => {
    setBindingsState(next);
    setDirty(true);
    setSaveError("");
  }, []);

  // Lưu gán chức năng (nút Lưu chung của trang)
  const saveBindings = useCallback(async () => {
    setSaving(true);
    setSaveError("");
    try {
      const res = await saveRoutingSettings({ function_bindings: bindings });
      setData(res.settings);
      setBindingsState(res.settings.function_bindings);
      setDirty(false);
      toast.success("Đã lưu gán chức năng");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Không lưu được gán chức năng");
    } finally {
      setSaving(false);
    }
  }, [bindings]);

  // Lưu toàn bộ danh sách provider (từ hộp thoại); giữ nháp gán chức năng nếu đang sửa dở
  const saveProviders = useCallback(
    async (providers: ProviderPatchItem[]): Promise<string | null> => {
      try {
        const res = await saveRoutingSettings({ providers });
        setData(res.settings);
        if (!dirty) setBindingsState(res.settings.function_bindings);
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : "Không lưu được nhà cung cấp";
      }
    },
    [dirty],
  );

  return { data, bindings, dirty, loading, saving, saveError, load, setBindings, saveBindings, saveProviders };
}
