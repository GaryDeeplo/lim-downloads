import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, Clock, Download, LoaderCircle, Play, RefreshCw, Sparkles, Undo2, X, Zap } from 'lucide-react'
import { useRef, useState, type CSSProperties } from 'react'
import type { AutoPending, AutoStatus } from '../api'
import { family, fmtBytes, fmtDate, fmtDateTime, fmtTime, plural, TARGET_STYLE } from '../lib'
import { tr } from '../i18n'
import { Segmented } from './ui'
import { useDialog } from './useDialog'

const DELAYS = [
  { value: '24', label: tr('{n} j', { n: 1 }) },
  { value: '72', label: tr('{n} j', { n: 3 }) },
  { value: '168', label: tr('{n} j', { n: 7 }) },
  { value: '336', label: tr('{n} j', { n: 14 }) },
  { value: '720', label: tr('{n} j', { n: 30 }) },
]

const ACTIONS: { key: string; title: string; detail: string; target: string }[] = [
  { key: 'sort', title: tr('Ranger'), detail: tr('Vidéos, images, documents et audio vers tes dossiers'), target: 'images' },
  { key: 'duplicates', title: tr('Doublons exacts'), detail: tr('Les copies partent en quarantaine, l\'original reste'), target: 'quarantine' },
  { key: 'installers', title: tr('Installeurs'), detail: tr('Les .exe et .msi déjà utilisés partent en quarantaine'), target: 'quarantine' },
  { key: 'backed_up', title: tr('Déjà sauvegardé'), detail: tr('Ce qui existe déjà dans tes sauvegardes part en quarantaine'), target: 'quarantine' },
]

const fmtDelay = (h: number) => (h >= 24 ? plural(Math.round(h / 24), 'jour') : plural(Math.round(h), 'heure'))

function when(due: number) {
  const s = due - Date.now() / 1000
  if (s <= 0) return tr('à la prochaine passe')
  const d = Math.floor(s / 86400)
  return tr('dans {delay}', { delay: d >= 1 ? plural(d, 'jour') : plural(Math.max(1, Math.round(s / 3600)), 'heure') })
}

function Switch({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={onChange}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${on ? 'bg-[var(--c-images)]' : 'bg-line'}`}>
      <motion.span className="absolute top-1 h-5 w-5 rounded-full bg-white shadow" animate={{ left: on ? 24 : 4 }}
        transition={{ type: 'spring', stiffness: 500, damping: 32 }} />
    </button>
  )
}

function PendingRow({ p }: { p: AutoPending }) {
  const t = p.target ? TARGET_STYLE[p.target] : null
  const f = family(p.ext, p.is_dir)
  const Icon = f.icon
  return (
    <li className="flex items-center gap-2.5 py-1.5" style={{ '--c': t?.color ?? 'var(--c-neutral)' } as CSSProperties}>
      <Icon size={14} className="shrink-0" style={{ color: f.color }} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12.5px]" title={p.name}>{p.name}</div>
        <div className="truncate font-mono text-[11px] text-muted" title={p.skip ?? undefined}>
          {fmtBytes(p.size)} · {tr('arrivé le {date}', { date: fmtDate(p.arrived) })}{p.skip ? ` · ${p.skip}` : ''}
        </div>
      </div>
      {t ? (
        <span className="tint text-c shrink-0 rounded-full px-2 py-0.5 text-right font-mono text-[11px]" title={tr('Le {date}', { date: fmtDateTime(p.due) })}>
          → {p.target === 'quarantine' ? tr('quarantaine') : p.bucket.toLowerCase()} · {when(p.due)}
        </span>
      ) : (
        <span className="shrink-0 rounded-full border border-line px-2 py-0.5 font-mono text-[11px] text-muted">{tr('pour toi')}</span>
      )}
    </li>
  )
}

/** Le tri auto expliqué et réglable : ce qu'il fait, quand, et ce qui attend son tour. */
export function AutoPanel({ open, auto, onClose, onUpdate, onRefresh, onRunNow, onUndo }: {
  open: boolean
  auto: AutoStatus | null
  onClose: () => void
  onUpdate: (patch: { enabled?: boolean; delay_hours?: number; actions?: string[] }) => void
  onRefresh: () => void
  onRunNow: () => Promise<void>
  onUndo: (batch: number) => void
}) {
  const [showSkipped, setShowSkipped] = useState(false)
  const [running, setRunning] = useState(false)
  const ref = useRef<HTMLElement>(null)
  useDialog(open && !!auto, ref)
  const a = auto
  const items = a?.preview?.items ?? []
  const planned = items.filter((p) => p.target)
  const skipped = items.filter((p) => !p.target)
  const delay = a ? fmtDelay(a.delay_hours) : ''
  const next = a?.last_run ? a.last_run + a.interval_minutes * 60 : null
  const toggleAction = (k: string) => a && onUpdate({ actions: a.actions.includes(k) ? a.actions.filter((x) => x !== k) : [...a.actions, k] })

  return (
    <AnimatePresence>
      {open && a && (
        <>
          <motion.div className="fixed inset-0 z-40 bg-black/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-label={tr('Réglages du tri auto')}
            initial={{ x: 460 }}
            animate={{ x: 0 }}
            exit={{ x: 460 }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="scroll-area fixed bottom-3 right-3 top-3 z-50 flex w-[min(420px,calc(100vw-24px))] flex-col gap-6 overflow-y-auto rounded-[24px] border border-line bg-surface-strong p-5 shadow-2xl"
            style={{ '--c': 'var(--c-images)' } as CSSProperties}
          >
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <h2 className="flex items-center gap-2 text-[22px] font-semibold tracking-tight"><Zap size={18} className="text-c" /> {tr('Tri auto')}</h2>
                <div className="mt-0.5 font-mono text-[11px] text-muted">
                  {a.enabled ? tr('actif · surveille ce qui arrive depuis le {date}', { date: fmtDateTime(a.since) }) : tr('en pause · rien ne bouge tout seul')}
                </div>
              </div>
              <Switch on={a.enabled} label={tr('Activer le tri auto')} onChange={() => onUpdate({ enabled: !a.enabled })} />
              <button type="button" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-full hover:bg-paper" aria-label={tr('Fermer')}><X size={16} /></button>
            </div>

            {/* Comment ça marche, en trois temps */}
            <ol className="grid grid-cols-3 gap-2">
              {[
                { Icon: Download, title: tr('Un fichier arrive'), text: tr('dans Téléchargements') },
                { Icon: Clock, title: tr('Il attend {delay}', { delay }), text: tr('le temps que tu t\'en serves') },
                { Icon: Sparkles, title: tr('Je le range'), text: tr('ou le mets en quarantaine') },
              ].map(({ Icon, title, text }, i) => (
                <li key={i} className="tint relative rounded-2xl p-3">
                  <Icon size={16} className="text-c" />
                  <div className="mt-2 text-[12.5px] font-semibold leading-tight">{title}</div>
                  <div className="mt-0.5 text-[11px] leading-snug text-muted">{text}</div>
                </li>
              ))}
            </ol>
            <p className="-mt-3 text-[12px] leading-snug text-muted">
              {tr('Ce qui était là avant l\'activation reste à trier à la main. Les noms sensibles (factures, contrats…) et les dossiers ne bougent jamais tout seuls. Tout s\'annule depuis l\'historique.')}
            </p>

            <section>
              <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{tr('Délai avant de ranger')}</div>
              <Segmented id="auto-delay" value={String(a.delay_hours)} onChange={(v) => onUpdate({ delay_hours: Number(v) })}
                options={DELAYS.some((d) => d.value === String(a.delay_hours)) ? DELAYS : [...DELAYS, { value: String(a.delay_hours), label: delay }]} />
            </section>

            <section>
              <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{tr('Ce qu\'il a le droit de faire')}</div>
              <ul className="divide-y divide-line">
                {ACTIONS.map((x) => {
                  const on = a.actions.includes(x.key)
                  return (
                    <li key={x.key} className="flex items-center gap-3 py-2.5" style={{ '--c': TARGET_STYLE[x.target].color } as CSSProperties}>
                      <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: 'var(--c)' }} />
                      <div className="min-w-0 flex-1">
                        <div className="text-[13.5px] font-medium">{x.title}</div>
                        <div className="text-[11.5px] leading-snug text-muted">{x.detail}</div>
                      </div>
                      <Switch on={on} label={x.title} onChange={() => toggleAction(x.key)} />
                    </li>
                  )
                })}
              </ul>
            </section>

            <section>
              <div className="mb-1 flex items-center gap-2">
                <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                  {tr('En attente')}{a.preview ? ` · ${a.preview.total}` : ''}
                </div>
                <span className="ml-auto font-mono text-[11px] text-muted">
                  {a.computing ? tr('calcul…') : a.preview ? tr('calculé à {time}', { time: fmtTime(a.preview.computed) }) : ''}
                </span>
                <button type="button" onClick={onRefresh} disabled={a.computing} title={tr('Recalculer')} className="grid h-7 w-7 place-items-center rounded-full text-muted hover:bg-paper hover:text-ink">
                  <RefreshCw size={13} className={a.computing ? 'animate-spin' : ''} />
                </button>
              </div>
              {!a.enabled ? (
                <div className="text-[12.5px] text-muted">{tr('Active le tri auto pour voir ce qu\'il fera.')}</div>
              ) : !a.preview ? (
                <div className="sweep relative h-16 overflow-hidden rounded-xl" />
              ) : !items.length ? (
                <div className="text-[12.5px] text-muted">{tr('Rien de nouveau depuis l\'activation : je surveille.')}</div>
              ) : (
                <>
                  {planned.length > 0 ? (
                    <ul className="divide-y divide-line">{planned.map((p) => <PendingRow key={p.name + p.arrived} p={p} />)}</ul>
                  ) : (
                    <div className="py-1 text-[12.5px] text-muted">{tr('Aucun nouveau fichier n\'entre dans les actions cochées.')}</div>
                  )}
                  {skipped.length > 0 && (
                    <>
                      <button type="button" onClick={() => setShowSkipped((v) => !v)} className="mt-2 flex items-center gap-1 text-[12px] text-muted hover:text-ink">
                        <ChevronDown size={13} className={`transition-transform ${showSkipped ? 'rotate-180' : ''}`} />
                        {tr('{files} pour toi', { files: plural(skipped.length, 'fichier laissé', 'fichiers laissés') })}
                      </button>
                      {showSkipped && <ul className="divide-y divide-line opacity-75">{skipped.map((p) => <PendingRow key={p.name + p.arrived} p={p} />)}</ul>}
                    </>
                  )}
                </>
              )}
            </section>

            {a.recent.length > 0 && (
              <section>
                <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{tr('Derniers rangements')}</div>
                <ul className="divide-y divide-line">
                  {a.recent.map((b) => (
                    <li key={b.id} className="flex items-center gap-2 py-2">
                      <div className="min-w-0 flex-1">
                        <div className={`truncate text-[12.5px] ${b.state !== 'done' ? 'text-muted line-through' : ''}`} title={b.label}>{b.label.replace('Auto · ', '')}</div>
                        <div className="font-mono text-[11px] text-muted">{fmtDateTime(b.created)} · {plural(b.count, 'élément')} · {fmtBytes(b.bytes)}</div>
                      </div>
                      {b.state === 'done' && (
                        <button type="button" onClick={() => onUndo(b.id)} className="flex shrink-0 items-center gap-1 rounded-full border border-line px-2.5 py-1 text-[11.5px] hover:bg-paper">
                          <Undo2 size={11} /> {tr('Annuler')}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <div className="mt-auto flex items-center gap-3 border-t border-line pt-4">
              <div className="min-w-0 flex-1 font-mono text-[11px] leading-relaxed text-muted">
                {tr('Passe toutes les {n} min', { n: a.interval_minutes })}
                {a.last_run && <><br />{tr('dernière à {date}', { date: fmtDateTime(a.last_run) })}{next && a.enabled ? ` · ${tr('prochaine vers {time}', { time: fmtTime(next) })}` : ''}</>}
                {a.last_error && <><br /><span className="text-[var(--c-pdf)]">{a.last_error}</span></>}
              </div>
              <button
                type="button"
                disabled={!a.enabled || running}
                onClick={async () => { setRunning(true); try { await onRunNow() } finally { setRunning(false) } }}
                className="flex shrink-0 items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-[12.5px] font-semibold text-bg disabled:opacity-40"
              >
                {running ? <LoaderCircle size={13} className="animate-spin" /> : <Play size={13} />} {tr('Passer maintenant')}
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
