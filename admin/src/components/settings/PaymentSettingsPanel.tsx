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
    return `${prefix}${fen} 分 ≈ ${format(fen)}`;
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
      "支付与汇率已保存",
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
        title="支付就绪状态"
        items={[
          {
            id: "bank",
            label: "银行转账",
            ready: bankReady,
            readyText: "已配置",
            pendingText: "未填收款信息",
          },
          {
            id: "billing",
            label: "Token 计费",
            ready: form.billing_enabled,
            readyText: "已开启",
            pendingText: "已关闭",
          },
          {
            id: "rates",
            label: "模型价目",
            ready: !rates.loadError && (rates.data?.unpriced_models.length ?? 0) === 0,
            readyText: "已覆盖全部模型",
            pendingText: rates.loadError ? "加载失败" : `${rates.data?.unpriced_models.length ?? 0} 个模型未定价`,
          },
          {
            id: "smtp",
            label: "SMTP",
            ready: smtpReady,
            readyText: "已配置",
            pendingText: form.smtp_enabled ? "不完整" : "未启用",
          },
        ]}
      />

      <div className="settings-routing-grid">
        <SettingsPanel
          className="settings-panel--compact"
          title="1. 银行转账收款"
          description="用户充值时展示的收款账户；未填写则定价页提示「充值暂未开放」"
        >
          <div className="settings-field-grid">
            <LabeledControl label="银行名称">
              <input
                className="settings-input"
                placeholder="例如 Vietcombank"
                value={form.topup_bank_name}
                onChange={(e) => patchField("topup_bank_name", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="收款账号">
              <input
                className="settings-input"
                value={form.topup_bank_account}
                onChange={(e) => patchField("topup_bank_account", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="户名">
              <input
                className="settings-input"
                value={form.topup_bank_holder}
                onChange={(e) => patchField("topup_bank_holder", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="银行 BIN" hint="可选；填写后为用户生成 VietQR 转账二维码">
              <input
                className="settings-input"
                placeholder="例如 970436"
                value={form.topup_bank_bin}
                onChange={(e) => patchField("topup_bank_bin", e.target.value)}
              />
            </LabeledControl>
          </div>
          <p className="settings-field-hint mt-2">
            银行 BIN 可在{" "}
            <a className="text-[#409eff] hover:underline" href="https://vietqr.io" target="_blank" rel="noreferrer">
              vietqr.io
            </a>{" "}
            查询；用户转账时需在备注填写商户单号，管理员在「订单流水」核对后点击「确认到账」。
          </p>
        </SettingsPanel>

        <SettingsPanel
          className="settings-panel--compact"
          title="2. 汇率与展示货币"
          description="钱包内部按记账单位（分）核算，界面按汇率折算为 VND / USD 展示"
        >
          <div className="settings-field-grid">
            <LabeledControl label="默认展示货币" hint="用户端与管理端未手动切换时的默认货币">
              <select
                className="settings-select"
                value={form.billing_display_currency}
                onChange={(e) => patchField("billing_display_currency", e.target.value as "VND" | "USD")}
              >
                <option value="VND">VND（越南盾）</option>
                <option value="USD">USD（美元）</option>
              </select>
            </LabeledControl>
            <LabeledControl label="待支付单有效期（小时）" hint="超时未确认的银行转账订单自动关闭">
              <input
                className="settings-input"
                type="number"
                min={1}
                value={form.topup_order_expire_hours}
                onChange={(e) => patchField("topup_order_expire_hours", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="VND 汇率（1 记账元 = ? VND）" hint={`当前：100 分 ≈ ${format(100)}`}>
              <input
                className="settings-input"
                type="number"
                step="1"
                min={1}
                value={form.billing_cny_vnd}
                onChange={(e) => patchField("billing_cny_vnd", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="USD 汇率（1 USD = ? 记账元）" hint="也用于把模型价目（美元）折算为记账单位">
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
            汇率变更只影响之后的展示与新建订单；已建订单保留下单时记录的应付金额与币种。保存后需刷新页面以更新前端缓存的汇率。
          </p>
        </SettingsPanel>
      </div>

      <div className="settings-routing-grid">
        <SettingsPanel
          className="settings-panel--compact"
          title="3. Token 计费"
          description="按模型价目表（美元）折算成本 1:1 扣费，不加价"
        >
          <div className="settings-toggle-row">
            <div>
              <strong>启用 Token 计费</strong>
              <span>关闭后生成不扣余额</span>
            </div>
            <Switch checked={form.billing_enabled} onCheckedChange={(v) => patchField("billing_enabled", v)} />
          </div>
          <div className="settings-field-grid mt-3">
            <LabeledControl label="预估缓冲系数">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                min={1}
                value={form.billing_estimate_buffer}
                onChange={(e) => patchField("billing_estimate_buffer", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="注册赠送（分）" hint={fenHint(form.billing_signup_grant_fen)}>
              <input
                className="settings-input"
                type="number"
                min={0}
                value={form.billing_signup_grant_fen}
                onChange={(e) => patchField("billing_signup_grant_fen", Number(e.target.value))}
              />
            </LabeledControl>
          </div>

          <div className="settings-subsection-title">兜底单价（未匹配价目表时，记账元 / 百万 token）</div>
          <p className="settings-field-hint">1 记账元 = 100 分 ≈ {format(100)}</p>
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
            <LabeledControl label="Seedream 生图">
              <input
                className="settings-input"
                type="number"
                step="0.1"
                value={form.billing_seedream_per_m}
                onChange={(e) => patchField("billing_seedream_per_m", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="TTS 语音">
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

          <div className="settings-subsection-title">估算 token（缺 usage 时）</div>
          <div className="settings-field-grid">
            <LabeledControl label="LLM 估算">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_llm_tokens}
                onChange={(e) => patchField("billing_est_llm_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedream 估算">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_seedream_tokens}
                onChange={(e) => patchField("billing_est_seedream_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="TTS 估算">
              <input
                className="settings-input"
                type="number"
                value={form.billing_est_tts_tokens}
                onChange={(e) => patchField("billing_est_tts_tokens", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="Seedance token/秒">
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
          title="4. 额度告警与 SMTP"
          description="用户消费提醒与平台费用邮件"
        >
          <div className="settings-toggle-row">
            <div>
              <strong>用户弹窗提醒</strong>
              <span>累计扣费达间隔档位时弹一次（跨多档也不连弹）</span>
            </div>
            <Switch
              checked={form.billing_user_alert_enabled}
              onCheckedChange={(v) => patchField("billing_user_alert_enabled", v)}
            />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl
              label="提醒间隔（分）"
              hint={`${fenHint(form.billing_user_alert_interval_fen)}；每笔结算最多弹一次`}
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
              <strong>管理员邮件告警</strong>
              <span>按上游 cost 汇总达阈值后发信</span>
            </div>
            <Switch
              checked={form.billing_admin_cost_alert_enabled}
              onCheckedChange={(v) => patchField("billing_admin_cost_alert_enabled", v)}
            />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl label="告警阈值（分）" hint={fenHint(form.billing_admin_cost_alert_threshold_fen)}>
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
            <LabeledControl label="统计周期">
              <select
                className="settings-select"
                value={form.billing_admin_cost_alert_period}
                onChange={(e) => patchField("billing_admin_cost_alert_period", e.target.value)}
              >
                <option value="daily">每日</option>
                <option value="monthly">每月</option>
                <option value="all_time">累计</option>
              </select>
            </LabeledControl>
            <LabeledControl label="收件邮箱" hint="逗号分隔" className="settings-field-span-full">
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
              <strong>启用 SMTP</strong>
              <span>邮件告警依赖 SMTP</span>
            </div>
            <Switch checked={form.smtp_enabled} onCheckedChange={(v) => patchField("smtp_enabled", v)} />
          </div>
          <div className="settings-field-grid mt-2">
            <LabeledControl label="SMTP 主机">
              <input
                className="settings-input"
                placeholder="smtp.example.com"
                value={form.smtp_host}
                onChange={(e) => patchField("smtp_host", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="端口">
              <input
                className="settings-input"
                type="number"
                min={1}
                value={form.smtp_port}
                onChange={(e) => patchField("smtp_port", Number(e.target.value))}
              />
            </LabeledControl>
            <LabeledControl label="发件人">
              <input
                className="settings-input"
                value={form.smtp_from}
                onChange={(e) => patchField("smtp_from", e.target.value)}
              />
            </LabeledControl>
            <LabeledControl label="用户名">
              <input
                className="settings-input"
                value={form.smtp_user}
                onChange={(e) => patchField("smtp_user", e.target.value)}
              />
            </LabeledControl>
            <SecretField
              label="SMTP 密码"
              value={smtpPasswordInput}
              configured={form.has_smtp_password && !clearSmtpPassword}
              onChange={setSmtpPasswordInput}
              onClear={() => {
                setSmtpPasswordInput("");
                setClearSmtpPassword(true);
              }}
            />
            <LabeledControl label="使用 TLS">
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
          usdCny={rates.data?.usd_cny ?? form.billing_usd_cny}
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
