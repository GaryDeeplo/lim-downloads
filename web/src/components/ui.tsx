import { animate, motion, useMotionValue, useSpring, useTransform, type AnimationPlaybackControls } from 'motion/react'
import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'

/** Nombre qui « roule » vers sa nouvelle valeur. */
export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const spring = useSpring(value, { stiffness: 90, damping: 22 })
  useEffect(() => { spring.set(value) }, [spring, value])
  const text = useTransform(spring, (v) => format(v))
  return <motion.span className="tabular-nums">{text}</motion.span>
}

/** Bouton à maintenir enfoncé : la jauge se remplit, l'action part à 100 %. */
export function HoldButton({ children, color, onConfirm, disabled, duration = 0.7, className = '' }: {
  children: ReactNode
  color: string
  onConfirm: () => void
  disabled?: boolean
  duration?: number
  className?: string
}) {
  const progress = useMotionValue(0)
  const run = useRef<AnimationPlaybackControls | null>(null)
  const width = useTransform(progress, (v) => `${v * 100}%`)

  const start = () => {
    if (disabled) return
    run.current?.stop()
    run.current = animate(progress, 1, {
      duration: duration * (1 - progress.get()),
      ease: 'linear',
      onComplete: () => {
        onConfirm()
        animate(progress, 0, { duration: 0.35, delay: 0.15 })
      },
    })
  }
  const cancel = () => {
    if (progress.get() >= 1) return
    run.current?.stop()
    animate(progress, 0, { duration: 0.25 })
  }

  return (
    <motion.button
      type="button"
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      onPointerDown={start}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) { e.preventDefault(); start() } }}
      onKeyUp={(e) => { if (e.key === 'Enter' || e.key === ' ') cancel() }}
      className={`relative isolate select-none overflow-hidden rounded-full px-5 py-2.5 text-[14px] font-semibold tracking-[-0.01em] text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-35 ${className}`}
      style={{ '--c': color, background: `color-mix(in oklab, ${color} 82%, black)` } as CSSProperties}
    >
      <motion.span className="absolute inset-y-0 left-0 -z-10" style={{ width, background: color }} />
      <span className="flex items-center gap-2">{children}</span>
    </motion.button>
  )
}

export function Segmented<T extends string>({ value, options, onChange, id }: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  id: string
}) {
  return (
    <div className="flex rounded-full border border-line bg-surface-strong p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`relative rounded-full px-2.5 py-1 font-mono text-[11px] transition-colors ${value === o.value ? 'text-bg' : 'text-muted hover:text-ink'}`}
        >
          {value === o.value && (
            <motion.span layoutId={`seg-${id}`} className="absolute inset-0 rounded-full bg-ink" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />
          )}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  )
}

export function IconButton({ children, onClick, title, active, tour }: { children: ReactNode; onClick: () => void; title: string; active?: boolean; tour?: string }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      data-tour={tour}
      onClick={onClick}
      className={`relative grid h-9 w-9 place-items-center rounded-full border border-line transition-colors hover:bg-surface-strong ${active ? 'bg-surface-strong' : ''}`}
    >
      {children}
    </button>
  )
}
