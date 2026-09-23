/** 模板分类：数据键为中文（与后端一致），展示文案按界面语言取 */
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'

export const CATEGORY_ORDER = [
  '开源',
  '科普',
  '获客',
  '纪录片',
  '写实感',
  '真人感',
  '电影感',
  '儿童',
  '动漫',
  '国风',
  '科幻',
  '奇幻',
  '悬疑',
  '商业',
  '复古',
  '图文',
]

// 按当前界面语言取分类展示名；未登记的键：非中文界面下含汉字时显示「其他」，否则原样返回
export function categoryLabel(key: string): string {
  const pack = messages[getActiveLocale()]
  const map = pack.categories as Record<string, string>
  if (map[key]) return map[key]
  if (getActiveLocale() !== 'zh' && /[\u4e00-\u9fff]/.test(key)) return pack.settingsPanels.templates.categoryOther
  return key
}

// 兼容旧的 HOME_CATEGORY_LABELS[key] 写法：按当前语言动态取值
export const HOME_CATEGORY_LABELS: Record<string, string> = new Proxy(
  {},
  {
    get(_target, prop: string) {
      return categoryLabel(prop)
    },
  },
)
