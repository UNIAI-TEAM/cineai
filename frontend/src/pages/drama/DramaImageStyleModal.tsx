/** 画面风格选择：触发器 + Modal 卡片网格 */
import { useState } from 'react'
import { BookOpen, ChevronDown } from 'lucide-react'
import { DramaImageStyleCardGrid } from '../../components/drama/DramaImageStyleCardGrid'
import { DramaImageStylePreviewImg } from '../../components/drama/DramaImageStylePreviewImg'
import Modal from '../../components/ui/Modal'
import { getImageStyleLabel, type ImageStyleId } from '../../lib/dramaImageStyles'
import { useI18n } from '../../i18n'

type Props = {
  value: ImageStyleId | ''
  onChange: (id: ImageStyleId | '') => void
  disabled?: boolean
  /** toolbar：列表页胶囊按钮；field：大纲页带缩略图字段 */
  variant?: 'toolbar' | 'field'
  /** field 变体左侧文案，默认 dramaStyle.projectStyle */
  fieldLabel?: string
  /** Modal 标题 */
  title?: string
  /** 未选时的触发文案 */
  emptyLabel?: string
}

// 渲染风格库触发器与画面风格 Modal
export function DramaImageStyleModal({
  value,
  onChange,
  disabled = false,
  variant = 'toolbar',
  fieldLabel,
  title,
  emptyLabel,
}: Props) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const styleLabel = getImageStyleLabel(value)
  const triggerLabel = styleLabel || emptyLabel || t(variant === 'field' ? 'dramaStyle.pick' : 'dramaStyle.library')
  const active = Boolean(value) || open

  // 选中风格并关闭
  function select(id: ImageStyleId | '') {
    onChange(id)
    setOpen(false)
  }

  return (
    <>
      {variant === 'field' ? (
        <div className="drama-style-picker-field">
          <span className="drama-style-picker-field-label">{fieldLabel || t('dramaStyle.projectStyle')}</span>
          <button
            type="button"
            className={`drama-style-picker-trigger${active ? ' is-active' : ''}`}
            disabled={disabled}
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            {value ? (
              <span className="drama-style-picker-thumb" aria-hidden>
                <DramaImageStylePreviewImg styleId={value} alt="" loading="lazy" />
              </span>
            ) : (
              <span className="drama-style-picker-thumb is-empty" aria-hidden />
            )}
            <span className="drama-style-picker-text">{triggerLabel}</span>
            <ChevronDown size={14} strokeWidth={2} className={open ? 'is-open' : undefined} />
          </button>
        </div>
      ) : (
        <button
          type="button"
          className={`drama-agent-opt-trigger${active ? ' is-active' : ''}`}
          disabled={disabled}
          aria-expanded={open}
          onClick={() => setOpen(true)}
        >
          <BookOpen size={15} strokeWidth={1.8} />
          <span className="drama-agent-opt-label">{triggerLabel}</span>
          <ChevronDown size={13} strokeWidth={2} />
        </button>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={title || t('dramaStyle.modalTitle')} size="md" className="drama-style-modal">
        {/* 封面即画风参考图，避免用户以为只是缩略预览 */}
        <p className="drama-style-modal-hint">
          {t('dramaStyle.hint')}
        </p>
        <DramaImageStyleCardGrid value={value} onChange={select} noneLabel={t('dramaStyle.none')} />
      </Modal>
    </>
  )
}
