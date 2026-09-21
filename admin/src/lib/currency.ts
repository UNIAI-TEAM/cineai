import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { api } from "@/api/client";

/** 服务端 /api/billing/currency 返回：默认货币、可选项与「1 分折合多少该货币」 */
export type CurrencyInfo = {
  default: string;
  options: string[];
  per_fen: Record<string, number>;
};

/** 管理员展示货币选择的本地持久化键 */
const STORAGE_KEY = "printfilm.admin.currency";

/** 接口不可用时的兜底汇率（1 CNY = 3600 VND，1 USD = 7 CNY） */
const FALLBACK_INFO: CurrencyInfo = {
  default: "VND",
  options: ["VND", "USD"],
  per_fen: { VND: 36, USD: 1 / 700 },
};

type CurrencyState = {
  info: CurrencyInfo;
  currency: string;
  loaded: boolean;
};

// 读取本地持久化的货币选择（隐私模式等场景可能抛错）
function readStoredCurrency(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

// 写入本地持久化的货币选择
function writeStoredCurrency(code: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // 忽略存储失败
  }
}

/*
 * state 模块级货币状态（所有页面共享）
 * inflight 正在进行的 /api/billing/currency 请求
 * listeners useSyncExternalStore 订阅者
 */
let state: CurrencyState = {
  info: FALLBACK_INFO,
  currency: readStoredCurrency() ?? FALLBACK_INFO.default,
  loaded: false,
};
let inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();

// 替换状态并通知订阅者
function setState(next: CurrencyState) {
  state = next;
  listeners.forEach((fn) => fn());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): CurrencyState {
  return state;
}

/** 拉取一次货币配置并缓存到模块（失败时保留兜底值，下次挂载再重试） */
export function ensureCurrencyLoaded(): Promise<void> {
  if (state.loaded) return Promise.resolve();
  if (inflight) return inflight;
  inflight = api<CurrencyInfo>("/api/billing/currency")
    .then((info) => {
      const options = info.options?.length ? info.options : FALLBACK_INFO.options;
      const normalized: CurrencyInfo = {
        default: info.default || options[0],
        options,
        per_fen: { ...FALLBACK_INFO.per_fen, ...(info.per_fen ?? {}) },
      };
      const stored = readStoredCurrency();
      const currency = stored && options.includes(stored) ? stored : normalized.default;
      setState({ info: normalized, currency, loaded: true });
    })
    .catch(() => {
      // 接口不可用：沿用兜底汇率，不阻塞页面
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** 切换展示货币（不在可选项内则忽略）并持久化 */
export function setDisplayCurrency(code: string) {
  if (!state.info.options.includes(code) || code === state.currency) return;
  writeStoredCurrency(code);
  setState({ ...state, currency: code });
}

/** 分 → 目标货币数值（未格式化） */
export function fenToAmount(fen: number, currency: string, perFen: Record<string, number>): number {
  const rate = perFen[currency];
  if (!rate) return fen / 100;
  return fen * rate;
}

/** 分 → 表单输入用字符串（VND 取整，其他两位小数，不带千分位） */
export function fenToInputValue(fen: number, currency: string, perFen: Record<string, number>): string {
  const amount = fenToAmount(fen, currency, perFen);
  return currency === "VND" ? String(Math.round(amount)) : amount.toFixed(2);
}

/** 目标货币数值 → 分（四舍五入，用于表单反向换算） */
export function amountToFen(amount: number, currency: string, perFen: Record<string, number>): number {
  const rate = perFen[currency];
  if (!rate) return Math.round(amount * 100);
  return Math.round(amount / rate);
}

const numberFormatCache = new Map<string, Intl.NumberFormat>();

// 按 locale + 小数位缓存 Intl.NumberFormat
function numberFormat(locale: string, fractionDigits: number): Intl.NumberFormat {
  const key = `${locale}:${fractionDigits}`;
  let nf = numberFormatCache.get(key);
  if (!nf) {
    nf = new Intl.NumberFormat(locale, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    });
    numberFormatCache.set(key, nf);
  }
  return nf;
}

/**
 * 按货币格式化已换算金额
 * - VND：取整、vi-VN 千分位 + " ₫"（如 1.000.000 ₫）
 * - USD："$" + 两位小数（如 $12.34，负数为 -$12.34）
 * - 其他：两位小数 + 货币代码
 */
export function formatAmount(amount: number, currency: string): string {
  const safe = Number.isFinite(amount) ? amount : 0;
  if (currency === "VND") {
    return `${numberFormat("vi-VN", 0).format(Math.round(safe))} ₫`;
  }
  if (currency === "USD") {
    const sign = safe < 0 ? "-" : "";
    return `${sign}$${numberFormat("en-US", 2).format(Math.abs(safe))}`;
  }
  return `${numberFormat("en-US", 2).format(safe)} ${currency}`;
}

/** 分 → 当前展示货币的格式化字符串（非组件场景使用；组件内请用 useCurrency().format 以响应切换） */
export function formatMoney(fen: number, currency: string = state.currency): string {
  return formatAmount(fenToAmount(fen, currency, state.info.per_fen), currency);
}

/** 当前展示货币代码（非组件场景） */
export function getDisplayCurrency(): string {
  return state.currency;
}

/**
 * 展示货币 Hook
 * 返回：currency 当前货币；options 可选项；perFen 汇率表；setCurrency 切换；
 * format(fen) 分 → 当前货币字符串；formatAmount(amount, currency) 已换算金额格式化；
 * toAmount(fen) / toInput(fen) / toFen(amount) 表单双向换算。
 */
export function useCurrency() {
  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => {
    void ensureCurrencyLoaded();
  }, []);

  const { currency, info } = snap;
  const perFen = info.per_fen;

  const format = useCallback(
    (fen: number) => formatAmount(fenToAmount(fen, currency, perFen), currency),
    [currency, perFen],
  );
  const toAmount = useCallback((fen: number) => fenToAmount(fen, currency, perFen), [currency, perFen]);
  const toInput = useCallback((fen: number) => fenToInputValue(fen, currency, perFen), [currency, perFen]);
  const toFen = useCallback((amount: number) => amountToFen(amount, currency, perFen), [currency, perFen]);

  return useMemo(
    () => ({
      currency,
      options: info.options,
      perFen,
      loaded: snap.loaded,
      setCurrency: setDisplayCurrency,
      format,
      formatAmount,
      toAmount,
      toInput,
      toFen,
    }),
    [currency, info.options, perFen, snap.loaded, format, toAmount, toInput, toFen],
  );
}
