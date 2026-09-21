import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Merge Tailwind class names with conflict resolution
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 金额格式化：分 → 当前展示货币（VND / USD）；组件内优先用 useCurrency().format 以响应切换
export { formatAmount, formatMoney } from "@/lib/currency";
