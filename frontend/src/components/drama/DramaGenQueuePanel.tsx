/** 漫剧全局生成队列：右下角圆钮，展示图片 / 视频等任务 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Clapperboard, ImageIcon, Layers, Octagon, Trash2, X } from 'lucide-react'
import { dramaApi } from '../../api/drama'
import { DramaGenTaskDetail } from './DramaGenTaskDetail'
import { formatDramaGenError } from '../../lib/dramaGenError'
import BillingTopupLink from '../billing/BillingTopupLink'
import { useI18n, type TFunction } from '../../i18n/context'
import {
  CANVAS_VIDEO_SUBTYPE,
  FRAGMENT_VIDEO_SUBTYPE,
  clearFinishedDramaGenJobs,
  dramaGenJobMessage,
  ensureEpisodeVideoStatusPoll,
  markVideoJobsCancelled,
  subscribeDramaGenQueueOpen,
  useDramaGenQueue,
  type DramaGenJob,
} from '../../lib/dramaGenQueue'
import '../../pages/drama/drama.css'

const OPEN_STORAGE_KEY = 'drama-gen-queue-fab-open'

// 图片 subtype（资产类型）→ 文案 key
const IMAGE_SUBTYPE_KEY: Record<string, string> = {
  character: 'character',
  scene: 'scene',
  prop: 'prop',
  material: 'material',
}

// 视频 subtype（内部标识）→ 文案 key
const VIDEO_SUBTYPE_KEY: Record<string, string> = {
  [FRAGMENT_VIDEO_SUBTYPE]: 'fragmentVideo',
  [CANVAS_VIDEO_SUBTYPE]: 'canvasVideo',
}

// 读取折叠偏好
function readOpenPreference(): boolean {
  try {
    return localStorage.getItem(OPEN_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

// 任务类型展示
function jobTypeLabel(job: DramaGenJob, t: TFunction): string {
  if (job.kind === 'video') {
    if (!job.subtype) return t('dramaGen.subtype.fragmentVideo')
    const key = VIDEO_SUBTYPE_KEY[job.subtype]
    return key ? t(`dramaGen.subtype.${key}`) : job.subtype
  }
  const key = IMAGE_SUBTYPE_KEY[job.subtype]
  if (key) return t(`dramaGen.subtype.${key}`)
  if (!job.subtype || job.subtype === 'image') return t('dramaGen.subtype.image')
  return job.subtype
}

// 任务图标
function JobKindIcon({ kind }: { kind: DramaGenJob['kind'] }) {
  if (kind === 'video') return <Clapperboard size={16} strokeWidth={1.75} aria-hidden />
  return <ImageIcon size={16} strokeWidth={1.75} aria-hidden />
}

// 渲染右下角统一生成队列
export function DramaGenQueuePanel() {
  const { t } = useI18n()
  const queue = useDramaGenQueue()
  const [open, setOpen] = useState(readOpenPreference)
  const [detailJob, setDetailJob] = useState<DramaGenJob | null>(null)

  const active = useMemo(
    () => queue.filter((j) => j.status === 'queued' || j.status === 'running'),
    [queue],
  )
  const finished = useMemo(
    () => queue.filter((j) => j.status === 'done' || j.status === 'failed'),
    [queue],
  )
  const failed = useMemo(() => queue.filter((j) => j.status === 'failed'), [queue])

  // 列表按入队时间倒序（最新在上）；排队序号仍按先入先出
  const sortedQueue = useMemo(
    () => [...queue].sort((a, b) => b.createdAt - a.createdAt),
    [queue],
  )
  const queuedOnly = useMemo(
    () =>
      queue
        .filter((j) => j.status === 'queued' || j.status === 'running')
        .sort((a, b) => a.createdAt - b.createdAt),
    [queue],
  )

  useEffect(() => {
    try {
      localStorage.setItem(OPEN_STORAGE_KEY, open ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [open])

  // 入队后自动展开面板
  useEffect(() => {
    return subscribeDramaGenQueueOpen(() => {
      setOpen(true)
    })
  }, [])

  // 有进行中的分镜视频时后台轮询，离开编辑页也不中断
  useEffect(() => {
    if (active.some((job) => job.kind === 'video' && job.subtype === FRAGMENT_VIDEO_SUBTYPE)) {
      ensureEpisodeVideoStatusPoll()
    }
  }, [active])

  // 详情随队列刷新同步同一 job
  useEffect(() => {
    if (!detailJob) return
    const latest = queue.find((j) => j.id === detailJob.id)
    if (!latest) {
      setDetailJob(null)
      return
    }
    if (latest !== detailJob) setDetailJob(latest)
  }, [queue, detailJob])

  const toggleOpen = useCallback(() => {
    setOpen((prev) => !prev)
  }, [])

  const close = useCallback(() => {
    setOpen(false)
    setDetailJob(null)
  }, [])

  const cancelAllVideo = useCallback(async () => {
    try {
      await dramaApi.cancelAllVideoJobs()
      markVideoJobsCancelled()
    } catch {
      /* ignore */
    }
  }, [])

  if (queue.length === 0) return null

  const badgeCount = active.length

  return (
    <div className="drama-gen-fab-root">
      {open ? (
        <div className="drama-gen-fab-panel" role="dialog" aria-label={t('dramaGen.panel.title')}>
          {detailJob ? (
            <DramaGenTaskDetail job={detailJob} onClose={() => setDetailJob(null)} />
          ) : (
            <>
              <header className="drama-gen-fab-head">
                <div className="drama-gen-fab-title">
                  <Layers size={18} strokeWidth={1.75} aria-hidden />
                  <div>
                    <strong>{t('dramaGen.panel.title')}</strong>
                    <span>
                      {active.length > 0
                        ? t('dramaGen.panel.activeCount', { n: active.length })
                        : failed.length > 0
                          ? t('dramaGen.panel.failedCount', { n: failed.length })
                          : finished.length > 0
                            ? t('dramaGen.panel.allDone')
                            : ''}
                    </span>
                  </div>
                </div>
                <div className="drama-gen-fab-actions">
                  {active.some((j) => j.kind === 'video') ? (
                    <button
                      type="button"
                      className="drama-gen-fab-icon-btn"
                      onClick={cancelAllVideo}
                      title={t('dramaGen.panel.cancelAllVideo')}
                      aria-label={t('dramaGen.panel.cancelAllVideo')}
                    >
                      <Octagon size={16} />
                    </button>
                  ) : null}
                  {finished.length > 0 ? (
                    <button
                      type="button"
                      className="drama-gen-fab-icon-btn"
                      onClick={clearFinishedDramaGenJobs}
                      title={t('dramaGen.panel.clearFinished')}
                      aria-label={t('dramaGen.panel.clearFinished')}
                    >
                      <Trash2 size={16} />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="drama-gen-fab-icon-btn"
                    onClick={close}
                    title={t('dramaGen.panel.close')}
                    aria-label={t('dramaGen.panel.close')}
                  >
                    <X size={18} />
                  </button>
                </div>
              </header>

              <ul className="drama-gen-fab-list">
                {sortedQueue.map((job) => {
                  const queueIndex = queuedOnly.findIndex((j) => j.id === job.id)
                  const errView = job.status === 'failed' ? formatDramaGenError(job.error) : null
                  const jobMessage = dramaGenJobMessage(job, t)
                  return (
                    <li key={job.id}>
                      <button
                        type="button"
                        className={`drama-gen-fab-item is-${job.status} is-clickable`}
                        onClick={() => setDetailJob(job)}
                      >
                        <div className="drama-gen-fab-item-head">
                          <div className="drama-gen-fab-item-main">
                            <span className="drama-gen-fab-kind">
                              <JobKindIcon kind={job.kind} />
                              <em>{job.kind === 'video' ? t('dramaGen.kind.video') : t('dramaGen.kind.image')}</em>
                            </span>
                            <span className="drama-gen-fab-name">{job.title}</span>
                            <span className="drama-gen-fab-type">{jobTypeLabel(job, t)}</span>
                            {jobMessage && (job.status === 'queued' || job.status === 'running') ? (
                              <span className="drama-gen-fab-msg">{jobMessage}</span>
                            ) : null}
                          </div>
                          <span className="drama-gen-fab-status">
                            {job.status === 'queued' && queueIndex >= 0
                              ? queuedOnly.length <= 1 || queueIndex === 0
                                ? t('dramaGen.status.queued')
                                : t('dramaGen.queuePosition', { n: queueIndex + 1 })
                              : t(`dramaGen.status.${job.status}`)}
                          </span>
                        </div>
                        {errView ? (
                          <div className="drama-gen-fab-error-block">
                            <p className="drama-gen-fab-error-title">{errView.title}</p>
                            <p className="drama-gen-fab-error">{errView.message}</p>
                            {errView.suggestion ? (
                              <p className="drama-gen-fab-error-tip">{errView.suggestion}</p>
                            ) : null}
                            {errView.billingBlocked ? (
                              <p className="drama-gen-fab-error-tip">
                                <BillingTopupLink className="pf-link pf-billing-topup-link drama-gen-fab-topup-link" />
                              </p>
                            ) : null}
                            {errView.upstreamAccountBlocked ? (
                              <p className="drama-gen-fab-error-tip drama-gen-fab-upstream-tip">
                                {t('dramaGen.panel.upstreamTip')}
                              </p>
                            ) : null}
                            <span className="drama-gen-fab-open-hint">{t('dramaGen.panel.viewReason')}</span>
                          </div>
                        ) : (
                          <span className="drama-gen-fab-open-hint">{t('dramaGen.panel.viewDetail')}</span>
                        )}
                        {(job.status === 'queued' || job.status === 'running') && (
                          <div className="drama-gen-fab-bar" aria-hidden />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>

              {active.length > 0 ? (
                <footer className="drama-gen-fab-foot">
                  <span className="drama-gen-fab-foot-dot" aria-hidden />
                </footer>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      <button
        type="button"
        className={`drama-gen-fab-btn${active.length > 0 ? ' is-busy' : ''}${failed.length > 0 && active.length === 0 ? ' is-failed' : ''}`}
        onClick={toggleOpen}
        title={open ? t('dramaGen.panel.collapse') : t('dramaGen.panel.expand')}
        aria-expanded={open}
        aria-label={t('dramaGen.panel.title')}
      >
        <Layers size={22} strokeWidth={1.75} aria-hidden />
        {badgeCount > 0 ? <span className="drama-gen-fab-badge">{badgeCount}</span> : null}
      </button>
    </div>
  )
}
