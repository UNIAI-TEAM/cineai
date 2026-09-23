import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, defaultsFromTemplate } from '../../api'
import type { Template } from '../../api'
import BillingErrorNotice from '../../components/billing/BillingErrorNotice'
import AppShell from '../../components/layout/AppShell'
import Stepper from '../../components/ui/Stepper'
import PillTabs from '../../components/ui/PillTabs'
import { IconChevronLeft, IconRefresh, IconSparkles } from '../../components/ui/Icons'
import { CATEGORY_ORDER } from '../../lib/categories'
import {
  contentLangOptions,
  cutToLimit,
  defaultContentLang,
  kepuTextLimits,
  type ContentLang,
} from '../../lib/contentLang'
import { kepuStepIndex, kepuSteps } from '../../lib/status'
import { templateDescription, templateName } from '../../lib/templateI18n'
import { useI18n } from '../../i18n'

/** 灵感示例：标题、一句话主题与完整口播文案（各语言文案见 studioCreate.inspirations） */
type Inspiration = {
  title: string
  theme: string
  script: string
}

/** 输入方式键：一句话主题 / 粘贴完整文案（显示文案走 studioCreate.inputTabs） */
type InputTab = 'theme' | 'script'
const INPUT_TABS: InputTab[] = ['theme', 'script']

/** 模板分类 Tab 的两个本地哨兵值（非数据库分类键，显示文案走 i18n） */
const CAT_ALL = 'all'
const CAT_HOT = 'hot'

const PAGE_SIZE = 6

// 标题为空或仍是默认「未命名作品」
function isDefaultTitle(value: string, untitled: string) {
  const v = value.trim()
  return !v || v === untitled
}

// 由主题/文案首行推导短标题，推不出时用默认名；zh 取 18 字，vi / en 按词截到标题上限
function deriveTitle(text: string, untitled: string, lang: ContentLang) {
  const line = text
    .trim()
    .split(/\n/)[0]
    .replace(/["""'']/g, '')
    .replace(/[。！？!?：:].*$/, '')
    .trim()
  if (!line) return untitled
  return lang === 'zh' ? line.slice(0, 18) : cutToLimit(line, kepuTextLimits(lang).title)
}

export default function CreateProjectPage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const { t, m, locale } = useI18n()
  /*
   * untitled 当前语言的默认作品名
   * inspirationPool 当前语言的灵感示例
   * contentLang AI 旁白 / 字幕所用语言（默认跟随界面语言，创建后锁定为显式选择）
   */
  const untitled = t('studioCreate.untitled')
  const inspirationPool: readonly Inspiration[] = m.studioCreate.inspirations
  const [templates, setTemplates] = useState<Template[]>([])
  const [templateId, setTemplateId] = useState(params.get('template') || '')
  const [category, setCategory] = useState(CAT_ALL)
  const [q, setQ] = useState('')
  const [inputTab, setInputTab] = useState<InputTab>('theme')
  const [contentLang, setContentLang] = useState<ContentLang>(() => defaultContentLang(locale))
  const [sourceText, setSourceText] = useState(() => inspirationPool[0].theme)
  const [title, setTitle] = useState(() => inspirationPool[0].title)
  const [titleTouched, setTitleTouched] = useState(false)
  const [inspPage, setInspPage] = useState(0)
  const [busy, setBusy] = useState(false)
  const [aiBusy, setAiBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      nav('/auth')
      return
    }
    api.me().catch(() => nav('/auth'))
    api.templates().then((list) => {
      setTemplates(list)
      const fromUrl = params.get('template') || ''
      setTemplateId((prev) => prev || fromUrl || list[0]?.id || '')
    })
  }, [nav, params])

  const categories = useMemo(() => {
    const found = new Set<string>()
    for (const tpl of templates) {
      for (const c of tpl.category || []) {
        if (CATEGORY_ORDER.includes(c)) found.add(c)
      }
    }
    return [CAT_ALL, CAT_HOT, ...CATEGORY_ORDER.filter((c) => found.has(c))]
  }, [templates])

  const filtered = useMemo(() => {
    let list = templates
    if (category === CAT_HOT) list = [...templates].sort((a, b) => a.sort_order - b.sort_order).slice(0, 8)
    else if (category !== CAT_ALL) list = list.filter((tpl) => (tpl.category || []).includes(category))
    if (q.trim()) {
      const s = q.trim().toLowerCase()
      list = list.filter(
        (tpl) => templateName(tpl).toLowerCase().includes(s) || tpl.name.toLowerCase().includes(s),
      )
    }
    return list
  }, [templates, category, q])

  const selected = templates.find((tpl) => tpl.id === templateId)
  // 主题 / 标题长度上限随内容语言（与后端扩写结果一致：zh 100/24，vi / en 400/80）
  const limits = kepuTextLimits(contentLang)
  const sourceType: InputTab = inputTab
  const inspTotal = Math.ceil(inspirationPool.length / PAGE_SIZE)
  const inspirations = inspirationPool.slice(inspPage * PAGE_SIZE, inspPage * PAGE_SIZE + PAGE_SIZE)

  // 分类 Tab 显示文案：哨兵值走本页文案，数据库分类键走 categories.*，缺失时回落原键
  function categoryLabel(key: string) {
    if (key === CAT_ALL) return t('studioCreate.catAll')
    if (key === CAT_HOT) return t('studioCreate.catHot')
    const label = t(`categories.${key}`)
    return label.startsWith('categories.') ? key : label
  }
  const categoryTabs = categories.slice(0, 6)

  // 把灵感示例填进主题/文案，并同步短标题
  function applyInspiration(item: Inspiration) {
    if (sourceType === 'script') {
      setInputTab('script')
      setSourceText(item.script.slice(0, 8000))
    } else {
      setInputTab('theme')
      setSourceText(cutToLimit(item.theme, limits.theme))
    }
    setTitle(cutToLimit(item.title, limits.title))
    setTitleTouched(false)
    setError('')
  }

  function shuffleInspirations() {
    setInspPage((p) => (p + 1) % inspTotal)
  }

  async function aiExpand() {
    const seed = sourceText.trim() || title.trim() || t('studioCreate.defaultSeed')
    setAiBusy(true)
    setError('')
    try {
      const mode = sourceType === 'script' ? 'script' : 'theme'
      const result = await api.expandContent(seed, mode, contentLang)
      setSourceText(mode === 'theme' ? cutToLimit(result.content, limits.theme) : result.content.slice(0, 8000))
      if (!titleTouched || isDefaultTitle(title, untitled)) {
        setTitle(cutToLimit(result.title, limits.title))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('studioCreate.aiFailed'))
    } finally {
      setAiBusy(false)
    }
  }

  async function next() {
    if (!templateId || !sourceText.trim()) {
      setError(t('studioCreate.needTemplateAndTopic'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const tpl = templates.find((item) => item.id === templateId)
      const d = tpl ? defaultsFromTemplate(tpl) : undefined
      const modeParam = params.get('mode')
      const pipeline_mode: 'full' | 'image_text' =
        modeParam === 'image_text' || modeParam === 'full' ? modeParam : 'full'
      const finalTitle =
        title.trim() ||
        deriveTitle(sourceText, untitled, contentLang) ||
        cutToLimit(sourceText.trim(), limits.title) ||
        untitled
      const project = await api.createProject({
        template_id: templateId,
        title: finalTitle,
        source_type: sourceType,
        source_text: sourceText.trim(),
        resolution_mode: 'preview',
        pipeline_mode,
        output_ratio: d?.output_ratio || '16:9',
        voice_id: d?.voice_id,
        content_lang: contentLang,
      })
      nav(`/studio/${project.id}/style`)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('studioCreate.createFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell active="studio" wide>
      <header className="pf-page-head">
        <div className="pf-page-head-row">
          <div>
            <button type="button" className="pf-back" onClick={() => nav('/')}>
              <IconChevronLeft size={18} />
              {t('studioCreate.backCrumb')}
            </button>
            <h1 className="pf-page-title">{t('studioCreate.title')}</h1>
          </div>
          <Stepper steps={kepuSteps()} current={kepuStepIndex('create')} doneThrough={-1} />
        </div>
      </header>

      <div className="pf-create">
        <aside className="pf-create-col">
          <h3>{t('studioCreate.pickTemplate')}</h3>
          <div className="pf-search">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('studioCreate.searchTemplate')} />
          </div>
          <PillTabs
            items={categoryTabs.map(categoryLabel)}
            value={categoryLabel(category)}
            onChange={(label) => setCategory(categoryTabs.find((key) => categoryLabel(key) === label) || CAT_ALL)}
            ariaLabel={t('studioCreate.categoryTabs')}
          />
          <div className="pf-tpl-list" style={{ marginTop: '0.75rem' }}>
            {filtered.map((tpl) => (
              <button
                key={tpl.id}
                type="button"
                className={templateId === tpl.id ? 'pf-tpl-mini selected' : 'pf-tpl-mini'}
                onClick={() => setTemplateId(tpl.id)}
              >
                <img src={api.assetUrl(tpl.preview_cover)} alt="" />
                <div>
                  <strong>{templateName(tpl)}</strong>
                  <span>
                    {tpl.default_ratio} ·{' '}
                    {(tpl.category || [])[0] ? categoryLabel((tpl.category || [])[0]) : t('studioCreate.generic')}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="pf-create-col">
          <h3>{t('studioCreate.inputTitle')}</h3>
          <div className="pf-input-tabs">
            {INPUT_TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={['pf-pill', inputTab === tab ? 'lime active' : ''].join(' ')}
                onClick={() => setInputTab(tab)}
              >
                {t(`studioCreate.inputTabs.${tab}`)}
              </button>
            ))}
          </div>

          <label className="pf-field">
            <span className="pf-field-label">{t('studioCreate.projectName')}</span>
            <input
              className="pf-field-input"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                setTitleTouched(true)
              }}
              onBlur={() => {
                if (isDefaultTitle(title, untitled) && sourceText.trim()) {
                  setTitle(deriveTitle(sourceText, untitled, contentLang))
                  setTitleTouched(false)
                }
              }}
              placeholder={t('studioCreate.projectNamePlaceholder')}
            />
          </label>

          <div className="pf-field">
            <span className="pf-field-label" id="studio-content-lang-label">
              {t('contentLang.label')}
            </span>
            <div
              className="pf-input-tabs"
              role="radiogroup"
              aria-labelledby="studio-content-lang-label"
              style={{ marginBottom: '0.35rem' }}
            >
              {contentLangOptions(contentLang).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  role="radio"
                  aria-checked={contentLang === lang}
                  className={['pf-pill', contentLang === lang ? 'lime active' : ''].join(' ')}
                  disabled={busy || aiBusy}
                  onClick={() => setContentLang(lang)}
                >
                  {t(`contentLang.names.${lang}`)}
                </button>
              ))}
            </div>
            <span className="pf-muted" style={{ fontSize: '0.75rem' }}>
              {t('contentLang.createHint')}
            </span>
          </div>

          <div className="pf-textarea-wrap">
            <div className="pf-textarea-toolbar">
              <button
                type="button"
                className="pf-btn pf-btn-ai pf-btn-sm pf-btn-icon"
                disabled={aiBusy || busy}
                onClick={aiExpand}
              >
                <IconSparkles size={14} />
                {aiBusy
                  ? t('studioCreate.generating')
                  : sourceType === 'script'
                    ? t('studioCreate.aiExpandScript')
                    : t('studioCreate.aiExpandTheme')}
              </button>
              <span className="pf-muted" style={{ fontSize: '0.75rem' }}>
                {sourceType === 'script' ? t('studioCreate.aiHintScript') : t('studioCreate.aiHintTheme')}
              </span>
            </div>
            <textarea
              value={sourceText}
              onChange={(e) => {
                // 手动输入按上限硬截（同 maxLength），避免吞掉正在输入的词；AI / 灵感填充才按词截
                const next = e.target.value.slice(0, sourceType === 'theme' ? limits.theme : 8000)
                setSourceText(next)
                if (!titleTouched || isDefaultTitle(title, untitled)) {
                  setTitle(deriveTitle(next, untitled, contentLang))
                }
              }}
              placeholder={
                sourceType === 'theme'
                  ? t('studioCreate.themePlaceholder')
                  : t('studioCreate.scriptPlaceholder')
              }
            />
            {sourceType === 'theme' ? (
              <span className="pf-char-count">{sourceText.length}/{limits.theme}</span>
            ) : (
              <span className="pf-char-count">{t('studioCreate.charCount', { count: sourceText.length })}</span>
            )}
          </div>

          <div className="pf-inspire">
            <div className="pf-inspire-head">
              <strong>{t('studioCreate.inspireTitle')}</strong>
              <button type="button" className="pf-btn pf-btn-ghost pf-btn-sm pf-btn-icon" onClick={shuffleInspirations}>
                <IconRefresh size={14} />
                {t('studioCreate.shuffle')}
              </button>
            </div>
            <div className="pf-chips">
              {inspirations.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  className="pf-chip"
                  title={sourceType === 'script' ? item.script.slice(0, 80) : item.theme}
                  onClick={() => applyInspiration(item)}
                >
                  {item.title}
                </button>
              ))}
            </div>
            <p className="pf-muted" style={{ fontSize: '0.78rem', margin: '0.55rem 0 0' }}>
              {sourceType === 'script' ? t('studioCreate.inspireHintScript') : t('studioCreate.inspireHintTheme')}
            </p>
          </div>

          <div className="pf-hint" style={{ marginTop: '1rem' }}>
            {t('studioCreate.topicHint')}
          </div>
          {error ? <BillingErrorNotice message={error} /> : null}
        </section>

        <aside className="pf-create-col">
          <h3>{t('studioCreate.summaryTitle')}</h3>
          {selected ? (
            <div style={{ marginBottom: '0.85rem' }}>
              <img
                src={api.assetUrl(selected.preview_cover)}
                alt=""
                style={{ width: '100%', borderRadius: 12, aspectRatio: '16/9', objectFit: 'cover' }}
              />
              <strong style={{ display: 'block', marginTop: '0.5rem' }}>{templateName(selected)}</strong>
              <p className="pf-muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                {templateDescription(selected)}
              </p>
            </div>
          ) : (
            <p className="pf-muted">{t('studioCreate.pleasePickTemplate')}</p>
          )}
          <div className="pf-summary-row">
            <span>{t('studioCreate.workName')}</span>
            <span>{title.trim() || untitled}</span>
          </div>
          <div className="pf-summary-row">
            <span>{t('studioCreate.outputMode')}</span>
            <span>
              {selected?.default_ratio === '9:16' ? t('studioCreate.outputPortrait') : t('studioCreate.outputLandscape')}
            </span>
          </div>
          <div className="pf-summary-row">
            <span>{t('studioCreate.estDuration')}</span>
            <span>{t('studioCreate.estDurationValue')}</span>
          </div>
          <div className="pf-summary-row">
            <span>{t('studioCreate.language')}</span>
            <span>{t(`contentLang.names.${contentLang}`)}</span>
          </div>
          <div className="pf-summary-row">
            <span>{t('studioCreate.inputMethod')}</span>
            <span>{t(`studioCreate.inputTabs.${inputTab}`)}</span>
          </div>
          <button
            type="button"
            className="pf-btn pf-btn-lime pf-btn-block pf-btn-lg pf-btn-icon"
            style={{ marginTop: '1.25rem' }}
            disabled={busy || aiBusy || !templateId || !sourceText.trim()}
            onClick={next}
          >
            {busy ? t('studioCreate.creating') : t('studioCreate.nextStyle')}
            {!busy ? <span aria-hidden>→</span> : null}
          </button>
          <button
            type="button"
            className="pf-btn pf-btn-ghost pf-btn-block pf-btn-sm pf-btn-icon"
            style={{ marginTop: '0.55rem' }}
            disabled={aiBusy || busy}
            onClick={aiExpand}
          >
            <IconSparkles size={14} />
            {aiBusy ? t('studioCreate.aiGenerating') : t('studioCreate.aiHelpWrite')}
          </button>
          <p className="pf-muted" style={{ fontSize: '0.78rem', marginTop: '0.5rem' }}>
            {t('studioCreate.styleNote')}
          </p>
        </aside>
      </div>
    </AppShell>
  )
}
