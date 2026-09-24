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
  // Lỗi: chỉ hiện thông báo đã dịch theo mã lỗi (không có mã thì dùng nhãn chung "lồng tiếng lỗi")
  const label = !dub
    ? t('dramaEpisode.page.dubNone')
    : dub.status === 'running'
      ? t('dramaEpisode.page.dubRunning')
      : dub.status === 'done'
        ? t('dramaEpisode.page.dubDone', { n: dub.lines.length })
        : dub.status === 'skipped'
          ? dub.reason === 'stale'
            ? t('dramaEpisode.page.dubStale')
            : t('dramaEpisode.page.dubSkipped')
          : localizeStoredError(t('dramaEpisode.page.dubFailed'), dub.errorCode, dub.errorParams ?? undefined)
  return (
    <div className="drama-ep-versions">
      <span className="drama-ep-versions-label">{t('dramaEpisode.page.dubTitle')}</span>
      <span className="drama-muted">{label}</span>
      {/* Không khoá nút chỉ vì params.dub đang "running" (cờ có thể treo): backend tự trả 409 nếu thật sự đang chạy */}
      <button type="button" className="drama-outline-chip-btn" disabled={disabled} onClick={onRedub}>
        {t('dramaEpisode.page.dubRedo')}
      </button>
    </div>
  )
}
