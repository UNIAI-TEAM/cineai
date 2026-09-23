/** 漫剧资产生成状态（与 params.generation.status 一致） */
export const DRAMA_GENERATION_STATUSES = [
  "queued",
  "running",
  "generating",
  "done",
  "failed",
  "cancelled",
] as const;

/** 漫剧生成状态越南语标签（idle 仅用于分镜等无 params.generation 时的展示回退） */
export function dramaGenerationStatusLabel(status: string): string {
  const map: Record<string, string> = {
    queued: "Đang chờ",
    running: "Đang tạo",
    generating: "Đang tạo",
    done: "Hoàn tất",
    failed: "Thất bại",
    cancelled: "Đã huỷ",
    idle: "Chưa bắt đầu",
  };
  return map[status] ?? status;
}

/** 列表/详情展示：空值显示 — */
export function formatDramaGenerationStatus(status: string | null | undefined): string {
  if (!status) return "—";
  return dramaGenerationStatusLabel(status);
}

/** 漫剧资产类型越南语标签 */
export function dramaAssetTypeLabel(type: string): string {
  const map: Record<string, string> = {
    character: "Nhân vật",
    scene: "Bối cảnh",
    prop: "Đạo cụ",
    material: "Tư liệu thô",
    narration: "Lời dẫn",
    video: "Video",
    audio: "Âm thanh",
    text: "Văn bản",
    none: "Chưa phân loại",
  };
  return map[type] ?? type;
}
