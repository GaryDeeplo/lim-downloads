export type Source = {
  kind: 'drive' | 'torrent' | 'public' | 'transfer' | 'mail' | 'generated' | 'site'
  label: string
  url: string | null
  page: string | null
  expirable: boolean
  redownloadable: boolean
}

export type Entry = {
  id: number
  name: string
  is_dir: boolean
  size: number
  mtime: number
  ext: string
  reason: string
  dest: string | null
  checked: boolean
  files: number
  parts: number
  source: Source | null
  keeper: number | null
}

export type Bucket = {
  key: string
  title: string
  description: string
  target: string | null
  action: 'quarantine' | 'move' | null
  entries: Entry[]
}

export type Target = {
  key: string
  label: string
  path: string
  available: boolean
  remote: boolean
  free?: number | null
  hint?: string
}

export type Plan = {
  status: 'idle' | 'scanning' | 'ready' | 'error'
  phase: string
  error: string | null
  root: string
  targets: Target[]
  buckets?: Bucket[]
  duration: number
  scanned_at: number | null
  receipts: string | null
}

export type ApplyResult = {
  batch_id: number
  target: string
  done: number
  errors: number
  bytes: number
  moved: number[]
  failed: { id: number; error: string }[]
}

export type JobStart = { job: number; target: string; total: number; ids: number[] }

export type Job = {
  status: 'running' | 'done' | 'error'
  total: number
  done: number
  target: string
  ids: number[]
  result: ApplyResult | null
  error: string | null
}

export type Contents = {
  files: number
  bytes: number
  truncated: boolean
  families: { key: string; label: string; count: number; bytes: number }[]
  top: { name: string; size: number }[]
}

export type AutoBatch = { batch_id: number; label: string; target: string; done: number; bytes: number; names: string[] }

export type AutoPending = { name: string; size: number; is_dir: boolean; ext: string; arrived: number; due: number; bucket: string; target: string | null; skip: string | null }
export type AutoPreview = { computed: number; total: number; items: AutoPending[] }

export type AutoStatus = {
  configured: boolean
  enabled: boolean
  since: number
  delay_hours: number
  actions: string[]
  interval_minutes: number
  last_run: number | null
  last_error: string | null
  events: { id: number; time: number; batches: AutoBatch[] }[]
  preview: AutoPreview | null
  computing: boolean
  recent: Batch[]
}

export type UndoResult = { restored: number; errors: number; ids: number[]; target: string | null; rescan: boolean }

export type Batch = {
  id: number
  created: number
  label: string
  action: string
  state: 'done' | 'undone' | 'purged'
  count: number
  bytes: number
  errors: number | null
}

export type History = {
  batches: Batch[]
  quarantine: { count: number; bytes: number; oldest: number | null }
  quarantine_days: number
  quarantine_dir: string
  receipts: string | null
}

export type QuarantineItem = { op: number; name: string; size: number; is_dir: boolean; ext: string; origin: string; exists: boolean }
export type QuarantineBatch = { id: number; label: string; created: number; expires: number; count: number; bytes: number; items: QuarantineItem[] }
export type Quarantine = { days: number; dir: string; batches: QuarantineBatch[] }

async function req<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const r = await fetch(path, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: { 'Content-Type': 'application/json', 'X-Downloads-Manager': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    const detail = await r.json().then((d) => d.detail).catch(() => r.statusText)
    throw new Error(typeof detail === 'string' ? detail : r.statusText)
  }
  return r.json()
}

export const api = {
  plan: () => req<Plan>('/api/plan'),
  scan: () => req<{ status: string }>('/api/scan', undefined, 'POST'),
  apply: (ids: number[], target?: string) => req<ApplyResult | JobStart>('/api/apply', { ids, target: target ?? null }),
  job: (id: number) => req<Job>(`/api/jobs/${id}`),
  contents: (id: number) => req<Contents>(`/api/contents/${id}`),
  undo: (batchId: number) => req<UndoResult>(`/api/undo/${batchId}`, undefined, 'POST'),
  history: () => req<History>('/api/history'),
  purge: (all = false) => req<{ batches: number; bytes: number }>(`/api/purge${all ? '?all=true' : ''}`, undefined, 'POST'),
  purgeBatch: (id: number) => req<{ batches: number; bytes: number }>(`/api/purge/${id}`, undefined, 'POST'),
  open: (id: number) => req(`/api/open/${id}`, undefined, 'POST'),
  reveal: (id: number) => req(`/api/reveal/${id}`, undefined, 'POST'),
  openTarget: (key: string) => req(`/api/open-target/${key}`, undefined, 'POST'),
  openReceipts: () => req('/api/open-receipts', undefined, 'POST'),
  quarantine: () => req<Quarantine>('/api/quarantine'),
  restoreItem: (op: number) => req<{ name: string; ids: number[]; rescan: boolean }>(`/api/quarantine/${op}/restore`, undefined, 'POST'),
  setLanguage: (language: 'auto' | 'fr' | 'en') => req<{ lang: string; setting: string }>('/api/language', { language }),
  auto: () => req<AutoStatus>('/api/auto'),
  updateAuto: (patch: { enabled?: boolean; delay_hours?: number; actions?: string[] }) => req<AutoStatus>('/api/auto', patch),
  previewAuto: () => req<AutoStatus>('/api/auto/preview', undefined, 'POST'),
  runAuto: () => req<{ batches: AutoBatch[] }>('/api/auto/run', undefined, 'POST'),
}

export const quarantineThumbUrl = (op: number, px = 256) => `/api/quarantine/${op}/thumb?s=${px}`
export const thumbUrl = (id: number, px = 256) => `/api/thumb/${id}?s=${px}`
