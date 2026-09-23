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
  mergeProviderEdit,
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
    "Slot Ảnh: nhà cung cấp 'ghost' không tồn tại",
    "Slot Video: model 'dola-seedream-5-0-pro-260628' không phải model video",
    "Slot Giọng đọc: model 'not-enabled-tts' chưa được bật ở nhà cung cấp BytePlus ModelArk",
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
    "Cần nhập tên nhà cung cấp",
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
    "Nhà cung cấp đang được gán cho: Video phim ngắn. Hãy đổi gán trước khi xoá.",
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
  assert.equal(connectionTestLabel("ark", { ok: true, message: "Kết nối thành công, 17 model" }), "Đã có key (chưa gọi thử nhà cung cấp)");
  assert.equal(connectionTestLabel("volc_tts", { ok: false, message: "Cần API key" }), "Cần API key");
});

test("mergeProviderEdit applies a save or delete on top of the fresh provider list", () => {
  const a = draft({ id: "a", name: "A" });
  const b = draft({ id: "b", name: "B" });
  const fresh = [a, b];
  // Sửa: chỉ thay đúng provider đó, giữ nguyên provider khác (kể cả bản mới từ phiên khác)
  const editedA = { ...a, name: "A2" };
  assert.deepEqual(mergeProviderEdit(fresh, { kind: "save", draft: editedA }), [editedA, b]);
  // Thêm mới: nối vào cuối danh sách mới nhất
  const c = draft({ id: "c", name: "C", is_new: true });
  assert.deepEqual(mergeProviderEdit(fresh, { kind: "save", draft: c }), [a, b, c]);
  // Thêm mới trùng id vừa được phiên khác tạo
  assert.equal(
    mergeProviderEdit(fresh, { kind: "save", draft: { ...c, id: "b" } }),
    "ID 'b' đã tồn tại, hãy chọn ID khác",
  );
  // Sửa provider vừa bị phiên khác xoá
  assert.equal(
    mergeProviderEdit([b], { kind: "save", draft: editedA }),
    "Nhà cung cấp này vừa bị xoá ở phiên khác, hãy tải lại trang",
  );
  // Xoá: chỉ bỏ đúng id, giữ provider khác
  assert.deepEqual(mergeProviderEdit(fresh, { kind: "delete", id: "a" }), [b]);
});
