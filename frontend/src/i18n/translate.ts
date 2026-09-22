import { getActiveLocale } from './detect'
import { interpolate, lookupMessage, type TVars } from './lookup'
import { messages } from './messages'

/**
 * 按当前界面语言翻译（非 React 场景 / effect 内使用，无需把 t 放进依赖）。
 * 参数 path：文案路径；vars：插值变量。缺 key 时返回 path，与 useI18n().t 一致。
 */
export function translate(path: string, vars?: TVars): string {
  const raw = lookupMessage(messages[getActiveLocale()], path)
  if (raw === undefined) return path
  return interpolate(raw, vars)
}
