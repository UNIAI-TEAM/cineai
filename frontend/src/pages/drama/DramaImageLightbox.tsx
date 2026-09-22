/** 资产图片全屏放大预览（点击遮罩 / Esc 关闭） */
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useI18n } from '../../i18n/context'

type Props = {
  src: string
  alt?: string
  onClose: () => void
}

// 渲染图片放大层
export function DramaImageLightbox({ src, alt, onClose }: Props) {
  const { t } = useI18n()
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey, true)
    }
  }, [onClose])

  return createPortal(
    <div
      className="drama-lightbox-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={t('dramaAssets.lightbox.aria')}
      onClick={onClose}
    >
      <button type="button" className="drama-lightbox-close" aria-label={t('common.close')} onClick={onClose}>
        ×
      </button>
      <img
        className="drama-lightbox-img"
        src={src}
        alt={alt || t('dramaAssets.common.preview')}
        onClick={(e) => e.stopPropagation()}
      />
    </div>,
    document.body,
  )
}
