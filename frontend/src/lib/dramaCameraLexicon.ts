/**
 * 漫剧运镜 / 景别词库（对齐 docs/EPISODE_RULES.md §5）
 * 供分集编辑 @ 菜单插入画面行前缀或运镜短语
 */

import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'

export type DramaCameraLexiconGroup = 'shot' | 'move'

export type DramaCameraLexiconItem = {
  id: string
  group: DramaCameraLexiconGroup
  /** 列表展示名（按当前语言） */
  readonly label: string
  /** 插入到脚本的文本（协议前缀，保持中文，用户可继续补描写） */
  insert: string
  /** 一行说明（按当前语言） */
  readonly hint: string
}

type CameraItemId = keyof typeof messages.zh.dramaEpisode.camera.items

// 构造词库项：insert 固定中文写入脚本，label / hint 取当前语言文案
function cameraItem(id: CameraItemId, group: DramaCameraLexiconGroup, insert: string): DramaCameraLexiconItem {
  return {
    id,
    group,
    insert,
    get label() {
      return messages[getActiveLocale()].dramaEpisode.camera.items[id].label
    },
    get hint() {
      return messages[getActiveLocale()].dramaEpisode.camera.items[id].hint
    },
  }
}

/** 景别标签：写入画面行，勿标成对白 */
export const DRAMA_SHOT_SIZE_LEXICON: DramaCameraLexiconItem[] = [
  cameraItem('empty', 'shot', '空镜：'),
  cameraItem('wide', 'shot', '远景：'),
  cameraItem('full', 'shot', '全景：'),
  cameraItem('medium', 'shot', '中景：'),
  cameraItem('close', 'shot', '近景：'),
  cameraItem('closeup', 'shot', '特写：'),
  cameraItem('ecu', 'shot', '大特写：'),
  cameraItem('establish', 'shot', '建立镜头：'),
  cameraItem('atmosphere', 'shot', '气氛镜头：'),
]

/** 运镜短语：单段运动轴建议 ≤ 2 */
export const DRAMA_CAMERA_MOVE_LEXICON: DramaCameraLexiconItem[] = [
  cameraItem('push', 'move', '推镜：'),
  cameraItem('pull', 'move', '拉镜：'),
  cameraItem('pan', 'move', '摇镜：'),
  cameraItem('truck', 'move', '移镜：'),
  cameraItem('follow', 'move', '跟拍：'),
  cameraItem('high', 'move', '俯拍：'),
  cameraItem('low', 'move', '仰拍：'),
  cameraItem('aerial', 'move', '航拍：'),
]

/** 合并词库（插入列表用） */
export const DRAMA_CAMERA_LEXICON: DramaCameraLexiconItem[] = [
  ...DRAMA_SHOT_SIZE_LEXICON,
  ...DRAMA_CAMERA_MOVE_LEXICON,
]

/** 运镜使用提示（只展示，不插入；按当前语言） */
export function dramaCameraUsageTips(): readonly string[] {
  return messages[getActiveLocale()].dramaEpisode.camera.tips
}

// 按关键字过滤词库（匹配 label / insert / hint）
export function filterDramaCameraLexicon(
  items: DramaCameraLexiconItem[],
  query: string,
): DramaCameraLexiconItem[] {
  const q = (query || '').trim().toLowerCase()
  if (!q) return items
  return items.filter(
    (item) =>
      item.label.toLowerCase().includes(q) ||
      item.insert.toLowerCase().includes(q) ||
      item.hint.toLowerCase().includes(q),
  )
}
