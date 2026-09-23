import { useCallback, useEffect, useState } from 'react'
import { api, type UsageChargeRecord } from '../../api'
import { useCurrency } from '../../currency'
import { useI18n } from '../../i18n'
import { LOCALE_DATE, type Locale } from '../../i18n/detect'
import Pagination from '../ui/Pagination'
import { pageCountOf } from '../../lib/pagination'

/** 格式化相对时间展示 */
function formatWhen(iso: string | null | undefined, locale: Locale) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(LOCALE_DATE[locale], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 格式化 token 数量 */
function formatTokens(n: number, locale: Locale) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`
  if (n >= 10_000) return `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k`
  return n.toLocaleString(LOCALE_DATE[locale])
}

type TFn = ReturnType<typeof useI18n>['t']

const CAPABILITIES = ['llm', 'image', 'video', 'tts'] as const

/** 计费类别名称：按 capability 走 i18n，未知类别显示「其他」 */
function capabilityLabel(item: UsageChargeRecord, t: TFn): string {
  const cap = CAPABILITIES.find((c) => c === item.capability) ?? 'other'
  return t(`billing.records.capability.${cap}`)
}

/** 扣费来源：漫剧 / 科普项目（有标题显示标题，否则显示项目编号）或工具创作 */
function contextLabel(item: UsageChargeRecord, t: TFn): string {
  const title = (item.context_title || '').trim()
  const id = item.context_project_id ?? ''
  if (item.context_kind === 'drama') {
    return title ? t('billing.records.context.drama', { title }) : t('billing.records.context.dramaProject', { id })
  }
  if (item.context_kind === 'kepu') {
    return title ? t('billing.records.context.kepu', { title }) : t('billing.records.context.kepuProject', { id })
  }
  return t('billing.records.context.tool')
}

type UsageChargeRecordsProps = {
  /** 嵌入设置页时为 compact */
  variant?: 'panel' | 'compact'
}

/** 使用扣费记录列表：按次展示 LLM / 生图 / 生视频等计费明细 */
export default function UsageChargeRecords({ variant = 'compact' }: UsageChargeRecordsProps) {
  const { t, locale } = useI18n()
  const { format } = useCurrency()
  /*
   * items 当前页记录
   * page 当前页码
   * pageSize 每页条数
   * total 总条数
   * loading 加载中
   * error 错误信息
   */
  const [items, setItems] = useState<UsageChargeRecord[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(5)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const pageCount = pageCountOf(total, pageSize)

  // 拉取指定页
  const loadPage = useCallback(async (nextPage: number, size: number) => {
    if (!localStorage.getItem('token')) {
      setItems([])
      setTotal(0)
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.usageEvents(nextPage, size)
      setTotal(res.meta.total)
      setPage(nextPage)
      setItems(res.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('billing.records.loadFailed'))
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadPage(page, pageSize)
  }, [loadPage, page, pageSize])

  function handlePageSizeChange(nextSize: number) {
    setPageSize(nextSize)
    setPage(1)
  }

  return (
    <section className={`pf-usage-records${variant === 'compact' ? ' is-compact' : ''}`}>
      <header className="pf-usage-records-head">
        <h3>{t('billing.records.title')}</h3>
        <p className="pf-muted">{t('billing.records.subtitle')}</p>
      </header>

      {loading ? <p className="pf-muted">{t('common.loading')}</p> : null}
      {error ? <p className="pf-error">{error}</p> : null}

      {!loading && !error && items.length === 0 ? (
        <div className="pf-settings-empty">
          <p>{t('billing.records.empty')}</p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <ul className="pf-settings-list pf-usage-records-list">
          {items.map((item) => (
            <li key={item.id}>
              <div className="pf-settings-list-row pf-usage-record-row">
                <span className="pf-settings-list-main">
                  <strong>{capabilityLabel(item, t)}</strong>
                  <em className="pf-muted">
                    {contextLabel(item, t)}
                    {item.total_tokens > 0 ? ` · ${formatTokens(item.total_tokens, locale)} tokens` : ''}
                    {item.estimated ? ` · ${t('billing.records.estimated')}` : ''}
                  </em>
                </span>
                <span className="pf-settings-list-meta pf-usage-record-meta">
                  <strong className="pf-usage-record-charge">
                    {item.charge_fen > 0 ? `-${format(item.charge_fen)}` : '—'}
                  </strong>
                  <em className="pf-muted">{formatWhen(item.created_at, locale)}</em>
                </span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {!loading && total > 0 ? (
        <Pagination
          page={page}
          pageCount={pageCount}
          total={total}
          pageSize={pageSize}
          onPageSizeChange={handlePageSizeChange}
          onChange={setPage}
          ariaLabel={t('billing.records.pagination')}
        />
      ) : null}
    </section>
  )
}
