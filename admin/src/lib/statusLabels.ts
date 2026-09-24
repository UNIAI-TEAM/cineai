/** Project pipeline status → nhãn tiếng Việt */
export const PROJECT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Bản nháp",
  SCRIPTING: "Đang viết kịch bản",
  SCRIPT_READY: "Đã có kịch bản",
  IMAGING: "Đang tạo ảnh phân cảnh",
  IMAGE_READY: "Đã có ảnh phân cảnh",
  VIDEOING: "Đang tạo video",
  VIDEO_READY: "Đã có video",
  AUDIOING: "Đang tạo giọng đọc",
  COMPOSING: "Đang dựng video",
  AUDITING: "Đang duyệt",
  DONE: "Hoàn tất",
  REJECTED: "Bị từ chối",
  FAILED: "Thất bại",
  CANCELLED: "Đã huỷ",
};

/** Order payment status → nhãn tiếng Việt */
export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "Chờ thanh toán",
  paid: "Đã thanh toán",
  closed: "Đã đóng",
};

/** Work audit / visibility → nhãn tiếng Việt */
export const AUDIT_STATUS_LABELS: Record<string, string> = {
  pending: "Chờ duyệt",
  passed: "Đã duyệt",
  rejected: "Bị từ chối",
};

export const VISIBILITY_LABELS: Record<string, string> = {
  public: "Công khai",
  private: "Riêng tư",
  unlisted: "Không công khai (ai có link xem được)",
};

/** Wallet ledger kind → nhãn tiếng Việt */
export const LEDGER_KIND_LABELS: Record<string, string> = {
  topup: "Nạp tiền",
  grant: "Tặng",
  adjust: "Điều chỉnh số dư",
  freeze: "Tạm giữ",
  unfreeze: "Hoàn tạm giữ",
  settle: "Quyết toán",
  refund: "Hoàn tiền",
};

/** Payment channel → nhãn tiếng Việt（alipay / wxpay 为历史订单只读展示） */
export const PAY_TYPE_LABELS: Record<string, string> = {
  bank_transfer: "Chuyển khoản ngân hàng",
  alipay: "Alipay (cũ)",
  wxpay: "WeChat Pay (cũ)",
};

/** Unified task platform status → nhãn tiếng Việt */
export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: "Đang chờ",
  leased: "Đã nhận xử lý",
  running: "Đang chạy",
  awaiting_poll: "Chờ kết quả nhà cung cấp",
  awaiting_review: "Chờ duyệt",
  cancel_requested: "Đang huỷ",
  succeeded: "Thành công",
  failed: "Thất bại",
  cancelled: "Đã huỷ",
};

/** Task domain → nhãn tiếng Việt */
export const TASK_DOMAIN_LABELS: Record<string, string> = {
  drama: "Phim ngắn AI",
  kepu: "Video ngắn AI",
  tools: "Công cụ",
  studio: "Studio",
  api: "API mở",
};

/** Task type → nhãn tiếng Việt（轻量同步 + 平台任务） */
export const TASK_TYPE_LABELS: Record<string, string> = {
  agent_chat: "Trò chuyện với trợ lý phim ngắn",
  skill_optimize: "Tối ưu prompt Skill",
  voice_prompt: "Mô tả giọng nhân vật",
  appearance_extract: "Tách ngoại hình nhân vật",
  content_expand: "Mở rộng chủ đề",
  script_summary: "Tóm tắt kịch bản",
  episode_script: "Kịch bản từng tập",
  fragment_plan: "Chia phân cảnh bằng AI",
  fragment_video: "Video phân cảnh",
  seed_assets: "Trích xuất tư liệu",
  asset_image: "Tạo ảnh tư liệu",
  asset_video: "Tạo video tư liệu",
  voice_synthesis: "Tạo giọng đọc",
  project_pipeline: "Quy trình video kiến thức",
  shot_regen_image: "Vẽ lại ảnh một cảnh",
  shot_regen_video: "Tạo lại video một cảnh",
  shot_regen_audio: "Tạo lại giọng đọc một cảnh",
  project_regen_audio: "Tạo lại giọng đọc cả video",
  project_compose_only: "Chỉ dựng video",
  v1_image: "API tạo ảnh",
  v1_video: "API tạo video",
  v1_seedance: "API Seedance",
  tool_image: "Công cụ tạo ảnh",
  tool_video: "Công cụ tạo video",
};

// Resolve project status display text
export function projectStatusLabel(status: string): string {
  return PROJECT_STATUS_LABELS[status] ?? status;
}

// Resolve order status display text
export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}

// Resolve audit status display text
export function auditStatusLabel(status: string): string {
  return AUDIT_STATUS_LABELS[status] ?? status;
}

// Resolve visibility display text
export function visibilityLabel(status: string): string {
  return VISIBILITY_LABELS[status] ?? status;
}

// Resolve ledger kind display text
export function ledgerKindLabel(kind: string): string {
  return LEDGER_KIND_LABELS[kind] ?? kind;
}

// Resolve pay type display text
export function payTypeLabel(payType: string): string {
  return PAY_TYPE_LABELS[payType] ?? payType;
}

// Resolve task status display text
export function taskStatusLabel(status: string): string {
  return TASK_STATUS_LABELS[status] ?? status;
}

// Resolve task domain display text
export function taskDomainLabel(domain: string): string {
  return TASK_DOMAIN_LABELS[domain] ?? domain;
}

// Resolve task type display text
export function taskTypeLabel(taskType: string): string {
  return TASK_TYPE_LABELS[taskType] ?? taskType;
}

/** Filter options for project status select (value stays English for API) */
export const PROJECT_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Tất cả trạng thái" },
  ...Object.entries(PROJECT_STATUS_LABELS).map(([value, label]) => ({ value, label })),
];

/** Billing basis → nhãn tiếng Việt（后端 billing_basis_label 仍为中文，前端按 billing_basis 取） */
export const BILLING_BASIS_LABELS: Record<string, string> = {
  estimate: "Ước tính",
  upstream_usage: "Thực tế (token)",
  upstream_cost: "Thực tế (chi phí)",
  unknown: "Thực tế (chưa phân loại)",
};

// Resolve billing basis display text
export function billingBasisLabel(basis: string | null | undefined, estimated?: boolean): string {
  if (basis && BILLING_BASIS_LABELS[basis]) return BILLING_BASIS_LABELS[basis];
  return estimated ? "Ước tính" : "Thực tế";
}
