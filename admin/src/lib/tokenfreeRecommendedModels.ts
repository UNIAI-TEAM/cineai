export type ModelCapability = "text" | "image" | "video" | "audio";

export type UpstreamModelOption = { id: string; label: string; capability: string };

/** 勾选推荐时补上的 TokenFree id；视频含 2.5 / 2.0 / Mini */
export const RECOMMENDED_MODEL_IDS: Record<ModelCapability, string[]> = {
  text: ["kimi-k2.6"],
  image: ["gpt-image-2-5"],
  video: ["seedance-2-5", "seedance-2-0", "seedance-2-0-mini"],
  audio: [
    "qwen-tts-2025-05-22",
    "qwen3-tts-flash",
    "gemini-3.1-flash-tts",
    "gemini-2.5-pro-preview-tts",
    "elevenlabs-tts",
    "elevenlabs/text-to-speech-multilingual-v2",
  ],
};

const CAPABILITY_ORDER: ModelCapability[] = ["text", "image", "video", "audio"];

// 把 Seedance 接入点/短名收到 TokenFree 目录 id
export function canonicalChannelModelId(model: string): string {
  const mid = (model || "").trim();
  if (!mid) return "";
  const low = mid.toLowerCase();
  if (!low.includes("seedance")) return mid;
  if (low.includes("mini")) return "seedance-2-0-mini";
  if (/(?:2-5|2\.5|260628)/.test(low)) return "seedance-2-5";
  if (/(?:2-0|2\.0|260128)/.test(low)) return "seedance-2-0";
  const compact = low.replace(/_/g, "-");
  if (compact === "seedance-2" || compact === "seedance2" || compact.endsWith("seedance-2")) {
    return "seedance-2-0";
  }
  return mid;
}

// 合并 Seedance 2.0 三档别名，保持原顺序
export function canonicalizeChannelModels(models: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of models) {
    const id = canonicalChannelModelId(raw);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

// 目录里同款 Seedance 只留一条，优先展示规范 id
export function collapseCatalogModels(models: UpstreamModelOption[]): UpstreamModelOption[] {
  const map = new Map<string, UpstreamModelOption>();
  for (const model of models) {
    const id = canonicalChannelModelId(model.id);
    if (!id) continue;
    const prev = map.get(id);
    if (!prev || model.id === id) {
      map.set(id, {
        ...model,
        id,
        label: model.id === id ? model.label || id : id,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) => a.id.localeCompare(b.id));
}

// 上游目录里实际存在的推荐 id
export function pickRecommendedModelIds(models: UpstreamModelOption[]): string[] {
  const ids = new Set(models.map((item) => canonicalChannelModelId(item.id)));
  const out: string[] = [];
  for (const cap of CAPABILITY_ORDER) {
    for (const want of RECOMMENDED_MODEL_IDS[cap]) {
      if (ids.has(want) && !out.includes(want)) out.push(want);
    }
  }
  return out;
}

// 各能力默认项；视频写逻辑 id seedance-2.5，与下拉选项对齐
export function pickRecommendedDefaults(models: UpstreamModelOption[]): Record<ModelCapability, string> {
  const ids = new Set(models.map((item) => canonicalChannelModelId(item.id)));
  const out: Record<ModelCapability, string> = { text: "", image: "", video: "", audio: "" };
  for (const cap of CAPABILITY_ORDER) {
    if (cap === "video" && (ids.has("seedance-2-5") || ids.has("seedance-2.5"))) {
      out.video = "seedance-2.5";
      continue;
    }
    out[cap] = RECOMMENDED_MODEL_IDS[cap].find((id) => ids.has(id)) || "";
  }
  return out;
}

// 勾选推荐：canonicalize 后补上短名单，不删已选的 Seedance 2.0
export function mergeRecommendedSelection(selected: string[], catalog: UpstreamModelOption[]): string[] {
  const recommended = pickRecommendedModelIds(catalog);
  return canonicalizeChannelModels([...selected, ...recommended]);
}
