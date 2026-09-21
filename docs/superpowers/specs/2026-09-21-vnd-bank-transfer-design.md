# 设计：去人民币化与银行转账充值

日期：2026-09-21　状态：已实现（2026-09-21）

## 目标

1. 用户与管理员界面**不再出现人民币**：金额默认以 **VND** 展示，可切换 **USD**。
2. **移除**支付宝 / 微信支付 / 银联 / 易支付（Epay）整条链路。
3. 充值改为 **银行转账 + 管理员确认到账**（后续可再接 VNPay / MoMo / Stripe）。
4. 移除仅限中国大陆的部分：右下角微信群入口、README 微信群说明；营销文案中的抖音 / 小红书 / B 站等换成 TikTok / Facebook / YouTube 等。

## 不做的事（明确边界）

- **钱包内部单位不变**：`users.balance_fen / frozen_fen`、`wallet_ledger`、`usage_events`、`task_runs.billing_*` 仍以「分」（1/100 CNY）记账，预扣 / 结算 / 估价逻辑一律不动。人民币只作为内部记账基准，不再对任何界面暴露。
- 不做余额迁移、不改 TokenFree 成本换算（`quota → USD → CNY` 仍经 `billing_usd_cny`）。
- 不接第三方支付网关（本期只做转账 + 人工确认）。
- 模板 prompt、LLM 提示词中的中文平台名（如 style_prefix 里的「抖音」）属于生成提示，不改。

## A. 展示货币层

### 配置（`config.py`，管理端可改，存 `app_settings.flat`）

| 键 | 默认 | 说明 |
|----|------|------|
| `billing_display_currency` | `VND` | 默认展示货币，`VND` / `USD` |
| `billing_cny_vnd` | `3600.0` | 1 CNY 折 VND（管理端可调） |
| `billing_usd_cny` | `7.0` | 已有；USD 展示 = fen / 100 / usd_cny |

### 接口

`GET /api/billing/currency`（公开）：

```json
{ "default": "VND", "options": ["VND", "USD"],
  "per_fen": { "VND": 36.0, "USD": 0.0014286 } }
```

`per_fen[c]` = 1 分折合该货币的数值；前端 `amount = fen × per_fen[c]`。VND 取整并按 `vi-VN` 分组（`1.000.000 ₫`），USD 两位小数（`$12.34`）。

### 用户端

- 新增 `src/lib/money.ts`：`fenToAmount(fen, currency, perFen)`、`formatMoney(fen, currency, perFen)`；`src/i18n` 之外单独一个 `CurrencyProvider`（`useCurrency()`：`currency`、`setCurrency`、`perFen`、`format(fen)`），用户选择持久化到 `localStorage['printfilm.currency']`，未选择时用服务端默认。
- 定价页与「套餐与余额」面板放一个 VND / USD 切换。
- 替换全部 `¥` 展示（PricingPage、PricingWalletCard、MonthlyUsageCard、UsageChargeRecords、TopupHistoryModal、PaymentModal、SettingsPage、dramaUsage 等 15 处）；API 中的 `*_yuan` 字段保留但前端不再使用。
- 文案里的 `¥{amount}` 占位改为已格式化的 `{amount}`。

### 管理端

- `lib/utils.ts` 的 `fenToYuan` 改为 `formatMoney(fen)`，读取 `/api/billing/currency`（缓存），73 处调用点统一换掉 `¥` 前缀。
- 「支付与计费」面板改为「支付与汇率」：银行转账信息 + 汇率 + 默认展示货币；删除 Epay 区块。

### 后端文案

`services/billing/money.py`：`format_money(fen)` 按默认展示货币格式化；`settlement.py` / `studio_tools.py` / `alerts.py` 中「余额不足：需要 ¥…」等改用它（保留「余额不足 / 请先充值」关键词，前端 `isBillingError` 正则不变）。

## B. 银行转账充值

### 配置

| 键 | 说明 |
|----|------|
| `topup_bank_name` | 银行名称（如 Vietcombank） |
| `topup_bank_account` | 收款账号 |
| `topup_bank_holder` | 户名 |
| `topup_bank_bin` | 银行 BIN（可选；有则生成 VietQR 图） |
| `topup_order_expire_hours` | 待支付单有效期，默认 24 |

### 充值包（`services/billing/pricing.py`）

以 VND 定义，赠送比例沿用原结构：

| id | amount_vnd | bonus |
|----|-----------:|------:|
| `topup_100k` | 100 000 | 0% |
| `topup_500k` | 500 000 | 0% |
| `topup_1m` | 1 000 000 | 5%（推荐） |
| `topup_2m` | 2 000 000 | 10% |

下单时换算：`amount_fen = round(amount_vnd / billing_cny_vnd × 100)`，`credit_fen = round(amount_fen × (1 + bonus))`。订单**记录下单时的展示金额与币种**，之后汇率变化不影响已建订单。

### 数据

`orders` 追加列（additive，`_apply_schema_patches`）：`pay_amount INTEGER`（用户需支付的展示金额）、`pay_currency VARCHAR(8)`（`VND`）、`note VARCHAR(255)`（管理员确认备注）。`pay_type` 新值 `bank_transfer`；历史 `alipay/wxpay` 订单只读保留。

### 流程

```
用户选包 → POST /api/billing/orders {sku_id}
  → 建 pending 单，返回 { out_trade_no, pay_amount, pay_currency, bank: {name, account, holder, bin}, transfer_note: out_trade_no, vietqr_url?, expire_seconds }
用户转账（备注写 out_trade_no）→ 弹窗显示银行信息 / 复制 / VietQR，「我已转账」关闭弹窗
前端沿用 GET /api/billing/orders/{no} 轮询（间隔放宽到 10s，弹窗关闭后停止；充值记录里可见 pending）
管理员：管理端「订单」列表对 pending 单提供「确认到账」「关闭」
  → POST /api/admin/orders/{no}/confirm {note?}：调用现有 credit_topup()，status=paid，paid_at=now，trade_no=admin:{admin_id}
  → POST /api/admin/orders/{no}/close
过期：close_expired_pending_orders 按 pay_type 取有效期（bank_transfer 用 topup_order_expire_hours）
```

VietQR 图片：`https://img.vietqr.io/image/{bin}-{account}-compact2.png?amount={pay_amount}&addInfo={out_trade_no}&accountName={holder}`，仅在配置了 `topup_bank_bin` 时返回；前端 `<img>` 直接引用，失败则退化为文字信息。

### 删除

`services/epay.py`、`/api/billing/epay/notify` 路由、`epay_*` 配置与 `schemas_settings` 字段、管理端 Epay 表单、`PaymentBrandIcon` 与 `public/payment/*.svg`、`pay_types` 中的 `alipay/wxpay`、定价页支付方式四宫格、nginx `/epay/notify` location、`docs/BILLING.md` / `docs/DEPLOY.md` 中的易支付说明（改写为转账流程）。

## C. 移除中国大陆专属内容

- 删除 `WeChatGroupFab` 组件、`App.tsx` 挂载、`wechatGroup.*` 文案、`.pf-wx-fab*` 样式、README 微信群小节。
- `lib/methodLanding.ts`（zh/en/vi）：分发表改为 TikTok / Facebook Reels / YouTube Shorts / Instagram Reels / 长文平台（Blog / LinkedIn）；正文中「抖音、小红书、视频号」改为「TikTok、Facebook、YouTube」。
- 帮助 FAQ、法律条款、定价文案中的「支付宝 / 微信支付 / 易支付」改为「银行转账」。
- 获客模板 en/vi 名称：`Douyin hook → TikTok hook`、`Xiaohongshu recommendation → Social recommendation`；`templates_i18n.py` 同步。中文 `name` 为数据库主值不改。

## 验证

- 后端：新增 `tests/test_bank_transfer_orders.py`（建单换算、确认到账入账、过期关闭）、`tests/test_money_format.py`；现有 billing 测试全过。
- 前端 / 管理端：`tsc -b`、lint；浏览器走一遍：定价页 → 建单弹窗 → 管理端确认 → 余额更新；切换 VND/USD 全站金额一致。
- `grep` 确认用户端 / 管理端源码不再有 `¥`、`alipay`、`wxpay`、`epay`、`WeChat`（除历史订单只读展示）。

## 发布注意

- 需在管理端填写银行信息后充值才可用；未填写时定价页提示「充值暂未开放」。
- 追加 `docs/releases/` 记录；`.env.example` 删除 `EPAY_*`，新增 `BILLING_DISPLAY_CURRENCY`、`BILLING_CNY_VND`、`TOPUP_BANK_*`。
