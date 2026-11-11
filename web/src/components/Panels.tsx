import { AnimatePresence, motion } from 'motion/react'
import { ExternalLink, Eye, FileSpreadsheet, FolderSearch, Trash2, Undo2, X } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { api, type Contents, type Entry, type History } from '../api'
import { family, fmtBytes, fmtCount, fmtDate, fmtDateTime, plural, TARGET_STYLE } from '../lib'
import { Thumb } from './Thumb'
import { HoldButton } from './ui'
import { useDialog } from './useDialog'

export type ToastData = { id: number; text: string; detail?: string; color: string; undoBatch?: number; error?: boolean }

export function Toast({ toast, onUndo, onClose }: { toast: ToastData | null; onUndo: (batch: number) => void; onClose: () => void }) {
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(onClose, toast.undoBatch ? 9000 : 5000)
    return () => clearTimeout(t)
  }, [toast, onClose])

  return (
    <div className="pointer-events-none fixed right-6 top-[88px] z-50">
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ type: 'spring', stiffness: 420, damping: 30 }}
            className="glass pointer-events-auto relative flex w-[340px] items-start gap-3 overflow-hidden rounded-2xl p-4"
            style={{ '--c': toast.color } as CSSProperties}
          >
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: toast.error ? 'var(--c-pdf)' : 'var(--c)' }} />
            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-semibold leading-snug">{toast.text}</div>
              {toast.detail && <div className="mt-0.5 font-mono text-[11px] text-muted">{toast.detail}</div>}
            </div>
            {toast.undoBatch !== undefined && (
              <button
                type="button"
                onClick={() => onUndo(toast.undoBatch!)}
                className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-[12.5px] font-medium hover:bg-surface-strong"
              >
                <Undo2 size={13} /> Annuler
              </button>
            )}
            <motion.span
              className="absolute bottom-0 left-0 h-[2px]"
              style={{ background: 'var(--c)' }}
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{ duration: toast.undoBatch ? 9 : 5, ease: 'linear' }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function HistoryPanel({ open, history, onClose, onUndo, onPurge, onPurgeBatch, onShowQuarantine, onReceipts }: {
  open: boolean
  history: History | null
  onClose: () => void
  onUndo: (batch: number) => void
  onPurge: () => void
  onPurgeBatch: (batch: number) => void
  onShowQuarantine: () => void
  onReceipts: () => void
}) {
  const q = history?.quarantine
  const ref = useRef<HTMLElement>(null)
  useDialog(open, ref)
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-40 bg-black/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-label="Historique et quarantaine"
            initial={{ x: 420 }}
            animate={{ x: 0 }}
            exit={{ x: 420 }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="scroll-area fixed bottom-3 right-3 top-3 z-50 flex w-[min(380px,calc(100vw-24px))] flex-col overflow-y-auto rounded-[24px] border border-line bg-surface-strong p-5 shadow-2xl"
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-[22px] font-semibold tracking-tight">Historique</h2>
              <button type="button" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-full hover:bg-surface-strong" aria-label="Fermer"><X size={16} /></button>
            </div>

            <div className="tint mb-6 rounded-2xl p-4" style={{ '--c': TARGET_STYLE.quarantine.color } as CSSProperties}>
              <div className="text-c font-mono text-[11px] uppercase tracking-[0.16em]">Quarantaine</div>
              {q && q.count ? (
                <>
                  <div className="mt-1 text-[26px] font-semibold tracking-tight">{fmtBytes(q.bytes)}</div>
                  <div className="font-mono text-[11px] text-muted">
                    {plural(q.count, 'élément')} · plus ancien {q.oldest ? fmtDate(q.oldest) : '—'}
                  </div>
                  <button type="button" onClick={onShowQuarantine} className="mt-3 flex items-center gap-1.5 rounded-full border border-line bg-surface-strong px-3.5 py-1.5 text-[12.5px] font-medium hover:bg-paper">
                    <Eye size={13} /> Voir le contenu
                  </button>
                  <HoldButton color={TARGET_STYLE.quarantine.color} onConfirm={onPurge} duration={1.2} className="mt-3 !px-4 !py-2 !text-[12.5px]">
                    Maintenir : supprimer définitivement ce qui a plus de {history!.quarantine_days} j
                  </HoldButton>
                </>
              ) : (
                <div className="mt-1 text-[14px] text-muted">Vide.</div>
              )}
              {history?.receipts && (
                <button type="button" onClick={onReceipts} className="mt-3 flex items-start gap-1.5 text-left text-[12.5px] font-medium underline decoration-line underline-offset-2 hover:decoration-ink">
                  <FileSpreadsheet size={13} className="mt-0.5 shrink-0" /> Reçus : noms, tailles et liens de tout ce qui est passé en quarantaine
                </button>
              )}
            </div>

            {!history?.batches.length && <div className="text-muted">Aucune action pour l'instant.</div>}
            <ol className="relative space-y-1 border-l border-line pl-4">
              {history?.batches.map((b) => (
                <li key={b.id} className="relative py-2">
                  <span className={`absolute -left-[21px] top-3.5 h-2 w-2 rounded-full ${b.state === 'done' ? 'bg-ink' : 'bg-faint'}`} />
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className={`text-[13.5px] font-medium leading-snug ${b.state !== 'done' ? 'text-muted line-through' : ''}`}>{b.label}</div>
                      <div className="mt-0.5 font-mono text-[11px] text-muted">
                        {fmtDateTime(b.created)} · {plural(b.count, 'élément')} · {fmtBytes(b.bytes)}
                        {b.errors ? ` · ${b.errors} err.` : ''}
                        {b.state === 'undone' ? ' · annulé' : b.state === 'purged' ? ' · purgé' : ''}
                      </div>
                    </div>
                    {b.state === 'done' && (
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <button type="button" onClick={() => onUndo(b.id)} className="flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-[12px] hover:bg-paper">
                          <Undo2 size={12} /> Annuler
                        </button>
                        {b.action === 'quarantine' && (
                          <HoldButton color={TARGET_STYLE.quarantine.color} onConfirm={() => onPurgeBatch(b.id)} duration={1.2}
                            className="!px-2.5 !py-1 !text-[11.5px] !font-medium">
                            <Trash2 size={12} /> Maintenir : supprimer
                          </HoldButton>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

function ContentsView({ entry }: { entry: Entry }) {
  const [data, setData] = useState<Contents | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    api.contents(entry.id).then((d) => alive && setData(d)).catch((e) => alive && setError(String(e.message ?? e)))
    return () => { alive = false }
  }, [entry.id])

  if (error) return <div className="p-6 text-[13px] text-muted">{error}</div>
  if (!data) return <div className="sweep relative h-full overflow-hidden" />
  const max = Math.max(1, ...data.families.map((f) => f.bytes))
  return (
    <div className="scroll-area flex h-full flex-col gap-5 overflow-y-auto p-6">
      <div>
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">Contenu</div>
        <div className="mt-1 text-[24px] font-semibold tracking-tight">
          {plural(data.files, 'fichier')} · {fmtBytes(data.bytes)}{data.truncated ? '+' : ''}
        </div>
      </div>
      <div className="space-y-2">
        {data.families.map((f, i) => (
          <div key={f.key} className="grid grid-cols-[88px_1fr_auto] items-center gap-3 text-[12.5px]" style={{ '--c': (TARGET_STYLE[f.key] ?? { color: 'var(--c-neutral)' }).color } as CSSProperties}>
            <span>{f.label}</span>
            <span className="h-2 overflow-hidden rounded-full bg-line">
              <motion.span className="block h-full rounded-full" style={{ background: 'var(--c)' }}
                initial={{ width: 0 }} animate={{ width: `${Math.max(2, (f.bytes / max) * 100)}%` }} transition={{ delay: i * 0.05, type: 'spring', stiffness: 140, damping: 22 }} />
            </span>
            <span className="w-28 text-right font-mono text-[11px] text-muted">{fmtCount(f.count)} · {fmtBytes(f.bytes)}</span>
          </div>
        ))}
      </div>
      <div>
        <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">Plus gros fichiers</div>
        <ul className="divide-y divide-line text-[12.5px]">
          {data.top.map((f) => (
            <li key={f.name} className="flex gap-3 py-1.5">
              <span className="min-w-0 flex-1 truncate" title={f.name}>{f.name}</span>
              <span className="font-mono text-[11px] text-muted">{fmtBytes(f.size)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export function QuickLook({ entry, bucket, onClose, onOpen, onReveal }: { entry: Entry | null; bucket?: string; onClose: () => void; onOpen: (id: number) => void; onReveal: (id: number) => void }) {
  const e = entry
  const ref = useRef<HTMLDivElement>(null)
  useDialog(!!entry, ref)
  const hasContents = !!e && (e.is_dir || e.ext === '.zip')
  const src = e?.source
  return (
    <AnimatePresence>
      {e && (
        <motion.div
          className="fixed inset-0 z-[70] grid place-items-center bg-black/35 p-10 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.94, y: 10 }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            onClick={(ev) => ev.stopPropagation()}
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-label={`Aperçu de ${e.name}`}
            className="flex max-h-full w-full max-w-[1020px] overflow-hidden rounded-[28px] border border-line bg-surface-strong shadow-2xl"
            style={{ '--c': family(e.ext, e.is_dir).color } as CSSProperties}
          >
            <div className="relative aspect-[4/3] min-w-0 flex-[1.5] bg-paper">
              {hasContents ? <ContentsView key={e.id} entry={e} /> : <Thumb key={e.id} entry={e} px={512} scale={2} />}
            </div>
            <div className="flex w-[330px] shrink-0 flex-col gap-4 p-6">
              <div className="flex items-start gap-2">
                <h3 className="min-w-0 flex-1 break-all text-[19px] font-semibold leading-tight tracking-tight">{e.name}</h3>
                <button type="button" onClick={onClose} className="grid h-8 w-8 shrink-0 place-items-center rounded-full hover:bg-paper" aria-label="Fermer"><X size={16} /></button>
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
                {bucket && <><dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Lot</dt><dd>{bucket}</dd></>}
                <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Taille</dt><dd>{fmtBytes(e.size)}</dd>
                <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Arrivé</dt><dd>{fmtDate(e.mtime)}</dd>
                <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Type</dt>
                <dd>{e.is_dir ? `dossier · ${plural(e.files, 'fichier')}` : e.parts > 1 ? `export en ${e.parts} zips` : e.ext || '—'}</dd>
                {src && (
                  <>
                    <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Source</dt>
                    <dd>
                      {src.label}
                      {src.redownloadable && <span className="ml-1.5 text-[var(--c-gdrive)]">· retéléchargeable</span>}
                      {src.expirable && <span className="ml-1.5 text-[var(--c-documents)]">· lien expiré</span>}
                    </dd>
                  </>
                )}
                {src?.url && (
                  <>
                    <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Lien</dt>
                    <dd className="min-w-0">
                      <a href={src.page ?? src.url} target="_blank" rel="noreferrer" className="block truncate font-mono text-[11.5px] underline decoration-line underline-offset-2 hover:decoration-ink" title={src.url}>
                        {src.page ?? src.url}
                      </a>
                    </dd>
                  </>
                )}
                {e.reason && <><dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Note</dt><dd>{e.reason}</dd></>}
                {e.dest && <><dt className="font-mono text-[11px] uppercase tracking-wider text-muted">Vers</dt><dd className="break-all font-mono text-[11.5px]">{e.dest}</dd></>}
              </dl>
              <div className="mt-auto flex gap-2">
                <button type="button" onClick={() => onOpen(e.id)} className="flex flex-1 items-center justify-center gap-2 rounded-full bg-ink px-4 py-2.5 text-[13px] font-semibold text-bg">
                  <ExternalLink size={14} /> Ouvrir
                </button>
                <button type="button" onClick={() => onReveal(e.id)} className="flex flex-1 items-center justify-center gap-2 rounded-full border border-line px-4 py-2.5 text-[13px] font-medium hover:bg-paper">
                  <FolderSearch size={14} /> Explorateur
                </button>
              </div>
              <div className="font-mono text-[11px] text-muted">Espace ou Échap pour fermer</div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
