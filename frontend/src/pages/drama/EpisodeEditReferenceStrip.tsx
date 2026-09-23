/** 分镜顶部：已关联资产缩略图条 */
import { normalizeAssetTab, type FragmentRefStripItem } from './dramaEpisodeEditUtils'
import { DRAMA_VOICE_BINDING_ENABLED } from '../../lib/dramaVoiceBinding'
import { useI18n } from '../../i18n/context'
import { displayDramaAssetName } from '../../lib/dramaLibraryAssets'

type Props = {
  items: FragmentRefStripItem[]
  onSelect?: (assetId: number) => void
}

// 渲染当前分镜关联资产条
export function EpisodeEditReferenceStrip({ items, onSelect }: Props) {
  const { t } = useI18n()
  if (items.length === 0) {
    return (
      <div className="drama-ep-ref-strip is-empty">
        <span className="drama-ep-ref-strip-hint">{t('dramaEpisode.refStrip.empty')}</span>
      </div>
    )
  }

  // 资产分类展示名：已知分类翻译；未知分类若含中文则不显示
  const typeLabel = (type: string) => {
    const tab = normalizeAssetTab(type)
    if (tab) return t(`dramaCanvas.assetTab.${tab}`)
    return /[\u4e00-\u9fff]/.test(type) ? '' : type
  }

  return (
    <div className="drama-ep-ref-strip" aria-label={t('dramaEpisode.refStrip.ariaLabel')}>
      {items.map((item) => (
        <button
          key={item.assetId}
          type="button"
          className={`drama-ep-ref-chip${item.isCharacter ? ' is-character' : ''}${
            item.voiceUrl ? ' has-voice' : item.isCharacter ? ' no-voice' : ''
          }`}
          title={`${displayDramaAssetName(item.name)}${typeLabel(item.type) ? ` · ${typeLabel(item.type)}` : ''}${
            DRAMA_VOICE_BINDING_ENABLED && item.isCharacter
              ? item.voiceLabel
                ? t('dramaEpisode.refStrip.voiceBound', { label: displayDramaAssetName(item.voiceLabel) })
                : t('dramaEpisode.refStrip.voiceUnbound')
              : ''
          }`}
          onClick={() => onSelect?.(item.assetId)}
        >
          {item.previewUrl ? (
            <img src={item.previewUrl} alt="" draggable={false} />
          ) : (
            <span className="drama-ep-ref-chip-fallback">{(displayDramaAssetName(item.name) || '?')[0]}</span>
          )}
          {DRAMA_VOICE_BINDING_ENABLED && item.isCharacter ? (
            <span className={`drama-ep-ref-voice-badge${item.voiceUrl ? ' bound' : ''}`}>
              {item.voiceUrl ? t('dramaEpisode.refStrip.voiceBadge') : t('dramaEpisode.refStrip.noVoiceBadge')}
            </span>
          ) : null}
          <em>{displayDramaAssetName(item.name)}</em>
        </button>
      ))}
    </div>
  )
}
