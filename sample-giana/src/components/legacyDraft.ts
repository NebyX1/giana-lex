export type LegacyResolutionArticle = { number: string; text: string }
export type LegacyResolutionDraft = {
  title: string
  number: string
  place: string
  date: string
  visto: string
  resultandos: string[]
  considerandos: string[]
  atento: string
  resuelve: LegacyResolutionArticle[]
  notes: string
}

export type LegacyDraft =
  | { kind: 'empty' }
  | { kind: 'text'; content: string }
  | { kind: 'resolution'; draft: LegacyResolutionDraft }

export const initialLegacyDraft: LegacyResolutionDraft = {
  title: 'RESOLUCIÓN',
  number: '',
  place: '',
  date: '',
  visto: '',
  resultandos: [''],
  considerandos: [''],
  atento: '',
  resuelve: [{ number: '1', text: '' }],
  notes: 'BORRADOR SUJETO A REVISIÓN HUMANA',
}

function looksLikeDocumentDraft(content: string) {
  if (content.trim().length < 200) return false
  return /(?:^|\n)\s*(?:#{1,6}\s+|\d+[.)]\s+|(?:CONTRATO|CL[AÁ]USULA|RESOLUCI[OÓ]N)\b)/i.test(content)
}

function stringList(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

export function parseLegacyDraftContent(content: string | undefined): LegacyDraft {
  if (!content) return { kind: 'empty' }
  try {
    const parsed: unknown = JSON.parse(content)
    if (!parsed || typeof parsed !== 'object') return { kind: 'empty' }
    const value = parsed as Record<string, unknown>
    if (value.document_type !== 'resolution' || !Array.isArray(value.resuelve)) return { kind: 'empty' }
    const articles = value.resuelve.flatMap((item, index) => {
      if (!item || typeof item !== 'object') return []
      const article = item as Record<string, unknown>
      const text = typeof article.text === 'string' ? article.text : ''
      return text ? [{ number: String(article.number ?? index + 1), text }] : []
    })
    const resultandos = stringList(value.resultandos)
    const considerandos = stringList(value.considerandos)
    return { kind: 'resolution', draft: {
      title: typeof value.title === 'string' ? value.title : initialLegacyDraft.title,
      number: typeof value.number === 'string' ? value.number : '',
      place: typeof value.place === 'string' ? value.place : '',
      date: typeof value.date === 'string' ? value.date : '',
      visto: typeof value.visto === 'string' ? value.visto : '',
      resultandos: resultandos.length ? resultandos : [''],
      considerandos: considerandos.length ? considerandos : [''],
      atento: typeof value.atento === 'string' ? value.atento : '',
      resuelve: articles.length ? articles : [{ number: '1', text: '' }],
      notes: stringList(value.notes).join('\n') || initialLegacyDraft.notes,
    } }
  } catch {
    return looksLikeDocumentDraft(content) ? { kind: 'text', content } : { kind: 'empty' }
  }
}
