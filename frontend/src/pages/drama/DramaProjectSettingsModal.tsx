/** 大纲「项目设置」：内容语言/画幅/画风/字幕/配音/人物介绍/尾帧衔接（全局可改；分镜页只读） */
import { useState } from 'react'
import Modal from '../../components/ui/Modal'
import { useI18n } from '../../i18n/context'
import { DramaImageStyleModal } from './DramaImageStyleModal'
import {
  characterIntroModeEnabled,
  readEpisodeCharacterIntroMode,
  type DramaCharacterIntroMode,
} from '../../lib/dramaCharacterIntro'
import { type ImageStyleId } from '../../lib/dramaImageStyles'
import {
  DRAMA_RATIO_OPTIONS,
  DRAMA_RES_OPTIONS,
  readProjectAspectRatio,
  readProjectResolution,
  type DramaAspectRatio,
  type DramaResolution,
} from '../../lib/dramaProjectOutputSettings'
import {
  readEpisodeSubtitleMode,
  subtitleModeUsesModelOutput,
  type DramaSubtitleMode,
} from '../../lib/dramaSubtitleBoard'
import { contentLangOptions, normalizeContentLang, type ContentLang } from '../../lib/contentLang'
import { readProjectVoiceMode, type DramaVoiceMode } from '../../lib/dramaFragmentDub'
import type { DramaProject, DramaScript } from '../../api/drama'
import { dramaApi } from '../../api/drama'

type Props = {
  open: boolean
  projectId: number
  project: DramaProject
  script: DramaScript | null
  onClose: () => void
  onProjectChange: (p: DramaProject) => void
  onScriptChange: (s: DramaScript) => void
  onError: (msg: string) => void
}

type ChoiceProps<T extends string | boolean> = {
  options: Array<{ value: T; label: string }>
  value: T
  disabled?: boolean
  onChange: (value: T) => void
}

function coerceLinkLastFrame(params: Record<string, unknown> | null | undefined): boolean {
  const raw = params?.linkLastFrame ?? params?.link_last_frame
  if (raw == null) return true
  if (typeof raw === 'boolean') return raw
  if (typeof raw === 'number') return raw !== 0
  if (typeof raw === 'string') {
    const n = raw.trim().toLowerCase()
    if (['0', 'false', 'no', 'off', ''].includes(n)) return false
  }
  return Boolean(raw)
}

/** 项目设置内选项条（复用大纲 chip 样式） */
function SettingsChoiceRow<T extends string | boolean>({
  options,
  value,
  disabled,
  onChange,
}: ChoiceProps<T>) {
  return (
    <div className="drama-project-settings-chips" role="group">
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          className={`drama-outline-chip-btn${value === opt.value ? ' is-on' : ''}`}
          disabled={disabled}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

/** 项目级全局成片设置弹窗 */
export function DramaProjectSettingsModal({
  open,
  projectId,
  project,
  script,
  onClose,
  onProjectChange,
  onScriptChange,
  onError,
}: Props) {
  const { t } = useI18n()
  const [saving, setSaving] = useState(false)
  const projectParams = (project.params || {}) as Record<string, unknown>
  const styleId = (String(script?.params?.image_style_id || projectParams.image_style_id || '') ||
    '') as ImageStyleId | ''
  const aspectRatio = readProjectAspectRatio(projectParams)
  const resolution = readProjectResolution(projectParams)
  const subtitleMode = readEpisodeSubtitleMode(projectParams)
  const characterIntroMode = readEpisodeCharacterIntroMode(projectParams)
  const linkLastFrame = coerceLinkLastFrame(projectParams)
  // 内容语言：后端返回的 content_lang 已含老项目推断；zh 只在项目本就是中文时可选
  const contentLang: ContentLang =
    normalizeContentLang(project.content_lang) || normalizeContentLang(projectParams.content_lang) || 'vi'
  const voiceMode = readProjectVoiceMode(projectParams, contentLang)

  async function patchProjectParams(patch: Record<string, unknown>) {
    setSaving(true)
    try {
      const nextParams = { ...projectParams, ...patch }
      const updated = await dramaApi.updateProject(projectId, { params: nextParams })
      onProjectChange(updated)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaProject.settings.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  // 修改内容语言：只影响之后 AI 生成的内容（后端 PATCH content_lang，非法值报 common.invalid_content_lang）
  async function handleContentLangChange(lang: ContentLang) {
    if (lang === contentLang) return
    setSaving(true)
    try {
      const updated = await dramaApi.updateProject(projectId, { content_lang: lang })
      onProjectChange(updated)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('contentLang.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleStyleChange(id: ImageStyleId | '') {
    setSaving(true)
    try {
      const updated = await dramaApi.updateScript(projectId, {
        image_style_id: id || undefined,
      })
      onScriptChange(updated)
      const p = await dramaApi.getProject(projectId)
      onProjectChange(p)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaProject.settings.styleSaveFailed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('dramaProject.settings.title')}
      size="md"
      className="drama-project-settings-modal"
      footer={
        <button type="button" className="drama-btn-primary" onClick={onClose} disabled={saving}>
          {t('dramaProject.settings.done')}
        </button>
      }
    >
      <div className="drama-project-settings">
        <p className="drama-muted drama-project-settings-lead">
          {t('dramaProject.settings.lead')}
        </p>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('contentLang.label')}</h4>
          </div>
          <SettingsChoiceRow
            value={contentLang}
            disabled={saving}
            options={contentLangOptions(contentLang).map((lang) => ({
              value: lang,
              label: t(`contentLang.names.${lang}`),
            }))}
            onChange={(lang) => void handleContentLangChange(lang)}
          />
          <p className="drama-muted">{t('contentLang.changeHint')}</p>
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.settings.ratio')}</h4>
          </div>
          <SettingsChoiceRow
            value={aspectRatio}
            disabled={saving}
            options={DRAMA_RATIO_OPTIONS.map((r) => ({ value: r as DramaAspectRatio, label: r }))}
            onChange={(ratio) => void patchProjectParams({ aspect_ratio: ratio })}
          />
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.output.resolution')}</h4>
          </div>
          <SettingsChoiceRow
            value={resolution}
            disabled={saving}
            options={DRAMA_RES_OPTIONS.map((r) => ({ value: r as DramaResolution, label: r }))}
            onChange={(res) => void patchProjectParams({ resolution: res })}
          />
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaStyle.modalTitle')}</h4>
          </div>
          <DramaImageStyleModal
            variant="field"
            fieldLabel=""
            title={t('dramaProject.pickProjectStyle')}
            emptyLabel={t('dramaStyle.pick')}
            value={styleId}
            disabled={saving}
            onChange={(id) => void handleStyleChange(id)}
          />
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.settings.subtitle')}</h4>
          </div>
          <SettingsChoiceRow
            value={subtitleMode}
            disabled={saving}
            options={[
              { value: 'post' as DramaSubtitleMode, label: t('dramaProject.settings.subtitlePost') },
              { value: 'model' as DramaSubtitleMode, label: t('dramaProject.settings.subtitleModel') },
            ]}
            onChange={(mode) =>
              void patchProjectParams({
                subtitleMode: mode,
                subtitleEnabled: subtitleModeUsesModelOutput(mode),
              })
            }
          />
          <p className="drama-muted">{t('dramaProject.settings.subtitleNote')}</p>
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.settings.voice')}</h4>
          </div>
          <SettingsChoiceRow
            value={voiceMode}
            disabled={saving}
            options={[
              { value: 'dub' as DramaVoiceMode, label: t('dramaProject.settings.voiceDub') },
              { value: 'native' as DramaVoiceMode, label: t('dramaProject.settings.voiceNative') },
            ]}
            onChange={(mode) => void patchProjectParams({ voiceMode: mode })}
          />
          <p className="drama-muted">{t('dramaProject.settings.voiceNote')}</p>
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.settings.intro')}</h4>
          </div>
          <SettingsChoiceRow
            value={characterIntroMode}
            disabled={saving}
            options={[
              { value: 'off' as DramaCharacterIntroMode, label: t('dramaProject.settings.introOff') },
              { value: 'model' as DramaCharacterIntroMode, label: t('dramaProject.settings.introOn') },
            ]}
            onChange={(mode) =>
              void patchProjectParams({
                characterIntroMode: mode,
                characterIntroEnabled: characterIntroModeEnabled(mode),
              })
            }
          />
        </section>

        <section className="drama-project-settings-section">
          <div className="drama-project-settings-head">
            <h4>{t('dramaProject.settings.link')}</h4>
          </div>
          <SettingsChoiceRow
            value={linkLastFrame}
            disabled={saving}
            options={[
              { value: true, label: t('dramaProject.settings.linkOn') },
              { value: false, label: t('dramaProject.settings.linkOff') },
            ]}
            onChange={(enabled) => void patchProjectParams({ linkLastFrame: enabled })}
          />
          <p className="drama-muted">{t('dramaProject.settings.linkNote')}</p>
        </section>
      </div>
    </Modal>
  )
}
