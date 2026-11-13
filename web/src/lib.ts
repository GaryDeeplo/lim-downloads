import {
  Archive, Clapperboard, File, FileArchive, FileCode, FileImage, FileMusic, FileSpreadsheet, FileText,
  FileVideo, Folder, HardDrive, Image, Music, Package, Presentation, Trash2, Cloud, CloudUpload, type LucideIcon,
} from 'lucide-react'
import type { Bucket, Source } from './api'
import { LANG, LOCALE, tr } from './i18n'

export function fmtBytes(b: number): string {
  const en = LANG === 'en'
  if (b < 1024) return `${Math.round(b)} ${en ? 'B' : 'o'}`
  const units = en ? ['KB', 'MB', 'GB', 'TB'] : ['Ko', 'Mo', 'Go', 'To']
  let i = -1
  do { b /= 1024; i++ } while (b >= 1024 && i < units.length - 1)
  const num = b.toFixed(b < 10 ? 1 : 0)
  return `${en ? num : num.replace('.', ',')} ${units[i]}`
}

export const fmtCount = (n: number) => Math.round(n).toLocaleString(LOCALE)

export const fmtDate = (t: number) =>
  new Date(t * 1000).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' })

export const fmtDateTime = (t: number) =>
  new Date(t * 1000).toLocaleString(LOCALE, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

/** « 3 éléments » : les mots sont donnés en français et traduits ; en anglais, 0 prend le pluriel. */
export const plural = (n: number, one: string, many = `${one}s`) =>
  `${fmtCount(n)} ${tr((LANG === 'en' ? n !== 1 : n > 1) ? many : one)}`

/** Heure courte (« 14:05 ») dans la langue de l'interface. */
export const fmtTime = (t: number) => new Date(t * 1000).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' })

/* Dossiers cibles du dock */
export const TARGET_STYLE: Record<string, { color: string; icon: LucideIcon }> = {
  videos: { color: 'var(--c-videos)', icon: Clapperboard },
  images: { color: 'var(--c-images)', icon: Image },
  documents: { color: 'var(--c-documents)', icon: FileText },
  audio: { color: 'var(--c-audio)', icon: Music },
  archives: { color: 'var(--c-archives)', icon: Archive },
  folders: { color: 'var(--c-folders)', icon: Folder },
  onedrive: { color: 'var(--c-onedrive)', icon: Cloud },
  gdrive: { color: 'var(--c-gdrive)', icon: CloudUpload },
  external: { color: 'var(--c-external)', icon: HardDrive },
  quarantine: { color: 'var(--c-quarantine)', icon: Trash2 },
}

export const bucketColor = (b: Pick<Bucket, 'target'>) => (b.target ? TARGET_STYLE[b.target].color : 'var(--c-neutral)')

/* Familles de fichiers pour les icônes de repli */
type Family = { color: string; icon: LucideIcon; cover: boolean }

const FAMILIES: [Set<string>, Family][] = [
  [new Set(['.mkv', '.mp4', '.mov', '.avi', '.wmv', '.webm', '.m4v', '.flv']), { color: 'var(--c-videos)', icon: FileVideo, cover: true }],
  [new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.bmp', '.tif', '.tiff', '.svg', '.nef', '.cr2', '.arw', '.dng', '.raw', '.avif']), { color: 'var(--c-images)', icon: FileImage, cover: true }],
  [new Set(['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.aiff', '.mid']), { color: 'var(--c-audio)', icon: FileMusic, cover: false }],
  [new Set(['.pdf']), { color: 'var(--c-pdf)', icon: FileText, cover: false }],
  [new Set(['.xls', '.xlsx', '.xlsm', '.csv', '.ods', '.numbers']), { color: 'var(--c-sheet)', icon: FileSpreadsheet, cover: false }],
  [new Set(['.ppt', '.pptx', '.odp', '.key']), { color: 'var(--c-slides)', icon: Presentation, cover: false }],
  [new Set(['.doc', '.docx', '.odt', '.rtf', '.txt', '.md', '.pages', '.epub', '.eml']), { color: 'var(--c-documents)', icon: FileText, cover: false }],
  [new Set(['.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2', '.xz']), { color: 'var(--c-archives)', icon: FileArchive, cover: false }],
  [new Set(['.exe', '.msi', '.msix', '.appx', '.dmg', '.pkg', '.deb', '.rpm', '.iso']), { color: 'var(--c-exe)', icon: Package, cover: false }],
  [new Set(['.html', '.htm', '.json', '.js', '.mjs', '.cjs', '.ts', '.py', '.css', '.xml', '.toml', '.yml', '.yaml', '.env']), { color: 'var(--c-code)', icon: FileCode, cover: false }],
]

export function family(ext: string, isDir: boolean): Family {
  if (isDir) return { color: 'var(--c-folders)', icon: Folder, cover: false }
  for (const [exts, f] of FAMILIES) if (exts.has(ext)) return f
  return { color: 'var(--c-neutral)', icon: File, cover: false }
}

/* Provenance affichée sur les cartes */
export function sourceBadge(s: Source | null): { text: string; title: string; tone: 'ok' | 'warn' | 'plain' } | null {
  if (!s) return null
  if (s.redownloadable) return { text: `↻ ${s.label}`, title: tr('Retéléchargeable depuis {label}', { label: s.label }), tone: 'ok' }
  if (s.expirable) return { text: `⌛ ${s.label}`, title: tr('Lien de transfert qui expire : pas de deuxième chance'), tone: 'warn' }
  return { text: s.label, title: tr('Téléchargé depuis {label}', { label: s.label }), tone: 'plain' }
}
