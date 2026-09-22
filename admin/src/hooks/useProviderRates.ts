import { useCallback, useEffect, useState } from "react";
import { fetchProviderRates, saveProviderRates, type ProviderRateRow, type ProviderRatesOut } from "@/api/providerRates";

/** Tải / sửa nháp / lưu bảng giá provider_rates */
export function useProviderRates() {
  /*
   * data: bản đã lưu (kèm defaults, units, unpriced_models, usd_cny); rows: bản nháp; dirty: nháp khác bản lưu
   * loading / loadError: trạng thái tải; saveError: lỗi 400 tiếng Việt từ backend
   */
  const [data, setData] = useState<ProviderRatesOut | null>(null);
  const [rows, setRowsState] = useState<ProviderRateRow[]>([]);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const res = await fetchProviderRates();
      setData(res);
      setRowsState(res.items);
      setDirty(false);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Không tải được bảng giá");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Sửa nháp
  const setRows = useCallback((next: ProviderRateRow[]) => {
    setRowsState(next);
    setDirty(true);
    setSaveError("");
  }, []);

  // Đưa nháp về bảng mặc định (chưa lưu)
  const resetToDefaults = useCallback(() => {
    if (data) setRows(data.defaults);
  }, [data, setRows]);

  // Lưu nháp; true = thành công
  const save = useCallback(async (): Promise<boolean> => {
    try {
      const res = await saveProviderRates(rows);
      setData(res);
      setRowsState(res.items);
      setDirty(false);
      setSaveError("");
      return true;
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Không lưu được bảng giá");
      return false;
    }
  }, [rows]);

  return { data, rows, dirty, loading, loadError, saveError, load, setRows, resetToDefaults, save };
}
