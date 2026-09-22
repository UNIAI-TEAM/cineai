/** Agent Skill 多选列表（弹窗 / 画布下拉共用）：可预览、下载 */
import { useRef, useState, type MouseEvent } from 'react'
import { Download, Eye, X } from 'lucide-react'
import type { AgentSkill } from '../../api/agentSkills'
import { useI18n } from '../../i18n/context'
import { triggerBlobDownload } from '../../lib/clientDownload'

type AgentSkillPickerProps = {
  skills: AgentSkill[]
  selectedIds: number[]
  onToggle: (skillId: number) => void
  onSelectAll?: () => void
  onSelectNone?: () => void
  onUpload?: (file: File) => void
  uploading?: boolean
  uploadError?: string
  emptyText?: string
  compact?: boolean
}

/** 把 Skill 还原成可下载的 Cursor 风格 SKILL.md */
export function skillToMarkdown(skill: AgentSkill): string {
  const tasks = Array.isArray(skill.tasks) ? skill.tasks.filter(Boolean) : []
  const taskLines =
    tasks.length > 0
      ? ['tasks:', ...tasks.map((task) => `  - ${String(task).replace(/\n/g, ' ')}`)]
      : ['tasks: []']
  const desc = String(skill.description || '').replace(/\n/g, ' ').trim()
  const name = String(skill.name || skill.slug || 'skill').trim() || 'skill'
  return [
    '---',
    `name: ${name}`,
    `description: ${desc}`,
    ...taskLines,
    '---',
    '',
    String(skill.body || '').trim(),
    '',
  ].join('\n')
}

/** 下载文件名 */
function skillDownloadName(skill: AgentSkill): string {
  const base = (skill.slug || skill.name || 'skill')
    .replace(/[^\w\u4e00-\u9fff.-]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return `${base || 'skill'}.md`
}

/** 渲染 Skill 勾选列表，可预览 / 下载 / 上传 */
export function AgentSkillPicker({
  skills,
  selectedIds,
  onToggle,
  onSelectAll,
  onSelectNone,
  onUpload,
  uploading = false,
  uploadError = '',
  emptyText,
  compact = false,
}: AgentSkillPickerProps) {
  const { t } = useI18n()
  const selected = new Set(selectedIds)
  const rootClass = compact ? 'fc-skill-picker' : 'pf-skill-picker'
  const fileRef = useRef<HTMLInputElement>(null)
  const [previewSkill, setPreviewSkill] = useState<AgentSkill | null>(null)

  // 下载单个 Skill 为 .md
  function handleDownload(skill: AgentSkill, event: MouseEvent) {
    event.preventDefault()
    event.stopPropagation()
    const markdown = skillToMarkdown(skill)
    triggerBlobDownload(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), skillDownloadName(skill))
  }

  // 打开预览（阻止勾选冒泡）
  function handlePreview(skill: AgentSkill, event: MouseEvent) {
    event.preventDefault()
    event.stopPropagation()
    setPreviewSkill(skill)
  }

  return (
    <div className={rootClass}>
      <div className={`${rootClass}-toolbar`}>
        {onSelectAll ? (
          <button type="button" className={`${rootClass}-link`} onClick={onSelectAll}>
            {t('dramaProject.skill.selectAll')}
          </button>
        ) : null}
        {onSelectNone ? (
          <button type="button" className={`${rootClass}-link`} onClick={onSelectNone}>
            {t('dramaProject.skill.selectNone')}
          </button>
        ) : null}
        {onUpload ? (
          <button
            type="button"
            className={`${rootClass}-link`}
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? t('dramaProject.skill.uploading') : t('dramaProject.skill.upload')}
          </button>
        ) : null}
      </div>
      {skills.length === 0 ? (
        <p className={`${rootClass}-empty`}>{emptyText ?? t('dramaProject.skill.empty')}</p>
      ) : (
        <ul className={`${rootClass}-list`}>
          {skills.map((skill) => {
            const checked = selected.has(skill.id)
            return (
              <li key={skill.id} className={`${rootClass}-row`}>
                <label className={`${rootClass}-item${checked ? ' is-checked' : ''}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggle(skill.id)}
                  />
                  <span>
                    <strong>{skill.name}</strong>
                    {skill.description ? <em>{skill.description}</em> : null}
                  </span>
                </label>
                <div className={`${rootClass}-actions`}>
                  <button
                    type="button"
                    className={`${rootClass}-action`}
                    title={t('common.preview')}
                    aria-label={t('dramaProject.skill.previewAria', { name: skill.name })}
                    onClick={(event) => handlePreview(skill, event)}
                  >
                    <Eye size={14} strokeWidth={1.8} />
                  </button>
                  <button
                    type="button"
                    className={`${rootClass}-action`}
                    title={t('dramaProject.skill.download')}
                    aria-label={t('dramaProject.skill.downloadAria', { name: skill.name })}
                    onClick={(event) => handleDownload(skill, event)}
                  >
                    <Download size={14} strokeWidth={1.8} />
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {onUpload ? (
        <input
          ref={fileRef}
          type="file"
          accept=".md,.markdown,.txt"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) onUpload(file)
          }}
        />
      ) : null}
      {uploadError ? <p className={`${rootClass}-error`}>{uploadError}</p> : null}

      {previewSkill ? (
        <div className={`${rootClass}-preview`} role="dialog" aria-label={t('dramaProject.skill.previewAria', { name: previewSkill.name })}>
          <div className={`${rootClass}-preview-head`}>
            <div>
              <strong>{previewSkill.name}</strong>
              {previewSkill.description ? <span>{previewSkill.description}</span> : null}
            </div>
            <div className={`${rootClass}-preview-head-actions`}>
              <button
                type="button"
                className={`${rootClass}-link`}
                onClick={(event) => handleDownload(previewSkill, event)}
              >
                {t('dramaProject.skill.download')}
              </button>
              <button
                type="button"
                className={`${rootClass}-action`}
                aria-label={t('dramaProject.skill.closePreview')}
                onClick={() => setPreviewSkill(null)}
              >
                <X size={16} />
              </button>
            </div>
          </div>
          <pre className={`${rootClass}-preview-body`}>{skillToMarkdown(previewSkill)}</pre>
        </div>
      ) : null}
    </div>
  )
}
