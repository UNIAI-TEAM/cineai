/** 帮助中心 FAQ 工具：类型与关键词过滤（文案在 i18n 的 help 命名空间） */

export type HelpFaqItem = {
  q: string
  a: string
}

// 按关键词过滤常见问题
export function filterHelpFaq(items: HelpFaqItem[], raw: string): HelpFaqItem[] {
  const needle = raw.trim().toLowerCase()
  if (!needle) return items
  return items.filter(
    (item) => item.q.toLowerCase().includes(needle) || item.a.toLowerCase().includes(needle),
  )
}
