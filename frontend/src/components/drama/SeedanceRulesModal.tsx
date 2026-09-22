/** Seedance 传值与脚本规则说明弹窗（分集编辑页，对齐 docs/EPISODE_RULES.md） */
import { Fragment, useState, type ReactNode } from 'react'
import Modal from '../ui/Modal'
import { useI18n } from '../../i18n/context'
import { interpolate, type TVars } from '../../i18n/lookup'
import {
  DRAMA_SEGMENT_DURATION_MAX,
  DRAMA_SEGMENT_DURATION_MIN,
  DRAMA_SHOT_DURATION_HARD_MAX,
  FRAGMENT_CONTENT_DURATION_MAX,
} from '../../lib/dramaEpisodePromptEditor'
import {
  DIALOGUE_PREFIX,
  DRAMA_NARRATION_PREFIX,
  DRAMA_SUBTITLE_CUE,
  VISUAL_PREFIX,
} from '../../lib/dramaEpisodeScriptValidate'

type Tab = 'payload' | 'script' | 'usage'

type Props = {
  open: boolean
  onClose: () => void
}

// 文案里可用的常量占位符：时长上限 + 脚本协议前缀 / 提示词约束块标记（中文原文由后端解析，不翻译）
const RULE_VARS: TVars = {
  max: FRAGMENT_CONTENT_DURATION_MAX,
  segMin: DRAMA_SEGMENT_DURATION_MIN,
  segMax: DRAMA_SEGMENT_DURATION_MAX,
  hardMax: DRAMA_SHOT_DURATION_HARD_MAX,
  visual: VISUAL_PREFIX,
  dialogue: DIALOGUE_PREFIX,
  narration: DRAMA_NARRATION_PREFIX,
  empty: '空镜：',
  wide: '远景：',
  close: '特写：',
  push: '推镜：',
  dialogueForm: '角色名：台词',
  blockStyle: '【强制约束：视频画面风格】',
  blockAudio: '【强制约束：音频、字幕与配乐】',
  blockRole: '【强制约束：角色形象】',
  blockScene: '【强制约束：场景】',
  blockProp: '【强制约束：道具】',
}

/**
 * 渲染带简单标记的说明文案：**粗体**、`代码`
 * @param text 文案（先插值 RULE_VARS）
 */
function rich(text: string): ReactNode {
  const parts = interpolate(text, RULE_VARS).split(/(\*\*[^*]+\*\*|`[^`]+`)/)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={i}>{part.slice(1, -1)}</code>
    }
    return <Fragment key={i}>{part}</Fragment>
  })
}

// 列表：每项一条 rich 文案
function RuleList({ items, ordered = false }: { items: readonly string[]; ordered?: boolean }) {
  const children = items.map((item, i) => <li key={i}>{rich(item)}</li>)
  return ordered ? (
    <ol className="seedance-rules-list">{children}</ol>
  ) : (
    <ul className="seedance-rules-list">{children}</ul>
  )
}

// 渲染 Seedance 规则说明弹窗
export function SeedanceRulesModal({ open, onClose }: Props) {
  const { t, m } = useI18n()
  const [tab, setTab] = useState<Tab>('payload')
  const r = m.dramaProject.seedance
  const tabs: Tab[] = ['payload', 'script', 'usage']

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('dramaProject.seedance.title')}
      size="lg"
      className="pf-help-modal seedance-rules-modal"
      footer={
        <button type="button" className="pf-btn pf-btn-lime pf-btn-sm" onClick={onClose}>
          {t('dramaProject.seedance.ok')}
        </button>
      }
    >
      <div className="pf-help">
        <p className="pf-help-lede">{rich(r.lede)}</p>

        <div className="pf-help-tabs" role="tablist" aria-label={t('dramaProject.seedance.tabsAria')}>
          {tabs.map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={tab === key ? 'active' : undefined}
              onClick={() => setTab(key)}
            >
              {r.tabs[key]}
            </button>
          ))}
        </div>

        {tab === 'payload' ? (
          <div className="seedance-rules-section">
            <h4>{r.payload.paramsTitle}</h4>
            <RuleList items={r.payload.params} />

            <h4>{r.payload.contentTitle}</h4>
            {/* 音色难控：暂不提交 reference_audio，口播由 generate_audio 自发挥（原第 3 项已移除） */}
            <RuleList items={r.payload.content} ordered />
            <p className="seedance-rules-note">{rich(r.payload.note)}</p>

            <h4>{r.payload.orderTitle}</h4>
            {/* 角色音色 / 旁白音色约束块暂关，未列出 */}
            <RuleList items={r.payload.order} ordered />
          </div>
        ) : null}

        {tab === 'script' ? (
          <div className="seedance-rules-section">
            <h4>{r.script.durationTitle}</h4>
            <RuleList items={r.script.duration} />

            <h4>{r.script.refsTitle}</h4>
            <RuleList items={r.script.refs} />

            <h4>{r.script.cuesTitle}</h4>
            {/* 示例为脚本协议原文（中文标记由后端解析），各语言一致不翻译 */}
            <div className="seedance-rules-examples">
              <code>{DRAMA_SUBTITLE_CUE}</code>
              <code>【BGM：低沉史诗，音量低于人声】</code>
              <code>@duration:4</code>
              <code>{VISUAL_PREFIX}空镜：浑浊黄河拍击老石……</code>
              <code>@duration:6</code>
              <code>{DIALOGUE_PREFIX}禹：水患未平，岂能退！</code>
              <code>{DRAMA_NARRATION_PREFIX}千年后，人们仍记得这一战。</code>
            </div>
            <RuleList items={r.script.cues} />

            <h4>{r.script.cameraTitle}</h4>
            <RuleList items={r.script.camera} />
          </div>
        ) : null}

        {tab === 'usage' ? (
          <div className="seedance-rules-section">
            <h4>{r.usage.checkTitle}</h4>
            <RuleList items={r.usage.check} />

            <h4>{r.usage.queueTitle}</h4>
            <RuleList items={r.usage.queue} />

            <h4>{r.usage.linkTitle}</h4>
            <RuleList items={r.usage.link} />

            <h4>{r.usage.audioTitle}</h4>
            <RuleList items={r.usage.audio} />

            <h4>{r.usage.replanTitle}</h4>
            <p className="seedance-rules-note">{rich(r.usage.replan)}</p>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
