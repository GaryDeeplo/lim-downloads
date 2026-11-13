import { AnimatePresence, motion, useAnimationControls } from 'motion/react'
import { useEffect, useState, type CSSProperties } from 'react'
import type { Target } from '../api'
import { tr } from '../i18n'
import { fmtBytes, fmtCount, TARGET_STYLE } from '../lib'

export type Received = Record<string, { n: number; bytes: number }>

/** Un dossier dessiné : rabat avant qui s'ouvre au survol, au glisser-déposer et à la réception. */
function FolderArt({ color, open, Icon }: { color: string; open: boolean; Icon: typeof TARGET_STYLE[string]['icon'] }) {
  const back = `color-mix(in oklab, ${color} 70%, black)`
  return (
    <div className="relative h-[46px] w-[58px]" style={{ perspective: 260 }}>
      <div className="absolute -top-[5px] left-0 h-3 w-6 rounded-t-[6px]" style={{ background: back }} />
      <div className="absolute inset-0 rounded-[7px] rounded-tl-none" style={{ background: back }} />
      <motion.div
        className="absolute inset-x-[7px] top-[3px] h-8 rounded-[3px] bg-paper shadow-sm"
        animate={{ y: open ? -9 : 0, rotate: open ? -3 : 0 }}
        transition={{ type: 'spring', stiffness: 420, damping: 22 }}
      />
      <motion.div
        className="absolute inset-x-[7px] top-[5px] h-7 rounded-[3px] bg-paper/80"
        animate={{ y: open ? -4 : 0, rotate: open ? 4 : 0 }}
        transition={{ type: 'spring', stiffness: 420, damping: 22 }}
      />
      <motion.div
        className="absolute inset-x-0 bottom-0 grid h-[78%] place-items-center rounded-[7px]"
        style={{ background: color, transformOrigin: 'bottom', boxShadow: '0 -1px 0 rgb(255 255 255 / .25) inset' }}
        animate={{ rotateX: open ? -38 : 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 20 }}
      >
        <Icon size={17} strokeWidth={2} color="white" style={{ opacity: 0.92 }} />
      </motion.div>
    </div>
  )
}

function DockFolder({ target, width, received, bump, isDefault, dragging, receiving, progress, onDropIds, onOpen }: {
  target: Target
  width: number
  received?: { n: number; bytes: number }
  bump: number
  isDefault: boolean
  dragging: boolean
  receiving: boolean
  progress: number | null
  onDropIds: (ids: number[]) => void
  onOpen: () => void
}) {
  const { color, icon } = TARGET_STYLE[target.key]
  const off = !target.available
  const sub = progress !== null ? tr('{n} %', { n: Math.round(progress * 100) })
    : !target.remote ? null
    : off ? tr('absent')
    : target.free != null ? tr('{x} libres', { x: fmtBytes(target.free) })
    : tr('en ligne')
  const [hover, setHover] = useState(false)
  const [over, setOver] = useState(false)
  const controls = useAnimationControls()

  useEffect(() => {
    if (bump) controls.start({ scale: [1, 1.14, 0.97, 1], transition: { duration: 0.42, ease: 'easeOut' } })
  }, [bump, controls])

  return (
    <motion.button
      type="button"
      data-target={target.key}
      title={off
        ? tr('{label} : {hint}', { label: target.label, hint: target.hint ?? tr('indisponible') })
        : `${target.label} — ${target.path}${target.hint ? `\n${target.hint}` : ''}\n` +
          (target.key === 'quarantine' ? tr('Clic : voir son contenu') : tr("Clic : ouvrir dans l'Explorateur"))}
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onDragOver={(e) => { if (off) return; e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const raw = e.dataTransfer.getData('application/x-dm-ids')
        if (raw) onDropIds(JSON.parse(raw))
      }}
      animate={{ y: over ? -14 : hover || dragging ? -6 : 0, scale: over ? 1.12 : 1 }}
      transition={{ type: 'spring', stiffness: 420, damping: 24 }}
      className={`relative flex shrink-0 flex-col items-center gap-1.5 rounded-2xl px-1 pb-1.5 pt-3 ${off ? 'opacity-40 grayscale' : ''}`}
      style={{ '--c': color, width } as CSSProperties}
    >
      <AnimatePresence>
        {(isDefault || over) && (
          <motion.span
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            className="text-c absolute -top-[18px] whitespace-nowrap font-mono text-[11px] uppercase tracking-[0.12em]"
          >
            {over ? tr('déposer') : tr('cible ↓')}
          </motion.span>
        )}
      </AnimatePresence>
      {over && <motion.span layoutId="dock-glow" className="absolute inset-0 -z-10 rounded-2xl tint" />}
      <motion.div animate={controls} style={{ zoom: Math.min(1, (width - 10) / 58) }}>
        <FolderArt color={color} open={!off && (hover || over || receiving)} Icon={icon} />
      </motion.div>
      <span className="max-w-full truncate text-[12px] font-medium leading-none">{target.label}</span>
      {sub && <span className="-mt-0.5 font-mono text-[11px] leading-none text-muted">{sub}</span>}
      {progress !== null && (
        <span className="absolute inset-x-3 bottom-0 h-[3px] overflow-hidden rounded-full bg-line">
          <motion.span className="block h-full rounded-full" style={{ background: color }} animate={{ width: `${progress * 100}%` }} />
        </span>
      )}
      <AnimatePresence>
        {received && received.n > 0 && (
          <motion.span
            key="badge"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            title={fmtBytes(received.bytes)}
            className="absolute right-1.5 top-1 min-w-5 rounded-full px-1.5 py-px text-center font-mono text-[11px] font-medium text-white shadow"
            style={{ background: color }}
          >
            <motion.span key={received.n} initial={{ y: -6, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="inline-block">
              {fmtCount(received.n)}
            </motion.span>
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}

export function Dock({ targets, room, received, bumps, defaultTarget, dragging, receiving, progress, onDropIds, onOpen }: {
  targets: Target[]
  room: number
  received: Received
  bumps: Record<string, number>
  defaultTarget: string | null
  dragging: boolean
  receiving: Set<string>
  progress: Record<string, number>
  onDropIds: (target: string, ids: number[]) => void
  onOpen: (target: string) => void
}) {
  const moves = targets.filter((t) => t.key !== 'quarantine' && !t.remote)
  const remotes = targets.filter((t) => t.remote)
  const quarantine = targets.find((t) => t.key === 'quarantine')
  const seps = (remotes.length ? 1 : 0) + (quarantine ? 1 : 0)
  const width = Math.max(56, Math.min(84, Math.floor((room - 48 - seps * 14) / Math.max(1, targets.length))))
  const folder = (t: Target) => (
    <DockFolder
      key={t.key}
      target={t}
      width={width}
      received={received[t.key]}
      bump={bumps[t.key] ?? 0}
      isDefault={defaultTarget === t.key}
      dragging={dragging}
      receiving={receiving.has(t.key)}
      progress={progress[t.key] ?? null}
      onDropIds={(ids) => onDropIds(t.key, ids)}
      onOpen={() => onOpen(t.key)}
    />
  )
  return (
    <motion.div
      initial={{ y: 120, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26, delay: 0.15 }}
      data-tour="dock"
      className="glass pointer-events-auto flex items-end gap-0.5 rounded-[26px] px-2 pb-1 pt-2"
    >
      {moves.map(folder)}
      {remotes.length > 0 && (
        <>
          <div className="mx-1.5 mb-3 h-12 w-px self-end bg-line" />
          {remotes.map(folder)}
        </>
      )}
      {quarantine && (
        <>
          <div className="mx-1.5 mb-3 h-12 w-px self-end bg-line" />
          {folder(quarantine)}
        </>
      )}
    </motion.div>
  )
}
