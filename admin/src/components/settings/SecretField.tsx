import { LabeledControl } from "@/components/settings/SettingsPanel";

type SecretFieldProps = {
  label: string;
  hint?: string;
  value: string;
  configured: boolean;
  placeholder?: string;
  onChange: (value: string) => void;
  onClear?: () => void;
};

// 密钥输入：留空不修改，支持清除已存密钥
export function SecretField({
  label,
  hint,
  value,
  configured,
  placeholder,
  onChange,
  onClear,
}: SecretFieldProps) {
  return (
    <LabeledControl
      label={label}
      hint={hint ?? (configured ? "Đã cấu hình. Để trống khi lưu thì giữ nguyên." : undefined)}
    >
      <div className="admin-secret-field">
        <div className="admin-secret-field-row">
          <input
            type="password"
            className="settings-input is-secret"
            placeholder={placeholder ?? (configured ? "Để trống để giữ nguyên" : "Nhập khoá bí mật")}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            autoComplete="new-password"
          />
          {configured && onClear ? (
            <button type="button" className="admin-btn admin-btn-secondary settings-mini-btn" onClick={onClear}>
              Xoá khoá
            </button>
          ) : null}
        </div>
        {configured ? <span className="admin-secret-status">Đã cấu hình</span> : null}
      </div>
    </LabeledControl>
  );
}
