import { enPages } from './en/pages'
import { enStudio } from './en/studio'
import { enStudioBoard } from './en/studioBoard'
import { enBilling } from './en/billing'
import { enSettingsPanels } from './en/settingsPanels'
import { enShell } from './en/shell'
import { enErrors } from './en/errors'
import { enDramaAssets } from './en/dramaAssets'
import { enDramaProject } from './en/dramaProject'
import { enDramaCanvas } from './en/dramaCanvas'
import { enDramaGen } from './en/dramaGen'

export const en = {
  ...enShell,
  ...enPages,
  ...enStudio,
  ...enStudioBoard,
  ...enBilling,
  ...enSettingsPanels,
  ...enErrors,
  ...enDramaAssets,
  ...enDramaProject,
  ...enDramaCanvas,
  ...enDramaGen,
}
