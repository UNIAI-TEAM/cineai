/** 生成队列任务详情：进行中看进度，失败才挖根因 */
import { useEffect, useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { tasksApi, type TaskRunOut } from '../../api/tasks'
import { formatDramaGenError, formatDramaGenJobError, pickRootDramaGenError } from '../../lib/dramaGenError'
import BillingTopupLink from '../billing/BillingTopupLink'
import { dramaGenJobMessage, type DramaGenJob } from '../../lib/dramaGenQueue'
import { useI18n, type TFunction } from '../../i18n/context'

type Props = {
  job: DramaGenJob
  onClose: () => void
}

// 拉取该目标相关的多条历史任务（用于挖出被「重试超限」覆盖的根因）
async function listRelatedTasks(job: DramaGenJob): Promise<TaskRunOut[]> {
  if (job.kind === 'video' && job.targetId > 0) {
    const list = await tasksApi.list({
      domain: 'drama',
      task_type: 'fragment_video',
      target_type: 'fragment',
      target_id: job.targetId,
      page: 1,
      page_size: 20,
    })
    return list.items || []
  }
  if (job.kind === 'image' && job.targetId > 0) {
    const list = await tasksApi.list({
      domain: 'drama',
      target_type: 'asset',
      target_id: job.targetId,
      page: 1,
      page_size: 20,
    })
    return list.items || []
  }
  if (job.taskId && job.taskId > 0) {
    try {
      const one = await tasksApi.get(job.taskId)
      return one ? [one] : []
    } catch {
      return []
    }
  }
  return []
}

// 进行中任务的进度说明
function activeJobHint(job: DramaGenJob, t: TFunction): string {
  const message = dramaGenJobMessage(job, t)?.trim()
  if (message) return message
  if (job.status === 'queued') return t('dramaGen.detail.hintQueued')
  if (job.kind === 'video') return t('dramaGen.detail.hintVideo')
  return t('dramaGen.detail.hintImage')
}

// 任务详情抽屉（进行中=进度；失败=错误文案）
export function DramaGenTaskDetail({ job, onClose }: Props) {
  const { t } = useI18n()
  const isFailed = job.status === 'failed'
  const isActive = job.status === 'queued' || job.status === 'running'
  const [loading, setLoading] = useState(isFailed)
  const [rawError, setRawError] = useState(job.error || '')
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    // 非失败任务不挖历史错误，避免把旧的「跳过重复任务」当成当前失败
    if (!isFailed) {
      setRawError('')
      setLoading(false)
      return
    }

    let cancelled = false
    setRawError(job.error || '')
    setLoading(true)
    void (async () => {
      try {
        const tasks = await listRelatedTasks(job)
        if (cancelled) return
        const candidates: Array<string | null | undefined> = [job.error]
        for (const task of tasks) {
          // 优先当前 job 绑定的任务；历史 cancelled「跳过重复」不当作根因抢占
          if (job.taskId && task.id === job.taskId) {
            candidates.unshift(task.error_message)
            continue
          }
          if (
            task.status === 'cancelled' &&
            /跳过重复任务|分镜已生成完成/.test(String(task.error_message || ''))
          ) {
            continue
          }
          candidates.push(task.error_message)
        }
        let best = pickRootDramaGenError(candidates)
        if (!best || /重试超过|超过上限/.test(best)) {
          for (const task of tasks.slice(0, 5)) {
            if (!task.id) continue
            if (
              task.status === 'cancelled' &&
              /跳过重复任务|分镜已生成完成/.test(String(task.error_message || ''))
            ) {
              continue
            }
            try {
              const detail = await tasksApi.get(task.id)
              if (cancelled) return
              candidates.push(detail.error_message)
              for (const ev of detail.events || []) {
                candidates.push(ev.message)
              }
            } catch {
              /* ignore */
            }
          }
          best = pickRootDramaGenError(candidates)
        }
        if (best) setRawError(best)
      } catch {
        /* 无平台任务时仍用 job.error */
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [job, isFailed])

  // 根因仍是队列自身错误时带上错误码分类，否则按文本分类
  const usesJobError = Boolean(rawError) && rawError === job.error
  let errView: ReturnType<typeof formatDramaGenError> | null = null
  if (isFailed) {
    errView = usesJobError ? formatDramaGenJobError(job) : formatDramaGenError(rawError || job.message)
  }
  const panelTitle = isFailed
    ? t('dramaGen.detail.failedTitle')
    : isActive
      ? t('dramaGen.detail.progressTitle')
      : t('dramaGen.detail.detailTitle')

  return (
    <div className="drama-gen-detail" role="dialog" aria-label={panelTitle}>
      <header className="drama-gen-detail-head">
        <div>
          <strong>{panelTitle}</strong>
          <span>{job.title}</span>
        </div>
        <button type="button" className="drama-gen-fab-icon-btn" onClick={onClose} aria-label={t('dramaGen.detail.close')}>
          <X size={18} />
        </button>
      </header>

      <div className="drama-gen-detail-body">
        {loading ? (
          <div className="drama-gen-detail-loading">
            <Loader2 size={18} className="drama-gen-detail-spin" />
            <span>{t('dramaGen.detail.parsing')}</span>
          </div>
        ) : null}

        {isFailed && errView ? (
          <section className="drama-gen-detail-card is-error">
            <h4>{errView.title}</h4>
            <p>{errView.message}</p>
            {errView.suggestion ? (
              <p className="drama-gen-detail-tip">
                <strong>{t('dramaGen.detail.suggestion')}</strong>
                {errView.suggestion}
                {errView.billingBlocked ? (
                  <>
                    {' '}
                    <BillingTopupLink />
                  </>
                ) : null}
                {errView.upstreamAccountBlocked ? (
                  <> {t('dramaGen.detail.upstreamShort')}</>
                ) : null}
              </p>
            ) : errView.billingBlocked ? (
              <p className="drama-gen-detail-tip">
                <BillingTopupLink />
              </p>
            ) : errView.upstreamAccountBlocked ? (
              <p className="drama-gen-detail-tip">{t('dramaGen.panel.upstreamTip')}</p>
            ) : null}
            {rawError ? (
              <button
                type="button"
                className="drama-gen-detail-raw-toggle"
                onClick={() => setShowRaw((v) => !v)}
              >
                {showRaw ? t('dramaGen.detail.hideRaw') : t('dramaGen.detail.showRaw')}
              </button>
            ) : null}
            {showRaw && rawError ? <pre className="drama-gen-detail-raw">{rawError}</pre> : null}
          </section>
        ) : (
          <section className={`drama-gen-detail-card${isActive ? '' : ' is-done'}`}>
            <h4>{t(`dramaGen.status.${job.status}`)}</h4>
            <p>{activeJobHint(job, t)}</p>
            {job.status === 'done' ? (
              <p className="drama-gen-detail-tip">{t('dramaGen.detail.doneTip')}</p>
            ) : null}
          </section>
        )}
      </div>
    </div>
  )
}
