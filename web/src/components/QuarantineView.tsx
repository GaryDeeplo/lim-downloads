import { AnimatePresence, motion } from 'motion/react'
import { FolderOpen, LoaderCircle, ShieldCheck, Trash2, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { api, quarantineThumbUrl, type Quarantine, type QuarantineBatch, type QuarantineItem } from '../api'
import { fmtBytes, fmtDate, fmtDateTime, plural, TARGET_STYLE } from '../lib'
import { Thumb } from './Thumb'
import { HoldButton } from './ui'

const COLOR = TARGET_STYLE.quarantine.color
const PER_BATCH = 48

const daysLeft = (expires: number) => Math.max(0, Math.ceil((expires * 1000 - Date.now()) / 86400000))

function ItemCard({ item, index, onRestore }: { item: QuarantineItem; index: number; onRestore: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const origin = item.origin.split(/[\\/]/).pop() || item.origin
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5, y: -30, transition: { duration: 0.22 } }}
      transition={{ type: 'spring', stiffness: 420, damping: 32, delay: index < 24 ? index * 0.015 : 0 }}
      className="group relative rounded-[18px] border border-line bg-surface p-1.5"
      style={{ boxShadow: 'var(--card-shadow)' }}
    >
      <div className="relative aspect-[4/3] overflow-hidden rounded-[13px]">
        <Thumb entry={item} url={item.exists ? quarantineThumbUrl(item.op) : undefined} />
        <button
          type="button"
          disabled={busy || !item.exists}
          title={`Remettre dans ${item.origin}`}
          onClick={async () => { setBusy(true); try { await onRestore() } finally { setBusy(false) } }}
          className="absolute inset-x-2 bottom-2 flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full bg-black/60 px-3 py-1.5 text-[12px] font-medium text-white opacity-0 backdrop-blur transition-opacity focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-wait"
        >
          {busy ? <LoaderCircle size={13} className="animate-spin" /> : <Undo2 size={13} />} Remettre
        </button>
      </div>
      <div className="px-1.5 pb-1 pt-2">
        <div className="line-clamp-2 break-all text-[13px] font-medium leading-[1.2]" title={item.name}>{item.name}</div>
        <div className="mt-1 truncate font-mono text-[11px] text-muted" title={item.origin}>
          {fmtBytes(item.size)} · {item.exists ? `venait de ${origin}` : 'introuvable sur le disque'}
        </div>
      </div>
    </motion.div>
  )
}

function BatchSection({ batch, days, onRestoreItem, onRestoreBatch, onPurgeBatch }: {
  batch: QuarantineBatch
  days: number
  onRestoreItem: (item: QuarantineItem) => Promise<void>
  onRestoreBatch: () => void
  onPurgeBatch: () => void
}) {
  const [limit, setLimit] = useState(PER_BATCH)
  const left = daysLeft(batch.expires)
  return (
    <motion.section layout="position" exit={{ opacity: 0, height: 0 }} className="mb-10">
      <div className="mb-3 flex flex-wrap items-end gap-x-6 gap-y-2 border-b border-line pb-3">
        <div className="min-w-0">
          <div className="text-[19px] font-semibold tracking-tight">{batch.label}</div>
          <div className="mt-0.5 font-mono text-[11px] text-muted">
            {fmtDateTime(batch.created)} · {plural(batch.count, 'élément')} · {fmtBytes(batch.bytes)} ·{' '}
            <span className={left <= 3 ? 'text-c' : ''} title={`Supprimé définitivement le ${fmtDate(batch.expires)} (${days} jours après la mise en quarantaine)`}>
              {left ? `supprimé dans ${plural(left, 'jour')}` : 'supprimé à la prochaine purge'}
            </span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={onRestoreBatch} className="flex items-center gap-1.5 rounded-full border border-line px-3.5 py-2 text-[12.5px] font-medium hover:bg-surface-strong">
            <Undo2 size={13} /> Tout remettre
          </button>
          <HoldButton color={COLOR} onConfirm={onPurgeBatch} duration={1.2} className="!px-3.5 !py-2 !text-[12.5px] !font-medium">
            <Trash2 size={13} /> Maintenir : supprimer le lot
          </HoldButton>
        </div>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
        <AnimatePresence mode="popLayout">
          {batch.items.slice(0, limit).map((it, i) => (
            <ItemCard key={it.op} item={it} index={i} onRestore={() => onRestoreItem(it)} />
          ))}
        </AnimatePresence>
      </div>
      {limit < batch.items.length && (
        <button type="button" onClick={() => setLimit((l) => l + PER_BATCH * 2)} className="mt-3 rounded-full border border-line px-4 py-2 text-[12.5px] text-muted hover:text-ink">
          Afficher {plural(Math.min(PER_BATCH * 2, batch.items.length - limit), 'autre élément', 'autres éléments')} sur {batch.items.length - limit}
        </button>
      )}
    </motion.section>
  )
}

/** La quarantaine, dans l'appli : ce qui va partir, lot par lot, avec restauration fichier par fichier. */
export function QuarantineView({ refresh, onRestoreItem, onRestoreBatch, onPurgeBatch, onEmpty, onExplorer }: {
  refresh: unknown
  onRestoreItem: (op: number, name: string) => Promise<boolean>
  onRestoreBatch: (batch: number) => void
  onPurgeBatch: (batch: number) => void
  onEmpty: () => void
  onExplorer: () => void
}) {
  const [data, setData] = useState<Quarantine | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api.quarantine().then((q) => { setData(q); setError(null) }).catch((e) => setError(String(e.message ?? e)))
  }, [])
  useEffect(load, [load, refresh])

  const restoreItem = useCallback(async (batchId: number, item: QuarantineItem) => {
    if (!(await onRestoreItem(item.op, item.name))) return
    setData((q) => q && {
      ...q,
      batches: q.batches
        .map((b) => b.id !== batchId ? b : { ...b, count: b.count - 1, bytes: b.bytes - item.size, items: b.items.filter((x) => x.op !== item.op) })
        .filter((b) => b.items.length),
    })
  }, [onRestoreItem])

  const count = data?.batches.reduce((a, b) => a + b.count, 0) ?? 0
  const bytes = data?.batches.reduce((a, b) => a + b.bytes, 0) ?? 0

  return (
    <section className="flex min-h-0 flex-1 flex-col" style={{ '--c': COLOR } as CSSProperties}>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4 px-8 pb-6 pt-7">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }} className="min-w-0 max-w-2xl">
          <h1 className="text-[42px] font-[640] leading-[0.95] tracking-[-0.035em]">Quarantaine</h1>
          <p className="mt-2.5 text-[14px] text-muted">
            Ce que tu as mis de côté. Chaque lot est gardé {data ? plural(data.days, 'jour') : '30 jours'}, puis supprimé pour de bon.
            D'ici là, tu peux remettre un fichier ou un lot entier dans Téléchargements.
          </p>
          <div className="mt-3 font-mono text-[12px] text-muted">
            {data ? <>{plural(count, 'élément')} · {fmtBytes(bytes)} · {plural(data.batches.length, 'lot')}</> : 'chargement…'}
          </div>
        </motion.div>
        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          {count > 0 && (
            <HoldButton color={COLOR} onConfirm={onEmpty} duration={2}>
              <Trash2 size={15} /> Maintenir : vider la quarantaine · <span className="font-mono text-[12px] opacity-80">{fmtBytes(bytes)}</span>
            </HoldButton>
          )}
          <button type="button" onClick={onExplorer} title={data?.dir} className="flex items-center gap-1.5 rounded-full border border-line px-3.5 py-2 text-[12.5px] text-muted hover:text-ink">
            <FolderOpen size={14} /> Ouvrir dans l'Explorateur
          </button>
        </div>
      </div>

      <div className="scroll-area relative min-h-0 flex-1 overflow-y-auto px-8 pb-44">
        {error && <div className="text-[13px] text-muted">{error}</div>}
        {!data && !error && <div className="sweep relative h-40 overflow-hidden rounded-2xl" />}
        {data && !data.batches.length && (
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="grid h-[60%] place-items-center">
            <div className="text-center">
              <div className="tint text-c mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl"><ShieldCheck size={28} /></div>
              <div className="text-[22px] font-semibold tracking-tight">Quarantaine vide</div>
              <div className="mt-1 text-muted">Ce que tu mets en quarantaine apparaîtra ici.</div>
            </div>
          </motion.div>
        )}
        <AnimatePresence>
          {data?.batches.map((b) => (
            <BatchSection
              key={b.id}
              batch={b}
              days={data.days}
              onRestoreItem={(it) => restoreItem(b.id, it)}
              onRestoreBatch={() => onRestoreBatch(b.id)}
              onPurgeBatch={() => onPurgeBatch(b.id)}
            />
          ))}
        </AnimatePresence>
      </div>
    </section>
  )
}
