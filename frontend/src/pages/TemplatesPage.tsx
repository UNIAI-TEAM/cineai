/** 模板库页：按分类/关键词筛选模板，点击进入科普建项 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Template } from '../api'
import BillingErrorNotice from '../components/billing/BillingErrorNotice'
import AppShell from '../components/layout/AppShell'
import PillTabs from '../components/ui/PillTabs'
import { CATEGORY_ORDER } from '../lib/categories'
import { templateDescription, templateName } from '../lib/templateI18n'
import { useI18n } from '../i18n'

// 渲染模板库列表
export default function TemplatesPage() {
  const nav = useNavigate()
  const { t, m, locale } = useI18n()
  // 分类展示名随界面语言变化；未登记的分类键原样显示（非中文界面下含汉字的显示「其他」）
  const categoryMap = m.categories as Record<string, string>
  const labelOf = (key: string) =>
    categoryMap[key] ||
    (locale !== 'zh' && /[\u4e00-\u9fff]/.test(key) ? t('settingsPanels.templates.categoryOther') : key)
  const [templates, setTemplates] = useState<Template[]>([])
  const [error, setError] = useState('')
  const [category, setCategory] = useState('全部')
  const [q, setQ] = useState('')

  useEffect(() => {
    api
      .templates()
      .then(setTemplates)
      .catch((e) => setError(String(e.message || e)))
  }, [])

  const categoryKeys = useMemo(() => {
    const found = new Set<string>()
    for (const tpl of templates) {
      for (const c of tpl.category || []) {
        if (CATEGORY_ORDER.includes(c)) found.add(c)
      }
    }
    return ['全部', ...CATEGORY_ORDER.filter((c) => found.has(c))]
  }, [templates])

  const categoryLabels = useMemo(
    () => categoryKeys.map((k) => categoryMap[k] || k),
    [categoryKeys, categoryMap],
  )
  const labelToKey = useMemo(() => {
    const map = new Map<string, string>()
    for (const k of categoryKeys) map.set(categoryMap[k] || k, k)
    return map
  }, [categoryKeys, categoryMap])

  const filtered = useMemo(() => {
    let list = templates
    if (category !== '全部') list = list.filter((tpl) => (tpl.category || []).includes(category))
    if (q.trim()) {
      const s = q.trim().toLowerCase()
      list = list.filter(
        (tpl) =>
          templateName(tpl, locale).toLowerCase().includes(s) ||
          templateDescription(tpl, locale).toLowerCase().includes(s),
      )
    }
    return list
  }, [templates, category, q, locale])

  function openTemplate(tpl: Template) {
    if (!localStorage.getItem('token')) {
      nav('/auth')
      return
    }
    nav(`/studio/new?template=${tpl.id}`)
  }

  return (
    <AppShell active="templates">
      <div className="pf-section-head">
        <div>
          <h2>{t('settingsPanels.templates.title')}</h2>
          <p>{t('settingsPanels.templates.lead')}</p>
        </div>
      </div>
      <div className="pf-search" style={{ maxWidth: 420, marginBottom: '1rem' }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('settingsPanels.templates.searchPlaceholder')}
        />
      </div>
      <PillTabs
        items={categoryLabels}
        value={labelOf(category)}
        onChange={(label) => setCategory(labelToKey.get(label) || '全部')}
        ariaLabel={t('settingsPanels.templates.categoryTabs')}
      />
      {error ? <BillingErrorNotice message={error} /> : null}
      <div className="pf-template-grid" style={{ marginTop: '1rem' }}>
        {filtered.map((tpl) => (
          <button key={tpl.id} type="button" className="pf-template-card" onClick={() => openTemplate(tpl)}>
            <img src={api.assetUrl(tpl.preview_cover)} alt="" />
            <div className="body">
              <h3>{templateName(tpl, locale)}</h3>
              <p>{templateDescription(tpl, locale)}</p>
              <div className="pf-tags">
                {tpl.category.map((c) => (
                  <span key={c}>{labelOf(c)}</span>
                ))}
              </div>
            </div>
          </button>
        ))}
      </div>
      {filtered.length === 0 ? <p className="pf-muted">{t('settingsPanels.templates.empty')}</p> : null}
    </AppShell>
  )
}
