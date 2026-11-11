import { motion } from 'motion/react'
import { memo, useState } from 'react'
import { Glyph } from './Thumb'

export type Rect = { x: number; y: number; w: number; h: number }

export type Flight = {
  key: string
  from: Rect
  to: Rect
  src: string | null      // miniature déjà chargée (cache navigateur) ou null → icône
  ext: string
  isDir: boolean
  delay: number
  reverse: boolean        // retour d'un dossier vers la grille (annulation)
  target: string
  weight: number          // nb d'éléments que ce vol « compte » à l'atterrissage
  bytes: number
  entryId: number
}

const center = (r: Rect) => ({ x: r.x + r.w / 2, y: r.y + r.h / 2 })

function trajectory(f: Flight) {
  // Le vol garde la taille de la carte d'origine (ou d'arrivée) et joue sur l'échelle.
  const card = f.reverse ? f.to : f.from
  const a = center(f.from)
  const b = center(f.to)
  const peak = Math.min(a.y, b.y) - 90 - Math.random() * 90
  return {
    card,
    xs: [a.x, (a.x + b.x) / 2 + (Math.random() - 0.5) * 120, b.x].map((v) => v - card.w / 2),
    ys: [a.y, peak, b.y].map((v) => v - card.h / 2),
    spin: (Math.random() - 0.5) * 40,
    small: 34 / Math.max(card.w, card.h),
  }
}

const FlightItem = memo(function FlightItem({ f, onLand }: { f: Flight; onLand: (f: Flight) => void }) {
  const [{ card, xs, ys, spin, small }] = useState(() => trajectory(f))

  return (
    <motion.div
      className="fixed left-0 top-0 overflow-hidden rounded-xl bg-paper"
      style={{ width: card.w, height: card.h, boxShadow: '0 24px 50px -12px rgb(0 0 0 / .45)', zIndex: 60 }}
      initial={{ x: xs[0], y: ys[0], scale: f.reverse ? small : 1, opacity: f.reverse ? 0 : 1, rotate: 0 }}
      animate={{
        x: xs,
        y: ys,
        scale: f.reverse ? [small, 0.75, 1] : [1, 0.72, small],
        rotate: f.reverse ? [spin, spin / 2, 0] : [0, spin, spin * 1.6],
        opacity: f.reverse ? [0, 1, 1] : [1, 1, 0.15],
      }}
      transition={{ duration: 0.78, delay: f.delay, ease: [0.55, 0.05, 0.35, 1], times: [0, 0.48, 1] }}
      onAnimationComplete={() => onLand(f)}
    >
      {f.src ? <img src={f.src} alt="" className="h-full w-full object-cover" /> : <Glyph ext={f.ext} isDir={f.isDir} />}
    </motion.div>
  )
})

export function FlightLayer({ flights, onLand }: { flights: Flight[]; onLand: (f: Flight) => void }) {
  return (
    <div className="pointer-events-none fixed inset-0 z-[60]">
      {flights.map((f) => <FlightItem key={f.key} f={f} onLand={onLand} />)}
    </div>
  )
}
