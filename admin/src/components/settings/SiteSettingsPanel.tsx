import {
  LabeledControl,
  SettingsLoading,
  SettingsPanel,
  SettingsStatusBar,
  SettingsTabShell,
} from "@/components/settings/SettingsPanel";
import { useAdminModelSettings } from "@/hooks/useAdminModelSettings";

/** 站点公网地址与媒体工具路径 */
export function SiteSettingsPanel() {
  const { form, loading, saving, patchField, save } = useAdminModelSettings();

  async function handleSave() {
    if (!form) return;
    await save(
      {
        public_base_url: form.public_base_url,
        ffmpeg_path: form.ffmpeg_path,
        ffprobe_path: form.ffprobe_path,
      },
      "Đã lưu cấu hình trang",
    );
  }

  if (loading || !form) {
    return <SettingsLoading />;
  }

  const hasPublic = Boolean(form.public_base_url?.trim());
  const hasFfmpeg = Boolean(form.ffmpeg_path?.trim());
  const hasFfprobe = Boolean(form.ffprobe_path?.trim());

  return (
    <SettingsTabShell onSave={() => void handleSave()} saving={saving}>
      <SettingsStatusBar
        title="Trạng thái trang và công cụ"
        items={[
          {
            id: "public",
            label: "Địa chỉ công khai",
            ready: hasPublic,
            readyText: "Đã cấu hình",
            pendingText: "Chưa điền",
          },
          {
            id: "ffmpeg",
            label: "ffmpeg",
            ready: hasFfmpeg,
            readyText: form.ffmpeg_path || "Đã cấu hình",
            pendingText: "Dùng PATH mặc định",
          },
          {
            id: "ffprobe",
            label: "ffprobe",
            ready: hasFfprobe,
            readyText: form.ffprobe_path || "Đã cấu hình",
            pendingText: "Dùng PATH mặc định",
          },
        ]}
      />

      <div className="settings-routing-grid">
        <SettingsPanel
          className="settings-panel--compact"
          title="1. Địa chỉ công khai"
          description="Dùng cho callback thanh toán, link chia sẻ và URL OSS trả về"
        >
          <div className="settings-field-grid">
            <LabeledControl
              label="URL công khai của backend"
              hint="Ví dụ: https://cineai.vn"
              className="settings-field-span-full"
            >
              <input
                className="settings-input"
                value={form.public_base_url}
                onChange={(e) => patchField("public_base_url", e.target.value)}
              />
            </LabeledControl>
          </div>
          <p className="settings-panel-footnote">
            Cơ sở dữ liệu, Redis, SECRET_KEY và các cấu hình hạ tầng khác vẫn đặt qua biến môi trường trên máy chủ, không sửa ở trang này.
          </p>
        </SettingsPanel>

        <SettingsPanel
          className="settings-panel--compact"
          title="2. Công cụ media"
          description="Dựng video và trích khung hình cần ffmpeg / ffprobe trên máy chủ"
        >
          <div className="settings-field-grid">
            <LabeledControl label="Đường dẫn ffmpeg">
              <input
                className="settings-input"
                placeholder="ffmpeg"
                value={form.ffmpeg_path}
                onChange={(e) => patchField("ffmpeg_path", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Đường dẫn ffprobe">
              <input
                className="settings-input"
                placeholder="ffprobe"
                value={form.ffprobe_path}
                onChange={(e) => patchField("ffprobe_path", e.target.value)}
              />
            </LabeledControl>
          </div>
        </SettingsPanel>
      </div>
    </SettingsTabShell>
  );
}
