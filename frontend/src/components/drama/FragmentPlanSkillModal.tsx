/** AI 重新分镜确认：可选本次注入的 Agent Skill 与本集目标时长 */
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { AgentSkillPicker } from './AgentSkillPicker'
import { EpisodeTargetChips } from './EpisodeTargetChips'
import { estimateFragmentRange, formatFragmentRange, type EpisodeTargetSec } from '../../lib/dramaEpisodeTarget'
import { useAgentSkillSelection } from '../../hooks/useAgentSkillSelection'
import { useI18n } from '../../i18n/context'

type FragmentPlanSkillModalProps = {
  open: boolean
  title?: string
  message: string
  confirmText?: string
  onCancel: () => void
  /** targetSec：用户改动后的本集目标时长；未改动或未传 initialTargetSec 时为 undefined（沿用分集→项目设置） */
  onConfirm: (skillIds: number[], targetSec?: EpisodeTargetSec) => void
  /** 传入则显示「目标时长」选择，默认选中该值 */
  initialTargetSec?: EpisodeTargetSec
  /** 剧本估算秒数，用于提示预计镜头数 */
  scriptEstimateSec?: number
}

/** 覆盖分镜前让用户勾选 Skill */
export function FragmentPlanSkillModal({
  open,
  title,
  message,
  confirmText,
  onCancel,
  onConfirm,
  initialTargetSec,
  scriptEstimateSec = 0,
}: FragmentPlanSkillModalProps) {
  const { t } = useI18n()
  const [targetSec, setTargetSec] = useState<EpisodeTargetSec | undefined>(initialTargetSec)
  // 仅在弹窗由关到开时重置为当前设置；打开期间设置变化不覆盖用户已选
  const initialTargetRef = useRef(initialTargetSec)
  initialTargetRef.current = initialTargetSec
  useEffect(() => {
    if (open) setTargetSec(initialTargetRef.current)
  }, [open])
  const shotRange = targetSec == null ? null : estimateFragmentRange(targetSec, scriptEstimateSec)
  const { skills, selectedIds, toggleSkill, selectAll, selectNone, uploadSkill, uploading, uploadError } =
    useAgentSkillSelection()

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onCancel])

  if (!open) return null

  return (
    <div className="pf-dialog-root" role="presentation">
      <div className="pf-dialog-veil" aria-hidden onMouseDown={onCancel} />
      <form
        className="pf-dialog pf-dialog--danger pf-dialog--skills"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="fragment-plan-skill-title"
        onSubmit={(event) => {
          event.preventDefault()
          // Chỉ gửi khi người dùng đổi thời lượng; giữ nguyên thì để tập tiếp tục theo cài đặt dự án
          onConfirm(selectedIds, targetSec !== initialTargetRef.current ? targetSec : undefined)
        }}
      >
        <div className="pf-dialog-glow" aria-hidden />
        <div className="pf-dialog-header">
          <div className="pf-dialog-mark" aria-hidden>
            <AlertTriangle size={22} strokeWidth={1.75} />
          </div>
          <div className="pf-dialog-body">
            <h2 id="fragment-plan-skill-title" className="pf-dialog-title">
              {title ?? t('dramaProject.skill.replanTitle')}
            </h2>
            <p className="pf-dialog-message">{message}</p>
          </div>
        </div>
        {targetSec != null ? (
          <div className="pf-dialog-target-block">
            <div className="pf-dialog-skill-label">{t('dramaProject.target.label')}</div>
            <EpisodeTargetChips value={targetSec} onChange={setTargetSec} />
            {shotRange ? (
              <p className="pf-dialog-target-hint">
                {targetSec
                  ? t('dramaProject.target.planHint', { n: formatFragmentRange(shotRange) })
                  : t('dramaProject.target.planHintAuto', { n: formatFragmentRange(shotRange) })}
              </p>
            ) : null}
          </div>
        ) : null}
        <div className="pf-dialog-skill-block">
          <div className="pf-dialog-skill-label">{t('dramaProject.skill.label')}</div>
          <AgentSkillPicker
            skills={skills}
            selectedIds={selectedIds}
            onToggle={toggleSkill}
            onSelectAll={selectAll}
            onSelectNone={selectNone}
            onUpload={(file) => void uploadSkill(file)}
            uploading={uploading}
            uploadError={uploadError}
            emptyText={t('dramaProject.skill.emptyUpload')}
          />
        </div>
        <div className="pf-dialog-actions">
          <button type="button" className="pf-dialog-btn pf-dialog-btn-ghost" onClick={onCancel}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="pf-dialog-btn pf-dialog-btn-danger">
            {confirmText ?? t('dramaProject.startPlan')}
          </button>
        </div>
      </form>
    </div>
  )
}
