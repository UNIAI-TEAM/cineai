/** Drama project workflow steps: 剧情大纲 → 分镜 → 生成视频 */
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'

export type ProjectStepKey = 'outline' | 'storyboard' | 'video'
export type WorkspaceViewKey = ProjectStepKey | 'assets' | 'episodes'

export type ProjectStepItem = {
  key: ProjectStepKey
  label: string
  order: number
}

export type WorkspaceLocationState = {
  activeStep?: WorkspaceViewKey
  returnStep?: ProjectStepKey | 'episodes'
}

// 有剧本走大纲；无剧本直接分镜（分集列表）
// 步骤名按当前界面语言取
export function buildProjectSteps(hasScript: boolean): ProjectStepItem[] {
  const labels = messages[getActiveLocale()].dramaProject.steps
  const keys: ProjectStepKey[] = hasScript ? ['outline', 'storyboard', 'video'] : ['storyboard', 'video']
  return keys.map((key, index) => ({ key, label: labels[key], order: index + 1 }))
}

export function getInitialProjectStep(hasScript: boolean): ProjectStepKey {
  return hasScript ? 'outline' : 'storyboard'
}

export function isProjectStepKey(value: string | undefined): value is ProjectStepKey {
  return value === 'outline' || value === 'storyboard' || value === 'video'
}

/** 旧 state activeStep=episodes 映射到分镜 */
export function normalizeWorkspaceStep(value: string | undefined): ProjectStepKey | 'assets' | null {
  if (value === 'assets') return 'assets'
  if (value === 'episodes' || value === 'storyboard' || value === 'video') {
    return value === 'episodes' ? 'storyboard' : value
  }
  if (value === 'outline') return 'outline'
  return null
}

export function getNextProjectStep(
  steps: ProjectStepItem[],
  currentStep: ProjectStepKey,
): ProjectStepKey | null {
  const currentIndex = steps.findIndex((step) => step.key === currentStep)
  if (currentIndex < 0 || currentIndex >= steps.length - 1) return null
  return steps[currentIndex + 1].key
}

/** 分镜 / 生成视频都进分集路由 */
export function isEpisodesRouteStep(step: ProjectStepKey | string | undefined): boolean {
  return step === 'storyboard' || step === 'video' || step === 'episodes'
}
