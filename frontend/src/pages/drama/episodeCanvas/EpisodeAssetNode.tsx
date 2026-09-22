/** 出境资产节点：缩略图卡片，可关联多个分镜 */
import { memo } from 'react'
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { X } from 'lucide-react'
import type { EpisodeAssetNodeData } from './buildEpisodeFlow'
import { useI18n } from '../../../i18n/context'

type Props = NodeProps<Node<EpisodeAssetNodeData>> & {
  onUnlinkAsset?: (fragmentId: number, assetId: number) => void
}

// 渲染出境资产节点（同一资产全局只显示一张卡片）
function EpisodeAssetNodeComponent({ data, selected, onUnlinkAsset }: Props) {
  const { t } = useI18n()
  const links = data.linkedFragments || []
  const name = data.name || t('dramaCanvas.episode.assetFallback', { id: data.assetId })
  const typeLabel = data.typeTab
    ? t(`dramaCanvas.assetTab.${data.typeTab}`)
    : data.typeLabel || t('dramaCanvas.episode.asset')
  // 分镜标签为空时按语言兜底
  const linkLabel = (link: { fragmentId: number; label: string }) =>
    link.label || t('dramaCanvas.episode.shotFallback', { id: link.fragmentId })

  return (
    <div className={`ep-asset-node${selected ? ' is-selected' : ''}`}>
      <div className="ep-asset-node-head">
        <span>{typeLabel}</span>
        {links.length > 1 ? (
          <span className="ep-asset-node-count" title={t('dramaCanvas.episode.linkedShots')}>
            {t('dramaCanvas.episode.shotCount', { count: links.length })}
          </span>
        ) : null}
      </div>
      <div className="ep-asset-node-thumb">
        {data.previewUrl ? (
          <img src={data.previewUrl} alt="" draggable={false} />
        ) : (
          <span>{(name || '?')[0]}</span>
        )}
      </div>
      <div className="ep-asset-node-name">{name}</div>
      {selected && links.length > 0 ? (
        <div className="ep-asset-node-links nodrag nopan">
          {links.map((link) => (
            <button
              key={link.fragmentId}
              type="button"
              className="ep-asset-node-unlink-chip"
              aria-label={t('dramaCanvas.episode.unlink', { label: linkLabel(link) })}
              title={t('dramaCanvas.episode.unlink', { label: linkLabel(link) })}
              onClick={() => onUnlinkAsset?.(link.fragmentId, data.assetId)}
            >
              {linkLabel(link)}
              <X size={11} strokeWidth={2.4} aria-hidden />
            </button>
          ))}
        </div>
      ) : null}
      <Handle className="ep-frag-handle" type="source" position={Position.Right} />
    </div>
  )
}

export const EpisodeAssetNode = memo(EpisodeAssetNodeComponent)
