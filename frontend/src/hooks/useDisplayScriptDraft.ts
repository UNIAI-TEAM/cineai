/**
 * 受控 textarea 用的剧本 / 分镜正文草稿：
 * 框内显示当前界面语言的结构标签，父级拿到的始终是规范正文（中文标签）。
 * 只在「外部正文变化 / 切换语言」时重新生成显示稿；用户打字时保留原样输入，不逐键改写，光标不跳。
 */
import { useCallback, useState } from 'react'
import { useI18n } from '../i18n/context'
import { toCanonicalScript, toDisplayScript } from '../lib/dramaScriptLocalize'

type DraftState = {
  /** 生成当前草稿时对应的规范正文 */
  source: string
  locale: string
  draft: string
}

/**
 * @param canonical 父级持有的规范正文
 * @param onCanonicalChange 草稿变化时回写规范正文
 * @returns [显示稿, 设置显示稿]
 */
export function useDisplayScriptDraft(
  canonical: string,
  onCanonicalChange: (next: string) => void,
): [string, (nextDraft: string) => void] {
  const { locale } = useI18n()
  const [state, setState] = useState<DraftState>(() => ({
    source: canonical,
    locale,
    draft: toDisplayScript(canonical, locale),
  }))

  // 外部改了正文（或切换语言）：渲染期同步重建显示稿
  let current = state
  if (state.source !== canonical || state.locale !== locale) {
    current = { source: canonical, locale, draft: toDisplayScript(canonical, locale) }
    setState(current)
  }

  const setDraft = useCallback(
    (nextDraft: string) => {
      const next = toCanonicalScript(nextDraft, locale)
      setState({ source: next, locale, draft: nextDraft })
      onCanonicalChange(next)
    },
    [locale, onCanonicalChange],
  )

  return [current.draft, setDraft]
}
