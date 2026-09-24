/** Trạng thái lồng tiếng TTS của phân cảnh đang chọn + nút "Lồng tiếng lại" (chỉ hiện khi video tạo ở chế độ dub) */
import { useI18n } from '../../i18n/context'
import { fragmentUsesDub, readFragmentDub } from '../../lib/dramaFragmentDub'
import { localizeStoredError } from '../../lib/apiError'

type Props = {
  params: Record<string, unknown> | null | undefined
  hasVideo: boolean
  disabled: boolean
  onRedub: () => void
}

export function FragmentDubPanel({ params, hasVideo, disabled, onRedub }: Props) {
  const { t } = useI18n()
  if (!hasVideo || !fragmentUsesDub(params)) return null
  const dub = readFragmentDub(params)
  const label = !dub
    ? t('dramaEpisode.page.dubNone')
    : dub.status === 'running'
      ? t('dramaEpisode.page.dubRunning')
      : dub.status === 'done'
        ? t('dramaEpisode.page.dubDone', { n: dub.lines.length })
        : dub.status === 'skipped'
          ? t('dramaEpisode.page.dubSkipped')
          : t('dramaEpisode.page.dubFailed')
  return (
    <div className="drama-ep-versions">
      <span className="drama-ep-versions-label">{t('dramaEpisode.page.dubTitle')}</span>
      <span className="drama-muted">{label}</span>
      {dub?.status === 'failed' && dub.errorCode ? (
        <span className="drama-muted">
          {localizeStoredError(t('dramaEpisode.page.dubFailed'), dub.errorCode, dub.errorParams ?? undefined)}
        </span>
      ) : null}
      <button
        type="button"
        className="drama-outline-chip-btn"
        disabled={disabled || dub?.status === 'running'}
        onClick={onRedub}
      >
        {t('dramaEpisode.page.dubRedo')}
      </button>
    </div>
  )
}
