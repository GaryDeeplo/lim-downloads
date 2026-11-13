import { AnimatePresence, motion } from 'motion/react'
import { Check, CheckCheck, CircleSlash, Eye, FolderSearch, LoaderCircle, Sparkles } from 'lucide-react'
import { memo, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type DragEvent } from 'react'
import type { Bucket, Entry, Target } from '../api'
import { tr } from '../i18n'
import { bucketColor, fmtBytes, fmtDate, plural, sourceBadge, TARGET_STYLE } from '../lib'
import { Thumb } from './Thumb'
import { HoldButton, Segmented } from './ui'

export type Zoom = 's' | 'm' | 'l'
export type Sort = 'size' | 'date' | 'name'
const ZOOM_PX: Record<Zoom, number> = { s: 128, m: 172, l: 236 }
const PAGE = 120

type CardProps = {
  entry: Entry
  index: number
  selected: boolean
  actionable: boolean
  hidden: boolean
  transferring: boolean
  zoom: Zoom
  onToggle: (id: number, shift: boolean) => void
  onOpen: (id: number) => void
  onPeek: (e: Entry) => void
  onKeeper: (id: number) => void
  onHover: (e: Entry | null) => void
  onDragStart: (ev: DragEvent, e: Entry) => void
  onDragEnd: () => void
}

const TONE = { ok: 'var(--c-gdrive)', warn: 'var(--c-documents)', plain: 'rgb(255 255 255 / .7)' }

const Card = memo(function Card({ entry, index, selected, actionable, hidden, transferring, zoom, onToggle, onOpen, onPeek, onKeeper, onHover, onDragStart, onDragEnd }: CardProps) {
  const dim = actionable && !selected
  const badge = sourceBadge(entry.source)
  return (
    <motion.div
      layout="position"
      data-entry={entry.id}
      initial={{ opacity: 0, y: 14, scale: 0.96 }}
      animate={{ opacity: hidden ? 0 : 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.4, transition: { duration: 0.12 } }}
      transition={{ type: 'spring', stiffness: 420, damping: 32, delay: index < 48 ? index * 0.012 : 0 }}
    >
      <div
        draggable={!transferring}
        onDragStart={(ev) => onDragStart(ev, entry)}
        onDragEnd={onDragEnd}
        onClick={(ev) => { if (!transferring) onToggle(entry.id, ev.shiftKey) }}
        onDoubleClick={() => onOpen(entry.id)}
        onMouseEnter={() => onHover(entry)}
        onMouseLeave={() => onHover(null)}
        tabIndex={0}
        role="button"
        aria-pressed={selected}
        aria-label={`${entry.name}, ${fmtBytes(entry.size)}${selected ? tr(', coché') : ''}`}
        onFocus={() => onHover(entry)}
        onBlur={() => onHover(null)}
        onKeyDown={(ev) => {
          if (ev.key === 'Enter' && !transferring) { ev.preventDefault(); onToggle(entry.id, ev.shiftKey) }
        }}
        className={`group relative cursor-pointer rounded-[18px] border p-1.5 transition-[opacity,transform,border-color,background] duration-200 hover:-translate-y-0.5 ${
          selected ? 'border-[var(--c)] bg-surface-strong' : 'border-line bg-surface hover:bg-surface-strong'
        } ${dim ? 'opacity-55 hover:opacity-90' : ''}`}
        style={{ boxShadow: selected ? '0 0 0 3px color-mix(in oklab, var(--c) 22%, transparent), var(--card-shadow)' : 'var(--card-shadow)' }}
      >
        <div className="relative aspect-[4/3] overflow-hidden rounded-[13px]">
          <Thumb entry={entry} px={zoom === 'l' ? 512 : 256} scale={zoom === 's' ? 0.8 : 1} dim={dim} />
          {(badge || entry.parts > 1) && zoom !== 's' && (
            <div className="absolute left-2 top-2 flex max-w-[78%] flex-col items-start gap-1">
              {badge && (
                <span title={badge.title} className="flex max-w-full items-center gap-1.5 rounded-full bg-black/60 px-2 py-0.5 font-mono text-[11px] text-white backdrop-blur">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: TONE[badge.tone] }} />
                  <span className="truncate">{badge.text}</span>
                </span>
              )}
              {entry.parts > 1 && (
                <span className="rounded-full bg-black/60 px-2 py-0.5 font-mono text-[11px] text-white backdrop-blur">{tr('{n} parties', { n: entry.parts })}</span>
              )}
            </div>
          )}
          {transferring && (
            <div className="absolute inset-0 grid place-items-center bg-black/55 text-white backdrop-blur-[2px]">
              <span className="flex items-center gap-2 font-mono text-[11px]"><LoaderCircle size={14} className="animate-spin" /> {tr('transfert…')}</span>
            </div>
          )}
          <span
            className={`absolute right-2 top-2 grid h-[22px] w-[22px] place-items-center rounded-full border-2 transition-all ${
              selected ? 'border-transparent bg-[var(--c)] text-white' : 'border-white/90 bg-black/15 text-transparent opacity-0 group-hover:opacity-100'
            }`}
          >
            <Check size={13} strokeWidth={3} />
          </span>
          <button
            type="button"
            title={tr('Aperçu (Espace)')}
            onClick={(ev) => { ev.stopPropagation(); onPeek(entry) }}
            className="absolute bottom-2 right-2 grid h-7 w-7 place-items-center rounded-full bg-black/45 text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100"
          >
            <Eye size={14} />
          </button>
        </div>
        <div className="px-1.5 pb-1 pt-2">
          <div className={`line-clamp-2 break-all leading-[1.2] font-medium ${zoom === 's' ? 'text-[11.5px]' : 'text-[13px]'}`} title={entry.name}>
            {entry.name}
          </div>
          <div className="mt-1 truncate font-mono text-[11px] text-muted">
            {fmtBytes(entry.size)} · {entry.is_dir ? plural(entry.files, 'fichier') : fmtDate(entry.mtime)}
          </div>
          {entry.keeper !== null ? (
            <button
              type="button"
              title={tr("Voir l'exemplaire gardé : {reason}", { reason: entry.reason })}
              onClick={(ev) => { ev.stopPropagation(); onKeeper(entry.keeper!) }}
              className="mt-0.5 block w-full truncate text-left text-[11px] text-muted underline decoration-line underline-offset-2 hover:text-ink hover:decoration-ink"
            >
              {entry.reason}
            </button>
          ) : entry.reason && zoom !== 's' && (
            <div className="mt-0.5 truncate text-[11px] text-muted" title={entry.reason}>{entry.reason}</div>
          )}
        </div>
      </div>
    </motion.div>
  )
})

export function BucketView({ bucket, targets, selected, hiddenIds, transferIds, zoom, sort, busy, onZoom, onSort, onToggle, onSelectAll, onSelectNone, onApply, onOpen, onPeek, onKeeper, onHover, onDragStart, onDragEnd }: {
  bucket: Bucket
  targets: Target[]
  selected: Set<number>
  hiddenIds: Set<number>
  transferIds: Set<number>
  zoom: Zoom
  sort: Sort
  busy: boolean
  onZoom: (z: Zoom) => void
  onSort: (s: Sort) => void
  onToggle: (id: number, shift: boolean, ordered: Entry[]) => void
  onSelectAll: () => void
  onSelectNone: () => void
  onApply: () => void
  onOpen: (id: number) => void
  onPeek: (e: Entry) => void
  onKeeper: (id: number) => void
  onHover: (e: Entry | null) => void
  onDragStart: (ev: DragEvent, e: Entry) => void
  onDragEnd: () => void
}) {
  const [limit, setLimit] = useState(PAGE)
  const sentinel = useRef<HTMLDivElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const color = bucketColor(bucket)
  const target = targets.find((t) => t.key === bucket.target)

  useEffect(() => { setLimit(PAGE); scroller.current?.scrollTo({ top: 0 }) }, [bucket.key])

  const ordered = useMemo(() => {
    const list = [...bucket.entries]
    if (sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name, 'fr'))
    else if (sort === 'date') list.sort((a, b) => b.mtime - a.mtime)
    else list.sort((a, b) => b.size - a.size)
    return list
  }, [bucket.entries, sort])

  useEffect(() => {
    const el = sentinel.current
    if (!el) return
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) setLimit((l) => l + PAGE) }, { root: scroller.current, rootMargin: '600px' })
    io.observe(el)
    return () => io.disconnect()
  }, [bucket.key, ordered.length])

  const total = bucket.entries.reduce((a, e) => a + e.size, 0)
  const selBytes = bucket.entries.reduce((a, e) => a + (selected.has(e.id) ? e.size : 0), 0)
  const verb = bucket.action === 'quarantine' ? tr('Mettre en quarantaine') : tr('Ranger')
  const TIcon = bucket.target ? TARGET_STYLE[bucket.target].icon : null
  const toggle = useCallback((id: number, shift: boolean) => onToggle(id, shift, ordered), [onToggle, ordered])

  return (
    <section className="flex min-h-0 flex-1 flex-col" style={{ '--c': color } as CSSProperties}>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4 px-8 pb-5 pt-7">
        <AnimatePresence mode="wait">
          <motion.div
            key={bucket.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
            className="min-w-0 max-w-2xl"
          >
            <h1 className="text-[42px] font-[640] leading-[0.95] tracking-[-0.035em]">{bucket.title}</h1>
            <p className="mt-2.5 text-[14px] text-muted">{bucket.description}</p>
            <div className="mt-3 flex flex-wrap items-center gap-x-1.5 font-mono text-[12px] text-muted">
              <span className="text-c inline-flex items-center gap-1.5 font-medium">
                {TIcon && <TIcon size={13} />}
                {target ? tr('vers {target}', { target: target.label }) : bucket.key === 'recent' ? tr('protégé') : tr('sans règle')}
              </span>
              · {plural(bucket.entries.length, 'élément')} · {fmtBytes(total)}
              {bucket.target && <> · <span className="text-ink">{tr('{n} sélectionnés', { n: selected.size })}</span></>}
            </div>
          </motion.div>
        </AnimatePresence>

        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          <Segmented id="sort" value={sort} onChange={onSort} options={[{ value: 'size', label: tr('taille') }, { value: 'date', label: tr('date') }, { value: 'name', label: tr('nom') }]} />
          <Segmented id="zoom" value={zoom} onChange={onZoom} options={[{ value: 's', label: 'S' }, { value: 'm', label: 'M' }, { value: 'l', label: 'L' }]} />
          <button type="button" onClick={onSelectAll} title={tr('Tout sélectionner (Ctrl+A)')} className="grid h-8 w-8 place-items-center rounded-full border border-line text-muted hover:text-ink"><CheckCheck size={15} /></button>
          <button type="button" onClick={onSelectNone} title={tr('Tout désélectionner')} className="grid h-8 w-8 place-items-center rounded-full border border-line text-muted hover:text-ink"><CircleSlash size={15} /></button>
          {bucket.target && (
            <span data-tour="apply" className="inline-flex">
              <HoldButton color={color} disabled={!selected.size || busy} onConfirm={onApply}>
                {TIcon && <TIcon size={16} />}
                {verb} · {selected.size} <span className="font-mono text-[12px] opacity-80">{fmtBytes(selBytes)}</span>
              </HoldButton>
            </span>
          )}
        </div>
      </div>
      {bucket.target && (
        <div className="-mt-2 px-8 pb-3 text-[12.5px] text-muted">
          {tr("Maintiens le bouton pour confirmer, ou glisse des cartes sur un dossier du dock. Entrée coche une carte, Espace ouvre l'aperçu.")}
        </div>
      )}

      <div ref={scroller} className="scroll-area relative min-h-0 flex-1 overflow-y-auto px-8 pb-44">
        {bucket.entries.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="grid h-[60%] place-items-center">
            <div className="text-center">
              <motion.div
                initial={{ rotate: -20, scale: 0 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ type: 'spring', stiffness: 300, damping: 14, delay: 0.1 }}
                className="tint text-c mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl"
              >
                <Sparkles size={28} />
              </motion.div>
              <div className="text-[22px] font-semibold tracking-tight">{tr('Lot terminé')}</div>
              <div className="mt-1 text-muted">{tr('Passe au lot suivant dans la colonne de gauche.')}</div>
            </div>
          </motion.div>
        ) : (
          <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${ZOOM_PX[zoom]}px, 1fr))` }}>
            <AnimatePresence mode="popLayout" initial>
              {ordered.slice(0, limit).map((e, i) => (
                <Card
                  key={e.id}
                  entry={e}
                  index={i}
                  selected={selected.has(e.id)}
                  actionable={!!bucket.target}
                  hidden={hiddenIds.has(e.id)}
                  transferring={transferIds.has(e.id)}
                  zoom={zoom}
                  onToggle={toggle}
                  onOpen={onOpen}
                  onPeek={onPeek}
                  onKeeper={onKeeper}
                  onHover={onHover}
                  onDragStart={onDragStart}
                  onDragEnd={onDragEnd}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
        {limit < ordered.length && (
          <div ref={sentinel} className="flex items-center justify-center gap-2 py-8 font-mono text-[11px] text-muted">
            <FolderSearch size={13} /> {tr('{n} autres…', { n: ordered.length - limit })}
          </div>
        )}
      </div>
    </section>
  )
}
