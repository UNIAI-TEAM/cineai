import { zhPages } from './zh/pages'
import { zhStudio } from './zh/studio'
import { zhStudioBoard } from './zh/studioBoard'
import { zhBilling } from './zh/billing'
import { zhSettingsPanels } from './zh/settingsPanels'
import { zhShell } from './zh/shell'
import { zhErrors } from './zh/errors'
import { zhDramaProject } from './zh/dramaProject'
import { zhDramaCanvas } from './zh/dramaCanvas'
import { zhDramaGen } from './zh/dramaGen'

export const zh = {
  ...zhShell,
  ...zhPages,
  ...zhStudio,
  ...zhStudioBoard,
  ...zhBilling,
  ...zhSettingsPanels,
  ...zhErrors,
  ...zhDramaProject,
  ...zhDramaCanvas,
  ...zhDramaGen,
}
