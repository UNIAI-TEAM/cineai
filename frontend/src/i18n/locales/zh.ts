import { zhPages } from './zh/pages'
import { zhStudio } from './zh/studio'
import { zhStudioBoard } from './zh/studioBoard'
import { zhBilling } from './zh/billing'
import { zhSettingsPanels } from './zh/settingsPanels'
import { zhShell } from './zh/shell'
import { zhErrors } from './zh/errors'
import { zhDramaGen } from './zh/dramaGen'

export const zh = {
  ...zhShell,
  ...zhPages,
  ...zhStudio,
  ...zhStudioBoard,
  ...zhBilling,
  ...zhSettingsPanels,
  ...zhErrors,
  ...zhDramaGen,
}
