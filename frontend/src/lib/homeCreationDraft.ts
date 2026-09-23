import type { ToolId } from './toolsCatalog'

/** Session key used to hand off homepage creation prompts into a tool page. */
export const HOME_CREATION_DRAFT_KEY = 'cineai.home.creation-draft'

type HomeCreationToolId = Extract<ToolId, 't2i' | 't2v'>

type HomeCreationDraftPayload = {
  toolId: HomeCreationToolId
  prompt: string
  ratio: string
}

const HOME_CREATION_TOOLS = new Set<HomeCreationToolId>(['t2i', 't2v'])
const HOME_CREATION_RATIOS = new Set(['16:9', '9:16', '1:1'])
const HOME_CREATION_DEFAULT_RATIO = '16:9'
const HOME_CREATION_MAX_PROMPT = 4000

function isHomeCreationToolId(value: unknown): value is HomeCreationToolId {
  return typeof value === 'string' && HOME_CREATION_TOOLS.has(value as HomeCreationToolId)
}

function normalizePrompt(value: unknown): string | null {
  const prompt = typeof value === 'string' ? value.trim().slice(0, HOME_CREATION_MAX_PROMPT) : ''
  return prompt || null
}

function normalizeRatio(value: unknown): string {
  return typeof value === 'string' && HOME_CREATION_RATIOS.has(value)
    ? value
    : HOME_CREATION_DEFAULT_RATIO
}

/** Parse and normalize a homepage creation draft without consuming storage. */
export function peekHomeCreationDraft(raw: string | null): HomeCreationDraftPayload | null {
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as { toolId?: unknown; prompt?: unknown; ratio?: unknown } | null
    if (!parsed || typeof parsed !== 'object') return null
    if (!isHomeCreationToolId(parsed.toolId)) return null

    const prompt = normalizePrompt(parsed.prompt)
    if (!prompt) return null

    return {
      toolId: parsed.toolId,
      prompt,
      ratio: normalizeRatio(parsed.ratio),
    }
  } catch {
    return null
  }
}

/** Read a draft only when it targets the active creation tool. */
export function readHomeCreationDraft(
  raw: string | null,
  toolId: string,
): { prompt: string; ratio: string } | null {
  const draft = peekHomeCreationDraft(raw)
  if (!draft || draft.toolId !== toolId) return null
  return { prompt: draft.prompt, ratio: draft.ratio }
}
