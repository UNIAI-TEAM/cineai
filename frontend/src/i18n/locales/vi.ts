import { viPages } from './vi/pages'
import { viStudio } from './vi/studio'
import { viStudioBoard } from './vi/studioBoard'
import { viBilling } from './vi/billing'
import { viSettingsPanels } from './vi/settingsPanels'
import { viShell } from './vi/shell'
import { viErrors } from './vi/errors'
import { viDramaProject } from './vi/dramaProject'
import { viDramaCanvas } from './vi/dramaCanvas'
import { viDramaGen } from './vi/dramaGen'

export const vi = {
  ...viShell,
  ...viPages,
  ...viStudio,
  ...viStudioBoard,
  ...viBilling,
  ...viSettingsPanels,
  ...viErrors,
  ...viDramaProject,
  ...viDramaCanvas,
  ...viDramaGen,
}
