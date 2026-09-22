# Bỏ TokenFree — Plan C: Admin UI + Frontend + Tài liệu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin cấu hình provider và gán model theo chức năng trên màn hình 2 cột mới, sửa bảng giá `provider_rates`, bỏ mọi màn đối chiếu upstream; phía user chọn model theo scope và có trạng thái rỗng rõ ràng; không còn chữ "TokenFree" nào trong `admin/src` và `frontend/src`.

**Architecture:** Admin: `api/routing.ts` (kiểu + gọi API routing) và `lib/providerRouting.ts` (hàm thuần, test bằng `node --test`) là nền; component mới ở `components/settings/models/` (`ProviderSidebar`, `ProviderDialog`, `ProviderModelsSection`, `FunctionBindingsPanel`, `BindingRow`, `ModelPickerDialog`, `ProviderIcon`) được `ModelsSettingsPanel` điều phối qua hook `useRoutingSettings`. Provider lưu ngay trong hộp thoại (`PATCH {providers}`); gán chức năng lưu bằng nút chung của trang (`PATCH {function_bindings}`). Bảng giá dùng `api/providerRates.ts` + `lib/providerRates.ts` + `hooks/useProviderRates.ts` + `ProviderRatesEditor.tsx` trong tab thanh toán. Frontend: `api.mediaModels(scope)`, cache theo scope, hàm thuần `lib/mediaModelChoice.ts` quyết định model hợp lệ, component `MediaModelGrid` cho trang phong cách video kiến thức.

**Tech Stack:** React 19, TypeScript 6, Vite 8, oxlint; admin: Tailwind v4 + Radix/shadcn-style + CSS `settings-*` trong `admin/src/index.css`; frontend: CSS `pf-*` (không Tailwind), i18n zh/en/vi. Test hàm thuần: Node 25 `node --test` (tự bỏ kiểu TypeScript). Backend (1 thay đổi nhỏ ở Task 7): Python 3.12, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-provider-migration-design.md` — §5.4 (phía user), §7.1 (màn 2 cột), §7.2 (API admin), §7.3 (chỗ khác trong admin), §9.2 (hồi quy thủ công), §9.3 (tài liệu). Plan A đã chạy: `docs/superpowers/plans/2026-09-22-provider-migration-a-backend-core.md`. Plan B **chạy trước Plan C**: `docs/superpowers/plans/2026-09-23-provider-migration-b-billing.md` — Plan C dùng đúng mục "Hợp đồng API cho Plan C (admin UI)" của Plan B.

## Global Constraints

- Thứ tự: Plan B phải được thực thi xong trước Task 5 và Task 6. Hai task này bắt đầu bằng bước kiểm tra endpoint Plan B; nếu kiểm tra thất bại thì **dừng, báo BLOCKED "Plan B chưa chạy"**, không tự viết backend thay Plan B.
- Hợp đồng backend dùng nguyên văn: `GET/PATCH /api/admin/settings/routing` (payload `AdminRoutingSettingsOut` / `AdminRoutingSettingsPatch` / `AdminRoutingSettingsSaveOut` trong `backend/app/schemas_routing.py`), `POST /api/admin/settings/providers/test`, `POST /api/admin/settings/upstream/models`, `GET/PUT /api/admin/settings/billing/model-rates` (Plan B), `GET /api/admin/finance/daily` shape mới (Plan B), `GET /api/media-models?scope=kepu|drama|tools`.
- Endpoint đã xoá, UI không được gọi: `/api/admin/stats/upstream-usage`, `/api/admin/stats/upstream-usage/sync`, `/api/admin/finance/daily/sync`, `/api/admin/settings/tokenfree/quota`. Field `billing_kie_fen_per_credit` không còn tác dụng — bỏ khỏi UI admin (không sửa backend `config.py` / `schemas_settings.py`).
- admin/: Tailwind v4, alias `@` → `src`, dùng `cn()` từ `@/lib/utils`, class `settings-*` hiện có. **Không thêm dependency npm** (không cài `@radix-ui/react-checkbox` / `tooltip`): dùng `<input type="checkbox">` như `.settings-model-option`, gợi ý bằng thuộc tính `title`.
- Ngôn ngữ admin: màn hình/component **mới** viết tiếng Việt; phần admin cũ giữ tiếng Trung, chỉ đổi những chỗ spec §7.3 nêu (nhãn trung tính ở `RuntimeSettingsPanel` viết tiếng Việt như ví dụ của spec) và chữ nhắc TokenFree.
- frontend/: **không Tailwind**; style bằng class `pf-*` (`src/styles/printfilm.css`) hoặc class có sẵn; gọi API qua `src/api.ts`. i18n: `zh` là nguồn kiểu (`Messages = typeof zh`) → key mới phải thêm đủ `zh`, `en`, `vi`. Tiếng Việt theo `docs/I18N_GLOSSARY_VI.md`: 管理员 trong văn bản cho người dùng → **"chúng tôi"**; 上游 → **"nhà cung cấp mô hình"**; 科普 → **"video kiến thức"**.
- UI không bao giờ hiện CNY: tiền trong admin qua `useCurrency().format(fen)` (`admin/src/lib/currency.ts`); giá `provider_rates` là USD thô, xem trước quy ra fen theo `ceil(round(usd × usd_cny × 100, 6))` rồi `format()`.
- Mỗi function/component/hook mới có comment đầu (JSDoc hoặc `//`) mô tả chức năng; nhóm state có block comment. File mới ≤ ~500 dòng; trang chỉ điều phối, logic thuần đặt ở `lib/`.
- Không đổi tên field cấu hình `ark_*` / `seedance_*` (chỉ đổi nhãn hiển thị).
- Kiểm tra mỗi task (chạy những dòng liên quan tới app đã sửa):
  - `cd admin && npm run lint && npm run build && npm test`
  - `cd frontend && npm run lint && npm run build && npm test`
  - khi sửa backend: `cd backend && .venv/bin/python -m pytest -q -p no:cacheprovider` — kỳ vọng chỉ còn **2 lỗi có sẵn** trong `tests/test_agent_skills.py`. Test có fixture `db_session` cần PostgreSQL đang chạy.
- **Không đụng** server của người dùng ở cổng 8000 / 5173 / 5174 và DB dev của họ. Smoke test dùng backend cổng **8765** (DB riêng `printfilm_plan_c`, `ARK_MOCK=true`), frontend **5273**, admin **5274**.
- Commit message tiếng Việt, kết thúc đúng một dòng `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Không commit `.env`, `docs/releases/` (thư mục bị `.gitignore`, chỉ lưu local), `dist/`, media sinh ra.

## Review Focus

1. **Bỏ tick model, xoá provider đang được gán, hoặc đổi host Base URL mà không nhập lại key** — backend trả 400 khó hiểu (backend `host_guard` từ chối dùng lại key cũ cho host khác) nếu để lọt; UI phải chặn trước và nói rõ lý do ("Model 'x' đang được gán cho: Slot Ảnh…", "Đổi địa chỉ máy chủ (Base URL) thì phải nhập lại API key."). Test: Task 1 (`providerSaveBlockers blocks unticking a bound model`, `providerDeleteBlocker names the functions`, `providerSaveBlockers asks for a new key when the base url host changes`).
2. **Provider tắt / thiếu key trong slot** — binding giữ nguyên, chip hiện gạch đứt + badge "N tạm không dùng được", lưu vẫn hợp lệ (backend chỉ kiểm tra tồn tại / model đã bật / đúng năng lực). Test: Task 1 (`bindingProblem reports disabled and incomplete providers`, `validateBindingsDraft accepts disabled provider`).
3. **Catalog rỗng, model đã lưu bị admin gỡ, hoặc catalog chưa tải xong** — user vẫn tạo được: model rỗng = "Tự động" (backend chia luân phiên theo weight), frontend không ghim `defaults.*`, xoá model đã bị gỡ về rỗng trước khi lưu/gửi, còn khi catalog chưa về thì gửi nguyên giá trị (backend chấp nhận giá trị cũ không đổi). Test: Task 8 (`reconcileCatalogModel …` 5 ca).
4. **ID model khác hoa/thường, có khoảng trắng, endpoint `ep-…`** — so khớp chuẩn hoá giống backend (`normalize_model_name`), không bật trùng, không tạo 2 chip cho cùng model. Test: Task 1 (`mergeModelIds dedupes case-insensitively`, `toggleBinding uses normalized key`).
5. **Bảng giá: số USD lẻ, đổi đơn vị, đổi thứ tự** — xem trước fen khớp backend (0.07 USD × 7 → 49 fen, không 50); đổi sang đơn vị khác `per_m_input_output` thì `usd_out = null`; ↑/↓ đổi đúng thứ tự ưu tiên. Test: Task 5 (`rateFenPreview matches backend rounding`, `withUnit clears usd_out`, `moveRow swaps neighbours and clamps`).

---

## Sơ đồ file

| File | Trách nhiệm | Task |
|---|---|---|
| `admin/src/api/routing.ts` (mới) | kiểu payload routing + hàm gọi API routing / test provider / tải danh sách model | 1 |
| `admin/src/lib/providerRouting.ts` (mới) | hàm thuần: năng lực model, trạng thái provider, lỗi binding, sửa nháp bindings, chặn lưu/xoá | 1 |
| `admin/tests/providerRouting.test.ts` (mới), `admin/package.json` (script `test`) | test `node --test` | 1 |
| `admin/src/components/settings/models/ProviderIcon.tsx` (mới) | icon theo preset/protocol | 2 |
| `admin/src/components/settings/models/BindingRow.tsx` (mới) | một hàng slot/override: chip, badge | 2 |
| `admin/src/components/settings/models/ModelPickerDialog.tsx` (mới) | chọn nhiều model + weight | 2 |
| `admin/src/components/settings/models/FunctionBindingsPanel.tsx` (mới) | cột phải: 4 slot + ghi đè theo chức năng | 2 |
| `admin/src/components/settings/models/ProviderModelsSection.tsx` (mới) | phần "Model bật" trong hộp thoại provider | 3 |
| `admin/src/components/settings/models/ProviderDialog.tsx` (mới) | tạo/sửa/kiểm tra/xoá provider | 3 |
| `admin/src/hooks/useRoutingSettings.ts` (mới) | tải/lưu routing, nháp bindings | 4 |
| `admin/src/components/settings/models/ProviderSidebar.tsx` (mới) | cột trái | 4 |
| `admin/src/components/settings/models/ModelsSettingsPanel.tsx` (mới) | điều phối tab "Mô hình" | 4 |
| `admin/src/pages/SettingsPage.tsx` (sửa) | tab "Mô hình" dùng panel mới, bỏ chữ TokenFree | 4, 6 |
| xoá `admin/src/components/settings/RoutingSettingsPanel.tsx`, `admin/src/lib/tokenfreeRecommendedModels.ts`; `admin/src/api/client.ts` (bỏ kiểu routing cũ) | | 4 |
| `admin/src/index.css` (thêm cuối file) | CSS `settings-providers-layout`, `settings-binding-*`, `settings-provider-*` | 2, 3, 4 |
| `admin/src/api/providerRates.ts`, `admin/src/lib/providerRates.ts`, `admin/src/hooks/useProviderRates.ts`, `admin/src/components/settings/ProviderRatesEditor.tsx` (mới), `admin/tests/providerRates.test.ts` (mới) | bảng giá `provider_rates` | 5 |
| `admin/src/components/settings/PaymentSettingsPanel.tsx` (sửa) | bỏ TokenFree, nhúng bảng giá | 5 |
| `admin/src/components/settings/RuntimeSettingsPanel.tsx`, `admin/src/pages/DashboardPage.tsx`, `admin/src/pages/dashboard/dashboardSectionInsights.tsx`, `admin/src/pages/FinanceListPage.tsx`, `admin/src/pages/OrdersPage.tsx`, `admin/src/api/client.ts` (sửa) | bỏ đối chiếu upstream / chữ TokenFree, nhãn trung tính, bỏ field flat đã chết khỏi kiểu | 6 |
| `backend/app/schemas_tasks.py`, `backend/app/api/admin/tasks.py`, `backend/tests/test_admin_task_usage_provider.py` (mới); `admin/src/api/client.ts`, `admin/src/pages/QueuesPage.tsx`, `admin/src/components/tasks/TaskDetailDialog.tsx` (sửa) | `TaskRunBriefOut.provider_channel_id`, `provider` trong dòng usage; task center hiện provider | 7 |
| `frontend/src/lib/mediaModelChoice.ts` (mới), `frontend/tests/mediaModelChoice.test.ts` (mới), `frontend/package.json` | model rỗng = Tự động; bỏ model đã bị gỡ | 8 |
| `frontend/src/lib/mediaModelsCatalogStore.ts` (mới), `frontend/src/lib/dramaImageGenQueue.ts`, `frontend/src/lib/dramaVideoGenQueue.ts` (sửa) | cache catalog theo scope; làm sạch model ngay trước khi gửi | 8 |
| `frontend/src/api.ts`, `frontend/src/hooks/useMediaModelsCatalog.ts`, `frontend/src/components/studio/MediaModelGrid.tsx` (mới), `frontend/src/pages/studio/StyleConfigPage.tsx`, `frontend/src/pages/drama/canvas/nodes/DramaImageGenOptionsBar.tsx`, `…/DramaVideoGenOptionsBar.tsx`, `frontend/src/pages/drama/EpisodeEditHeaderControls.tsx`, `frontend/src/pages/drama/EpisodeEditPage.tsx`, i18n `studio.ts`/`dramaCanvas.ts`/`dramaEpisode.ts` ×3 ngôn ngữ | catalog theo scope, ô “Tự động”, trạng thái rỗng | 8 |
| i18n `errors.ts`/`dramaGen.ts`/`pages.ts` ×3, `frontend/src/lib/legalContent.ts`, `frontend/src/lib/dramaGenError.ts`, `frontend/src/lib/dramaGenerationOptions.ts`, `frontend/src/lib/dramaVideoGenerationOptions.ts` | bỏ chữ TokenFree | 9 |
| `README.md`, `docs/PROVIDERS.md` (sửa), `docs/releases/<ngày>-provider-migration.md` (mới, không commit) | tài liệu | 10 |
| `admin/vite.config.ts` (sửa: đích proxy đọc env) | smoke test cổng riêng | 12 |

---

### Task 1: Admin — kiểu API routing + hàm thuần `providerRouting.ts` + chạy test `node --test`

**Files:**
- Create: `admin/src/api/routing.ts`
- Create: `admin/src/lib/providerRouting.ts`
- Create: `admin/tests/providerRouting.test.ts`
- Modify: `admin/package.json` (thêm script `test`)

**Interfaces:**
- Consumes: `api`, `ModelCapabilityReadiness` từ `@/api/client`; payload backend `AdminRoutingSettingsOut` (`backend/app/schemas_routing.py`).
- Produces:
  ```ts
  // @/api/routing
  export type Capability = "text" | "image" | "video" | "audio";
  export type ProviderProtocol = "openai" | "ark" | "volc_tts";
  export type AdminProvider = { id; name; base_url; api_key; has_api_key; protocol: ProviderProtocol | "auto" | "kie"; models: string[]; enabled; sort_order };
  export type ModelBinding = { channel_id: string; model: string; weight: number };
  export type FunctionBindings = { slots: Partial<Record<Capability, ModelBinding[]>>; overrides: Record<string, ModelBinding[]> };
  export type FunctionInfo = { id: string; capability: Capability; label: string; description: string };
  export type CatalogModel = { id: string; label?: string; capability?: string };
  export type ProviderPreset = { id; name; protocol: ProviderProtocol; base_url; catalog: "remote" | "static" | "none"; models: CatalogModel[] };
  export type AdminRoutingSettings = { providers; function_bindings; readiness; function_catalog; presets; validation_errors; updated_at? };
  export type ProviderPatchItem = { id; name; base_url; api_key: string | null; clear_api_key; protocol: ProviderProtocol; models; enabled; sort_order };
  export type AdminRoutingSaveOut = { ok: boolean; settings: AdminRoutingSettings; applied: string[] };
  export type ProviderConnectionInput = { channel_id?: string | null; protocol: ProviderProtocol; base_url: string; api_key?: string | null };
  export type ProviderTestResult = { ok: boolean; message: string; models_count?: number };
  export function fetchRoutingSettings(): Promise<AdminRoutingSettings>;
  export function saveRoutingSettings(body: { providers?: ProviderPatchItem[]; function_bindings?: FunctionBindings }): Promise<AdminRoutingSaveOut>;
  export function testProviderConnection(input: ProviderConnectionInput): Promise<ProviderTestResult>;
  export function listProviderModels(input: ProviderConnectionInput & { capability?: string }): Promise<CatalogModel[]>;
  // @/lib/providerRouting
  export const CAPABILITIES, CAPABILITY_LABELS, CAPABILITY_HINTS, PROVIDER_STATUS_LABELS, BINDING_PROBLEM_LABELS, BLANK_PRESET;
  export type ProviderDraft, ProviderStatus, BindingProblem, ModelOption;
  export function normalizeModelName(v: string): string;
  export function inferModelCapability(model: string): Capability;
  export function modelCapability(protocol: string, model: string): Capability;
  export function normalizeProtocol(p: string): ProviderProtocol;
  export function draftFromProvider(p: AdminProvider): ProviderDraft;
  export function uniqueProviderId(base: string, existingIds: string[]): string;
  export function draftFromPreset(preset: ProviderPreset, existingIds: string[]): ProviderDraft;
  export function draftHasKey(d: ProviderDraft): boolean;
  export function providerStatus(d: ProviderDraft): ProviderStatus;
  export function staticCatalogFor(presets: ProviderPreset[], d: Pick<ProviderDraft, "preset_id" | "protocol">): CatalogModel[];
  export function bindingKey(b: { channel_id: string; model: string }): string;
  export function bindingProblem(b: ModelBinding, capability: Capability, providers: ProviderDraft[]): BindingProblem | null;
  export function modelOptionsFor(providers: ProviderDraft[], capability: Capability): ModelOption[];
  export function toggleBinding(list: ModelBinding[], option: { channel_id: string; model: string }): ModelBinding[];
  export function setBindingWeight(list: ModelBinding[], key: string, weight: number): ModelBinding[];
  export function withSlot(b: FunctionBindings, cap: Capability, list: ModelBinding[]): FunctionBindings;
  export function withOverride(b: FunctionBindings, functionId: string, list: ModelBinding[]): FunctionBindings;
  export function assignedSlotCount(b: FunctionBindings): number;
  export function providerUsages(b: FunctionBindings, catalog: FunctionInfo[], channelId: string): string[];
  export function modelUsages(b: FunctionBindings, catalog: FunctionInfo[], channelId: string, model: string): string[];
  export function mergeModelIds(current: string[], added: string[]): string[];
  export function validateBindingsDraft(b: FunctionBindings, providers: ProviderDraft[], catalog: FunctionInfo[]): string[];
  export function validateProviderDraft(d: ProviderDraft, others: ProviderDraft[]): string[];
  export function providerSaveBlockers(initial: ProviderDraft, draft: ProviderDraft, others: ProviderDraft[], bindingSets: FunctionBindings[], catalog: FunctionInfo[]): string[];
  export function providerDeleteBlocker(id: string, bindingSets: FunctionBindings[], catalog: FunctionInfo[]): string | null;
  export function toProviderPatch(drafts: ProviderDraft[]): ProviderPatchItem[];
  export function urlOrigin(value: string): string;   // scheme+host+port, giống host_guard.same_host
  export const CONNECTION_TEST_HINTS: Record<ProviderProtocol, string>;
  export function connectionTestLabel(protocol: ProviderProtocol, result: ProviderTestResult): string;
  ```
- Ghi chú hành vi backend mà lib phải phản ánh: (a) key đã lưu **không được dùng lại khi host của Base URL đổi** → sửa provider mà đổi host thì phải nhập lại key (`providerSaveBlockers` chặn); (b) `POST /settings/providers/test` với `ark` / `volc_tts` **chỉ kiểm tra đã có key**, không gọi provider → câu hiển thị phải nói rõ (`CONNECTION_TEST_HINTS`, `connectionTestLabel`).

- [ ] **Step 1: Thêm script test vào `admin/package.json`**

Trong khối `"scripts"` thêm dòng sau `"lint": "oxlint",`:

```json
    "test": "node --test \"tests/*.test.ts\"",
```

(Node 25 tự bỏ kiểu TypeScript; `import type` bị xoá hoàn toàn nên alias `@/…` trong `import type` không cần resolve. Thư mục `tests/` nằm ngoài `include: ["src"]` của `tsconfig.app.json` nên không ảnh hưởng `tsc -b`.)

- [ ] **Step 2: Viết `admin/src/api/routing.ts`**

```ts
import { api, type ModelCapabilityReadiness } from "@/api/client";

/** Năng lực AI của một slot / model */
export type Capability = "text" | "image" | "video" | "audio";

/** Protocol provider backend hỗ trợ */
export type ProviderProtocol = "openai" | "ark" | "volc_tts";

/** Provider đã lưu (key bị che, chỉ còn cờ has_api_key) */
export type AdminProvider = {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  has_api_key: boolean;
  protocol: ProviderProtocol | "auto" | "kie";
  models: string[];
  enabled: boolean;
  sort_order: number;
};

/** Một (provider, model) được gán cho slot/override, kèm tỉ lệ chia luân phiên */
export type ModelBinding = { channel_id: string; model: string; weight: number };

/** Gán chức năng: 4 slot năng lực + ghi đè theo chức năng */
export type FunctionBindings = {
  slots: Partial<Record<Capability, ModelBinding[]>>;
  overrides: Record<string, ModelBinding[]>;
};

/** Một chức năng AI cố định trong danh mục backend */
export type FunctionInfo = { id: string; capability: Capability; label: string; description: string };

/** Một model trong danh mục (tĩnh của preset hoặc tải từ provider) */
export type CatalogModel = { id: string; label?: string; capability?: string };

/** Preset provider backend gợi ý khi thêm mới */
export type ProviderPreset = {
  id: string;
  name: string;
  protocol: ProviderProtocol;
  base_url: string;
  catalog: "remote" | "static" | "none";
  models: CatalogModel[];
};

/** GET /api/admin/settings/routing */
export type AdminRoutingSettings = {
  providers: AdminProvider[];
  function_bindings: FunctionBindings;
  readiness: ModelCapabilityReadiness[];
  function_catalog: FunctionInfo[];
  presets: ProviderPreset[];
  validation_errors: string[];
  updated_at?: string | null;
};

/** Một provider trong body PATCH (api_key null = giữ key đã lưu) */
export type ProviderPatchItem = {
  id: string;
  name: string;
  base_url: string;
  api_key: string | null;
  clear_api_key: boolean;
  protocol: ProviderProtocol;
  models: string[];
  enabled: boolean;
  sort_order: number;
};

/** PATCH /api/admin/settings/routing → 200 */
export type AdminRoutingSaveOut = { ok: boolean; settings: AdminRoutingSettings; applied: string[] };

/** Thông tin kết nối dùng cho kiểm tra / tải danh sách model (key trống + channel_id = dùng key đã lưu) */
export type ProviderConnectionInput = {
  channel_id?: string | null;
  protocol: ProviderProtocol;
  base_url: string;
  api_key?: string | null;
};

/** POST /api/admin/settings/providers/test */
export type ProviderTestResult = { ok: boolean; message: string; models_count?: number };

// Đọc toàn bộ cấu hình routing (provider, gán chức năng, danh mục, preset)
export function fetchRoutingSettings(): Promise<AdminRoutingSettings> {
  return api<AdminRoutingSettings>("/api/admin/settings/routing");
}

// Lưu danh sách provider (thay toàn bộ) và/hoặc gán chức năng; 400 trả câu lỗi tiếng Việt
export function saveRoutingSettings(body: {
  providers?: ProviderPatchItem[];
  function_bindings?: FunctionBindings;
}): Promise<AdminRoutingSaveOut> {
  return api<AdminRoutingSaveOut>("/api/admin/settings/routing", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// Kiểm tra kết nối provider trước/sau khi lưu
export function testProviderConnection(input: ProviderConnectionInput): Promise<ProviderTestResult> {
  return api<ProviderTestResult>("/api/admin/settings/providers/test", {
    method: "POST",
    body: JSON.stringify({ ...input, api_key: input.api_key || null, channel_id: input.channel_id || null }),
  });
}

// Tải danh mục model của provider (openai: GET /models; ark/volc_tts: danh sách tĩnh)
export async function listProviderModels(
  input: ProviderConnectionInput & { capability?: string },
): Promise<CatalogModel[]> {
  const res = await api<{ models: CatalogModel[] }>("/api/admin/settings/upstream/models", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      api_key: input.api_key || null,
      channel_id: input.channel_id || null,
      capability: input.capability ?? "all",
    }),
  });
  return res.models ?? [];
}
```

- [ ] **Step 3: Viết test thất bại `admin/tests/providerRouting.test.ts`**

```ts
/** Hàm thuần tab "Mô hình": năng lực model, trạng thái provider, kiểm tra binding, chặn lưu/xoá. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  assignedSlotCount,
  bindingKey,
  bindingProblem,
  connectionTestLabel,
  draftFromPreset,
  draftFromProvider,
  inferModelCapability,
  mergeModelIds,
  modelCapability,
  modelOptionsFor,
  modelUsages,
  providerDeleteBlocker,
  providerSaveBlockers,
  providerStatus,
  providerUsages,
  setBindingWeight,
  staticCatalogFor,
  toggleBinding,
  toProviderPatch,
  uniqueProviderId,
  urlOrigin,
  validateBindingsDraft,
  validateProviderDraft,
  withOverride,
  withSlot,
  type ProviderDraft,
} from "../src/lib/providerRouting.ts";

const CATALOG = [
  { id: "kepu.image", capability: "image" as const, label: "Ảnh phân cảnh khoa học", description: "" },
  { id: "tools.image", capability: "image" as const, label: "Ảnh công cụ & Open API", description: "" },
  { id: "drama.video", capability: "video" as const, label: "Video phim ngắn", description: "" },
];

function draft(over: Partial<ProviderDraft> = {}): ProviderDraft {
  return {
    id: "byteplus",
    name: "BytePlus ModelArk",
    base_url: "https://ark.ap-southeast.bytepluses.com/api/v3",
    protocol: "ark",
    models: ["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"],
    enabled: true,
    has_api_key: true,
    api_key_input: "",
    clear_api_key: false,
    is_new: false,
    preset_id: "byteplus",
    ...over,
  };
}

test("inferModelCapability mirrors backend keywords", () => {
  assert.equal(inferModelCapability("dreamina-seedance-2-5-260628"), "video");
  assert.equal(inferModelCapability("dola-seedream-5-0-pro-260628"), "image");
  assert.equal(inferModelCapability("gpt-image-2"), "image");
  assert.equal(inferModelCapability("gpt-4o-mini-tts"), "audio");
  assert.equal(inferModelCapability("gpt-5.6-sol"), "text");
  assert.equal(inferModelCapability("seed-2-0-pro-260328"), "text");
  assert.equal(inferModelCapability(""), "text");
});

test("modelCapability forces audio for volc_tts", () => {
  assert.equal(modelCapability("volc_tts", "seed-icl-2.0"), "audio");
  assert.equal(modelCapability("openai", "seed-icl-2.0"), "text");
});

test("draftFromProvider maps legacy auto protocol to openai", () => {
  const d = draftFromProvider({
    id: "x", name: "X", base_url: "https://a/v1", api_key: "", has_api_key: true,
    protocol: "auto", models: ["m"], enabled: true, sort_order: 0,
  });
  assert.equal(d.protocol, "openai");
  assert.equal(d.is_new, false);
  assert.equal(d.api_key_input, "");
});

test("uniqueProviderId slugifies and appends a counter", () => {
  assert.equal(uniqueProviderId("openai", []), "openai");
  assert.equal(uniqueProviderId("openai", ["openai"]), "openai-2");
  assert.equal(uniqueProviderId("openai", ["openai", "openai-2"]), "openai-3");
  assert.equal(uniqueProviderId("My Provider!", []), "my-provider");
});

test("draftFromPreset fills preset fields and a free id", () => {
  const d = draftFromPreset(
    { id: "openai", name: "OpenAI", protocol: "openai", base_url: "https://api.openai.com/v1", catalog: "remote", models: [] },
    ["openai"],
  );
  assert.equal(d.id, "openai-2");
  assert.equal(d.is_new, true);
  assert.equal(d.base_url, "https://api.openai.com/v1");
});

test("providerStatus: disabled, incomplete, ready", () => {
  assert.equal(providerStatus(draft({ enabled: false })), "disabled");
  assert.equal(providerStatus(draft()), "ready");
  assert.equal(providerStatus(draft({ clear_api_key: true })), "incomplete");
  assert.equal(providerStatus(draft({ has_api_key: false, api_key_input: " sk-1 " })), "ready");
  assert.equal(providerStatus(draft({ base_url: "" })), "incomplete");
  assert.equal(providerStatus(draft({ protocol: "volc_tts", has_api_key: false, base_url: "https://tts" })), "ready");
});

test("staticCatalogFor picks the preset static list by protocol", () => {
  const presets = [
    { id: "byteplus", name: "B", protocol: "ark" as const, base_url: "", catalog: "static" as const, models: [{ id: "a" }] },
    { id: "openai", name: "O", protocol: "openai" as const, base_url: "", catalog: "remote" as const, models: [] },
  ];
  assert.deepEqual(staticCatalogFor(presets, { preset_id: "my-ark", protocol: "ark" }), [{ id: "a" }]);
  assert.deepEqual(staticCatalogFor(presets, { preset_id: "openai", protocol: "openai" }), []);
});

test("bindingProblem reports disabled and incomplete providers", () => {
  const b = { channel_id: "byteplus", model: "dola-seedream-5-0-pro-260628", weight: 1 };
  assert.equal(bindingProblem(b, "image", [draft()]), null);
  assert.equal(bindingProblem(b, "image", [draft({ enabled: false })]), "provider_disabled");
  assert.equal(bindingProblem(b, "image", [draft({ clear_api_key: true })]), "provider_incomplete");
  assert.equal(bindingProblem(b, "image", []), "missing_provider");
  assert.equal(bindingProblem(b, "image", [draft({ models: [] })]), "model_not_enabled");
  assert.equal(bindingProblem(b, "video", [draft()]), "wrong_capability");
});

test("modelOptionsFor lists enabled models of the capability across providers", () => {
  const opts = modelOptionsFor(
    [draft(), draft({ id: "openai", name: "OpenAI", protocol: "openai", models: ["gpt-image-2", "gpt-5.6-sol"] })],
    "image",
  );
  assert.deepEqual(opts.map((o) => `${o.channel_id}/${o.model}`), [
    "byteplus/dola-seedream-5-0-pro-260628",
    "openai/gpt-image-2",
  ]);
});

test("toggleBinding uses normalized key", () => {
  const list = toggleBinding([], { channel_id: "byteplus", model: "Seedream-5-0-260128" });
  assert.equal(list.length, 1);
  assert.equal(list[0].weight, 1);
  assert.equal(bindingKey(list[0]), "byteplus::seedream-5-0-260128");
  assert.deepEqual(toggleBinding(list, { channel_id: "byteplus", model: "seedream-5-0-260128 " }), []);
});

test("setBindingWeight clamps to 1..100 and handles NaN", () => {
  const list = [{ channel_id: "a", model: "m", weight: 1 }];
  assert.equal(setBindingWeight(list, "a::m", 250)[0].weight, 100);
  assert.equal(setBindingWeight(list, "a::m", 0)[0].weight, 1);
  assert.equal(setBindingWeight(list, "a::m", Number.NaN)[0].weight, 1);
  assert.equal(setBindingWeight(list, "a::m", 3.4)[0].weight, 3);
});

test("withSlot / withOverride drop empty lists", () => {
  const b0 = { slots: {}, overrides: {} };
  const b1 = withSlot(b0, "image", [{ channel_id: "a", model: "m", weight: 1 }]);
  assert.equal(assignedSlotCount(b1), 1);
  assert.deepEqual(withSlot(b1, "image", []).slots, {});
  const b2 = withOverride(b1, "tools.image", [{ channel_id: "a", model: "m", weight: 1 }]);
  assert.deepEqual(Object.keys(b2.overrides), ["tools.image"]);
  assert.deepEqual(withOverride(b2, "tools.image", []).overrides, {});
});

test("providerUsages and modelUsages name slots and overrides", () => {
  const b = {
    slots: { image: [{ channel_id: "byteplus", model: "dola-seedream-5-0-pro-260628", weight: 1 }] },
    overrides: { "tools.image": [{ channel_id: "byteplus", model: "DOLA-seedream-5-0-pro-260628", weight: 1 }] },
  };
  assert.deepEqual(providerUsages(b, CATALOG, "byteplus"), ["Slot Ảnh", "Ảnh công cụ & Open API"]);
  assert.deepEqual(modelUsages(b, CATALOG, "byteplus", "dola-seedream-5-0-pro-260628"), [
    "Slot Ảnh",
    "Ảnh công cụ & Open API",
  ]);
  assert.deepEqual(modelUsages(b, CATALOG, "byteplus", "other"), []);
});

test("mergeModelIds dedupes case-insensitively and trims", () => {
  assert.deepEqual(mergeModelIds(["ep-2026-ABC"], ["ep-2026-abc", " new-model ", ""]), ["ep-2026-ABC", "new-model"]);
});

test("validateBindingsDraft mirrors backend messages", () => {
  const b = {
    slots: {
      image: [{ channel_id: "ghost", model: "x", weight: 1 }],
      video: [{ channel_id: "byteplus", model: "dola-seedream-5-0-pro-260628", weight: 1 }],
      audio: [{ channel_id: "byteplus", model: "not-enabled-tts", weight: 1 }],
    },
    overrides: { "nope.fn": [] },
  };
  assert.deepEqual(validateBindingsDraft(b, [draft()], CATALOG), [
    "Slot Ảnh: provider 'ghost' không tồn tại",
    "Slot Video: model 'dola-seedream-5-0-pro-260628' không phải model video",
    "Slot Giọng đọc: model 'not-enabled-tts' chưa được bật ở provider BytePlus ModelArk",
    "Chức năng 'nope.fn' không tồn tại",
  ]);
});

test("validateBindingsDraft accepts disabled provider", () => {
  const b = { slots: { image: [{ channel_id: "byteplus", model: "dola-seedream-5-0-pro-260628", weight: 1 }] }, overrides: {} };
  assert.deepEqual(validateBindingsDraft(b, [draft({ enabled: false, has_api_key: false })], CATALOG), []);
});

test("validateProviderDraft checks new id, name and base url", () => {
  assert.deepEqual(validateProviderDraft(draft({ is_new: true, id: "Bad Id" }), []), [
    "ID chỉ gồm chữ thường, số, '-' hoặc '_' (tối đa 64 ký tự)",
  ]);
  assert.deepEqual(validateProviderDraft(draft({ is_new: true }), [draft()]), ["ID 'byteplus' đã tồn tại"]);
  assert.deepEqual(validateProviderDraft(draft({ name: " ", base_url: "" }), []), [
    "Cần nhập tên provider",
    "Cần nhập Base URL",
  ]);
  assert.deepEqual(validateProviderDraft(draft({ protocol: "volc_tts", base_url: "" }), []), []);
});

test("providerSaveBlockers blocks unticking a bound model", () => {
  const initial = draft();
  const next = draft({ models: ["dreamina-seedance-2-5-260628"] });
  const saved = { slots: { image: [{ channel_id: "byteplus", model: "dola-seedream-5-0-pro-260628", weight: 1 }] }, overrides: {} };
  assert.deepEqual(providerSaveBlockers(initial, next, [], [saved, { slots: {}, overrides: {} }], CATALOG), [
    "Model 'dola-seedream-5-0-pro-260628' đang được gán cho: Slot Ảnh. Hãy đổi gán trước khi bỏ tick.",
  ]);
  assert.deepEqual(providerSaveBlockers(initial, initial, [], [saved], CATALOG), []);
});

test("providerDeleteBlocker names the functions", () => {
  const draftB = { slots: {}, overrides: { "drama.video": [{ channel_id: "byteplus", model: "dreamina-seedance-2-5-260628", weight: 1 }] } };
  assert.equal(
    providerDeleteBlocker("byteplus", [{ slots: {}, overrides: {} }, draftB], CATALOG),
    "Provider đang được gán cho: Video phim ngắn. Hãy đổi gán trước khi xoá.",
  );
  assert.equal(providerDeleteBlocker("openai", [draftB], CATALOG), null);
});

test("toProviderPatch keeps saved key when input empty and trims base url", () => {
  const [item] = toProviderPatch([draft({ base_url: "https://x/v3/ ", api_key_input: " ", clear_api_key: false })]);
  assert.equal(item.api_key, null);
  assert.equal(item.clear_api_key, false);
  assert.equal(item.base_url, "https://x/v3");
  assert.equal(item.sort_order, 0);
  const [cleared] = toProviderPatch([draft({ clear_api_key: true })]);
  assert.equal(cleared.clear_api_key, true);
  const [replaced] = toProviderPatch([draft({ clear_api_key: true, api_key_input: "sk-new" })]);
  assert.equal(replaced.api_key, "sk-new");
  assert.equal(replaced.clear_api_key, false);
});

test("urlOrigin compares scheme, host and port like the backend", () => {
  assert.equal(urlOrigin("https://ARK.ap-southeast.bytepluses.com/api/v3/"), "https://ark.ap-southeast.bytepluses.com");
  assert.equal(urlOrigin("https://ark.ap-southeast.bytepluses.com:443/x"), "https://ark.ap-southeast.bytepluses.com");
  assert.equal(urlOrigin("http://127.0.0.1:9000/v1"), "http://127.0.0.1:9000");
  assert.equal(urlOrigin(" not a url "), "");
  assert.equal(urlOrigin(""), "");
});

test("providerSaveBlockers asks for a new key when the base url host changes", () => {
  const initial = draft();
  const moved = draft({ base_url: "https://ark.cn-beijing.volces.com/api/v3" });
  assert.deepEqual(providerSaveBlockers(initial, moved, [], [], CATALOG), [
    "Đổi địa chỉ máy chủ (Base URL) thì phải nhập lại API key.",
  ]);
  assert.deepEqual(providerSaveBlockers(initial, { ...moved, api_key_input: "sk-new" }, [], [], CATALOG), []);
  assert.deepEqual(
    providerSaveBlockers(initial, draft({ base_url: "https://ark.ap-southeast.bytepluses.com/api/v3/" }), [], [], CATALOG),
    [],
  );
});

test("connectionTestLabel says ark and volc_tts only check the key", () => {
  assert.equal(connectionTestLabel("openai", { ok: true, message: "Kết nối thành công, 12 model" }), "Kết nối thành công, 12 model");
  assert.equal(connectionTestLabel("ark", { ok: true, message: "Kết nối thành công, 17 model" }), "Đã có key (chưa gọi thử provider)");
  assert.equal(connectionTestLabel("volc_tts", { ok: false, message: "Cần API key" }), "Cần API key");
});
```

- [ ] **Step 4: Chạy test, xác nhận thất bại**

Run: `cd admin && npm test`
Expected: FAIL — `Cannot find module '…/src/lib/providerRouting.ts'`.

- [ ] **Step 5: Viết `admin/src/lib/providerRouting.ts`**

```ts
/**
 * Hàm thuần cho tab "Mô hình": suy luận năng lực model, trạng thái provider, lỗi binding,
 * sửa bản nháp function_bindings, chặn lưu/xoá provider đang được gán.
 * Chỉ `import type` để chạy được bằng `node --test`.
 */
import type {
  AdminProvider,
  CatalogModel,
  Capability,
  FunctionBindings,
  FunctionInfo,
  ModelBinding,
  ProviderPatchItem,
  ProviderPreset,
  ProviderProtocol,
  ProviderTestResult,
} from "@/api/routing";

export const CAPABILITIES: readonly Capability[] = ["text", "image", "video", "audio"];

export const CAPABILITY_LABELS: Record<Capability, string> = {
  text: "Văn bản",
  image: "Ảnh",
  video: "Video",
  audio: "Giọng đọc",
};

export const CAPABILITY_HINTS: Record<Capability, string> = {
  text: "Kịch bản, tách phân cảnh, viết prompt",
  image: "Ảnh phân cảnh, ảnh tư liệu, công cụ tạo ảnh",
  video: "Video phân cảnh, video tư liệu, công cụ tạo video",
  audio: "Lời dẫn, lồng tiếng, nghe thử giọng",
};

/** Bản nháp provider trên UI: key mới nhập tách khỏi cờ "đã lưu key" */
export type ProviderDraft = {
  id: string;
  name: string;
  base_url: string;
  protocol: ProviderProtocol;
  models: string[];
  enabled: boolean;
  has_api_key: boolean;
  api_key_input: string;
  clear_api_key: boolean;
  is_new: boolean;
  preset_id: string;
};

export type ProviderStatus = "ready" | "incomplete" | "disabled";

export const PROVIDER_STATUS_LABELS: Record<ProviderStatus, string> = {
  ready: "Sẵn sàng",
  incomplete: "Thiếu key",
  disabled: "Đang tắt",
};

export type BindingProblem =
  | "missing_provider"
  | "model_not_enabled"
  | "wrong_capability"
  | "provider_disabled"
  | "provider_incomplete";

export const BINDING_PROBLEM_LABELS: Record<BindingProblem, string> = {
  missing_provider: "Provider đã bị xoá",
  model_not_enabled: "Model chưa được bật ở provider",
  wrong_capability: "Model không đúng năng lực của hàng này",
  provider_disabled: "Provider đang tắt",
  provider_incomplete: "Provider thiếu key hoặc Base URL",
};

/** Một model đã bật ở một provider (dùng cho hộp chọn model) */
export type ModelOption = { channel_id: string; channel_name: string; model: string; status: ProviderStatus };

/** Preset trống dự phòng khi backend không trả preset nào */
export const BLANK_PRESET: ProviderPreset = {
  id: "custom_openai",
  name: "OpenAI-compatible",
  protocol: "openai",
  base_url: "",
  catalog: "remote",
  models: [],
};

/** Chuẩn hoá tên model để so khớp (giống normalize_model_name ở backend) */
export function normalizeModelName(value: string): string {
  return (value || "").trim().replace(/\s+/g, "").toLowerCase();
}

/** Suy luận năng lực từ tên model — bản sao `infer_model_capability` (backend/app/services/model_routing_config.py) */
export function inferModelCapability(model: string): Capability {
  const mid = normalizeModelName(model);
  if (!mid) return "text";
  if (
    mid.includes("tts") ||
    mid.includes("text-to-speech") ||
    mid.includes("text-to-dialogue") ||
    mid.includes("elevenlabs") ||
    mid.startsWith("zh_") ||
    mid.includes("speaker") ||
    mid.startsWith("s_")
  ) {
    return "audio";
  }
  if (
    mid.includes("seedance") ||
    mid.includes("veo") ||
    mid.includes("video") ||
    mid.includes("i2v") ||
    mid.includes("sora") ||
    mid.startsWith("kie-veo") ||
    mid.startsWith("kie-seedance")
  ) {
    return "video";
  }
  if (
    mid.includes("seedream") ||
    mid.includes("nano-banana") ||
    mid.includes("banana") ||
    mid.includes("dream") ||
    mid.startsWith("gpt-image") ||
    mid.includes("grok-imagine") ||
    mid.includes("image") ||
    mid.startsWith("kie-")
  ) {
    return "image";
  }
  return "text";
}

/** Năng lực model trong một provider (volc_tts luôn là giọng đọc, như validation backend) */
export function modelCapability(protocol: string, model: string): Capability {
  return protocol === "volc_tts" ? "audio" : inferModelCapability(model);
}

/** Protocol cũ (auto/kie/rỗng) coi là openai */
export function normalizeProtocol(protocol: string): ProviderProtocol {
  return protocol === "ark" || protocol === "volc_tts" ? protocol : "openai";
}

/** Provider đã lưu → bản nháp */
export function draftFromProvider(p: AdminProvider): ProviderDraft {
  return {
    id: p.id,
    name: p.name,
    base_url: p.base_url || "",
    protocol: normalizeProtocol(p.protocol),
    models: [...(p.models ?? [])],
    enabled: p.enabled,
    has_api_key: p.has_api_key,
    api_key_input: "",
    clear_api_key: false,
    is_new: false,
    preset_id: p.id,
  };
}

/** Sinh id provider dạng slug chưa bị dùng (openai, openai-2, …) */
export function uniqueProviderId(base: string, existingIds: string[]): string {
  const slug =
    (base || "")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "provider";
  if (!existingIds.includes(slug)) return slug;
  let n = 2;
  while (existingIds.includes(`${slug}-${n}`)) n += 1;
  return `${slug}-${n}`;
}

/** Preset → bản nháp provider mới */
export function draftFromPreset(preset: ProviderPreset, existingIds: string[]): ProviderDraft {
  return {
    id: uniqueProviderId(preset.id, existingIds),
    name: preset.name,
    base_url: preset.base_url,
    protocol: normalizeProtocol(preset.protocol),
    models: [],
    enabled: true,
    has_api_key: false,
    api_key_input: "",
    clear_api_key: false,
    is_new: true,
    preset_id: preset.id,
  };
}

/** Provider có key (đã lưu và chưa bị xoá, hoặc vừa nhập) */
export function draftHasKey(d: ProviderDraft): boolean {
  return (d.has_api_key && !d.clear_api_key) || d.api_key_input.trim().length > 0;
}

/** Trạng thái chấm màu: bật + đủ kết nối / thiếu key / tắt (giống _channel_ok ở backend) */
export function providerStatus(d: ProviderDraft): ProviderStatus {
  if (!d.enabled) return "disabled";
  if (d.protocol === "volc_tts") return draftHasKey(d) || d.base_url.trim() ? "ready" : "incomplete";
  return d.base_url.trim() && draftHasKey(d) ? "ready" : "incomplete";
}

/** Danh sách model tĩnh của preset (ark / volc_tts); openai trả rỗng vì tải từ provider */
export function staticCatalogFor(
  presets: ProviderPreset[],
  d: Pick<ProviderDraft, "preset_id" | "protocol">,
): CatalogModel[] {
  const own = presets.find((p) => p.id === d.preset_id && p.protocol === d.protocol && p.catalog === "static");
  const byProtocol = presets.find((p) => p.protocol === d.protocol && p.catalog === "static");
  return (own ?? byProtocol)?.models ?? [];
}

/** Khoá duy nhất của một binding (provider + model đã chuẩn hoá) */
export function bindingKey(b: { channel_id: string; model: string }): string {
  return `${b.channel_id}::${normalizeModelName(b.model)}`;
}

/** Lý do binding tạm không dùng được; null = dùng được */
export function bindingProblem(
  b: ModelBinding,
  capability: Capability,
  providers: ProviderDraft[],
): BindingProblem | null {
  const p = providers.find((x) => x.id === b.channel_id);
  if (!p) return "missing_provider";
  if (!p.models.some((m) => normalizeModelName(m) === normalizeModelName(b.model))) return "model_not_enabled";
  if (modelCapability(p.protocol, b.model) !== capability) return "wrong_capability";
  const status = providerStatus(p);
  if (status === "disabled") return "provider_disabled";
  if (status === "incomplete") return "provider_incomplete";
  return null;
}

/** Model đã bật ở mọi provider, đúng năng lực */
export function modelOptionsFor(providers: ProviderDraft[], capability: Capability): ModelOption[] {
  const out: ModelOption[] = [];
  for (const p of providers) {
    const status = providerStatus(p);
    const seen = new Set<string>();
    for (const m of p.models) {
      const key = normalizeModelName(m);
      if (!key || seen.has(key) || modelCapability(p.protocol, m) !== capability) continue;
      seen.add(key);
      out.push({ channel_id: p.id, channel_name: p.name, model: m, status });
    }
  }
  return out;
}

/** Bật/tắt một model trong danh sách binding (mặc định weight 1) */
export function toggleBinding(
  list: ModelBinding[],
  option: { channel_id: string; model: string },
): ModelBinding[] {
  const key = bindingKey(option);
  if (list.some((b) => bindingKey(b) === key)) return list.filter((b) => bindingKey(b) !== key);
  return [...list, { channel_id: option.channel_id, model: option.model, weight: 1 }];
}

/** Đặt weight (số nguyên 1..100) cho binding có khoá `key` */
export function setBindingWeight(list: ModelBinding[], key: string, weight: number): ModelBinding[] {
  const w = Number.isFinite(weight) ? Math.min(100, Math.max(1, Math.round(weight))) : 1;
  return list.map((b) => (bindingKey(b) === key ? { ...b, weight: w } : b));
}

/** Thay danh sách của một slot; rỗng thì xoá khoá */
export function withSlot(b: FunctionBindings, cap: Capability, list: ModelBinding[]): FunctionBindings {
  const slots = { ...b.slots };
  if (list.length) slots[cap] = list;
  else delete slots[cap];
  return { ...b, slots };
}

/** Thay danh sách ghi đè của một chức năng; rỗng thì xoá khoá (= dùng slot) */
export function withOverride(b: FunctionBindings, functionId: string, list: ModelBinding[]): FunctionBindings {
  const overrides = { ...b.overrides };
  if (list.length) overrides[functionId] = list;
  else delete overrides[functionId];
  return { ...b, overrides };
}

/** Số slot năng lực đã gán ít nhất một model */
export function assignedSlotCount(b: FunctionBindings): number {
  return CAPABILITIES.filter((c) => (b.slots[c]?.length ?? 0) > 0).length;
}

/** Nhãn các nơi có binding thoả `match` ("Slot Ảnh", nhãn chức năng) */
function bindingUsages(
  b: FunctionBindings,
  catalog: FunctionInfo[],
  match: (x: ModelBinding) => boolean,
): string[] {
  const out: string[] = [];
  for (const cap of CAPABILITIES) {
    if ((b.slots[cap] ?? []).some(match)) out.push(`Slot ${CAPABILITY_LABELS[cap]}`);
  }
  for (const fn of catalog) {
    if ((b.overrides[fn.id] ?? []).some(match)) out.push(fn.label);
  }
  return out;
}

/** Nơi đang dùng provider */
export function providerUsages(b: FunctionBindings, catalog: FunctionInfo[], channelId: string): string[] {
  return bindingUsages(b, catalog, (x) => x.channel_id === channelId);
}

/** Nơi đang dùng một model của provider */
export function modelUsages(
  b: FunctionBindings,
  catalog: FunctionInfo[],
  channelId: string,
  model: string,
): string[] {
  const target = normalizeModelName(model);
  return bindingUsages(b, catalog, (x) => x.channel_id === channelId && normalizeModelName(x.model) === target);
}

/** Gộp id model, bỏ trống và trùng (không phân biệt hoa/thường), giữ thứ tự */
export function mergeModelIds(current: string[], added: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of [...current, ...added]) {
    const id = (raw || "").trim();
    const key = normalizeModelName(id);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(id);
  }
  return out;
}

/** Kiểm tra nháp gán chức năng — cùng câu chữ với validate_function_bindings ở backend */
export function validateBindingsDraft(
  b: FunctionBindings,
  providers: ProviderDraft[],
  catalog: FunctionInfo[],
): string[] {
  const errs: string[] = [];
  const check = (label: string, capability: Capability, items: ModelBinding[]) => {
    for (const item of items) {
      const p = providers.find((x) => x.id === item.channel_id);
      if (!p) {
        errs.push(`${label}: provider '${item.channel_id}' không tồn tại`);
        continue;
      }
      if (!p.models.some((m) => normalizeModelName(m) === normalizeModelName(item.model))) {
        errs.push(`${label}: model '${item.model}' chưa được bật ở provider ${p.name}`);
        continue;
      }
      if (modelCapability(p.protocol, item.model) !== capability) {
        errs.push(`${label}: model '${item.model}' không phải model ${CAPABILITY_LABELS[capability].toLowerCase()}`);
      }
    }
  };
  for (const cap of CAPABILITIES) check(`Slot ${CAPABILITY_LABELS[cap]}`, cap, b.slots[cap] ?? []);
  for (const [fid, items] of Object.entries(b.overrides)) {
    const fn = catalog.find((f) => f.id === fid);
    if (!fn) {
      errs.push(`Chức năng '${fid}' không tồn tại`);
      continue;
    }
    check(fn.label, fn.capability, items);
  }
  return [...new Set(errs)];
}

/** Kiểm tra form provider: id mới hợp lệ và chưa trùng, có tên, có Base URL (trừ volc_tts) */
export function validateProviderDraft(d: ProviderDraft, others: ProviderDraft[]): string[] {
  const errs: string[] = [];
  const id = d.id.trim();
  if (d.is_new) {
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(id)) {
      errs.push("ID chỉ gồm chữ thường, số, '-' hoặc '_' (tối đa 64 ký tự)");
    } else if (others.some((o) => o.id === id)) {
      errs.push(`ID '${id}' đã tồn tại`);
    }
  }
  if (!d.name.trim()) errs.push("Cần nhập tên provider");
  if (d.protocol !== "volc_tts" && !d.base_url.trim()) errs.push("Cần nhập Base URL");
  return errs;
}

/**
 * Origin (scheme + host + port, chữ thường) của Base URL — cùng cách so của `host_guard.same_host` ở backend;
 * chuỗi không phải URL tuyệt đối → "" (backend cũng coi mọi URL hỏng là cùng một origin rỗng)
 */
export function urlOrigin(value: string): string {
  try {
    return new URL((value || "").trim()).origin.toLowerCase();
  } catch {
    return "";
  }
}

/** Câu giải thích nút "Kiểm tra kết nối" theo protocol (ark / volc_tts chỉ kiểm tra có key) */
export const CONNECTION_TEST_HINTS: Record<ProviderProtocol, string> = {
  openai: "Gọi thử GET /models của provider bằng key này.",
  ark: "BytePlus ModelArk không có endpoint kiểm tra miễn phí: nút này chỉ xác nhận đã có key, chưa gọi thử provider.",
  volc_tts: "Seed Speech không có endpoint kiểm tra miễn phí: nút này chỉ xác nhận đã có key, chưa gọi thử provider.",
};

/** Câu hiển thị kết quả kiểm tra; ark / volc_tts thành công thì không nói "kết nối thành công" */
export function connectionTestLabel(protocol: ProviderProtocol, result: ProviderTestResult): string {
  if (!result.ok || protocol === "openai") return result.message;
  return "Đã có key (chưa gọi thử provider)";
}

/**
 * Lý do không cho lưu provider: lỗi form; model bị bỏ tick nhưng đang được gán (bản lưu hoặc bản nháp);
 * đổi host Base URL mà không nhập key mới (backend không dùng lại key đã lưu cho host khác).
 */
export function providerSaveBlockers(
  initial: ProviderDraft,
  draft: ProviderDraft,
  others: ProviderDraft[],
  bindingSets: FunctionBindings[],
  catalog: FunctionInfo[],
): string[] {
  const errs = validateProviderDraft(draft, others);
  if (!initial.is_new) {
    const kept = new Set(draft.models.map(normalizeModelName));
    for (const m of initial.models) {
      if (kept.has(normalizeModelName(m))) continue;
      const uses = [...new Set(bindingSets.flatMap((b) => modelUsages(b, catalog, initial.id, m)))];
      if (uses.length) {
        errs.push(`Model '${m}' đang được gán cho: ${uses.join(", ")}. Hãy đổi gán trước khi bỏ tick.`);
      }
    }
    const hostChanged = urlOrigin(initial.base_url) !== urlOrigin(draft.base_url);
    if (hostChanged && initial.has_api_key && !draft.clear_api_key && !draft.api_key_input.trim()) {
      errs.push("Đổi địa chỉ máy chủ (Base URL) thì phải nhập lại API key.");
    }
  }
  return errs;
}

/** Lý do không cho xoá provider (đang được gán ở bản lưu hoặc bản nháp); null = xoá được */
export function providerDeleteBlocker(
  id: string,
  bindingSets: FunctionBindings[],
  catalog: FunctionInfo[],
): string | null {
  const uses = [...new Set(bindingSets.flatMap((b) => providerUsages(b, catalog, id)))];
  return uses.length ? `Provider đang được gán cho: ${uses.join(", ")}. Hãy đổi gán trước khi xoá.` : null;
}

/** Danh sách nháp → body PATCH (key trống = giữ key cũ; nhập key mới thì bỏ cờ xoá) */
export function toProviderPatch(drafts: ProviderDraft[]): ProviderPatchItem[] {
  return drafts.map((d, idx) => {
    const key = d.api_key_input.trim();
    return {
      id: d.id.trim(),
      name: d.name.trim(),
      base_url: d.base_url.trim().replace(/\/+$/, ""),
      api_key: key || null,
      clear_api_key: d.clear_api_key && !key,
      protocol: d.protocol,
      models: mergeModelIds([], d.models),
      enabled: d.enabled,
      sort_order: idx,
    };
  });
}
```

- [ ] **Step 6: Chạy test, xác nhận qua**

Run: `cd admin && npm test`
Expected: PASS, `ℹ fail 0` (24 test).

- [ ] **Step 7: Lint + build**

Run: `cd admin && npm run lint && npm run build`
Expected: không lỗi (file mới chưa được import ở đâu là bình thường).

- [ ] **Step 8: Commit**

```bash
git add admin/package.json admin/src/api/routing.ts admin/src/lib/providerRouting.ts admin/tests/providerRouting.test.ts
git commit -m "feat(admin): kiểu API routing mới và hàm thuần cho màn Mô hình

Tách logic kiểm tra provider/binding thành hàm thuần có test để màn 2 cột dùng lại và khớp validation backend.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Admin — cột phải "Gán chức năng AI" (`FunctionBindingsPanel`, `BindingRow`, `ModelPickerDialog`, `ProviderIcon`)

**Files:**
- Create: `admin/src/components/settings/models/ProviderIcon.tsx`
- Create: `admin/src/components/settings/models/BindingRow.tsx`
- Create: `admin/src/components/settings/models/ModelPickerDialog.tsx`
- Create: `admin/src/components/settings/models/FunctionBindingsPanel.tsx`
- Modify: `admin/src/index.css` (thêm khối CSS cuối file)

**Interfaces:**
- Consumes: Task 1 (`ProviderDraft`, `CAPABILITIES`, `CAPABILITY_LABELS`, `CAPABILITY_HINTS`, `PROVIDER_STATUS_LABELS`, `BINDING_PROBLEM_LABELS`, `bindingKey`, `bindingProblem`, `modelOptionsFor`, `toggleBinding`, `setBindingWeight`, `withSlot`, `withOverride`, `assignedSlotCount`), kiểu `Capability`, `FunctionBindings`, `FunctionInfo`, `ModelBinding` từ `@/api/routing`; `AdminModal` (`@/components/admin/AdminModal`), `Button` (`@/components/ui/button`).
- Produces:
  ```tsx
  export function ProviderIcon(props: { provider?: Pick<ProviderDraft, "protocol" | "base_url" | "preset_id">; className?: string }): JSX.Element;
  export function BindingRow(props: { icon: ReactNode; title: string; description: string; capability: Capability; bindings: ModelBinding[]; providers: ProviderDraft[]; emptyLabel: string; emptyTone: "warn" | "muted"; actions: ReactNode; onRemove: (key: string) => void }): JSX.Element;
  export function ModelPickerDialog(props: { title: string; capability: Capability; providers: ProviderDraft[]; value: ModelBinding[]; onApply: (list: ModelBinding[]) => void; onClose: () => void }): JSX.Element;
  export function FunctionBindingsPanel(props: { providers: ProviderDraft[]; bindings: FunctionBindings; catalog: FunctionInfo[]; dirty: boolean; errors: string[]; onChange: (next: FunctionBindings) => void }): JSX.Element;
  ```

- [ ] **Step 1: `ProviderIcon.tsx`**

```tsx
import { Globe, Layers, Mic, Plug, Sparkles, type LucideIcon } from "lucide-react";
import type { ProviderDraft } from "@/lib/providerRouting";

type ProviderIconProps = {
  provider?: Pick<ProviderDraft, "protocol" | "base_url" | "preset_id">;
  className?: string;
};

// Chọn icon chung (không dùng logo thương hiệu) theo protocol / preset / base URL
function iconFor(provider: ProviderIconProps["provider"]): LucideIcon {
  if (!provider) return Plug;
  if (provider.protocol === "volc_tts") return Mic;
  if (provider.protocol === "ark") return Layers;
  if (provider.base_url.includes("openrouter")) return Globe;
  if (provider.base_url.includes("api.openai.com")) return Sparkles;
  return Plug;
}

/** Icon của provider trong danh sách và chip model */
export function ProviderIcon({ provider, className }: ProviderIconProps) {
  const Icon = iconFor(provider);
  return <Icon className={className} aria-hidden />;
}
```

- [ ] **Step 2: `BindingRow.tsx`**

```tsx
import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { Capability, ModelBinding } from "@/api/routing";
import {
  BINDING_PROBLEM_LABELS,
  bindingKey,
  bindingProblem,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";
import { ProviderIcon } from "@/components/settings/models/ProviderIcon";

type BindingRowProps = {
  icon: ReactNode;
  title: string;
  description: string;
  capability: Capability;
  bindings: ModelBinding[];
  providers: ProviderDraft[];
  emptyLabel: string;
  emptyTone: "warn" | "muted";
  actions: ReactNode;
  onRemove: (key: string) => void;
};

/** Một hàng slot/override: tiêu đề, chip "provider · model · ×", badge Chưa gán / N tạm không dùng được */
export function BindingRow({
  icon,
  title,
  description,
  capability,
  bindings,
  providers,
  emptyLabel,
  emptyTone,
  actions,
  onRemove,
}: BindingRowProps) {
  const problems = bindings.map((b) => bindingProblem(b, capability, providers));
  const broken = problems.filter(Boolean).length;
  return (
    <div className="settings-binding-row">
      <div className="settings-binding-icon">{icon}</div>
      <div className="min-w-0">
        <div className="settings-binding-head">
          <strong>{title}</strong>
          {bindings.length === 0 ? (
            <span className={cn("settings-binding-badge", emptyTone === "warn" ? "is-warn" : "is-muted")}>
              {emptyLabel}
            </span>
          ) : null}
          {broken > 0 ? <span className="settings-binding-badge is-muted">{broken} tạm không dùng được</span> : null}
        </div>
        <p className="settings-binding-desc">{description}</p>
        {bindings.length > 0 ? (
          <div className="settings-binding-chips">
            {bindings.map((b, i) => {
              const problem = problems[i];
              const provider = providers.find((p) => p.id === b.channel_id);
              return (
                <span
                  key={bindingKey(b)}
                  className={cn("settings-binding-chip", problem && "is-broken")}
                  title={problem ? BINDING_PROBLEM_LABELS[problem] : undefined}
                >
                  <ProviderIcon provider={provider} className="h-3.5 w-3.5 shrink-0" />
                  <span className="shrink-0">{provider?.name ?? b.channel_id}</span>
                  <span aria-hidden>·</span>
                  <span className="font-mono">{b.model}</span>
                  {b.weight > 1 ? <span className="settings-binding-chip-weight">×{b.weight}</span> : null}
                  <button type="button" aria-label={`Bỏ ${b.model}`} onClick={() => onRemove(bindingKey(b))}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
      <div className="settings-binding-actions">{actions}</div>
    </div>
  );
}
```

- [ ] **Step 3: `ModelPickerDialog.tsx`**

```tsx
import { useMemo, useState } from "react";
import type { Capability, ModelBinding } from "@/api/routing";
import { AdminModal } from "@/components/admin/AdminModal";
import { Button } from "@/components/ui/button";
import {
  CAPABILITY_LABELS,
  PROVIDER_STATUS_LABELS,
  bindingKey,
  modelOptionsFor,
  setBindingWeight,
  toggleBinding,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ModelPickerDialogProps = {
  title: string;
  capability: Capability;
  providers: ProviderDraft[];
  value: ModelBinding[];
  onApply: (list: ModelBinding[]) => void;
  onClose: () => void;
};

/** Hộp chọn nhiều model đúng năng lực (từ mọi provider) và đặt tỉ lệ chia luân phiên */
export function ModelPickerDialog({ title, capability, providers, value, onApply, onClose }: ModelPickerDialogProps) {
  /*
   * selected: danh sách binding đang chọn (khởi tạo từ value lúc mở)
   * query: ô tìm theo provider / model
   */
  const [selected, setSelected] = useState<ModelBinding[]>(value);
  const [query, setQuery] = useState("");

  const options = useMemo(() => modelOptionsFor(providers, capability), [providers, capability]);
  const q = query.trim().toLowerCase();
  const visible = options.filter((o) => !q || `${o.channel_name} ${o.model}`.toLowerCase().includes(q));
  const selectedByKey = new Map(selected.map((b) => [bindingKey(b), b]));
  const optionKeys = new Set(options.map((o) => bindingKey(o)));
  const orphans = selected.filter((b) => !optionKeys.has(bindingKey(b)));
  const capLabel = CAPABILITY_LABELS[capability].toLowerCase();

  return (
    <AdminModal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      size="lg"
      title={title}
      subtitle="Tick một hoặc nhiều model. Chọn nhiều thì các yêu cầu được chia luân phiên theo tỉ lệ."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            onClick={() => {
              onApply(selected);
              onClose();
            }}
          >
            Áp dụng ({selected.length})
          </Button>
        </>
      }
    >
      <input
        className="settings-input"
        placeholder="Tìm theo provider hoặc model"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {options.length === 0 ? (
        <p className="settings-empty-hint">
          Chưa có model {capLabel} nào được bật. Mở một provider ở cột trái và tick model trước.
        </p>
      ) : null}
      <div className="settings-model-catalog">
        {visible.map((o) => {
          const key = bindingKey(o);
          const current = selectedByKey.get(key);
          return (
            <div key={key} className={cn("settings-picker-row", current && "is-checked")}>
              <label className="settings-model-option min-w-0 flex-1">
                <input
                  type="checkbox"
                  checked={Boolean(current)}
                  onChange={() => setSelected((prev) => toggleBinding(prev, o))}
                />
                <span className="min-w-0">
                  <span className="block truncate font-mono text-xs">{o.model}</span>
                  <span className="settings-picker-provider">
                    {o.channel_name}
                    {o.status !== "ready" ? ` · ${PROVIDER_STATUS_LABELS[o.status]}` : ""}
                  </span>
                </span>
              </label>
              {current ? (
                <label className="settings-weight-field">
                  <span>Tỉ lệ</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    className="settings-input settings-weight-input"
                    value={current.weight}
                    onChange={(e) => setSelected((prev) => setBindingWeight(prev, key, Number(e.target.value)))}
                  />
                </label>
              ) : null}
            </div>
          );
        })}
        {orphans.map((b) => (
          <div key={bindingKey(b)} className="settings-picker-row is-checked">
            <label className="settings-model-option min-w-0 flex-1">
              <input type="checkbox" checked onChange={() => setSelected((prev) => toggleBinding(prev, b))} />
              <span className="min-w-0">
                <span className="block truncate font-mono text-xs">{b.model}</span>
                <span className="settings-picker-provider">{b.channel_id} · không còn được bật, bỏ tick để gỡ</span>
              </span>
            </label>
          </div>
        ))}
      </div>
    </AdminModal>
  );
}
```

- [ ] **Step 4: `FunctionBindingsPanel.tsx`**

```tsx
import { useState } from "react";
import { ChevronRight, FileText, Film, Image as ImageIcon, Mic, type LucideIcon } from "lucide-react";
import type { Capability, FunctionBindings, FunctionInfo, ModelBinding } from "@/api/routing";
import { Button } from "@/components/ui/button";
import {
  CAPABILITIES,
  CAPABILITY_HINTS,
  CAPABILITY_LABELS,
  assignedSlotCount,
  bindingKey,
  withOverride,
  withSlot,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";
import { BindingRow } from "@/components/settings/models/BindingRow";
import { ModelPickerDialog } from "@/components/settings/models/ModelPickerDialog";

const CAP_ICONS: Record<Capability, LucideIcon> = { text: FileText, image: ImageIcon, video: Film, audio: Mic };

/** Hàng đang mở hộp chọn model: một slot năng lực hoặc một chức năng ghi đè */
type PickerTarget = { kind: "slot"; capability: Capability } | { kind: "override"; fn: FunctionInfo };

type FunctionBindingsPanelProps = {
  providers: ProviderDraft[];
  bindings: FunctionBindings;
  catalog: FunctionInfo[];
  dirty: boolean;
  errors: string[];
  onChange: (next: FunctionBindings) => void;
};

/** Cột phải tab "Mô hình": 4 slot năng lực + nhóm ghi đè theo chức năng */
export function FunctionBindingsPanel({ providers, bindings, catalog, dirty, errors, onChange }: FunctionBindingsPanelProps) {
  /*
   * picker: hàng đang chọn model (null = đóng)
   * overridesOpen: nhóm "Ghi đè theo chức năng" đang mở (mặc định mở nếu đã có ghi đè)
   */
  const [picker, setPicker] = useState<PickerTarget | null>(null);
  const [overridesOpen, setOverridesOpen] = useState(() => Object.keys(bindings.overrides).length > 0);
  const assigned = assignedSlotCount(bindings);

  // Danh sách binding hiện tại của một hàng
  function listOf(t: PickerTarget): ModelBinding[] {
    return t.kind === "slot" ? bindings.slots[t.capability] ?? [] : bindings.overrides[t.fn.id] ?? [];
  }

  // Ghi danh sách mới cho một hàng
  function apply(t: PickerTarget, list: ModelBinding[]) {
    onChange(t.kind === "slot" ? withSlot(bindings, t.capability, list) : withOverride(bindings, t.fn.id, list));
  }

  // Gỡ một chip khỏi hàng
  function removeFrom(t: PickerTarget, key: string) {
    apply(t, listOf(t).filter((b) => bindingKey(b) !== key));
  }

  return (
    <section className="settings-bindings-panel">
      <header className="settings-bindings-header">
        <div className="min-w-0">
          <h3 className="settings-panel-title">Gán chức năng AI</h3>
          <p className="settings-panel-desc">
            Mỗi chức năng chạy bằng model bạn chọn ở đây. Chọn nhiều model thì các yêu cầu được chia luân phiên.
          </p>
        </div>
        <div className="settings-bindings-progress">
          <span>{assigned}/4 slot đã gán</span>
          <div className="settings-progress-track">
            <div className="settings-progress-fill" style={{ width: `${(assigned / 4) * 100}%` }} />
          </div>
          {dirty ? <em>Có thay đổi chưa lưu</em> : null}
        </div>
      </header>

      {errors.length > 0 ? (
        <ul className="settings-bindings-errors" role="alert">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}

      <div className="settings-binding-list">
        {CAPABILITIES.map((cap) => {
          const Icon = CAP_ICONS[cap];
          const target: PickerTarget = { kind: "slot", capability: cap };
          const list = listOf(target);
          return (
            <BindingRow
              key={cap}
              icon={<Icon className="h-4 w-4" />}
              title={CAPABILITY_LABELS[cap]}
              description={CAPABILITY_HINTS[cap]}
              capability={cap}
              bindings={list}
              providers={providers}
              emptyLabel="Chưa gán"
              emptyTone="warn"
              onRemove={(key) => removeFrom(target, key)}
              actions={
                <Button size="sm" variant="outline" onClick={() => setPicker(target)}>
                  {list.length ? "Đổi model" : "Chọn model"}
                </Button>
              }
            />
          );
        })}
      </div>

      <div className="settings-overrides">
        <button
          type="button"
          className="settings-overrides-toggle"
          aria-expanded={overridesOpen}
          onClick={() => setOverridesOpen((v) => !v)}
        >
          <ChevronRight className={cn("h-4 w-4 transition-transform", overridesOpen && "rotate-90")} />
          Ghi đè theo chức năng
          <span className="settings-overrides-count">
            {Object.keys(bindings.overrides).length}/{catalog.length}
          </span>
        </button>
        {overridesOpen ? (
          <div className="settings-binding-list">
            {catalog.map((fn) => {
              const Icon = CAP_ICONS[fn.capability];
              const target: PickerTarget = { kind: "override", fn };
              const list = listOf(target);
              return (
                <BindingRow
                  key={fn.id}
                  icon={<Icon className="h-4 w-4" />}
                  title={fn.label}
                  description={fn.description}
                  capability={fn.capability}
                  bindings={list}
                  providers={providers}
                  emptyLabel={`Dùng slot ${CAPABILITY_LABELS[fn.capability]}`}
                  emptyTone="muted"
                  onRemove={(key) => removeFrom(target, key)}
                  actions={
                    <>
                      <Button size="sm" variant="outline" onClick={() => setPicker(target)}>
                        {list.length ? "Đổi" : "Chọn"}
                      </Button>
                      {list.length ? (
                        <Button size="sm" variant="ghost" onClick={() => apply(target, [])}>
                          Bỏ ghi đè
                        </Button>
                      ) : null}
                    </>
                  }
                />
              );
            })}
          </div>
        ) : null}
      </div>

      {picker ? (
        <ModelPickerDialog
          title={
            picker.kind === "slot"
              ? `Chọn model cho slot ${CAPABILITY_LABELS[picker.capability]}`
              : `Ghi đè: ${picker.fn.label}`
          }
          capability={picker.kind === "slot" ? picker.capability : picker.fn.capability}
          providers={providers}
          value={listOf(picker)}
          onApply={(list) => apply(picker, list)}
          onClose={() => setPicker(null)}
        />
      ) : null}
    </section>
  );
}
```

- [ ] **Step 5: CSS — thêm vào cuối `admin/src/index.css`**

```css
/* ===== Tab "Mô hình": cột phải gán chức năng AI ===== */
.settings-bindings-panel {
  background: #fff;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius);
  padding: 14px;
  box-shadow: var(--admin-shadow);
  min-width: 0;
}
.settings-bindings-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.settings-bindings-progress {
  min-width: 160px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--admin-muted);
}
.settings-bindings-progress em {
  font-style: normal;
  color: #c2410c;
}
.settings-progress-track {
  height: 6px;
  border-radius: 999px;
  background: #eef2f6;
  overflow: hidden;
}
.settings-progress-fill {
  height: 100%;
  background: var(--admin-accent);
  transition: width 0.2s;
}
.settings-bindings-errors {
  margin: 10px 0 0;
  padding: 8px 12px 8px 28px;
  border-radius: 10px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 12px;
  list-style: disc;
}
.settings-binding-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.settings-binding-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: #fafbfc;
}
.settings-binding-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--admin-border);
  color: var(--admin-forest);
}
.settings-binding-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
}
.settings-binding-desc {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--admin-muted);
}
.settings-binding-badge {
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
}
.settings-binding-badge.is-warn {
  background: #fff7ed;
  color: #c2410c;
}
.settings-binding-badge.is-muted {
  background: #f4f4f5;
  color: #71717a;
}
.settings-binding-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.settings-binding-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 3px 4px 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--admin-border);
  background: #fff;
  font-size: 12px;
}
.settings-binding-chip .font-mono {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.settings-binding-chip.is-broken {
  border-style: dashed;
  color: #a1a1aa;
}
.settings-binding-chip button {
  display: inline-flex;
  padding: 2px;
  border-radius: 999px;
  color: var(--admin-muted);
}
.settings-binding-chip button:hover {
  background: #fee2e2;
  color: #dc2626;
}
.settings-binding-chip-weight {
  color: var(--admin-forest);
  font-weight: 600;
}
.settings-binding-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}
.settings-overrides {
  margin-top: 14px;
  border-top: 1px solid var(--admin-border);
  padding-top: 10px;
}
.settings-overrides-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-text);
}
.settings-overrides-count {
  font-weight: 400;
  font-size: 12px;
  color: var(--admin-muted);
}
.settings-picker-row {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
}
.settings-picker-row.is-checked {
  background: #fff;
}
.settings-picker-provider {
  display: block;
  font-size: 11px;
  color: var(--admin-muted);
}
.settings-weight-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--admin-muted);
  padding-right: 6px;
}
.settings-weight-input {
  width: 72px;
}
@media (max-width: 560px) {
  .settings-binding-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Lint + build + test**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi; test Task 1 vẫn PASS.

- [ ] **Step 7: Commit**

```bash
git add admin/src/components/settings/models admin/src/index.css
git commit -m "feat(admin): cột Gán chức năng AI với 4 slot, ghi đè và hộp chọn model

Admin chọn nhiều model theo năng lực kèm tỉ lệ chia luân phiên, thấy ngay binding nào tạm không dùng được.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Admin — hộp thoại provider (`ProviderDialog`, `ProviderModelsSection`)

**Files:**
- Create: `admin/src/components/settings/models/ProviderModelsSection.tsx`
- Create: `admin/src/components/settings/models/ProviderDialog.tsx`
- Modify: `admin/src/index.css` (thêm khối CSS cuối file)

**Interfaces:**
- Consumes: Task 1 (`ProviderDraft`, `CAPABILITIES`, `CAPABILITY_LABELS`, `modelCapability`, `mergeModelIds`, `normalizeModelName`, `staticCatalogFor`, `draftFromPreset`, `providerSaveBlockers`, `providerDeleteBlocker`, `urlOrigin`, `CONNECTION_TEST_HINTS`, `connectionTestLabel`, `testProviderConnection`, `listProviderModels`), `AdminModal`, `AdminConfirmDialog` (`@/components/admin/AdminConfirmDialog`), `LabeledControl` (`@/components/settings/SettingsPanel`), `Switch` (`@/components/ui/switch`), `Button`, `toast` (sonner).
- Produces:
  ```tsx
  export function ProviderModelsSection(props: { draft: ProviderDraft; staticModels: CatalogModel[]; onModelsChange: (models: string[]) => void }): JSX.Element;
  export function ProviderDialog(props: {
    initial: ProviderDraft; presets: ProviderPreset[]; providers: ProviderDraft[];
    bindingSets: FunctionBindings[]; catalog: FunctionInfo[];
    onClose: () => void;
    onSave: (draft: ProviderDraft) => Promise<string | null>;   // null = đã lưu
    onDelete: (id: string) => Promise<string | null>;
  }): JSX.Element;
  ```

- [ ] **Step 1: `ProviderModelsSection.tsx`**

```tsx
import { useMemo, useState } from "react";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { listProviderModels, type Capability, type CatalogModel } from "@/api/routing";
import { Button } from "@/components/ui/button";
import {
  CAPABILITIES,
  CAPABILITY_LABELS,
  mergeModelIds,
  modelCapability,
  normalizeModelName,
  type ProviderDraft,
} from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ProviderModelsSectionProps = {
  draft: ProviderDraft;
  staticModels: CatalogModel[];
  onModelsChange: (models: string[]) => void;
};

/** Phần "Model bật": openai tải danh sách từ provider, ark/volc_tts dùng danh sách tĩnh; luôn thêm ID thủ công được */
export function ProviderModelsSection({ draft, staticModels, onModelsChange }: ProviderModelsSectionProps) {
  /*
   * remote: danh sách tải từ provider (openai); loading/error: trạng thái tải
   * query/capFilter: lọc theo tên và năng lực; manual: ô nhập ID thủ công
   */
  const [remote, setRemote] = useState<CatalogModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [capFilter, setCapFilter] = useState<Capability | "all">("all");
  const [manual, setManual] = useState("");

  const enabled = useMemo(() => new Set(draft.models.map(normalizeModelName)), [draft.models]);

  // Gộp danh mục (tải về hoặc tĩnh) với model đã bật nhưng không có trong danh mục (ID thủ công)
  const items = useMemo(() => {
    const base = draft.protocol === "openai" ? remote : staticModels;
    const known = new Set(base.map((m) => normalizeModelName(m.id)));
    const extra = draft.models.filter((m) => !known.has(normalizeModelName(m))).map((id) => ({ id, label: id }));
    return [...base, ...extra];
  }, [draft.protocol, draft.models, remote, staticModels]);

  const q = query.trim().toLowerCase();
  const visible = items.filter((m) => {
    const cap = modelCapability(draft.protocol, m.id);
    if (capFilter !== "all" && cap !== capFilter) return false;
    return !q || `${m.id} ${m.label ?? ""}`.toLowerCase().includes(q);
  });

  // Tải danh sách model từ provider (dùng key đang nhập, hoặc key đã lưu nếu provider đã có)
  async function fetchRemote() {
    setLoading(true);
    setError("");
    try {
      const models = await listProviderModels({
        channel_id: draft.is_new ? null : draft.id,
        protocol: draft.protocol,
        base_url: draft.base_url,
        api_key: draft.api_key_input.trim() || null,
      });
      setRemote(models);
      if (models.length === 0) setError("Provider không trả model nào");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách model");
    } finally {
      setLoading(false);
    }
  }

  // Bật/tắt một model
  function toggle(id: string) {
    const key = normalizeModelName(id);
    onModelsChange(
      enabled.has(key) ? draft.models.filter((m) => normalizeModelName(m) !== key) : mergeModelIds(draft.models, [id]),
    );
  }

  // Thêm ID thủ công (vd. endpoint ep-…)
  function addManual() {
    const id = manual.trim();
    if (!id) return;
    onModelsChange(mergeModelIds(draft.models, [id]));
    setManual("");
  }

  return (
    <div className="settings-provider-models">
      <div className="settings-provider-models-head">
        <strong>Model bật</strong>
        <span className="settings-model-count">Đã bật {draft.models.length} model</span>
        {draft.protocol === "openai" ? (
          <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void fetchRemote()}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Tải danh sách
          </Button>
        ) : null}
      </div>
      {error ? <p className="settings-provider-models-error">{error}</p> : null}

      <div className="settings-model-cap-row">
        {(["all", ...CAPABILITIES] as const).map((cap) => (
          <button
            key={cap}
            type="button"
            className={cn("settings-model-cap-chip", capFilter === cap && "is-active")}
            onClick={() => setCapFilter(cap)}
          >
            {cap === "all" ? "Tất cả" : CAPABILITY_LABELS[cap]}
          </button>
        ))}
      </div>
      <div className="settings-model-search">
        <input
          className="settings-input"
          placeholder="Tìm model"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="settings-model-catalog">
        {visible.length === 0 ? (
          <p className="settings-empty-hint">
            {draft.protocol === "openai" && remote.length === 0
              ? "Bấm “Tải danh sách” để lấy model từ provider, hoặc thêm ID thủ công bên dưới."
              : "Không có model khớp bộ lọc."}
          </p>
        ) : null}
        {visible.map((m) => {
          const cap = modelCapability(draft.protocol, m.id);
          const checked = enabled.has(normalizeModelName(m.id));
          return (
            <label key={m.id} className={cn("settings-model-option", checked && "is-checked")}>
              <input type="checkbox" checked={checked} onChange={() => toggle(m.id)} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-xs">{m.id}</span>
                {m.label && m.label !== m.id ? <span className="settings-picker-provider">{m.label}</span> : null}
              </span>
              <span className={cn("settings-cap-tag", `is-${cap}`)}>{CAPABILITY_LABELS[cap]}</span>
            </label>
          );
        })}
      </div>

      <div className="settings-model-manual">
        <input
          className="settings-input"
          placeholder="Thêm ID thủ công, vd. ep-20260923-abc"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addManual();
            }
          }}
        />
        <Button type="button" size="sm" variant="outline" onClick={addManual}>
          <Plus className="h-3.5 w-3.5" />
          Thêm
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `ProviderDialog.tsx`**

```tsx
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

/** Hộp thoại tạo/sửa provider: preset, key, kiểm tra kết nối, model bật, lưu ngay, xoá (có xác nhận) */
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
          channel_id: draft.is_new ? null : draft.id,
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
    toast.success(`Đã lưu provider ${draft.name.trim()}`);
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
    toast.success(`Đã xoá provider ${initial.name}`);
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
        title={draft.is_new ? "Thêm provider" : `Provider: ${initial.name}`}
        subtitle="Provider lưu ngay khi bấm Lưu. Key được mã hoá khi lưu vào DB."
        footer={
          <>
            {!draft.is_new ? (
              <Button variant="destructive" className="mr-auto" disabled={Boolean(busy)} onClick={askDelete}>
                Xoá provider
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
            <LabeledControl label="Mẫu provider" className="settings-field-span-full">
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
                onChange={(e) => patch({ api_key_input: e.target.value })}
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
            <strong>Bật provider</strong>
            <span>Tắt thì mọi model của provider này tạm không được dùng; phần gán chức năng vẫn giữ nguyên</span>
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
        title={`Xoá provider ${initial.name}?`}
        description="Key và danh sách model của provider sẽ bị xoá. Thao tác này không hoàn tác được."
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
```

Ghi chú cho implementer: `AdminConfirmDialog` render một `AdminModal` thứ hai; Radix Dialog cho phép lồng. Nếu `settings-field-span-full` chưa có trong `index.css` (đã dùng ở `PaymentSettingsPanel` dòng 546), giữ nguyên — class đó đã tồn tại.

- [ ] **Step 3: CSS — thêm vào cuối `admin/src/index.css`**

```css
/* ===== Tab "Mô hình": hộp thoại provider ===== */
.settings-provider-test {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.settings-provider-test-result {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.settings-provider-test-result.is-ok {
  color: #15803d;
}
.settings-provider-test-result.is-fail {
  color: #dc2626;
}
.settings-provider-models {
  margin-top: 14px;
  border-top: 1px solid var(--admin-border);
  padding-top: 12px;
}
.settings-provider-models-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
}
.settings-provider-models-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #dc2626;
}
.settings-provider-dialog-error {
  margin: 12px 0 0;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 12px;
}
```

- [ ] **Step 4: Lint + build + test**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/settings/models admin/src/index.css
git commit -m "feat(admin): hộp thoại provider với preset, kiểm tra kết nối và chọn model bật

Provider được tạo/sửa/xoá ngay trong hộp thoại, chặn bỏ tick hoặc xoá khi đang được gán để tránh lỗi lưu khó hiểu.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Admin — ghép tab "Mô hình" (`useRoutingSettings`, `ProviderSidebar`, `ModelsSettingsPanel`) và xoá màn TokenFree cũ

**Files:**
- Create: `admin/src/hooks/useRoutingSettings.ts`
- Create: `admin/src/components/settings/models/ProviderSidebar.tsx`
- Create: `admin/src/components/settings/models/ModelsSettingsPanel.tsx`
- Modify: `admin/src/pages/SettingsPage.tsx`
- Modify: `admin/src/api/client.ts` (xoá kiểu routing cũ)
- Modify: `admin/src/index.css` (thêm khối CSS cuối file)
- Delete: `admin/src/components/settings/RoutingSettingsPanel.tsx`, `admin/src/lib/tokenfreeRecommendedModels.ts`

**Interfaces:**
- Consumes: Task 1 (`fetchRoutingSettings`, `saveRoutingSettings`, `draftFromProvider`, `draftFromPreset`, `draftHasKey`, `providerStatus`, `PROVIDER_STATUS_LABELS`, `validateBindingsDraft`, `toProviderPatch`, `BLANK_PRESET`), Task 2 (`FunctionBindingsPanel`, `ProviderIcon`), Task 3 (`ProviderDialog`), `SettingsTabShell` / `SettingsLoading` (`@/components/settings/SettingsPanel`).
- Produces:
  ```ts
  export function useRoutingSettings(): {
    data: AdminRoutingSettings | null; bindings: FunctionBindings; dirty: boolean; loading: boolean; saving: boolean; saveError: string;
    load: () => Promise<void>; setBindings: (next: FunctionBindings) => void; saveBindings: () => Promise<void>;
    saveProviders: (providers: ProviderPatchItem[]) => Promise<string | null>;
  };
  export function ProviderSidebar(props: { providers: ProviderDraft[]; onOpen: (p: ProviderDraft) => void; onCreate: () => void }): JSX.Element;
  export function ModelsSettingsPanel(): JSX.Element;
  ```

- [ ] **Step 1: `useRoutingSettings.ts`**

```ts
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
        return err instanceof Error ? err.message : "Không lưu được provider";
      }
    },
    [dirty],
  );

  return { data, bindings, dirty, loading, saving, saveError, load, setBindings, saveBindings, saveProviders };
}
```

- [ ] **Step 2: `ProviderSidebar.tsx`**

```tsx
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProviderIcon } from "@/components/settings/models/ProviderIcon";
import { PROVIDER_STATUS_LABELS, draftHasKey, providerStatus, type ProviderDraft } from "@/lib/providerRouting";
import { cn } from "@/lib/utils";

type ProviderSidebarProps = {
  providers: ProviderDraft[];
  onOpen: (p: ProviderDraft) => void;
  onCreate: () => void;
};

/** Cột trái: danh sách provider (icon, tên, "1 key"/"Chưa có key", chấm trạng thái) và nút thêm */
export function ProviderSidebar({ providers, onOpen, onCreate }: ProviderSidebarProps) {
  return (
    <aside className="settings-provider-sidebar">
      <div className="settings-provider-sidebar-head">
        <h3 className="settings-panel-title">Provider</h3>
        <span className="settings-panel-desc">{providers.length} provider</span>
      </div>
      {providers.length === 0 ? (
        <p className="settings-empty-hint">Chưa có provider nào. Thêm OpenAI hoặc BytePlus để bắt đầu.</p>
      ) : null}
      <ul className="settings-provider-list">
        {providers.map((p) => {
          const status = providerStatus(p);
          return (
            <li key={p.id}>
              <button type="button" className="settings-provider-item" onClick={() => onOpen(p)}>
                <span className="settings-provider-icon">
                  <ProviderIcon provider={p} className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-[13px]">{p.name}</strong>
                  <span className="settings-provider-sub">
                    {draftHasKey(p) ? "1 key" : "Chưa có key"} · {p.models.length} model
                  </span>
                </span>
                <span
                  className={cn("settings-provider-dot", `is-${status}`)}
                  title={PROVIDER_STATUS_LABELS[status]}
                  aria-label={PROVIDER_STATUS_LABELS[status]}
                />
              </button>
            </li>
          );
        })}
      </ul>
      <Button variant="outline" size="sm" className="w-full" onClick={onCreate}>
        <Plus className="h-4 w-4" />
        Thêm provider
      </Button>
    </aside>
  );
}
```

- [ ] **Step 3: `ModelsSettingsPanel.tsx`**

```tsx
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { SettingsLoading, SettingsTabShell } from "@/components/settings/SettingsPanel";
import { FunctionBindingsPanel } from "@/components/settings/models/FunctionBindingsPanel";
import { ProviderDialog } from "@/components/settings/models/ProviderDialog";
import { ProviderSidebar } from "@/components/settings/models/ProviderSidebar";
import { useRoutingSettings } from "@/hooks/useRoutingSettings";
import {
  BLANK_PRESET,
  draftFromPreset,
  draftFromProvider,
  toProviderPatch,
  validateBindingsDraft,
  type ProviderDraft,
} from "@/lib/providerRouting";

/** Tab "Mô hình": cột trái provider (lưu ngay trong hộp thoại), cột phải gán chức năng (lưu bằng nút của trang) */
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

  if (routing.loading || !routing.data) {
    return <SettingsLoading label="Đang tải cấu hình mô hình…" />;
  }

  const presets = routing.data.presets.length ? routing.data.presets : [BLANK_PRESET];
  const savedBindings = routing.data.function_bindings;
  const errors = Array.from(new Set([...draftErrors, ...(routing.saveError ? [routing.saveError] : [])]));

  // Lưu một provider: thay/ thêm vào danh sách rồi PATCH toàn bộ
  function handleSaveProvider(draft: ProviderDraft): Promise<string | null> {
    const next = draft.is_new ? [...providers, draft] : providers.map((p) => (p.id === draft.id ? draft : p));
    return routing.saveProviders(toProviderPatch(next));
  }

  // Xoá một provider: PATCH danh sách không còn provider đó
  function handleDeleteProvider(id: string): Promise<string | null> {
    return routing.saveProviders(toProviderPatch(providers.filter((p) => p.id !== id)));
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
```

- [ ] **Step 4: CSS layout — thêm vào cuối `admin/src/index.css`**

```css
/* ===== Tab "Mô hình": bố cục 2 cột + cột trái provider ===== */
.settings-providers-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
@media (max-width: 900px) {
  .settings-providers-layout {
    grid-template-columns: 1fr;
  }
}
.settings-provider-sidebar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius);
  padding: 14px;
  box-shadow: var(--admin-shadow);
}
.settings-provider-sidebar-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.settings-provider-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.settings-provider-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.settings-provider-item:hover {
  border-color: rgba(31, 92, 72, 0.35);
  background: #f8fbf9;
}
.settings-provider-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--admin-accent-ring);
}
.settings-provider-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--admin-accent-soft);
  color: var(--admin-forest);
  flex-shrink: 0;
}
.settings-provider-sub {
  display: block;
  font-size: 11px;
  color: var(--admin-muted);
}
.settings-provider-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.settings-provider-dot.is-ready {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.settings-provider-dot.is-incomplete {
  background: #a1a1aa;
}
.settings-provider-dot.is-disabled {
  background: #ef4444;
}
```

- [ ] **Step 5: `SettingsPage.tsx` dùng panel mới**

Thay dòng import:

```tsx
import { RoutingSettingsPanel } from "@/components/settings/RoutingSettingsPanel";
```

bằng:

```tsx
import { ModelsSettingsPanel } from "@/components/settings/models/ModelsSettingsPanel";
```

Trong `TABS` đổi `{ id: "routing", label: "模型" },` thành `{ id: "routing", label: "Mô hình" },`.

Thay `{tab === "routing" ? <RoutingSettingsPanel /> : null}` bằng `{tab === "routing" ? <ModelsSettingsPanel /> : null}`.

Thay câu mô tả trong `SettingsPageHeader`:

```tsx
          TokenFree API Key、运行参数、OSS / 银行转账收款 / 汇率与计费与站点配置；密钥加密存库，留空保存不修改。
```

bằng:

```tsx
          模型服务商与功能分配、运行参数、OSS / 银行转账收款 / 汇率与计费与站点配置；密钥加密存库，留空保存不修改。
```

- [ ] **Step 6: Xoá file cũ và kiểu cũ**

```bash
git rm admin/src/components/settings/RoutingSettingsPanel.tsx admin/src/lib/tokenfreeRecommendedModels.ts
```

Trong `admin/src/api/client.ts` xoá nguyên các khối kiểu `AdminRoutingChannel`, `AdminLogicalModelBinding`, `AdminLogicalModel`, `AdminDefaultModels`, `AdminRoutingSettings` (đoạn từ `export type AdminRoutingChannel = {` tới hết `export type AdminRoutingSettings = { … };`, ngay trước `export type AdminTemplate`). Giữ `ModelCapabilityReadiness`.

Run: `cd admin && grep -rn "AdminRoutingChannel\|AdminLogicalModel\|AdminDefaultModels\|RoutingSettingsPanel\|tokenfreeRecommendedModels" src`
Expected: không có kết quả.

- [ ] **Step 7: Lint + build + test**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 8: Commit**

```bash
git add -A admin/src
git commit -m "feat(admin): tab Mô hình 2 cột thay màn cấu hình TokenFree cũ

Admin thêm nhiều provider và gán model cho 4 slot năng lực trên một màn; bỏ màn cũ khoá cứng base URL TokenFree và danh sách model gợi ý viết tay.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Admin — bảng giá `provider_rates` trong tab thanh toán (theo hợp đồng Plan B)

**Files:**
- Create: `admin/src/api/providerRates.ts`
- Create: `admin/src/lib/providerRates.ts`
- Create: `admin/tests/providerRates.test.ts`
- Create: `admin/src/hooks/useProviderRates.ts`
- Create: `admin/src/components/settings/ProviderRatesEditor.tsx`
- Modify: `admin/src/components/settings/PaymentSettingsPanel.tsx`
- Modify: `admin/src/api/client.ts` (bỏ `billing_kie_fen_per_credit`)

**Interfaces:**
- Consumes: hợp đồng Plan B §1–§2 (`GET/PUT /api/admin/settings/billing/model-rates`), `api` (`@/api/client`), `useCurrency` (`@/lib/currency`), `AdminConfirmDialog`, `SettingsPanel`.
- Produces:
  ```ts
  // @/api/providerRates
  export type RateUnit = "per_image" | "per_m_tokens" | "per_m_output_tokens" | "per_m_input_output" | "per_m_chars";
  export type ProviderRateRow = { pattern: string; unit: RateUnit; usd: number; usd_out: number | null; note: string };
  export type RateUnitOption = { id: RateUnit; label: string };
  export type UnpricedModel = { channel_id: string; model: string; capability: string };
  export type ProviderRatesOut = { items: ProviderRateRow[]; defaults: ProviderRateRow[]; units: RateUnitOption[]; unpriced_models: UnpricedModel[]; usd_cny: number; updated_at?: string | null };
  export function fetchProviderRates(): Promise<ProviderRatesOut>;
  export function saveProviderRates(items: ProviderRateRow[]): Promise<ProviderRatesOut>;
  // @/lib/providerRates
  export const RATE_UNIT_SUFFIX: Record<RateUnit, string>;
  export function rateFenPreview(usd: number, usdCny: number): number;
  export function withUnit(row: ProviderRateRow, unit: RateUnit): ProviderRateRow;
  export function moveRow<T>(rows: T[], index: number, delta: -1 | 1): T[];
  export function emptyRateRow(): ProviderRateRow;
  export function rowForUnpriced(m: UnpricedModel): ProviderRateRow;
  export function pendingUnpriced(unpriced: UnpricedModel[], rows: ProviderRateRow[]): UnpricedModel[];
  // @/hooks/useProviderRates
  export function useProviderRates(): { data; rows; dirty; loading; loadError; saveError; load; setRows; resetToDefaults; save: () => Promise<boolean> };
  // ProviderRatesEditor
  export function ProviderRatesEditor(props: { rows; units; unpriced; usdCny; loading; loadError; saveError; onChange; onReset; onReload }): JSX.Element;
  ```

- [ ] **Step 1: Kiểm tra Plan B đã chạy**

Run:

```bash
cd backend && grep -n '"/settings/billing/model-rates"' app/api/admin/settings.py && test -f app/services/billing/provider_rates_admin.py && echo PLAN_B_OK; grep -rn "upstream-usage\|daily/sync\|tokenfree/quota" app/api/admin/ || echo NO_OLD_ENDPOINTS
```

Expected: hai dòng route model-rates (GET và PUT), `PLAN_B_OK`, `NO_OLD_ENDPOINTS`. Khác → **dừng task, báo BLOCKED "Plan B chưa chạy"**.

- [ ] **Step 2: Viết test thất bại `admin/tests/providerRates.test.ts`**

```ts
/** Hàm thuần bảng giá provider_rates: xem trước fen, đổi đơn vị, đổi thứ tự, dòng cho model chưa có giá. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyRateRow,
  moveRow,
  pendingUnpriced,
  rateFenPreview,
  rowForUnpriced,
  withUnit,
} from "../src/lib/providerRates.ts";

test("rateFenPreview matches backend rounding", () => {
  assert.equal(rateFenPreview(0.045, 7), 32);
  assert.equal(rateFenPreview(0.07, 7), 49);
  assert.equal(rateFenPreview(1, 7), 700);
  assert.equal(rateFenPreview(0, 7), 0);
  assert.equal(rateFenPreview(-1, 7), 0);
  assert.equal(rateFenPreview(0.0000001, 7), 1);
  assert.equal(rateFenPreview(1, 0), 0);
});

test("withUnit clears usd_out except for input/output unit", () => {
  const row = { pattern: "gpt-5.6-sol", unit: "per_m_input_output" as const, usd: 4, usd_out: 20, note: "" };
  assert.equal(withUnit(row, "per_m_tokens").usd_out, null);
  assert.equal(withUnit({ ...row, usd_out: null }, "per_m_input_output").usd_out, 0);
  assert.equal(withUnit(row, "per_m_input_output").usd_out, 20);
});

test("moveRow swaps neighbours and clamps", () => {
  assert.deepEqual(moveRow(["a", "b", "c"], 1, -1), ["b", "a", "c"]);
  assert.deepEqual(moveRow(["a", "b", "c"], 1, 1), ["a", "c", "b"]);
  assert.deepEqual(moveRow(["a", "b"], 0, -1), ["a", "b"]);
  assert.deepEqual(moveRow(["a", "b"], 1, 1), ["a", "b"]);
});

test("rowForUnpriced guesses unit by capability", () => {
  assert.equal(rowForUnpriced({ channel_id: "byteplus", model: "ep-1", capability: "image" }).unit, "per_image");
  assert.equal(rowForUnpriced({ channel_id: "byteplus", model: "ep-2", capability: "video" }).unit, "per_m_tokens");
  assert.equal(rowForUnpriced({ channel_id: "openai", model: "tts-x", capability: "audio" }).unit, "per_m_chars");
  const text = rowForUnpriced({ channel_id: "openai", model: "gpt-x", capability: "text" });
  assert.equal(text.unit, "per_m_input_output");
  assert.equal(text.usd_out, 0);
  assert.equal(text.pattern, "gpt-x");
  assert.equal(text.note, "openai");
});

test("pendingUnpriced hides models that already have an exact row", () => {
  const unpriced = [
    { channel_id: "b", model: "EP-1", capability: "image" },
    { channel_id: "b", model: "ep-2", capability: "image" },
  ];
  assert.deepEqual(
    pendingUnpriced(unpriced, [{ ...emptyRateRow(), pattern: "ep-1" }]).map((m) => m.model),
    ["ep-2"],
  );
});
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `cd admin && npm test`
Expected: FAIL — không tìm thấy `src/lib/providerRates.ts`.

- [ ] **Step 4: Viết `admin/src/api/providerRates.ts`**

```ts
import { api } from "@/api/client";

/** Đơn vị tính giá trong provider_rates */
export type RateUnit = "per_image" | "per_m_tokens" | "per_m_output_tokens" | "per_m_input_output" | "per_m_chars";

/** Một dòng bảng giá (USD); usd_out chỉ dùng cho per_m_input_output */
export type ProviderRateRow = { pattern: string; unit: RateUnit; usd: number; usd_out: number | null; note: string };

export type RateUnitOption = { id: RateUnit; label: string };

/** Model đã gán nhưng chưa khớp dòng giá nào */
export type UnpricedModel = { channel_id: string; model: string; capability: string };

/** GET/PUT /api/admin/settings/billing/model-rates */
export type ProviderRatesOut = {
  items: ProviderRateRow[];
  defaults: ProviderRateRow[];
  units: RateUnitOption[];
  unpriced_models: UnpricedModel[];
  usd_cny: number;
  updated_at?: string | null;
};

// Đọc bảng giá hiện hành + bảng mặc định + model chưa có giá
export function fetchProviderRates(): Promise<ProviderRatesOut> {
  return api<ProviderRatesOut>("/api/admin/settings/billing/model-rates");
}

// Thay toàn bộ bảng giá; 400 trả câu lỗi tiếng Việt theo từng dòng
export function saveProviderRates(items: ProviderRateRow[]): Promise<ProviderRatesOut> {
  return api<ProviderRatesOut>("/api/admin/settings/billing/model-rates", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}
```

- [ ] **Step 5: Viết `admin/src/lib/providerRates.ts`**

```ts
/** Hàm thuần cho bảng giá provider_rates (chỉ `import type` để chạy được bằng `node --test`). */
import type { ProviderRateRow, RateUnit, UnpricedModel } from "@/api/providerRates";

/** Hậu tố hiển thị sau giá xem trước */
export const RATE_UNIT_SUFFIX: Record<RateUnit, string> = {
  per_image: "/ ảnh",
  per_m_tokens: "/ 1 triệu token",
  per_m_output_tokens: "/ 1 triệu token đầu ra",
  per_m_input_output: "/ 1 triệu token (vào | ra)",
  per_m_chars: "/ 1 triệu ký tự",
};

/** USD → fen giống backend: ceil(round(usd × usd_cny × 100, 6)), usd > 0 thì tối thiểu 1 fen */
export function rateFenPreview(usd: number, usdCny: number): number {
  if (!(usd > 0) || !(usdCny > 0)) return 0;
  const raw = Math.round(usd * usdCny * 100 * 1e6) / 1e6;
  return Math.max(1, Math.ceil(raw));
}

/** Đổi đơn vị; chỉ per_m_input_output giữ usd_out (mặc định 0), còn lại null */
export function withUnit(row: ProviderRateRow, unit: RateUnit): ProviderRateRow {
  return { ...row, unit, usd_out: unit === "per_m_input_output" ? row.usd_out ?? 0 : null };
}

/** Đổi chỗ dòng với dòng kề trên/dưới (thứ tự = ưu tiên khớp) */
export function moveRow<T>(rows: T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (index < 0 || index >= rows.length || target < 0 || target >= rows.length) return rows;
  const next = [...rows];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Dòng trống để thêm mới */
export function emptyRateRow(): ProviderRateRow {
  return { pattern: "", unit: "per_image", usd: 0, usd_out: null, note: "" };
}

/** Dòng gợi ý cho một model chưa có giá (đơn vị đoán theo năng lực) */
export function rowForUnpriced(m: UnpricedModel): ProviderRateRow {
  const unit: RateUnit =
    m.capability === "image"
      ? "per_image"
      : m.capability === "video"
        ? "per_m_tokens"
        : m.capability === "audio"
          ? "per_m_chars"
          : "per_m_input_output";
  return { pattern: m.model, unit, usd: 0, usd_out: unit === "per_m_input_output" ? 0 : null, note: m.channel_id };
}

/** Model chưa có giá mà bảng nháp cũng chưa có dòng trùng tên (không phân biệt hoa/thường) */
export function pendingUnpriced(unpriced: UnpricedModel[], rows: ProviderRateRow[]): UnpricedModel[] {
  const patterns = new Set(rows.map((r) => r.pattern.trim().toLowerCase()));
  return unpriced.filter((m) => !patterns.has(m.model.trim().toLowerCase()));
}
```

- [ ] **Step 6: Chạy test, xác nhận qua**

Run: `cd admin && npm test`
Expected: PASS (`fail 0`).

- [ ] **Step 7: `admin/src/hooks/useProviderRates.ts`**

```ts
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
```

- [ ] **Step 8: `admin/src/components/settings/ProviderRatesEditor.tsx`**

```tsx
import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { ProviderRateRow, RateUnit, RateUnitOption, UnpricedModel } from "@/api/providerRates";
import { AdminConfirmDialog } from "@/components/admin/AdminConfirmDialog";
import { Button } from "@/components/ui/button";
import { useCurrency } from "@/lib/currency";
import {
  RATE_UNIT_SUFFIX,
  emptyRateRow,
  moveRow,
  pendingUnpriced,
  rateFenPreview,
  rowForUnpriced,
  withUnit,
} from "@/lib/providerRates";

type ProviderRatesEditorProps = {
  rows: ProviderRateRow[];
  units: RateUnitOption[];
  unpriced: UnpricedModel[];
  usdCny: number;
  loading: boolean;
  loadError: string;
  saveError: string;
  onChange: (rows: ProviderRateRow[]) => void;
  onReset: () => void;
  onReload: () => void;
};

// Đọc số từ ô nhập; rỗng hoặc sai → 0
function toNumber(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** Bảng giá model theo USD: sửa, đổi thứ tự ưu tiên, xem trước giá quy đổi, cảnh báo model chưa có giá */
export function ProviderRatesEditor({
  rows,
  units,
  unpriced,
  usdCny,
  loading,
  loadError,
  saveError,
  onChange,
  onReset,
  onReload,
}: ProviderRatesEditorProps) {
  const { format } = useCurrency();
  /* confirmReset: hộp xác nhận khôi phục bảng mặc định */
  const [confirmReset, setConfirmReset] = useState(false);

  if (loading) return <p className="settings-field-hint">Đang tải bảng giá…</p>;
  if (loadError) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-red-600">{loadError}</p>
        <Button size="sm" variant="outline" onClick={onReload}>
          Thử lại
        </Button>
      </div>
    );
  }

  const pending = pendingUnpriced(unpriced, rows);

  // Sửa một ô của dòng i
  function patchRow(i: number, patch: Partial<ProviderRateRow>) {
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="settings-field-hint">
        Dòng trên cùng khớp trước. Mẫu tên model dùng * và ?, không phân biệt hoa thường. Model không khớp dòng nào
        sẽ tính theo đơn giá token dự phòng ở mục 3.
      </p>

      {pending.length > 0 ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">
            {pending.length} model đã gán nhưng chưa có giá — đang tính theo đơn giá token dự phòng. Bấm để thêm dòng:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {pending.map((m) => (
              <Button
                key={`${m.channel_id}:${m.model}`}
                size="sm"
                variant="outline"
                type="button"
                onClick={() => onChange([...rows, rowForUnpriced(m)])}
              >
                <Plus className="h-3.5 w-3.5" />
                <span className="font-mono">{m.model}</span>
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left">
              <th className="p-2">#</th>
              <th className="p-2">Mẫu tên model</th>
              <th className="p-2">Đơn vị</th>
              <th className="p-2">Giá USD</th>
              <th className="p-2">Quy đổi</th>
              <th className="p-2">Ghi chú</th>
              <th className="p-2" aria-label="Thao tác" />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-3 text-center text-muted-foreground">
                  Bảng giá trống — mọi model tính theo đơn giá token dự phòng.
                </td>
              </tr>
            ) : null}
            {rows.map((row, i) => (
              <tr key={i} className="border-b last:border-0 align-top">
                <td className="p-2 text-xs text-muted-foreground">{i + 1}</td>
                <td className="p-2">
                  <input
                    className="settings-input font-mono"
                    value={row.pattern}
                    placeholder="vd. dreamina-seedance-2-0*"
                    onChange={(e) => patchRow(i, { pattern: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <select
                    className="settings-select"
                    value={row.unit}
                    onChange={(e) => onChange(rows.map((r, idx) => (idx === i ? withUnit(r, e.target.value as RateUnit) : r)))}
                  >
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <input
                      className="settings-input w-24"
                      type="number"
                      min={0}
                      step="0.001"
                      aria-label={row.unit === "per_m_input_output" ? "Giá token vào" : "Giá USD"}
                      value={row.usd}
                      onChange={(e) => patchRow(i, { usd: toNumber(e.target.value) })}
                    />
                    {row.unit === "per_m_input_output" ? (
                      <input
                        className="settings-input w-24"
                        type="number"
                        min={0}
                        step="0.001"
                        aria-label="Giá token ra"
                        value={row.usd_out ?? 0}
                        onChange={(e) => patchRow(i, { usd_out: toNumber(e.target.value) })}
                      />
                    ) : null}
                  </div>
                </td>
                <td className="p-2 whitespace-nowrap text-xs">
                  {format(rateFenPreview(row.usd, usdCny))}
                  {row.unit === "per_m_input_output" ? ` | ${format(rateFenPreview(row.usd_out ?? 0, usdCny))}` : ""}{" "}
                  <span className="text-muted-foreground">{RATE_UNIT_SUFFIX[row.unit]}</span>
                </td>
                <td className="p-2">
                  <input
                    className="settings-input"
                    value={row.note}
                    onChange={(e) => patchRow(i, { note: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <Button size="icon" variant="ghost" aria-label="Lên" disabled={i === 0} onClick={() => onChange(moveRow(rows, i, -1))}>
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Xuống"
                      disabled={i === rows.length - 1}
                      onClick={() => onChange(moveRow(rows, i, 1))}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Xoá dòng"
                      onClick={() => onChange(rows.filter((_, idx) => idx !== i))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {saveError ? (
        <p className="text-sm text-red-600" role="alert">
          {saveError}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => onChange([...rows, emptyRateRow()])}>
          <Plus className="h-3.5 w-3.5" />
          Thêm dòng
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => setConfirmReset(true)}>
          <RotateCcw className="h-3.5 w-3.5" />
          Khôi phục mặc định
        </Button>
      </div>

      <AdminConfirmDialog
        open={confirmReset}
        title="Khôi phục bảng giá mặc định?"
        description="Bảng nháp sẽ được thay bằng giá chính thức mặc định. Chỉ áp dụng sau khi bấm Lưu."
        confirmLabel="Khôi phục"
        cancelLabel="Huỷ"
        onOpenChange={setConfirmReset}
        onConfirm={() => {
          onReset();
          setConfirmReset(false);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 9: Sửa `PaymentSettingsPanel.tsx`**

(a) Import: xoá `import { Button } from "@/components/ui/button";` và `import { api } from "@/api/client";`; thêm:

```tsx
import { toast } from "sonner";
import { ProviderRatesEditor } from "@/components/settings/ProviderRatesEditor";
import { useProviderRates } from "@/hooks/useProviderRates";
```

(b) Xoá nguyên khối kiểu `ModelRateRow` (dòng 16–30, gồm comment `/** TokenFree 官方价目行…*/`).

(c) Thay khối state từ `/*\n   * tokenfreeBusy …` tới `const [modelRatesBusy, setModelRatesBusy] = useState(false);` bằng:

```tsx
  const rates = useProviderRates();
```

(d) Xoá dòng `const tokenfreeReady = Boolean(form?.has_openai_api_key);`.

(e) Trong `handleSave`: xoá dòng `billing_kie_fen_per_credit: form.billing_kie_fen_per_credit,`; ngay sau `if (!form) return;` thêm:

```tsx
    // Bảng giá lưu riêng (PUT model-rates); lỗi thì dừng để admin sửa trước
    if (rates.dirty && !(await rates.save())) {
      toast.error("Bảng giá model chưa lưu được, xem lỗi ở mục 5");
      return;
    }
```

(f) Xoá nguyên hai hàm `loadModelRates` và `queryTokenfreeQuota` (kèm comment phía trên mỗi hàm).

(g) Trong `SettingsStatusBar` thay mục `id: "tokenfree"` bằng:

```tsx
          {
            id: "rates",
            label: "模型价目",
            ready: !rates.loadError && (rates.data?.unpriced_models.length ?? 0) === 0,
            readyText: "已覆盖全部模型",
            pendingText: rates.loadError ? "加载失败" : `${rates.data?.unpriced_models.length ?? 0} 个模型未定价`,
          },
```

(h) Nhãn USD: đổi `hint="也用于把 TokenFree 上游 USD 成本折算为记账单位"` thành `hint="也用于把模型价目（美元）折算为记账单位"`.

(i) Panel 3: đổi `description="按 TokenFree 官方成本 1:1 扣费，不再加价"` thành `description="按模型价目表（美元）折算成本 1:1 扣费，不加价"`; đổi tiêu đề phụ `单价（记账元 / 百万 token）` thành `兜底单价（未匹配价目表时，记账元 / 百万 token）`.

(j) Xoá nguyên khối từ `<div className="settings-subsection-title mt-3">TokenFree 上游与模型费率</div>` tới hết `) : null}` của bảng `modelRates` (dòng 379–444 cũ).

(k) Ngay trước `</SettingsTabShell>` (sau `</div>` của lưới chứa panel 3 và 4) thêm panel toàn chiều ngang:

```tsx
      <SettingsPanel
        className="settings-panel--compact"
        title="5. Bảng giá model (USD)"
        description="Giá chính thức của từng provider; dùng cho tạm giữ trước và quyết toán. Lưu bằng nút Lưu phía trên."
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
```

(l) Trong `admin/src/api/client.ts` xoá dòng `billing_kie_fen_per_credit: number;` khỏi `AdminModelSettings`.

Run: `cd admin && grep -n -i "tokenfree\|kie_fen\|model-rates\"\|quota" src/components/settings/PaymentSettingsPanel.tsx src/api/client.ts`
Expected: không có kết quả. `wc -l src/components/settings/PaymentSettingsPanel.tsx` ≤ ~520.

- [ ] **Step 10: Lint + build + test**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 11: Commit**

```bash
git add admin/src admin/tests
git commit -m "feat(admin): sửa bảng giá provider_rates trong tab thanh toán, bỏ số dư và giá TokenFree

Admin tự quản giá USD theo model (thêm/xoá/đổi thứ tự, khôi phục mặc định) và thấy ngay model nào chưa có giá.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Admin — bỏ đối chiếu upstream ở Dashboard/Finance, nhãn trung tính ở Runtime, ẩn field flat đã chết, bỏ chữ TokenFree ở Orders

**Files:**
- Modify: `admin/src/pages/DashboardPage.tsx`
- Modify: `admin/src/pages/dashboard/dashboardSectionInsights.tsx`
- Modify: `admin/src/pages/FinanceListPage.tsx`
- Modify: `admin/src/pages/OrdersPage.tsx`
- Modify: `admin/src/components/settings/RuntimeSettingsPanel.tsx`
- Modify: `admin/src/api/client.ts`

**Interfaces:**
- Consumes: hợp đồng Plan B §3 (endpoint đã xoá), §4 (`GET /api/admin/finance/daily` không còn `configured`, `last_sync_at`; `actual_cost_fen == cost_fen`).
- Produces: `AdminFinanceDaily = { days: number; totals: AdminFinanceDailyTotals; series: AdminFinanceDailyRow[] }`; `buildFinanceInsights(stats: AdminStats | null, format: MoneyFormatter): DashboardInsightItem[]` (bỏ tham số upstream); `AdminModelSettings` không còn các field flat đã chết `openai_*` / `ark_api_key` / `ark_base_url` / `model_*`.

- [ ] **Step 1: Kiểm tra Plan B đã chạy**

Run:

```bash
cd backend && grep -rn "upstream-usage\|daily/sync" app/api/admin/ || echo NO_OLD_ENDPOINTS; grep -n "configured\|last_sync_at" app/services/admin/finance.py || echo FINANCE_NEW_SHAPE
```

Expected: `NO_OLD_ENDPOINTS` và `FINANCE_NEW_SHAPE`. Khác → **dừng, báo BLOCKED "Plan B chưa chạy"**.

- [ ] **Step 2: `client.ts` — kiểu**

Xoá nguyên ba kiểu `AdminUpstreamUsageDay`, `AdminUpstreamUsage`, `AdminUpstreamUsageSync`. Thay kiểu `AdminFinanceDaily` bằng:

```ts
export type AdminFinanceDaily = {
  days: number;
  totals: AdminFinanceDailyTotals;
  series: AdminFinanceDailyRow[];
};
```

Field flat đã chết (chỉ seed provider lần khởi động đầu và làm nhãn dòng tính phí): xoá khỏi kiểu `AdminModelSettings` các dòng `openai_api_key`, `openai_base_url`, `model_llm`, `has_openai_api_key`, `ark_api_key`, `ark_base_url`, `model_image`, `model_image_45`, `model_video`, `model_audio`, `has_ark_api_key`, và thêm comment ngay trên `export type AdminModelSettings = {`:

```ts
/**
 * Cấu hình flat (DB overlay trên .env). Các field openai_* / ark_api_key / ark_base_url / model_* vẫn có trong
 * payload backend nhưng chỉ dùng để seed provider lần khởi động đầu và làm nhãn dòng tính phí — admin cấu hình
 * provider/model ở tab "Mô hình", nên không khai báo và không hiển thị ở đây.
 */
```

Rồi xác nhận không màn nào còn hiện hoặc gửi các field này, và admin không có nút "nhập từ env" (`POST /settings/models/import-env`) — nếu có thì xoá nút đó:

Run: `cd admin && grep -rn "openai_api_key\|openai_base_url\|ark_api_key\|ark_base_url\|model_llm\|model_image\|model_video\|model_audio\|import-env" src`
Expected: không có kết quả (sau khi Task 5 đã bỏ `has_openai_api_key` khỏi `PaymentSettingsPanel`).

- [ ] **Step 3: `dashboardSectionInsights.tsx`**

Đổi import `import type { AdminStats, AdminUpstreamUsage } from "@/api/client";` thành `import type { AdminStats } from "@/api/client";`. Đổi chữ ký:

```ts
/** 财务账单 Tab 图标指标（format：分 → 当前展示货币） */
export function buildFinanceInsights(stats: AdminStats | null, format: MoneyFormatter): DashboardInsightItem[] {
```

Xoá 4 dòng `const recent = …`, `const localCost7 = …`, `const officialCost7 = …`, `const delta7 = …` và nguyên khối `if (upstream?.configured && officialCost7 > 0) { items.push({ key: "upstream-delta", … }); }`. Xoá `TrendingUp` khỏi import lucide nếu tsc báo không dùng (giữ `TrendingDown`, `STATUS_META` còn dùng).

- [ ] **Step 4: `DashboardPage.tsx`**

- Import: `import { api, type AdminOrder, type AdminStats, type PageMeta } from "@/api/client";` (bỏ `AdminUpstreamUsage`).
- Xoá state `upstreamUsage`, `upstreamSyncing`, hai callback `loadUpstreamUsage`, `syncUpstreamUsage` và effect `useEffect(() => { void loadUpstreamUsage(); }, [loadUpstreamUsage]);`.
- `const financeInsights = buildFinanceInsights(stats, format);`
- Xoá nguyên `<PageSection title="TokenFree 官方用量对照" …> … </PageSection>`.
- Xoá import `Button` nếu `npm run build` báo không còn dùng.

- [ ] **Step 5: `FinanceListPage.tsx`**

- Xoá import `Button`, state `syncing`, callback `syncOfficial`.
- `PageHeader`: `description="按日汇总扣费、成本（按模型价目表计算）与利润"`.
- `PageSection` `description`:

```tsx
        description={
          rangeMismatch ? "数据与当前时间范围不一致，请重新加载" : `近 ${days} 日 · 成本 = 按模型价目表计算的上游成本`
        }
```

  và xoá prop `actions`.
- Bảng gộp "本地成本" và "实际成本" thành một cột "成本": header còn `日期 / 扣费 / 成本 / Token / 利润`; mọi `colSpan={6}` → `colSpan={5}`; trong hàng dữ liệu và hàng 合计 xoá ô `actual_cost_fen` (giữ ô `cost_fen`).

- [ ] **Step 6: `OrdersPage.tsx` — title của Badge căn cứ tính phí**

Thay:

```tsx
                          row.billing_basis === "upstream_cost"
                            ? "按 TokenFree 返回的实际费用扣费"
                            : row.billing_basis === "upstream_usage"
                              ? "按 TokenFree usage token × 官方单价扣费"
```

bằng:

```tsx
                          row.billing_basis === "upstream_cost"
                            ? "按模型价目表与实际用量算出的费用扣费"
                            : row.billing_basis === "upstream_usage"
                              ? "按上游返回的 usage token × 价目表单价扣费"
```

- [ ] **Step 7: `RuntimeSettingsPanel.tsx` — nhãn trung tính (tiếng Việt theo spec §7.3), readiness từ backend**

- `statusItems`: `readyText: item.model || "Sẵn sàng",` và `pendingText: item.message || "Chưa sẵn sàng",`.
- `SettingsStatusBar`: `title="Trạng thái gán model"`; mục rỗng `{ id: "empty", label: "Gán model", ready: false, pendingText: "Chưa gán model" }`; `extra`:

```tsx
            {form.readiness?.every((item) => item.ready)
              ? "Đủ 4 slot năng lực"
              : "Vào tab “Mô hình” để thêm provider và gán model"}
```

- Panel 1: `title="1. Chất lượng và mặc định"`, `description="Kích thước ảnh, độ phân giải và tỉ lệ video, thời lượng video, chu kỳ kiểm tra kết quả"`. Nhãn:
  - `默认生图尺寸` → `label="Kích thước ảnh mặc định" hint="VD: 2K, 1K hoặc 1024x1024"`
  - `默认视频清晰度` → `label="Độ phân giải video mặc định" hint="480p / 720p / 1080p"`
  - `默认视频比例` → `label="Tỉ lệ video mặc định"`
  - `Seedance 最小时长（秒）` → `label="Thời lượng video tối thiểu (giây)"`
  - `Seedance 最大时长（秒）` → `label="Thời lượng video tối đa (giây)"`
  - `视频轮询间隔（秒）` → `label="Chu kỳ kiểm tra video (giây)"`
  - `视频轮询超时（秒）` → `label="Thời gian chờ video tối đa (giây)"`
- Công tắc mock: `<strong>Chế độ mô phỏng (mock)</strong>` và `<span>Không gọi nhà cung cấp thật; trả ảnh/video mẫu để thử luồng</span>`.

Field `ark_*` / `seedance_*` giữ nguyên.

- [ ] **Step 8: Kiểm tra không còn gọi endpoint đã xoá**

Run: `cd admin && grep -rn -i "upstream-usage\|daily/sync\|tokenfree\|AdminUpstreamUsage\|last_sync_at" src`
Expected: không có kết quả.

- [ ] **Step 9: Lint + build + test**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 10: Commit**

```bash
git add admin/src
git commit -m "refactor(admin): bỏ đối chiếu dùng lượng upstream và chữ TokenFree ở dashboard, tài chính, đơn hàng, tham số chạy

Chi phí giờ tính cục bộ theo bảng giá nên các nút đồng bộ và cột chi phí thực tế không còn ý nghĩa; nhãn tham số chạy đổi sang tên trung tính.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Task center hiện provider (backend `provider` trong dòng usage + admin UI)

**Files:**
- Modify: `backend/app/schemas_tasks.py` (`TaskRunBriefOut`, `AdminUsageEventBriefOut`)
- Modify: `backend/app/api/admin/tasks.py` (`_load_usage_lines`)
- Test: `backend/tests/test_admin_task_usage_provider.py` (mới)
- Modify: `admin/src/api/client.ts`, `admin/src/pages/QueuesPage.tsx`, `admin/src/components/tasks/TaskDetailDialog.tsx`

**Interfaces:**
- Consumes: `TaskRun.provider_channel_id` (Plan A, đã có trong `TaskRunOut` → `AdminTaskRunOut`), `UsageEvent.provider` (= `route.channel_id`, Plan A).
- Produces: `TaskRunBriefOut.provider_channel_id: str | None` (bản tóm tắt task nhúng trong response nghiệp vụ, vd. `AdminTaskBrief` / `recent_tasks` của dự án); `AdminUsageEventBriefOut.provider: str | None`; admin `AdminTaskRow.provider_channel_id?: string | null`, `AdminTaskBrief.provider_channel_id?: string | null`, `AdminUsageEventBrief.provider?: string | null`.

- [ ] **Step 1: Viết test thất bại**

```python
# backend/tests/test_admin_task_usage_provider.py
"""Tab tính phí của chi tiết task hiện provider (channel id) của từng dòng usage."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.tasks import _load_usage_lines
from app.models import UsageEvent
from app.schemas_tasks import TaskRunBriefOut
from tests.conftest import make_user


def test_task_brief_exposes_provider_channel_id() -> None:
    task = SimpleNamespace(
        id=1, domain="drama", task_type="fragment_video", status="awaiting_poll",
        provider_task_id="cgt-1", provider_channel_id="byteplus",
    )
    assert TaskRunBriefOut.model_validate(task).provider_channel_id == "byteplus"


async def test_usage_lines_include_provider(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    task_run_id = 987_654_321
    db_session.add(
        UsageEvent(
            user_id=user.id,
            task_run_id=task_run_id,
            domain="tools",
            capability="image",
            billing_key="seedream",
            model="dola-seedream-5-0-pro-260628",
            provider="byteplus",
            charge_fen=32,
        )
    )
    await db_session.flush()

    lines = await _load_usage_lines(db_session, task_run_id)

    assert [line.provider for line in lines] == ["byteplus"]
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_task_usage_provider.py -v -p no:cacheprovider`
Expected: FAIL — `AttributeError: 'TaskRunBriefOut' object has no attribute 'provider_channel_id'` và `'AdminUsageEventBriefOut' object has no attribute 'provider'`.

- [ ] **Step 3: Sửa backend**

`backend/app/schemas_tasks.py`, trong `class TaskRunBriefOut` thêm sau `provider_task_id: str | None = None`:

```python
    provider_channel_id: str | None = None
```

Trong `class AdminUsageEventBriefOut` thêm sau `model: str = ""`:

```python
    provider: str | None = None
```

`backend/app/api/admin/tasks.py`, trong `_load_usage_lines` thêm tham số khi dựng `AdminUsageEventBriefOut(...)`, sau `model=row.model or "",`:

```python
                provider=row.provider or None,
```

- [ ] **Step 4: Chạy test, xác nhận qua + toàn bộ**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_task_usage_provider.py -v -p no:cacheprovider && .venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: 2 test mới PASS; toàn bộ chỉ còn 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 5: Admin — kiểu**

`admin/src/api/client.ts`: trong `AdminTaskRow` thêm sau `current_step_status?: string | null;`:

```ts
  /** Provider (channel id) đã nhận tác vụ video — dùng để poll đúng kênh */
  provider_channel_id?: string | null;
```

Trong `AdminUsageEventBrief` thêm sau `model?: string;`:

```ts
  provider?: string | null;
```

Trong `AdminTaskBrief` (task gần đây trong chi tiết dự án) thêm sau `billing_estimate_fen: number;`:

```ts
  provider_channel_id?: string | null;
```

Chỗ nào render `recent_tasks` (grep `recent_tasks` trong `admin/src`) mà có cột/ô loại task thì hiện thêm `provider: {t.provider_channel_id}` bằng font mono cỡ 11px khi có giá trị, giống Step 6.

- [ ] **Step 6: `QueuesPage.tsx` — hiện provider dưới loại task**

Trong ô `领域 / 类型` của mỗi hàng, sau `<div className="font-mono text-[11px] text-[#909399]">{taskTypeLabel(task.task_type)}</div>` thêm:

```tsx
                          {task.provider_channel_id ? (
                            <div className="font-mono text-[11px] text-[#909399]">provider: {task.provider_channel_id}</div>
                          ) : null}
```

- [ ] **Step 7: `TaskDetailDialog.tsx`**

Trong `<DetailSection title="调度">`, sau `DlRow label="provider_task_id"` thêm:

```tsx
                  <DlRow label="provider">
                    {task.provider_channel_id ? (
                      <span className="font-mono text-xs">{task.provider_channel_id}</span>
                    ) : null}
                  </DlRow>
```

Bảng usage: thêm `<th>Provider</th>` sau `<th>模型</th>`; ô tương ứng sau ô model:

```tsx
                              <td className="font-mono text-xs">{line.provider || "—"}</td>
```

và đổi `colSpan={8}` của dòng "暂无用量记录" thành `colSpan={9}`.

- [ ] **Step 8: Lint + build**

Run: `cd admin && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas_tasks.py backend/app/api/admin/tasks.py backend/tests/test_admin_task_usage_provider.py admin/src
git commit -m "feat: task center hiện provider của tác vụ và của từng dòng tính phí

Admin kiểm tra được tác vụ đi qua kênh nào khi tắt/đổi provider, đúng mục hồi quy của spec.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Frontend — catalog model theo scope, lựa chọn "Tự động", trạng thái rỗng, không gửi model đã bị gỡ

**Files:**
- Create: `frontend/src/lib/mediaModelChoice.ts`
- Create: `frontend/tests/mediaModelChoice.test.ts`
- Modify: `frontend/package.json` (script `test`)
- Create: `frontend/src/lib/mediaModelsCatalogStore.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/hooks/useMediaModelsCatalog.ts`
- Create: `frontend/src/components/studio/MediaModelGrid.tsx`
- Modify: `frontend/src/pages/studio/StyleConfigPage.tsx`
- Modify: `frontend/src/pages/drama/canvas/nodes/DramaImageGenOptionsBar.tsx`, `frontend/src/pages/drama/canvas/nodes/DramaVideoGenOptionsBar.tsx`, `frontend/src/pages/drama/EpisodeEditHeaderControls.tsx`, `frontend/src/pages/drama/EpisodeEditPage.tsx`
- Modify: `frontend/src/lib/dramaImageGenQueue.ts`, `frontend/src/lib/dramaVideoGenQueue.ts`
- Modify: `frontend/src/i18n/locales/{zh,en,vi}/studio.ts`, `…/dramaCanvas.ts`, `…/dramaEpisode.ts`

**Interfaces:**
- Consumes: `GET /api/media-models?scope=…` → `{image_models[], video_models[], defaults}`, mỗi dòng `{id, label, description, provider, recommended}`. Hành vi backend (sửa sau Plan A, trước Plan C): **model rỗng = "Tự động"** — backend chọn luân phiên theo weight trong các model admin bật cho chức năng đó; backend chấp nhận giá trị model cũ **không đổi** khi lưu dự án. Vì vậy frontend **không ghim `defaults.*`** nữa: mặc định là rỗng (Tự động), và chỉ xoá về rỗng model không còn trong catalog.
- Produces:
  ```ts
  // lib/mediaModelChoice.ts (thuần)
  export function reconcileCatalogModel(current: string | null | undefined, models: ReadonlyArray<{ id: string }> | null): string;
  export function modelProviderLabel(m: { description?: string; provider?: string }): string;
  // lib/mediaModelsCatalogStore.ts
  export function loadMediaModelsCatalog(scope: MediaModelScope): Promise<MediaModelsCatalog>;
  export function peekMediaModelsCatalog(scope: MediaModelScope): MediaModelsCatalog | null;
  // api.ts
  export type MediaModelScope = 'kepu' | 'drama' | 'tools';
  api.mediaModels(scope?: MediaModelScope): Promise<MediaModelsCatalog>;
  // hooks/useMediaModelsCatalog.ts
  export function useMediaModelsCatalog(scope: MediaModelScope): MediaModelsCatalog | null;
  // components/studio/MediaModelGrid.tsx
  export default function MediaModelGrid(props: { title: string; hint: string; emptyText: string; recommendedLabel: string; autoLabel: string; autoDesc: string; models: MediaModelOption[]; value: string; onChange: (id: string) => void }): JSX.Element;
  ```
- i18n key mới (đủ zh/en/vi): `studioStyle.noImageModels`, `studioStyle.noVideoModels`, `studioStyle.modelAuto`, `studioStyle.modelAutoDesc`, `dramaCanvas.genOptions.modelAuto`, `dramaCanvas.genOptions.modelAutoDesc`, `dramaEpisode.header.modelAuto`.

- [ ] **Step 1: Script test `frontend/package.json`**

Thêm sau `"lint": "oxlint",`:

```json
    "test": "node --test \"tests/*.test.ts\"",
```

- [ ] **Step 2: Viết test thất bại `frontend/tests/mediaModelChoice.test.ts`**

```ts
/** Chọn model phía user: rỗng = Tự động; model bị admin gỡ thì về Tự động; catalog chưa về thì giữ nguyên. */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { modelProviderLabel, reconcileCatalogModel } from '../src/lib/mediaModelChoice.ts'

const MODELS = [{ id: 'dola-seedream-5-0-pro-260628' }, { id: 'gpt-image-2' }]

test('reconcileCatalogModel keeps a still-allowed choice', () => {
  assert.equal(reconcileCatalogModel('gpt-image-2', MODELS), 'gpt-image-2')
})

test('reconcileCatalogModel turns a removed model into Auto (empty)', () => {
  assert.equal(reconcileCatalogModel('seedream-5.0', MODELS), '')
})

test('reconcileCatalogModel keeps Auto and never pins a default', () => {
  assert.equal(reconcileCatalogModel('', MODELS), '')
  assert.equal(reconcileCatalogModel(undefined, MODELS), '')
})

test('reconcileCatalogModel returns Auto when the catalog is empty', () => {
  assert.equal(reconcileCatalogModel('seedream-5.0', []), '')
})

test('reconcileCatalogModel leaves the value alone while the catalog is unknown', () => {
  assert.equal(reconcileCatalogModel(' seedream-5.0 ', null), 'seedream-5.0')
})

test('modelProviderLabel prefers description, then provider', () => {
  assert.equal(modelProviderLabel({ description: 'Nhanh', provider: 'byteplus' }), 'Nhanh')
  assert.equal(modelProviderLabel({ description: '', provider: 'byteplus' }), 'byteplus')
  assert.equal(modelProviderLabel({}), '')
})
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `cd frontend && npm test`
Expected: FAIL — không tìm thấy `src/lib/mediaModelChoice.ts`.

- [ ] **Step 4: Viết `frontend/src/lib/mediaModelChoice.ts`**

```ts
/**
 * Chọn model phía user (thuần, không import runtime). Model rỗng = "Tự động": backend chia luân phiên
 * theo weight trong các model admin đã bật cho chức năng đó.
 * - models null (catalog chưa về / tải lỗi) → giữ nguyên (backend vẫn nhận giá trị cũ không đổi)
 * - model còn trong catalog → giữ
 * - model đã bị gỡ, hoặc catalog rỗng → '' (Tự động); không bao giờ tự ghim model mặc định
 */
export function reconcileCatalogModel(
  current: string | null | undefined,
  models: ReadonlyArray<{ id: string }> | null,
): string {
  const cur = (current || '').trim()
  if (models === null) return cur
  return cur && models.some((m) => m.id === cur) ? cur : ''
}

/** Dòng phụ dưới tên model: mô tả nếu có, không thì tên provider */
export function modelProviderLabel(m: { description?: string; provider?: string }): string {
  return (m.description || '').trim() || (m.provider || '').trim()
}
```

- [ ] **Step 5: Chạy test, xác nhận qua**

Run: `cd frontend && npm test`
Expected: PASS (`fail 0`, 6 test).

- [ ] **Step 6: `api.ts` — scope**

Ngay trên `export type MediaModelsCatalog = {` thêm:

```ts
/** Scope sản phẩm của catalog model: video kiến thức / phim ngắn / công cụ */
export type MediaModelScope = 'kepu' | 'drama' | 'tools'
```

Thay hàm `mediaModels()` bằng:

```ts
  mediaModels(scope?: MediaModelScope) {
    return request<MediaModelsCatalog>(scope ? `/api/media-models?scope=${scope}` : '/api/media-models')
  },
```

- [ ] **Step 7: Cache dùng chung `frontend/src/lib/mediaModelsCatalogStore.ts`**

```ts
/** Cache danh mục model phía user theo scope; dùng chung cho hook và hàng đợi tạo (đọc đồng bộ khi gửi). */
import { api, type MediaModelScope, type MediaModelsCatalog } from '../api'

const cached = new Map<MediaModelScope, MediaModelsCatalog>()
const inflight = new Map<MediaModelScope, Promise<MediaModelsCatalog>>()

/** Tải catalog một scope; dùng chung request đang chạy; lỗi thì cho phép tải lại lần sau */
export function loadMediaModelsCatalog(scope: MediaModelScope): Promise<MediaModelsCatalog> {
  const hit = cached.get(scope)
  if (hit) return Promise.resolve(hit)
  let pending = inflight.get(scope)
  if (!pending) {
    pending = api.mediaModels(scope).then(
      (cat) => {
        cached.set(scope, cat)
        inflight.delete(scope)
        return cat
      },
      (err: unknown) => {
        inflight.delete(scope)
        throw err
      },
    )
    inflight.set(scope, pending)
  }
  return pending
}

/** Catalog đã tải của scope (null nếu chưa có) — không gọi mạng */
export function peekMediaModelsCatalog(scope: MediaModelScope): MediaModelsCatalog | null {
  return cached.get(scope) ?? null
}
```

- [ ] **Step 8: Viết lại `frontend/src/hooks/useMediaModelsCatalog.ts`**

```ts
/** Hook lấy danh mục model ảnh/video phía user theo scope sản phẩm (kepu / drama / tools). */
import { useEffect, useState } from 'react'
import type { MediaModelOption, MediaModelScope, MediaModelsCatalog } from '../api'
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { loadMediaModelsCatalog, peekMediaModelsCatalog } from '../lib/mediaModelsCatalogStore'

/** Catalog của scope; null khi chưa về hoặc tải lỗi */
export function useMediaModelsCatalog(scope: MediaModelScope) {
  const [catalog, setCatalog] = useState<MediaModelsCatalog | null>(() => peekMediaModelsCatalog(scope))

  useEffect(() => {
    let cancelled = false
    loadMediaModelsCatalog(scope)
      .then((cat) => {
        if (!cancelled) setCatalog(cat)
      })
      .catch(() => {
        if (!cancelled) setCatalog(null)
      })
    return () => {
      cancelled = true
    }
  }, [scope])

  return catalog
}

/** 当前目录下的视频模型；目录未到时为空。 */
export function catalogVideoModels(catalog: MediaModelsCatalog | null): MediaModelOption[] {
  return catalog?.video_models ?? []
}

/** 当前目录下的图片模型；目录未到时为空。 */
export function catalogImageModels(catalog: MediaModelsCatalog | null): MediaModelOption[] {
  return catalog?.image_models ?? []
}

/** 用目录 label 展示模型名，找不到则显示 id；空 id 显示 fallback（调用方传「自动」文案）。 */
export function catalogModelLabel(
  modelId: string | undefined | null,
  models: Array<{ id: string; label: string }>,
  fallback = messages[getActiveLocale()].dramaEpisode.modelFallback,
): string {
  const id = (modelId || '').trim()
  if (!id) return fallback
  return models.find((m) => m.id === id)?.label || id
}
```

- [ ] **Step 9: i18n — key mới và câu trạng thái rỗng**

`zh/studio.ts`: thay `imageModelHint: '使用管理后台「模型」中已勾选的 TokenFree 模型。',` bằng `imageModelHint: '管理员为科普视频启用的图片模型。',`; sau dòng `videoModelHint: '图生视频所用模型；静图成片模式不调用。',` thêm:

```ts
    noImageModels: '尚未配置图片模型，请联系管理员。仍可直接生成，系统会自动选择模型。',
    noVideoModels: '尚未配置视频模型，请联系管理员。仍可直接生成，系统会自动选择模型。',
    modelAuto: '自动',
    modelAutoDesc: '在管理员启用的模型间轮流使用',
```

`en/studio.ts`: `imageModelHint: 'Image models the site admin has enabled for explainer videos.',`; sau `videoModelHint: 'Used for image-to-video; not called in still-image mode.',` thêm:

```ts
    noImageModels: 'No image models are set up yet. Contact the site admin. You can still generate; a model will be picked automatically.',
    noVideoModels: 'No video models are set up yet. Contact the site admin. You can still generate; a model will be picked automatically.',
    modelAuto: 'Auto',
    modelAutoDesc: 'Rotates among the models the admin has enabled',
```

`vi/studio.ts`: `imageModelHint: 'Các mô hình tạo ảnh chúng tôi đã bật cho video kiến thức.',`; sau `videoModelHint: 'Dùng để tạo video từ ảnh; kiểu video ảnh tĩnh không dùng đến.',` thêm:

```ts
    noImageModels: 'Chưa cấu hình mô hình tạo ảnh — hãy liên hệ với chúng tôi. Bạn vẫn bấm tạo được, hệ thống sẽ tự chọn mô hình.',
    noVideoModels: 'Chưa cấu hình mô hình tạo video — hãy liên hệ với chúng tôi. Bạn vẫn bấm tạo được, hệ thống sẽ tự chọn mô hình.',
    modelAuto: 'Tự động',
    modelAutoDesc: 'Dùng luân phiên các mô hình đang được bật',
```

`dramaCanvas.ts` khối `genOptions`: thay giá trị `noImageModels` / `noVideoModels` bằng đúng chuỗi `noImageModels` / `noVideoModels` của `studio.ts` cùng ngôn ngữ ở trên; và ngay sau dòng `model: …,` của khối này thêm `modelAuto` + `modelAutoDesc` với đúng chuỗi của `studio.ts` cùng ngôn ngữ.

`dramaEpisode.ts` khối `header`: thay giá trị `noVideoModels` bằng chuỗi `noVideoModels` của `studio.ts` cùng ngôn ngữ; ngay sau dòng `videoModel: …,` thêm `modelAuto: '自动',` (zh) / `modelAuto: 'Auto',` (en) / `modelAuto: 'Tự động',` (vi).

- [ ] **Step 10: `DramaImageGenOptionsBar.tsx`**

(a) `useMediaModelsCatalog()` → `useMediaModelsCatalog('drama')`; thêm import `import { modelProviderLabel, reconcileCatalogModel } from '../../../../lib/mediaModelChoice'`.

(b) Thay effect "目录到达后，把旧 Kie/方舟 id 换成后台默认图片模型" (khối `useEffect` ~dòng 49–57 có `catalog.defaults.image_model`) bằng:

```tsx
  useEffect(() => {
    // Catalog về: model đã bị admin gỡ → Tự động (''); không ghim model mặc định
    if (!catalog || disabled) return
    const next = reconcileCatalogModel(value.model_id, imageModels)
    if (next !== (value.model_id || '')) onChange({ ...value, model_id: next })
  }, [catalog, disabled])
```

(c) Nhãn nút: `catalogModelLabel(value.model_id, imageModels, t('dramaCanvas.options.imageModel'))` → `catalogModelLabel(value.model_id, imageModels, t('dramaCanvas.genOptions.modelAuto'))`.

(d) Trong panel `open === 'model'`, ngay sau khối `{imageModels.length === 0 ? (<p className="fc-gen-model-empty">…</p>) : null}` thêm mục "Tự động":

```tsx
            {imageModels.length > 0 ? (
              <button
                type="button"
                className={`fc-gen-model-item${!value.model_id ? ' selected' : ''}`}
                onClick={() => {
                  onChange({ ...value, model_id: '' })
                  setOpen(null)
                }}
              >
                <strong>{t('dramaCanvas.genOptions.modelAuto')}</strong>
                <span>{t('dramaCanvas.genOptions.modelAutoDesc')}</span>
              </button>
            ) : null}
```

(e) `<span>{m.description || 'TokenFree'}</span>` → `<span>{modelProviderLabel(m)}</span>`.

- [ ] **Step 11: `DramaVideoGenOptionsBar.tsx` — như Step 10 với video**

Làm đúng (a)–(e) của Step 10 nhưng: danh sách `videoModels`; effect dùng `reconcileCatalogModel(value.model_id, videoModels)`; nhãn `catalogModelLabel(value.model_id, videoModels, t('dramaCanvas.genOptions.modelAuto'))`; mục "Tự động" đặt sau `{videoModels.length === 0 ? … : null}` với điều kiện `videoModels.length > 0`. Code effect:

```tsx
  useEffect(() => {
    // Catalog về: model đã bị admin gỡ → Tự động (''); không ghim model mặc định
    if (!catalog || disabled) return
    const next = reconcileCatalogModel(value.model_id, videoModels)
    if (next !== (value.model_id || '')) onChange({ ...value, model_id: next })
  }, [catalog, disabled])
```

(Trước khi sửa, mở file xem đúng khối effect ~dòng 49–57; nếu biến điều kiện khác `disabled`, giữ nguyên điều kiện đó.)

- [ ] **Step 12: `EpisodeEditHeaderControls.tsx`**

- `useMediaModelsCatalog()` → `useMediaModelsCatalog('drama')`.
- `const modelLabel = catalogModelLabel(modelId, videoModels, t('dramaEpisode.header.videoModel'))` → `const modelLabel = catalogModelLabel(modelId, videoModels, t('dramaEpisode.header.modelAuto'))`.
- Trong danh sách model (sau `{videoModels.length === 0 ? (<p className="fc-gen-model-empty">…</p>) : null}`) thêm:

```tsx
                    {videoModels.length > 0 ? (
                      <button
                        type="button"
                        className={`fc-gen-model-item${!modelId ? ' selected' : ''}`}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => {
                          onModelChange('')
                          setOpen(null)
                        }}
                      >
                        {t('dramaEpisode.header.modelAuto')}
                      </button>
                    ) : null}
```

- [ ] **Step 13: `EpisodeEditPage.tsx`**

- `useMediaModelsCatalog()` → `useMediaModelsCatalog('drama')`; thêm import `import { reconcileCatalogModel } from '../../lib/mediaModelChoice'`.
- Thay effect "目录到达后，把旧 Kie/方舟 id 换成后台默认视频模型" (khối có `mediaCatalog.defaults.video_model || ids[0]`) bằng:

```tsx
  useEffect(() => {
    // Catalog về: model đã bị admin gỡ → Tự động (''); không ghim model mặc định
    if (!mediaCatalog) return
    setModelId((prev) => reconcileCatalogModel(prev, mediaCatalog.video_models))
  }, [mediaCatalog])
```

- Hai chỗ gửi (`dramaApi.generateEpisode(eid, [frag.id], modelId)` và `dramaApi.generateEpisode(eid, ids, modelId)`): thay đối số `modelId` bằng `reconcileCatalogModel(modelId, mediaCatalog?.video_models ?? null)` để không gửi model đã bị gỡ (catalog chưa về thì giữ nguyên).

- [ ] **Step 14: Hàng đợi tạo phim ngắn — làm sạch model ngay trước khi gửi**

`frontend/src/lib/dramaImageGenQueue.ts`: thêm import

```ts
import { reconcileCatalogModel } from './mediaModelChoice'
import { peekMediaModelsCatalog } from './mediaModelsCatalogStore'
```

và trong `submitJob`, thay `model_id: job.options.model_id,` bằng:

```ts
        // Model đã bị admin gỡ → bỏ trống (Tự động); catalog chưa tải thì gửi nguyên giá trị
        model_id: reconcileCatalogModel(job.options.model_id, peekMediaModelsCatalog('drama')?.image_models ?? null) || undefined,
```

`frontend/src/lib/dramaVideoGenQueue.ts`: cùng hai import; trong `startJob`, thay `model_id: job.options.model_id,` bằng:

```ts
          // Model đã bị admin gỡ → bỏ trống (Tự động); catalog chưa tải thì gửi nguyên giá trị
          model_id: reconcileCatalogModel(job.options.model_id, peekMediaModelsCatalog('drama')?.video_models ?? null) || undefined,
```

(`dramaApi.generateImage/generateVideo` khai báo `model_id?: string` trong `frontend/src/api/drama.ts`, nên `undefined` bị bỏ khỏi JSON = request không có model.)

- [ ] **Step 15: Component `frontend/src/components/studio/MediaModelGrid.tsx`**

```tsx
import type { MediaModelOption } from '../../api'

type MediaModelGridProps = {
  title: string
  hint: string
  emptyText: string
  recommendedLabel: string
  autoLabel: string
  autoDesc: string
  models: MediaModelOption[]
  value: string
  onChange: (id: string) => void
}

/** Lưới chọn model ảnh/video ở trang phong cách video kiến thức: ô "Tự động" (rỗng) + các model; catalog rỗng thì hiện lời nhắc */
export default function MediaModelGrid({
  title,
  hint,
  emptyText,
  recommendedLabel,
  autoLabel,
  autoDesc,
  models,
  value,
  onChange,
}: MediaModelGridProps) {
  return (
    <div className="pf-style-block">
      <h3>{title}</h3>
      <p className="pf-muted" style={{ fontSize: '0.78rem', margin: '0 0 0.65rem' }}>
        {hint}
      </p>
      {models.length === 0 ? (
        <p className="pf-muted" role="status" style={{ fontSize: '0.85rem', margin: 0 }}>
          {emptyText}
        </p>
      ) : (
        <div className="pf-model-grid">
          <button
            type="button"
            className={!value ? 'pf-model-opt selected' : 'pf-model-opt'}
            onClick={() => onChange('')}
          >
            <div className="pf-model-opt-title">
              <span>{autoLabel}</span>
            </div>
            <div className="pf-model-opt-desc">{autoDesc}</div>
          </button>
          {models.map((m) => (
            <button
              key={m.id}
              type="button"
              className={value === m.id ? 'pf-model-opt selected' : 'pf-model-opt'}
              onClick={() => onChange(m.id)}
            >
              <div className="pf-model-opt-title">
                <span>{m.label}</span>
                {m.recommended ? <span className="pf-model-badge">{recommendedLabel}</span> : null}
              </div>
              {m.description ? <div className="pf-model-opt-desc">{m.description}</div> : null}
              <div className="pf-model-opt-provider">{m.provider}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 16: `StyleConfigPage.tsx`**

(a) Import: đổi `import type { MediaModelOption, MediaModelsCatalog, PipelineMode, Project, Template, VoicePreset } from '../../api'` thành `import type { MediaModelsCatalog, PipelineMode, Project, Template, VoicePreset } from '../../api'`; thêm `import MediaModelGrid from '../../components/studio/MediaModelGrid'` và `import { reconcileCatalogModel } from '../../lib/mediaModelChoice'`.

(b) Trong effect tải dữ liệu, thay (dòng ~75–82):

```tsx
    api
      .mediaModels()
      .then((cat) => {
        setMediaCatalog(cat)
        setImageModel((prev) => prev || cat.defaults.image_model)
        setVideoModel((prev) => prev || cat.defaults.video_model)
      })
      .catch(() => setMediaCatalog(null))
```

bằng (không ghim `defaults.*` nữa):

```tsx
    api
      .mediaModels('kepu')
      .then(setMediaCatalog)
      .catch(() => setMediaCatalog(null))
```

(c) Thêm effect ngay sau effect đó:

```tsx
  useEffect(() => {
    // Model đã lưu bị admin gỡ → Tự động (''), tránh lưu dự án với id cũ
    if (!mediaCatalog) return
    setImageModel((prev) => reconcileCatalogModel(prev, mediaCatalog.image_models))
    setVideoModel((prev) => reconcileCatalogModel(prev, mediaCatalog.video_models))
  }, [mediaCatalog, project])
```

(d) Trong hàm lưu + tạo (`api.updateProject(project.id, { … image_model: imageModel, video_model: videoModel })`), thay hai dòng đó bằng:

```tsx
        image_model: reconcileCatalogModel(imageModel, mediaCatalog?.image_models ?? null),
        video_model: reconcileCatalogModel(videoModel, mediaCatalog?.video_models ?? null),
```

(e) Thay hai khối `{mediaCatalog ? ( <div className="pf-style-block"> … image_models … ) : null}` và `{mediaCatalog && pipelineMode === 'full' ? ( … video_models … ) : null}` bằng:

```tsx
          {mediaCatalog ? (
            <MediaModelGrid
              title={t('studioStyle.imageModel')}
              hint={t('studioStyle.imageModelHint')}
              emptyText={t('studioStyle.noImageModels')}
              recommendedLabel={t('studioStyle.recommended')}
              autoLabel={t('studioStyle.modelAuto')}
              autoDesc={t('studioStyle.modelAutoDesc')}
              models={mediaCatalog.image_models}
              value={imageModel}
              onChange={setImageModel}
            />
          ) : null}

          {mediaCatalog && pipelineMode === 'full' ? (
            <MediaModelGrid
              title={t('studioStyle.videoModel')}
              hint={t('studioStyle.videoModelHint')}
              emptyText={t('studioStyle.noVideoModels')}
              recommendedLabel={t('studioStyle.recommended')}
              autoLabel={t('studioStyle.modelAuto')}
              autoDesc={t('studioStyle.modelAutoDesc')}
              models={mediaCatalog.video_models}
              value={videoModel}
              onChange={setVideoModel}
            />
          ) : null}
```

- [ ] **Step 17: Xác nhận không còn ghim mặc định / gọi không scope**

Run: `cd frontend && grep -rn "defaults\.image_model\|defaults\.video_model\|useMediaModelsCatalog()\|mediaModels()" src`
Expected: không có kết quả.

- [ ] **Step 18: Lint + build + test**

Run: `cd frontend && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 19: Commit**

```bash
git add frontend/package.json frontend/tests frontend/src
git commit -m "feat(frontend): chọn model theo scope với tuỳ chọn Tự động, báo rõ khi chưa cấu hình

Model rỗng để backend chia luân phiên theo tỉ lệ admin đặt; model đã bị gỡ được bỏ trước khi gửi nên người dùng không bị lỗi, và vẫn tạo được khi chưa cấu hình.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Frontend — bỏ mọi chữ "TokenFree" trong i18n / copy, nhận diện lỗi kết nối không theo host

**Files:**
- Modify: `frontend/src/i18n/locales/{zh,en,vi}/errors.ts`, `…/dramaGen.ts`, `…/pages.ts`
- Modify: `frontend/src/lib/legalContent.ts`, `frontend/src/lib/dramaGenError.ts`, `frontend/src/lib/dramaGenerationOptions.ts`, `frontend/src/lib/dramaVideoGenerationOptions.ts`

**Interfaces:** không đổi key; chỉ đổi giá trị chuỗi và regex.

- [ ] **Step 1: `errors.ts` — thay chuỗi (Edit từng chuỗi cũ → mới, giữ nguyên key)**

zh:
| Cũ | Mới |
|---|---|
| `'请稍后重试；若反复失败，检查网络/代理是否能访问 TokenFree，以及后台模型渠道密钥。'` | `'请稍后重试；若反复失败，检查网络/代理是否能访问模型服务商，以及后台配置的服务商密钥。'` |
| `'已经连上 TokenFree，但出图/出视频等待超过上限。` | `'已经连上模型服务商，但出图/出视频等待超过上限。` (phần sau giữ nguyên) |
| `并确认后台 TokenFree 渠道密钥有效。'` | `并确认后台配置的服务商密钥有效。'` |
| `'请重新生成一次；新版本会写出明确错误。仍失败时检查 TokenFree 网络与密钥。'` | `'请重新生成一次；新版本会写出明确错误。仍失败时检查网络与服务商密钥。'` |
| `'请联系站点管理员在 TokenFree 控制台充值；充值完成后请重试生图。'` | `'请联系站点管理员为模型服务商账户充值；充值完成后请重试生图。'` |
| `'请联系管理员在 TokenFree 控制台充值后再重试；充值后重新生成该分镜即可。'` | `'请联系管理员为模型服务商账户充值后再重试；充值后重新生成该分镜即可。'` |

en:
| Cũ | Mới |
|---|---|
| `check that your network or proxy can reach TokenFree and that the model channel key in the admin panel is valid.'` | `check that your network or proxy can reach the model provider and that the provider key in the admin panel is valid.'` |
| `'TokenFree was reachable, but the image or video took longer than the limit.` | `'The model provider was reachable, but the image or video took longer than the limit.` |
| `and make sure the TokenFree channel key in the admin panel is valid.'` | `and make sure the provider key in the admin panel is valid.'` |
| `If it still fails, check the TokenFree network and key.'` | `If it still fails, check the network and the provider key.'` |
| `'Please ask the site admin to top up in the TokenFree console, then generate the image again.'` | `'Please ask the site admin to top up the model provider account, then generate the image again.'` |
| `'Ask the admin to top up in the TokenFree console, then generate this shot again.'` | `'Ask the admin to top up the model provider account, then generate this shot again.'` |

vi:
| Cũ | Mới |
|---|---|
| `hãy kiểm tra mạng/proxy có kết nối được TokenFree không và key kênh mô hình trong trang quản trị còn hiệu lực không.'` | `hãy kiểm tra mạng/proxy có kết nối được nhà cung cấp mô hình không và key nhà cung cấp trong trang quản trị còn hiệu lực không.'` |
| `'Đã kết nối được TokenFree nhưng` | `'Đã kết nối được nhà cung cấp mô hình nhưng` |
| `và kiểm tra key kênh TokenFree trong trang quản trị.'` | `và kiểm tra key nhà cung cấp trong trang quản trị.'` |
| `hãy kiểm tra kết nối và key TokenFree.'` | `hãy kiểm tra kết nối và key nhà cung cấp.'` |
| `'Vui lòng báo cho chúng tôi để nạp tiền vào TokenFree, sau đó tạo ảnh lại.'` | `'Vui lòng báo cho chúng tôi để nạp tiền vào tài khoản nhà cung cấp mô hình, sau đó tạo ảnh lại.'` |
| `'Vui lòng báo cho chúng tôi để nạp thêm vào TokenFree, sau đó tạo lại phân cảnh này.'` | `'Vui lòng báo cho chúng tôi để nạp thêm vào tài khoản nhà cung cấp mô hình, sau đó tạo lại phân cảnh này.'` |

- [ ] **Step 2: `dramaGen.ts`**

- zh: `upstreamTip: '需管理员为模型服务商账户充值，用户端充值无法解决。',` ; `upstreamShort: '需管理员为模型服务商账户充值。',`
- en: `upstreamTip: 'We need to top up the model provider account. Topping up your wallet won’t fix this.',` ; `upstreamShort: 'We need to top up the model provider account.',`
- vi: `upstreamTip: 'Chúng tôi cần nạp tiền cho tài khoản nhà cung cấp mô hình. Nạp thêm tiền vào ví của bạn sẽ không khắc phục được lỗi này.',` ; `upstreamShort: 'Chúng tôi cần nạp tiền cho tài khoản nhà cung cấp mô hình.',`

- [ ] **Step 3: `pages.ts` (`billing1`)**

- zh: `billing1: '拆分镜、出图、配音、AI 视频按模型服务商官方价计费（不加价）',`
- en: `billing1: 'Storyboard, stills, voice, and AI video are billed at the model provider’s list price (no markup)',`
- vi: `billing1: 'Phân cảnh, ảnh, giọng đọc và video AI tính đúng theo giá gốc của nhà cung cấp mô hình (không cộng thêm)',`

- [ ] **Step 4: `legalContent.ts`**

- Dòng zh: `'生成类任务按 TokenFree 官方成本计费（与上游一致，不再加价）；` → `'生成类任务按模型服务商官方价计费（与上游一致，不再加价）；` (phần sau giữ nguyên).
- Dòng vi: `'Các lần tạo nội dung được tính phí theo giá chính thức của TokenFree (đúng bằng giá gốc của nhà cung cấp mô hình, không cộng thêm).` → `'Các lần tạo nội dung được tính phí đúng theo giá gốc của nhà cung cấp mô hình (không cộng thêm).` (phần sau giữ nguyên).

- [ ] **Step 5: `dramaGenError.ts` — nhận diện lỗi kết nối theo loại lỗi, không theo host**

Thay:

```ts
  if (/网络错误|ConnectError|ConnectTimeout|无法连接上游|tokenfree\.com|api\.kie\.ai/i.test(text)) {
```

bằng:

```ts
  // Lỗi kết nối nhận theo loại exception / câu backend (providers/base.py, exc_format.py), không theo host provider
  if (/网络错误|ConnectError|ConnectTimeout|无法连接上游/i.test(text)) {
```

- [ ] **Step 6: Comment còn nhắc TokenFree**

- `frontend/src/lib/dramaGenerationOptions.ts` dòng 1: `/** 漫剧生图：模型 / 比例 / 清晰度选项（模型列表来自后台 /api/media-models?scope=drama） */`
- `frontend/src/lib/dramaVideoGenerationOptions.ts` dòng 1: `/** 漫剧画布 / 分集：视频生成选项（模型列表来自后台 /api/media-models?scope=drama） */`; dòng `/** 任意非空字符串均可作为视频模型 id（后台 TokenFree 目录） */` → `/** 任意非空字符串均可作为视频模型 id（由后台功能分配决定是否可用） */`

- [ ] **Step 7: Xác nhận sạch**

Run: `cd frontend && grep -rni "tokenfree\|api\.kie\.ai" src`
Expected: không có kết quả.

- [ ] **Step 8: Lint + build + test**

Run: `cd frontend && npm run lint && npm run build && npm test`
Expected: không lỗi.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "fix(frontend): bỏ chữ TokenFree khỏi thông báo lỗi, giá và điều khoản

Hệ thống không còn đi qua TokenFree nên lời khuyên phải trỏ tới nhà cung cấp mô hình chung; lỗi kết nối nhận theo loại lỗi thay vì tên miền.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Tài liệu — README, `docs/PROVIDERS.md`, ghi chú phát hành `docs/releases/`

**Files:**
- Modify: `README.md`
- Modify: `docs/PROVIDERS.md`
- Create (không commit, thư mục bị `.gitignore`): `docs/releases/<YYYY-MM-DD>-provider-migration.md`

**Interfaces:** không có mã.

- [ ] **Step 1: `README.md`**

- Dòng `可在管理后台 **系统设置 → 模型** 填写渠道 Key 并拉取模型；…` thay bằng:

```markdown
在管理后台 **系统设置 → Mô hình**：左栏添加 provider（OpenAI / BytePlus ModelArk / OpenRouter / BytePlus Seed Speech / 自定义 OpenAI 兼容），填 Key、测试连接、勾选启用的模型；右栏把模型分配到 4 个能力槽（文本 / 图片 / 视频 / 配音），需要时再按功能单独覆盖，多个模型按权重轮流使用。`deploy/.env.docker` 或 `backend/.env` 仅作首次导入（DB 已有 provider 后不再生效）。
```

- Mục 6.5: `开源默认按 TokenFree 官方成本、不再加价。` → `默认按各 provider 官方美元价目（管理后台「支付与汇率 → 模型价目」可改）、不再加价。`

- [ ] **Step 2: `docs/PROVIDERS.md`**

Ngay trước tiêu đề `### Cấu hình qua curl khi chưa có UI` chèn:

```markdown
### Cấu hình qua trang quản trị

Admin → **Hệ thống → Mô hình** (màn 2 cột):

- **Cột trái — Provider**: “+ Thêm provider” → chọn mẫu (OpenAI, BytePlus ModelArk, OpenRouter, BytePlus Seed
  Speech, OpenAI-compatible tuỳ chỉnh) → nhập API key → **Kiểm tra kết nối** → tick model ở phần “Model bật”
  (OpenAI: bấm “Tải danh sách”; BytePlus: danh sách tĩnh ở mục 2; luôn thêm được ID thủ công như `ep-…`) → **Lưu**.
  Provider lưu ngay; key được mã hoá. Chấm xanh = bật và đủ key, xám = thiếu key, đỏ = đang tắt.
  Không xoá được provider (hoặc bỏ tick model) đang được gán — UI báo chức năng nào đang dùng.
- **Cột phải — Gán chức năng AI**: 4 slot Văn bản / Ảnh / Video / Giọng đọc, mỗi slot chọn một hoặc nhiều
  model kèm tỉ lệ (weight). Nhóm “Ghi đè theo chức năng” cho 10 chức năng ở mục 3; để trống = dùng slot.
  Bấm **Lưu gán chức năng** ở đầu trang. Binding trỏ vào provider tắt/thiếu key vẫn được giữ, hiện badge
  “N tạm không dùng được” và không nhận yêu cầu mới.
- Bảng giá USD theo model nằm ở tab **Thanh toán & tỉ giá → mục 5** (xem `docs/BILLING.md`).
```

Đổi tiêu đề `### Cấu hình qua curl khi chưa có UI` thành `### Cấu hình qua curl (tự động hoá)`.

- [ ] **Step 3: Ghi chú phát hành (local, không commit)**

Run: `date +%F` để lấy ngày, rồi tạo `docs/releases/<ngày>-provider-migration.md`:

```markdown
# <ngày> — Bỏ TokenFree, gọi thẳng OpenAI + BytePlus ModelArk

- Nhánh: `feat/provider-migration` (Plan A: backend core; Plan B: billing; Plan C: admin UI + frontend + tài liệu)
- Spec: `docs/superpowers/specs/2026-09-22-provider-migration-design.md`

## Thay đổi chính
- Backend gọi thẳng provider qua adapter `openai` / `ark` / `volc_tts`; xoá toàn bộ module `tokenfree_*`.
- Cấu hình theo “Provider ↔ Gán chức năng AI”: 4 slot năng lực + ghi đè theo 10 chức năng, chia luân phiên theo weight.
- Tác vụ video lưu `task_runs.provider_channel_id` và poll đúng kênh đã tạo.
- Tính phí cục bộ theo bảng giá USD `provider_rates` (admin sửa được); bỏ đối chiếu dùng lượng upstream.
- Admin: tab “Mô hình” 2 cột mới; bảng giá ở tab thanh toán; task center hiện provider.
- Frontend: catalog model theo scope; báo rõ khi chưa cấu hình mô hình; bỏ chữ TokenFree.

## Đường nâng cấp (đọc trước khi deploy)
- **Kênh `tokenfree` bị xoá** ở lần khởi động đầu; cấu hình `logical_models` / `default_models` cũ bị bỏ. Không có đường tương thích ngược: admin phải thêm provider và gán lại model.
- **Tác vụ đang chạy lúc deploy** (video đang chờ poll qua TokenFree, task cũ `submit_mode == "kie"`) sẽ thất bại với thông báo "Kênh cũ không còn, hãy tạo lại" và được **hoàn tiền tạm giữ** theo luồng quyết toán thường. Nên deploy lúc ít tác vụ, hoặc chờ hàng đợi video trống.
- **Cập nhật env trước lần khởi động đầu**: `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, mặc định `https://api.openai.com/v1`), `ARK_API_KEY` (+ `ARK_BASE_URL`, mặc định mới `https://ark.ap-southeast.bytepluses.com/api/v3`), `VOLC_TTS_*`. Provider chỉ được **seed từ env đúng một lần** — khi DB chưa có provider nào; sau đó sửa env không còn tác dụng, mọi thay đổi làm ở admin → Mô hình. Env còn trỏ `tokenfree.com` sẽ không được seed.
- **`VOLC_TTS_URL` có mặc định mới** là BytePlus quốc tế (`https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/unidirectional`). Bộ key openspeech Trung Quốc (Volcengine) phải đặt `VOLC_TTS_URL=https://openspeech.bytedance.com/api/v3/tts/unidirectional` một cách tường minh (trong env trước lần khởi động đầu, hoặc làm Base URL của provider Seed Speech trong admin).
- **Key đã lưu không được dùng lại khi đổi host Base URL** (scheme + host + port): sửa Base URL của provider sang máy chủ khác thì admin phải nhập lại API key, nếu không backend trả lỗi "Đổi địa chỉ máy chủ thì phải nhập lại API key".
- Ô chọn model phía user có thêm "Tự động" (model rỗng): backend chia luân phiên theo tỉ lệ admin đặt. Model đã lưu trong dự án mà admin gỡ khỏi slot sẽ được đưa về "Tự động".
- Field flat `OPENAI_*` / `ARK_API_KEY` / `ARK_BASE_URL` / `MODEL_*` từ nay chỉ dùng để seed lần đầu và làm nhãn dòng tính phí; admin không còn hiển thị.

## Các bước triển khai
1. Sao lưu DB (ít nhất `app_settings`, `system_model_channels`, `task_runs`, `usage_events`).
2. Cập nhật env theo mục trên (key OpenAI / BytePlus, `VOLC_TTS_URL` nếu dùng key Trung Quốc).
3. Deploy backend (uvicorn một worker). Lần khởi động đầu tự: xoá kênh `tokenfree`, thêm cột `task_runs.provider_channel_id`, nới `projects.image_model/video_model` lên 128 ký tự, seed provider từ env (nếu DB chưa có provider), seed `provider_rates` mặc định.
4. Build + deploy `frontend/` và `admin/`.
5. Admin → Hệ thống → Mô hình: kiểm tra provider đã seed (hoặc thêm OpenAI / BytePlus ModelArk), Kiểm tra kết nối (lưu ý: với BytePlus nút này chỉ xác nhận đã có key), tick model, gán đủ 4 slot, Lưu gán chức năng.
6. Admin → Thanh toán & tỉ giá → mục 5: bổ sung giá cho model trong cảnh báo “chưa có giá”, Lưu.
7. `GET /api/health`: `models` không còn `not_configured`.
8. Chạy checklist hồi quy §9.2 với key thật (vòng 2).

## Rollback
- Deploy lại bản trước và khôi phục bản sao lưu `app_settings` + `system_model_channels` (kênh `tokenfree` đã bị xoá khi khởi động). Cột mới là additive, bản cũ bỏ qua được.

## Kết quả hồi quy
- Vòng mock (ARK_MOCK=true): <điền từ báo cáo Task 12>
- Vòng key thật: <điền khi chạy trên môi trường thật>
```

Run: `git check-ignore docs/releases/<ngày>-provider-migration.md`
Expected: in ra đường dẫn (file bị ignore — **không** `git add`).

- [ ] **Step 4: Commit (chỉ README + PROVIDERS.md)**

```bash
git add README.md docs/PROVIDERS.md
git commit -m "docs: hướng dẫn cấu hình provider và gán chức năng trên trang quản trị

README và PROVIDERS.md mô tả màn Mô hình 2 cột thay cho cách chỉnh bằng curl và bỏ câu tính giá theo TokenFree.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Quét cuối — không còn "tokenfree" trong `admin/src`, `frontend/src`; lint/build/test toàn bộ

**Files:** chỉ sửa nếu quét còn sót (sửa theo đúng cách của Task 4–9).

- [ ] **Step 1: Quét không phân biệt hoa thường**

Run:

```bash
grep -rni "tokenfree" admin/src frontend/src; echo "exit=$?"
grep -rni "tokenfree\|kie_fen_per_credit\|upstream-usage\|daily/sync\|tokenfree/quota" admin/src frontend/src admin/tests frontend/tests; echo "exit=$?"
```

Expected: không in dòng nào, cả hai `exit=1` (grep không khớp). Nếu còn: sửa chuỗi/comment đó (user-visible: đổi sang "nhà cung cấp mô hình" / "模型服务商" / "model provider"), chạy lại tới khi sạch.

- [ ] **Step 2: Quét endpoint admin không còn tồn tại**

Run: `grep -rn "/api/admin/settings/tokenfree\|/api/admin/stats/upstream-usage\|/api/admin/finance/daily/sync" admin/src; echo "exit=$?"`
Expected: `exit=1`.

- [ ] **Step 3: Chạy toàn bộ kiểm tra**

```bash
cd admin && npm run lint && npm run build && npm test
cd ../frontend && npm run lint && npm run build && npm test
cd ../backend && .venv/bin/python -m pytest -q -p no:cacheprovider
```

Expected: admin/frontend không lỗi; backend chỉ 2 lỗi có sẵn ở `tests/test_agent_skills.py`.

- [ ] **Step 4: Commit (nếu Step 1–2 phải sửa gì)**

```bash
git add admin/src frontend/src
git commit -m "chore: dọn nốt chữ TokenFree còn sót trong admin và frontend

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Nếu không có gì để sửa: không commit, ghi "quét sạch" vào báo cáo.

---

### Task 12: Hồi quy thủ công §9.2 trên trình duyệt (vòng mock) và báo cáo

**Files:**
- Modify: `admin/vite.config.ts` (đích proxy đọc biến môi trường)

**Interfaces:** không có mã mới ngoài vite config.

- [ ] **Step 1: Cho admin dev server trỏ backend khác cổng 8000**

Trong `admin/vite.config.ts`, trên `export default defineConfig` thêm:

```ts
// Đích proxy /api, /static: mặc định backend dev :8000; smoke test đặt ADMIN_API_TARGET để không đụng server đang chạy
const apiTarget = process.env.ADMIN_API_TARGET || "http://127.0.0.1:8000";
```

và thay hai `target: "http://127.0.0.1:8000",` bằng `target: apiTarget,`.

Run: `cd admin && npm run build` → không lỗi. Commit:

```bash
git add admin/vite.config.ts
git commit -m "chore(admin): cho phép đổi đích proxy dev qua ADMIN_API_TARGET

Để chạy smoke test với backend cổng riêng mà không đụng server dev đang chạy ở cổng 8000.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: DB riêng cho smoke test**

```bash
cd backend && .venv/bin/python - <<'EOF'
import os, re
from dotenv import dotenv_values
import psycopg2
url = dotenv_values(".env").get("DATABASE_URL_SYNC") or os.environ["DATABASE_URL_SYNC"]
m = re.match(r"postgresql\+psycopg2://([^:]+):([^@]+)@([^:/]+):(\d+)/(.+)", url)
user, pwd, host, port, _ = m.groups()
conn = psycopg2.connect(user=user, password=pwd, host=host, port=port, dbname="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='printfilm_plan_c'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE printfilm_plan_c")
print("ok", user, host, port)
EOF
```

Expected: `ok …`. (Nếu `python-dotenv` không có, đọc `.env` bằng tay; không in mật khẩu.) Ghi lại `PLANC_ASYNC=postgresql+asyncpg://<user>:<pwd>@<host>:<port>/printfilm_plan_c` và `PLANC_SYNC=postgresql+psycopg2://…/printfilm_plan_c` vào biến shell cho bước sau (không ghi vào file trong repo).

- [ ] **Step 3: Chạy backend cổng 8765 (nền), frontend 5273, admin 5274 (nền)**

```bash
cd backend && DATABASE_URL="$PLANC_ASYNC" DATABASE_URL_SYNC="$PLANC_SYNC" ARK_MOCK=true \
  CORS_ORIGINS="http://localhost:5273,http://127.0.0.1:5273,http://localhost:5274,http://127.0.0.1:5274" \
  .venv/bin/uvicorn app.main:app --port 8765
cd frontend && VITE_API_BASE=http://127.0.0.1:8765 npx vite --port 5273 --strictPort
cd admin && ADMIN_API_TARGET=http://127.0.0.1:8765 npx vite --port 5274 --strictPort
```

(Mỗi lệnh chạy bằng `run_in_background`.) Chờ `curl -s http://127.0.0.1:8765/api/health` trả JSON có `"status"`.

- [ ] **Step 4: Tạo tài khoản admin smoke**

```bash
curl -s -X POST http://127.0.0.1:8765/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"planc-admin@cineai.dev","password":"planc-smoke-123","nickname":"Plan C"}'
cd backend && DATABASE_URL_SYNC="$PLANC_SYNC" .venv/bin/python - <<'EOF'
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL_SYNC"])
with e.begin() as c:
    c.execute(text("UPDATE users SET role='admin', balance_fen=100000 WHERE email='planc-admin@cineai.dev'"))
print("admin ok")
EOF
```

- [ ] **Step 5: Chạy checklist §9.2 vòng mock bằng trình duyệt**

Dùng công cụ trình duyệt có sẵn (Playwright MCP hoặc Claude in Chrome). Đăng nhập admin tại `http://127.0.0.1:5274`, user tại `http://127.0.0.1:5273` bằng `planc-admin@cineai.dev`. Với mỗi mục ghi **Đạt / Không đạt / Không chạy được (lý do)** và bằng chứng ngắn (URL, ảnh chụp, id task):

6. **Admin** (làm trước để có cấu hình):
   - Tab “Mô hình”: thêm provider BytePlus ModelArk (key giả `sk-test`), Kiểm tra kết nối → phải hiện “Đã có key (chưa gọi thử provider)” kèm câu giải thích BytePlus không có endpoint kiểm tra, tick `dola-seedream-5-0-pro-260628`, `dreamina-seedance-2-5-260628`, `seed-2-0-pro-260328`, Lưu. Thêm OpenAI (key giả) → Kiểm tra kết nối phải báo lỗi rõ ràng (không crash), thêm ID thủ công `gpt-4o-mini-tts`, Lưu.
   - Gán 4 slot + 1 ghi đè (`tools.image` → seedream), Lưu gán chức năng; header hiện “4/4 slot đã gán”; `GET /api/admin/settings/routing` phản ánh đúng.
   - Thử bỏ tick model đang gán → hộp thoại chặn, nêu chức năng; thử xoá provider đang gán → chặn; sửa Base URL BytePlus sang `https://ark.cn-beijing.volces.com/api/v3` mà không nhập key → chặn với “Đổi địa chỉ máy chủ (Base URL) thì phải nhập lại API key.” (Huỷ, không lưu).
   - Admin không còn ô/nhãn nào của field flat `openai_*` / `ark_api_key` / `ark_base_url` / `model_*` hay nút nhập từ env.
   - Tắt provider BytePlus → chip gạch đứt + badge “N tạm không dùng được”; `GET /api/media-models?scope=kepu` không còn model của BytePlus; bật lại.
   - Tab thanh toán: bảng giá tải được, đổi thứ tự ↑/↓, thêm dòng, Lưu; nhập đơn vị sai qua PUT tay (curl) → 400 tiếng Việt hiển thị đúng khi lưu từ UI với `usd` âm. Tab tham số chạy: nhãn tiếng Việt, readiness đúng. Dashboard/Finance không còn card/nút đối chiếu; Network không có request 404 tới endpoint đã xoá.
   - Task center: sau các bước 1–3 bên dưới, cột loại task hiện `provider: …` với task video; chi tiết task tab tính phí có cột Provider.
7. **Không key** (vòng này chính là mock): luồng 1–4 chạy hết trạng thái.
1. **Video kiến thức**: tạo dự án từ chủ đề → kịch bản → ảnh phân cảnh → video → lời dẫn → dựng (mode `full`) tới `DONE`; mode `image_text`; tạo lại ảnh/video/audio một phân cảnh; đổi mô hình ảnh/video ở trang phong cách và xác nhận trong task center model đó được ghi ở dòng usage.
   - “Tự động”: dự án mới mặc định chọn ô “Tự động” (không ghim model); để 2 model trong slot Ảnh, tạo vài ảnh ở chế độ Tự động và xem dòng usage dùng luân phiên; chọn một model cụ thể, lưu, rồi admin gỡ model đó khỏi slot → mở lại trang phong cách thấy về “Tự động” và bấm tạo không bị lỗi `project.invalid_image_model`.
   - Trường hợp rỗng: gỡ hết binding slot Ảnh ở admin → trang phong cách hiện lời nhắc “Chưa cấu hình mô hình tạo ảnh — hãy liên hệ với chúng tôi…”, bấm tạo vẫn không bị chặn ở frontend (ghi lại phản hồi backend); gán lại.
8. (tiếp) **Phim ngắn**: tạo project → tóm tắt / chia tập → seed tư liệu → tạo ảnh nhân vật/bối cảnh/đạo cụ → video tư liệu → tách phân cảnh → tạo video phân cảnh trên canvas (hàng đợi, huỷ, thử lại, nối khung hình cuối) → lồng tiếng. Kiểm tra bộ chọn mô hình hiện đúng danh sách scope `drama`, có mục “Tự động” đứng đầu và được chọn sẵn, khi rỗng hiện lời nhắc mới; model đã chọn rồi bị admin gỡ thì request tạo (tab Network) không còn gửi `model_id` cũ.
3. **Công cụ**: t2i, i2p (ảnh tham chiếu), t2v / i2v; Lịch sử công cụ.
4. **Open API**: tạo API key trong Cài đặt → gọi `POST /api/v1/images/generations` và endpoint video `/api/v1` bằng curl với `X-Api-Key`, poll tới xong.
5. **Billing**: bật `billing_enabled` ở tab thanh toán; một lần tạo ảnh: số dư bị tạm giữ → trừ thật → hoàn phần dư; số tiền khớp bảng giá (fen xem trước × số ảnh); hiển thị VND; tạo đơn nạp tiền và xác nhận ở trang Đơn hàng.
   - Chuyển ngôn ngữ user sang vi/en/zh, xác nhận không còn chữ TokenFree ở trang Bảng giá, Điều khoản, thông báo lỗi phim ngắn.

- [ ] **Step 6: Dọn dẹp**

Dừng 3 tiến trình nền (TaskStop hoặc `kill` đúng PID đã khởi động — không dùng `pkill` rộng có thể trúng server của người dùng). Để lại DB `printfilm_plan_c` (ghi tên vào báo cáo để người dùng tự xoá nếu muốn).

- [ ] **Step 7: Báo cáo**

Trong báo cáo cuối của task (không tạo file .md): bảng 7 mục §9.2 × kết quả vòng mock, lỗi tìm thấy (kèm bước tái hiện), mục chưa chạy được và lý do. Ghi rõ **vòng 2 (key thật OpenAI + BytePlus) chưa chạy — cần người dùng chạy với key thật** theo cùng checklist. Chép phần kết quả vòng mock vào mục “Kết quả hồi quy” của `docs/releases/<ngày>-provider-migration.md` (file local, không commit). Lỗi chức năng tìm thấy: báo lại, không tự sửa ngoài phạm vi Plan C.

---

## Tự rà soát (đã làm khi viết plan)

- **Phủ spec + review Plan A**: §5.4 → Task 8 (scope, “Tự động” = model rỗng, không ghim `defaults.*`, làm sạch model bị gỡ trước khi lưu/gửi); host-change key + câu kiểm tra kết nối ark/volc_tts → Task 1, 3; `TaskRunBriefOut.provider_channel_id` → Task 7; field flat đã chết → Task 6; ghi chú nâng cấp (xoá kênh tokenfree, task đang chạy thất bại + hoàn tiền, env seed một lần, `VOLC_TTS_URL`, key theo host) → Task 10 + Task 9 (chuỗi TokenFree, regex `dramaGenError`); §7.1 → Task 1–4 (CSS `settings-providers-layout` grid 280px + 1fr, dưới 900px xếp dọc; sidebar chấm trạng thái, “1 key”/“Chưa có key”; `ProviderDialog` preset/test/model bật/ID thủ công/xoá có xác nhận và chặn khi đang gán; header “N/4 slot đã gán” + thanh tiến độ; badge “Chưa gán” / “N tạm không dùng được”; `ModelPickerDialog` tick nhiều + weight + tìm; nhóm ghi đè 10 hàng “Dùng slot …”; lỗi validation tiếng Việt dưới header); §7.2 → dùng nguyên API Plan A/B; §7.3 → Task 5 (Payment), Task 6 (Runtime, Dashboard, Finance), Task 7 (task center), Task 4 (xoá `tokenfreeRecommendedModels.ts`, `RoutingSettingsPanel.tsx`); §9.2 → Task 12; §9.3 → Task 10 (`docs/BILLING.md`, `CLAUDE.md` thuộc Plan B).
- **Kiểu nhất quán**: `ProviderDraft`, `bindingKey`, `withSlot/withOverride`, `providerSaveBlockers(initial, draft, others, bindingSets, catalog)`, `providerDeleteBlocker(id, bindingSets, catalog)`, `toProviderPatch`, `saveProviders(): Promise<string | null>`, `ProviderDialog.onSave/onDelete: Promise<string | null>`, `ModelPickerDialog.onClose`, `useMediaModelsCatalog(scope)`, `reconcileCatalogModel(current, models | null)`, `peekMediaModelsCatalog(scope)`, `urlOrigin`, `connectionTestLabel` dùng cùng tên/chữ ký ở mọi task.
