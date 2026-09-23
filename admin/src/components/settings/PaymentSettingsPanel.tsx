import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  LabeledControl,
  SettingsLoading,
  SettingsPanel,
  SettingsStatusBar,
  SettingsTabShell,
} from "@/components/settings/SettingsPanel";
import { SecretField } from "@/components/settings/SecretField";
import { Switch } from "@/components/ui/switch";
import { useAdminModelSettings } from "@/hooks/useAdminModelSettings";
import { useProviderRates } from "@/hooks/useProviderRates";
import { useCurrency } from "@/lib/currency";
import { ProviderRatesEditor } from "@/components/settings/ProviderRatesEditor";

// 银行转账收款、汇率与展示货币、Token 计费与告警配置
export function PaymentSettingsPanel() {
  const { form, loading, saving, patchField, save } = useAdminModelSettings();
  const { format } = useCurrency();
  const [smtpPasswordInput, setSmtpPasswordInput] = useState("");
  const [clearSmtpPassword, setClearSmtpPassword] = useState(false);
  // rates: bảng giá provider_rates (mục 5), lưu riêng qua PUT model-rates
  const rates = useProviderRates();

  // 银行转账收款就绪：银行名 / 账号 / 户名齐全（BIN 可选）
  const bankReady = useMemo(() => {
    if (!form) return false;
    return Boolean(
      form.topup_bank_name?.trim() && form.topup_bank_account?.trim() && form.topup_bank_holder?.trim(),
    );
  }, [form]);

  const smtpReady = useMemo(() => {
    if (!form?.smtp_enabled) return false;
    const hasPass = (form.has_smtp_password && !clearSmtpPassword) || smtpPasswordInput.trim().length > 0;
    return Boolean(form.smtp_host && form.smtp_from && hasPass);
  }, [form, clearSmtpPassword, smtpPasswordInput]);

  // 记账单位（分）字段的换算提示
  function fenHint(fen: number, prefix = ""): string {
    return `${prefix}${fen} fen ≈ ${format(fen)}`;
  }

  async function handleSave() {
    if (!form) return;
    // Bảng giá lưu riêng (PUT model-rates); lỗi thì dừng để admin sửa trước
    if (rates.dirty && !(await rates.save())) {
      toast.error("Bảng giá model chưa lưu được, xem lỗi ở mục 5");
      return;
    }
    await save(
      {
        billing_display_currency: form.billing_display_currency,
        billing_cny_vnd: form.billing_cny_vnd,
        billing_usd_cny: form.billing_usd_cny,
        topup_bank_name: form.topup_bank_name,
        topup_bank_account: form.topup_bank_account,
        topup_bank_holder: form.topup_bank_holder,
        topup_bank_bin: form.topup_bank_bin,
        topup_order_expire_hours: form.topup_order_expire_hours,
        billing_enabled: form.billing_enabled,
        billing_markup: 1.0,
        billing_estimate_buffer: form.billing_estimate_buffer,
        billing_seedance_video0: form.billing_seedance_video0,
        billing_seedance_video1: form.billing_seedance_video1,
        billing_llm_per_m: form.billing_llm_per_m,
        billing_seedream_per_m: form.billing_seedream_per_m,
        billing_tts_per_m: form.billing_tts_per_m,
        billing_est_llm_tokens: form.billing_est_llm_tokens,
        billing_est_seedream_tokens: form.billing_est_seedream_tokens,
        billing_est_tts_tokens: form.billing_est_tts_tokens,
        billing_est_seedance_tokens_per_sec: form.billing_est_seedance_tokens_per_sec,
        billing_signup_grant_fen: form.billing_signup_grant_fen,
        billing_user_alert_enabled: form.billing_user_alert_enabled,
        billing_user_alert_interval_fen: form.billing_user_alert_interval_fen,
        billing_admin_cost_alert_enabled: form.billing_admin_cost_alert_enabled,
        billing_admin_cost_alert_threshold_fen: form.billing_admin_cost_alert_threshold_fen,
        billing_admin_cost_alert_emails: form.billing_admin_cost_alert_emails,
        billing_admin_cost_alert_period: form.billing_admin_cost_alert_period,
        smtp_enabled: form.smtp_enabled,
        smtp_host: form.smtp_host,
        smtp_port: form.smtp_port,
        smtp_user: form.smtp_user,
        smtp_password: smtpPasswordInput.trim() || undefined,
        clear_smtp_password: clearSmtpPassword,
        smtp_from: form.smtp_from,
        smtp_use_tls: form.smtp_use_tls,
      },
      "Đã lưu thanh toán và tỷ giá",
    );
    setSmtpPasswordInput("");
    setClearSmtpPassword(false);
  }

  if (loading || !form) {
    return <SettingsLoading />;
  }

  return (
    <SettingsTabShell onSave={() => void handleSave()} saving={saving || rates.saving}>
      <SettingsStatusBar
        title="Tình trạng thanh toán"
        items={[
          {
            id: "bank",
            label: "Chuyển khoản ngân hàng",
            ready: bankReady,
            readyText: "Đã cấu hình",
            pendingText: "Chưa nhập tài khoản nhận tiền",
          },
          {
            id: "billing",
            label: "Tính phí theo token",
            ready: form.billing_enabled,
            readyText: "Đang bật",
            pendingText: "Đang tắt",
          },
          {
            id: "rates",
            label: "Bảng giá mô hình",
            ready: !rates.loadError && (rates.data?.unpriced_models.length ?? 0) === 0,
            readyText: "Đã có giá cho mọi mô hình",
            pendingText: rates.loadError ? "Không tải được" : `${rates.data?.unpriced_models.length ?? 0} mô hình chưa có giá`,
          },
          {
            id: "smtp",
            label: "SMTP",
            ready: smtpReady,
            readyText: "Đã cấu hình",
            pendingText: form.smtp_enabled ? "Chưa đủ thông tin" : "Chưa bật",
          },
        ]}
      />

      <div className="settings-routing-grid">
        <SettingsPanel
          className="settings-panel--compact"
          title="1. Nhận tiền qua chuyển khoản"
          description="Tài khoản hiện cho người dùng khi nạp tiền. Để trống thì trang bảng giá báo “Chưa mở nạp tiền”"
        >
          <div className="settings-field-grid">
            <LabeledControl label="Tên ngân hàng">
              <input
                className="settings-input"
                placeholder="Vd. Vietcombank"
                value={form.topup_bank_name}
                onChange={(e) => patchField("topup_bank_name", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Số tài khoản">
              <input
                className="settings-input"
                value={form.topup_bank_account}
                onChange={(e) => patchField("topup_bank_account", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Chủ tài khoản">
              <input
                className="settings-input"
                value={form.topup_bank_holder}
                onChange={(e) => patchField("topup_bank_holder", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Mã BIN ngân hàng" hint="Không bắt buộc. Có mã BIN thì người dùng được tạo mã VietQR để chuyển khoản">
              <input
                className="settings-input"
                placeholder="Vd. 970436"
                value={form.topup_bank_bin}
                onChange={(e) => patchField("topup_bank_bin", e.target.value)}
              />
            </LabeledControl>
          </div>
          <p className="settings-field-hint mt-2">
            Tra mã BIN ngân hàng tại{" "}
            <a className="text-[#409eff] hover:underline" href="https://vietqr.io" target="_blank" rel="noreferrer">
              vietqr.io
            </a>
            . Khi chuyển khoản, người dùng phải ghi mã đơn vào nội dung; quản trị viên đối chiếu ở mục “Đơn nạp tiền” rồi bấm “Xác nhận đã nhận tiền”.
          </p>
        </SettingsPanel>

        <SettingsPanel
          className="settings-panel--compact"
          title="2. Tỷ giá và tiền tệ hiển thị"
          description="Ví tính nội bộ theo đơn vị ghi sổ (fen), giao diện quy đổi sang VND / USD theo tỷ giá"
        >
          <div className="settings-field-grid">
            <LabeledControl label="Tiền tệ hiển thị mặc định" hint="Dùng cho trang người dùng và trang quản trị khi chưa tự chọn tiền tệ">
              <select
                className="settings-select"
                value={form.billing_display_currency}
                onChange={(e) => patchField("billing_display_currency", e.target.value as "VND" | "USD")}
              >
                <option value="VND">VND (Việt Nam đồng)</option>
                <option value="USD">USD (đô la Mỹ)</option>
              </select>
            </LabeledControl>
            <LabeledControl label="Hạn đơn chờ thanh toán (giờ)" hint="Đơn chuyển khoản quá hạn chưa xác nhận sẽ tự đóng">
              <input
                className="settings-input"
                type="number"
                min={1}
                value={form.topup_order_expire_hours}
                onChange={(e) => patchField("topup_order_expire_hours", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Tỷ giá VND (1 đơn vị ghi sổ = ? VND)" hint={`Hiện tại: 100 fen ≈ ${format(100)}`}>
              <input
                className="settings-input"
                type="number"
                step="1"
                min={1}
                value={form.billing_cny_vnd}
                onChange={(e) => patchField("billing_cny_vnd", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Tỷ giá USD (1 USD = ? đơn vị ghi sổ)" hint="Cũng dùng để quy đổi bảng giá mô hình (USD) sang đơn vị ghi sổ">
              <input
                className="settings-input"
                type="number"
                step="0.01"
                min={0.01}
                value={form.billing_usd_cny}
                onChange={(e) => patchField("billing_usd_cny", Number(e.target.value))}
              />
            </LabeledControl>
          </div>
          <p className="settings-field-hint mt-2">
            Đổi tỷ giá chỉ ảnh hưởng đến hiển thị và đơn tạo sau đó; đơn đã tạo giữ số tiền cần trả và loại tiền lúc đặt. Sau khi lưu, tải lại trang để cập nhật tỷ giá đang lưu trên trình duyệt.
          </p>
        </SettingsPanel>
      </div>

      <div className="settings-routing-grid">
        <SettingsPanel
          className="settings-panel--compact"
          title="3. Tính phí theo token"
          description="Trừ tiền đúng bằng chi phí quy đổi từ bảng giá mô hình (USD), không cộng thêm"
        >
          <div className="settings-toggle-row">
            <div>
              <strong>Bật tính phí theo token</strong>
              <span>Tắt thì tạo nội dung không trừ số dư</span>
            </div>
            <Switch checked={form.billing_enabled} onCheckedChange={(v) => patchField("billing_enabled", v)} />
          </div>
          <div className="settings-field-grid mt-3">
            <LabeledControl label="Hệ số dự phòng khi ước tính">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                min={1}
                value={form.billing_estimate_buffer}
                onChange={(e) => patchField("billing_estimate_buffer", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Tặng khi đăng ký (fen)" hint={fenHint(form.billing_signup_grant_fen)}>
              <input
                className="settings-input"
                type="number"
                min={0}
                value={form.billing_signup_grant_fen}
                onChange={(e) => patchField("billing_signup_grant_fen", Number(e.target.value))}
              />
            </LabeledControl>
          </div>

          <div className="settings-subsection-title">Đơn giá dự phòng (khi không khớp bảng giá, đơn vị ghi sổ / 1 triệu token)</div>
          <p className="settings-field-hint">1 đơn vị ghi sổ = 100 fen ≈ {format(100)}</p>
          <div className="settings-field-grid">
            <LabeledControl label="LLM">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_llm_per_m}
                onChange={(e) => patchField("billing_llm_per_m", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedream tạo ảnh">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_seedream_per_m}
                onChange={(e) => patchField("billing_seedream_per_m", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="TTS giọng đọc">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_tts_per_m}
                onChange={(e) => patchField("billing_tts_per_m", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedance video0">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_seedance_video0}
                onChange={(e) => patchField("billing_seedance_video0", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedance video1">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_seedance_video1}
                onChange={(e) => patchField("billing_seedance_video1", Number(e.target.value))}
              />
            </LabeledControl>
          </div>

          <div className="settings-subsection-title">Token ước tính (khi thiếu usage)</div>
          <div className="settings-field-grid">
            <LabeledControl label="LLM ước tính">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_llm_tokens}
                onChange={(e) => patchField("billing_est_llm_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedream ước tính">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_seedream_tokens}
                onChange={(e) => patchField("billing_est_seedream_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="TTS ước tính">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_tts_tokens}
                onChange={(e) => patchField("billing_est_tts_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedance token/giây">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_seedance_tokens_per_sec}
                onChange={(e) => patchField("billing_est_seedance_tokens_per_sec", Number(e.target.value))}
              />
            </LabeledControl>
          </div>
        </SettingsPanel>

        <SettingsPanel
          className="settings-panel--compact"
          title="4. Cảnh báo chi tiêu và SMTP"
          description="Nhắc người dùng về chi tiêu và gửi email chi phí nền tảng"
        >
          <div className="settings-toggle-row">
            <div>
              <strong>Hiện thông báo cho người dùng</strong>
              <span>Hiện một lần khi tổng tiền đã trừ chạm mỗi mốc (vượt nhiều mốc cùng lúc vẫn chỉ hiện một lần)</span>
            </div>
            <Switch
              checked={form.billing_user_alert_enabled}
              onCheckedChange={(v) => patchField("billing_user_alert_enabled", v)}
            />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl
              label="Khoảng cách mốc nhắc (fen)"
              hint={`${fenHint(form.billing_user_alert_interval_fen)}; mỗi lần quyết toán hiện tối đa một lần`}
            >
              <input
                className="settings-input"
                type="number"
                min={1}
                value={form.billing_user_alert_interval_fen}
                onChange={(e) => patchField("billing_user_alert_interval_fen", Number(e.target.value))}
              />
            </LabeledControl>
          </div>

          <div className="settings-toggle-row mt-3">
            <div>
              <strong>Email cảnh báo cho quản trị viên</strong>
              <span>Gửi email khi tổng giá gốc nhà cung cấp chạm ngưỡng</span>
            </div>
            <Switch
              checked={form.billing_admin_cost_alert_enabled}
              onCheckedChange={(v) => patchField("billing_admin_cost_alert_enabled", v)}
            />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl label="Ngưỡng cảnh báo (fen)" hint={fenHint(form.billing_admin_cost_alert_threshold_fen)}>
              <input
                className="settings-input"
                type="number"
                min={0}
                value={form.billing_admin_cost_alert_threshold_fen}
                onChange={(e) =>
                  patchField("billing_admin_cost_alert_threshold_fen", Number(e.target.value))
                }
              />
            </LabeledControl>
            <LabeledControl label="Chu kỳ tính">
              <select
                className="settings-select"
                value={form.billing_admin_cost_alert_period}
                onChange={(e) => patchField("billing_admin_cost_alert_period", e.target.value)}
              >
                <option value="daily">Hằng ngày</option>
                <option value="monthly">Hằng tháng</option>
                <option value="all_time">Cộng dồn</option>
              </select>
            </LabeledControl>
            <LabeledControl label="Email nhận" hint="Cách nhau bằng dấu phẩy" className="settings-field-span-full">
              <input
                className="settings-input"
                placeholder="admin@example.com"
                value={form.billing_admin_cost_alert_emails}
                onChange={(e) => patchField("billing_admin_cost_alert_emails", e.target.value)}
              />
            </LabeledControl>
          </div>

          <div className="settings-toggle-row mt-3">
            <div>
              <strong>Bật SMTP</strong>
              <span>Email cảnh báo cần SMTP để gửi</span>
            </div>
            <Switch checked={form.smtp_enabled} onCheckedChange={(v) => patchField("smtp_enabled", v)} />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl label="Máy chủ SMTP">
              <input
                className="settings-input"
                placeholder="smtp.example.com"
                value={form.smtp_host}
                onChange={(e) => patchField("smtp_host", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Cổng">
              <input
                className="settings-input"
                type="number"
                min={1}
                value={form.smtp_port}
                onChange={(e) => patchField("smtp_port", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Người gửi">
              <input
                className="settings-input"
                value={form.smtp_from}
                onChange={(e) => patchField("smtp_from", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="Tên đăng nhập">
              <input
                className="settings-input"
                value={form.smtp_user}
                onChange={(e) => patchField("smtp_user", e.target.value)}
              />
            </LabeledControl>
            <SecretField
              label="Mật khẩu SMTP"
              value={smtpPasswordInput}
              configured={form.has_smtp_password && !clearSmtpPassword}
              onChange={setSmtpPasswordInput}
              onClear={() => {
                setSmtpPasswordInput("");
                setClearSmtpPassword(true);
              }}
            />
            <LabeledControl label="Dùng TLS">
              <div className="settings-inline-switch">
                <Switch checked={form.smtp_use_tls} onCheckedChange={(v) => patchField("smtp_use_tls", v)} />
              </div>
            </LabeledControl>
          </div>
        </SettingsPanel>
      </div>

      <SettingsPanel
        className="settings-panel--compact"
        title="5. Bảng giá model (USD)"
        description="Giá chính thức của từng nhà cung cấp; dùng cho tạm giữ trước và quyết toán. Lưu bằng nút Lưu phía trên."
      >
        <ProviderRatesEditor
          rows={rates.rows}
          units={rates.data?.units ?? []}
          unpriced={rates.data?.unpriced_models ?? []}
          usdCny={form.billing_usd_cny > 0 ? form.billing_usd_cny : (rates.data?.usd_cny ?? 0)}
          loading={rates.loading}
          loadError={rates.loadError}
          saveError={rates.saveError}
          onChange={rates.setRows}
          onReset={rates.resetToDefaults}
          onReload={() => void rates.load()}
        />
      </SettingsPanel>
    </SettingsTabShell>
  );
}
