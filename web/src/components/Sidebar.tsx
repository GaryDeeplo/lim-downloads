import { motion } from 'motion/react'
import { Globe, History, RefreshCw, ShieldCheck, Trash2, Zap } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { api, type AutoStatus, type Bucket, type History as HistoryData } from '../api'
import { LANG, tr } from '../i18n'
import { bucketColor, fmtBytes, fmtCount, fmtDateTime, TARGET_STYLE } from '../lib'
import { LimIcon } from './Guide'
import { AnimatedNumber, IconButton } from './ui'

const GROUPS: { title: string; match: (b: Bucket) => boolean }[] = [
  { title: tr('Libérer de la place'), match: (b) => b.action === 'quarantine' },
  { title: tr('Ranger'), match: (b) => b.action === 'move' },
  { title: tr('À vérifier'), match: (b) => b.action === null },
]

export function Sidebar({ buckets, activeKey, onSelect, quarantine, quarantineActive, onQuarantine }: {
  buckets: Bucket[]
  activeKey: string | null
  onSelect: (k: string) => void
  quarantine: HistoryData['quarantine'] | null
  quarantineActive: boolean
  onQuarantine: () => void
}) {
  const max = Math.max(1, ...buckets.map((b) => b.entries.reduce((a, e) => a + e.size, 0)))
  return (
    <nav data-tour="sidebar" className="scroll-area flex w-[232px] xl:w-[272px] shrink-0 flex-col gap-6 overflow-y-auto border-r border-line px-3 pb-32 pt-6">
      {GROUPS.map((g) => {
        const list = buckets.filter(g.match).filter((b) => b.entries.length || b.key === activeKey)
        if (!list.length) return null
        return (
          <div key={g.title}>
            <div className="mb-1.5 px-3 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{g.title}</div>
            {list.map((b) => {
              const bytes = b.entries.reduce((a, e) => a + e.size, 0)
              const active = b.key === activeKey
              return (
                <button
                  key={b.key}
                  type="button"
                  onClick={() => onSelect(b.key)}
                  className="relative block w-full rounded-xl px-3 py-2.5 text-left"
                  style={{ '--c': bucketColor(b) } as CSSProperties}
                >
                  {active && (
                    <motion.span
                      layoutId="active-bucket"
                      className="glass absolute inset-0 rounded-xl"
                      transition={{ type: 'spring', stiffness: 480, damping: 38 }}
                    />
                  )}
                  <span className="relative flex items-center gap-2.5">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: 'var(--c)' }} />
                    <span className={`flex-1 truncate text-[14px] ${active ? 'font-semibold' : 'text-ink/85'}`}>{b.title}</span>
                    <span className="font-mono text-[11.5px] text-muted">{fmtCount(b.entries.length)}</span>
                  </span>
                  <span className="relative mt-1.5 flex items-center gap-2 pl-5">
                    <span className="h-[3px] flex-1 overflow-hidden rounded-full bg-line">
                      <motion.span
                        className="block h-full rounded-full"
                        style={{ background: 'var(--c)' }}
                        initial={false}
                        animate={{ width: `${Math.max(1.5, (bytes / max) * 100)}%` }}
                        transition={{ type: 'spring', stiffness: 120, damping: 22 }}
                      />
                    </span>
                    <span className="w-14 text-right font-mono text-[11px] text-muted">{fmtBytes(bytes)}</span>
                  </span>
                </button>
              )
            })}
          </div>
        )
      })}
      <div>
        <div className="mb-1.5 px-3 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{tr('Déjà mis de côté')}</div>
        <button
          type="button"
          data-tour="quarantine-nav"
          onClick={onQuarantine}
          className="relative block w-full rounded-xl px-3 py-2.5 text-left"
          style={{ '--c': TARGET_STYLE.quarantine.color } as CSSProperties}
        >
          {quarantineActive && (
            <motion.span layoutId="active-bucket" className="glass absolute inset-0 rounded-xl" transition={{ type: 'spring', stiffness: 480, damping: 38 }} />
          )}
          <span className="relative flex items-center gap-2.5">
            <Trash2 size={13} className="text-c shrink-0" />
            <span className={`flex-1 truncate text-[14px] ${quarantineActive ? 'font-semibold' : 'text-ink/85'}`}>{tr('Quarantaine')}</span>
            <span className="font-mono text-[11.5px] text-muted">{quarantine?.count ? fmtBytes(quarantine.bytes) : tr('vide')}</span>
          </span>
        </button>
      </div>
      <div className="mx-3 mt-auto flex gap-2 rounded-xl border border-dashed border-line p-3 text-[12px] leading-snug text-muted">
        <ShieldCheck size={16} className="mt-px shrink-0" />
        {tr("Rien n'est supprimé directement. La quarantaine garde tout 30 jours et chaque action s'annule.")}
      </div>
    </nav>
  )
}

function Stat({ label, value, format, accent, wide }: { label: string; value: number; format: (n: number) => string; accent?: boolean; wide?: boolean }) {
  return (
    <div className={`text-right ${wide ? 'hidden xl:block' : ''}`}>
      <div className={`text-[21px] font-semibold leading-none tracking-[-0.02em] ${accent ? 'text-accent-text' : ''}`}>
        <AnimatedNumber value={value} format={format} />
      </div>
      <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">{label}</div>
    </div>
  )
}

function AutoPill({ auto, onOpen }: { auto: AutoStatus; onOpen: () => void }) {
  const days = auto.delay_hours / 24
  const delay = days >= 1 ? tr('{n} j', { n: Math.round(days) }) : tr('{n} h', { n: Math.round(auto.delay_hours) })
  const title = !auto.configured
    ? tr('Tri automatique pas encore réglé. Clic : choisir ce que je range tout seul, et quand.')
    : auto.enabled
    ? tr('Tri automatique actif : les téléchargements arrivés depuis le {since} sont rangés après {delay}.', { since: fmtDateTime(auto.since), delay }) + '\n' +
      (auto.last_run
        ? tr('Vérification toutes les {n} min · dernière {last}.', { n: auto.interval_minutes, last: fmtDateTime(auto.last_run) })
        : tr('Vérification toutes les {n} min.', { n: auto.interval_minutes })) +
      '\n' + tr('Clic : voir et régler.')
    : tr('Tri automatique en pause. Clic : voir et régler.')
  return (
    <button
      type="button"
      data-tour="auto"
      onClick={onOpen}
      title={title}
      className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors ${
        !auto.configured ? 'border-[color-mix(in_oklab,var(--accent)_55%,transparent)] text-ink hover:bg-surface-strong'
        : auto.enabled ? 'border-[color-mix(in_oklab,var(--c-images)_45%,transparent)] text-ink' : 'border-line text-muted'}`}
    >
      <span className="relative flex h-2 w-2">
        {(auto.enabled || !auto.configured) && (
          <span className="absolute inset-0 animate-ping rounded-full opacity-60" style={{ background: auto.configured ? 'var(--c-images)' : 'var(--accent)' }} />
        )}
        <span className="relative h-2 w-2 rounded-full" style={{ background: !auto.configured ? 'var(--accent)' : auto.enabled ? 'var(--c-images)' : 'var(--faint)' }} />
      </span>
      <Zap size={13} />
      {!auto.configured ? tr('Régler le tri auto') : auto.enabled ? tr('Tri auto · {delay}', { delay }) : tr('Tri auto en pause')}
      {auto.last_error && <span className="text-[var(--c-pdf)]" title={auto.last_error}>!</span>}
    </button>
  )
}

/** FR / EN : enregistre le choix côté serveur puis recharge l'appli dans l'autre langue. */
function LanguageButton() {
  const next = LANG === 'fr' ? 'en' : 'fr'
  const [busy, setBusy] = useState(false)
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true)
        try { await api.setLanguage(next); window.location.reload() } catch { setBusy(false) }
      }}
      title={tr('Langue : français. Clic : passer en anglais')}
      aria-label={tr('Langue : français. Clic : passer en anglais')}
      className="flex h-9 items-center gap-1.5 rounded-full border border-line px-3 font-mono text-[12px] font-medium text-muted transition-colors hover:bg-surface-strong hover:text-ink disabled:opacity-50"
    >
      <Globe size={14} /> {LANG.toUpperCase()}
    </button>
  )
}

export function Header({ root, buckets, scanning, historyCount, auto, onScan, onHistory, onAuto, onGuide }: {
  root: string
  buckets: Bucket[]
  scanning: boolean
  historyCount: number
  auto: AutoStatus | null
  onScan: () => void
  onHistory: () => void
  onAuto: () => void
  onGuide: () => void
}) {
  const sum = (f: (b: Bucket) => boolean) => buckets.filter(f).reduce((a, b) => a + b.entries.reduce((x, e) => x + e.size, 0), 0)
  const count = buckets.reduce((a, b) => a + b.entries.length, 0)
  return (
    <header className="relative z-10 flex h-[72px] shrink-0 items-center gap-6 border-b border-line px-6">
      <div className="flex min-w-0 items-center gap-3">
        <div className="relative h-9 w-9">
          <span className="absolute inset-x-1 top-0 h-5 rounded-[4px] bg-paper shadow" style={{ rotate: '-8deg' }} />
          <span className="absolute inset-x-0 bottom-0 h-6 rounded-[6px] bg-accent" />
          <span className="absolute bottom-[23px] left-0 h-2 w-4 rounded-t-[4px] bg-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-[17px] font-bold leading-none tracking-[-0.03em]">Lim</div>
          <div className="mt-1 max-w-[34ch] truncate font-mono text-[12px] text-muted" title={root}>{root}</div>
        </div>
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-5 xl:gap-7">
        {buckets.length > 0 && (
          <>
            <Stat label={tr('éléments')} value={count} format={fmtCount} />
            <Stat label={tr('au total')} value={sum(() => true)} format={fmtBytes} wide />
            <Stat label={tr('libérables')} value={sum((b) => b.action === 'quarantine')} format={fmtBytes} accent />
            <Stat label={tr('à ranger')} value={sum((b) => b.action === 'move')} format={fmtBytes} wide />
          </>
        )}
        <div className="flex items-center gap-2">
          {auto && <AutoPill auto={auto} onOpen={onAuto} />}
          <IconButton tour="scan" title={scanning ? tr('Scan en cours…') : tr('Rescanner')} onClick={onScan}>
            <RefreshCw size={16} className={scanning ? 'animate-spin' : ''} />
          </IconButton>
          <IconButton tour="history" title={tr('Historique et quarantaine')} onClick={onHistory}>
            <History size={16} />
            {historyCount > 0 && (
              <span className="absolute -right-1 -top-1 rounded-full bg-accent-strong px-1.5 font-mono text-[11px] leading-4 text-white">{historyCount}</span>
            )}
          </IconButton>
          <LanguageButton />
          <IconButton tour="guide" title={tr("Lim, le guide de l'appli")} onClick={onGuide}>
            <LimIcon size={20} />
          </IconButton>
        </div>
      </div>
    </header>
  )
}
