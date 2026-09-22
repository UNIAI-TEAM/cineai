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
