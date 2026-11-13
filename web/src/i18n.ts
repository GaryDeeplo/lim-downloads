/* Traduction de l'interface : le texte français sert de clé, l'anglais vient des dictionnaires de i18n/.
   La langue est choisie par le serveur (langue de Windows ou réglage `language` de config.json)
   et posée sur <html lang>, pour que l'interface et les textes du serveur parlent la même langue. */
import core from './i18n/en-core'
import guide from './i18n/en-guide'
import panels from './i18n/en-panels'

export const LANG: 'fr' | 'en' = document.documentElement.lang === 'en' ? 'en' : 'fr'
export const LOCALE = LANG === 'en' ? 'en-GB' : 'fr-BE'

const EN: Record<string, string> = { ...core, ...guide, ...panels }

/** Traduit un texte français ; `{nom}` est remplacé par vars.nom. */
export function tr(fr: string, vars?: Record<string, string | number>): string {
  let s = LANG === 'en' ? (EN[fr] ?? fr) : fr
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m))
  return s
}
