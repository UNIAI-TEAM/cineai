import { zhPages } from './zh/pages'
import { zhStudio } from './zh/studio'
import { zhStudioBoard } from './zh/studioBoard'
import { zhBilling } from './zh/billing'
import { zhSettingsPanels } from './zh/settingsPanels'
import { zhShell } from './zh/shell'
import { zhErrors } from './zh/errors'

export const zh = {
  ...zhShell,
  ...zhPages,
  ...zhStudio,
  ...zhStudioBoard,
  ...zhBilling,
  ...zhSettingsPanels,
  ...zhErrors,
}
