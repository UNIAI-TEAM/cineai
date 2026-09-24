/** 单集目标时长选择条（项目设置 / 分镜确认弹窗共用） */
import type { TFunction } from '../../i18n/context'
import { useI18n } from '../../i18n/context'
import { EPISODE_TARGET_OPTIONS, type EpisodeTargetSec } from '../../lib/dramaEpisodeTarget'

/** 目标时长展示名：0 → 自动，≥120 且整分钟 → N 分钟，其余 N 秒（60/90 写秒更直观） */
export function formatEpisodeTargetLabel(sec: number, t: TFunction): string {
  if (!sec) return t('dramaProject.target.auto')
  if (sec >= 120 && sec % 60 === 0) {
    return t('dramaProject.target.min', { n: sec / 60 })
  }
  return t('dramaProject.target.sec', { n: sec })
}

type EpisodeTargetChipsProps = {
  value: EpisodeTargetSec
  disabled?: boolean
  onChange: (value: EpisodeTargetSec) => void
}

/** 目标时长 chip 组 */
export function EpisodeTargetChips({ value, disabled, onChange }: EpisodeTargetChipsProps) {
  const { t } = useI18n()
  return (
    <div className="drama-project-settings-chips" role="group" aria-label={t('dramaProject.target.label')}>
      {EPISODE_TARGET_OPTIONS.map((sec) => (
        <button
          key={sec}
          type="button"
          className={`drama-outline-chip-btn${value === sec ? ' is-on' : ''}`}
          aria-pressed={value === sec}
          disabled={disabled}
          onClick={() => onChange(sec)}
        >
          {formatEpisodeTargetLabel(sec, t)}
        </button>
      ))}
    </div>
  )
}
