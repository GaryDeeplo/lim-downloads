import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useDialog } from './useDialog'
import { tr } from '../i18n'

/* Lim, le robot guide : il vole jusqu'à chaque zone de l'appli et explique ce qu'on y fait. */

const PREF = 'dm.guide'  // 'hide' : ne plus le montrer au lancement · 'again' : le remontrer
export function guidePref(): 'hide' | 'again' | null {
  try { return localStorage.getItem(PREF) as 'hide' | 'again' | null } catch { return null }
}
function setGuidePref(again: boolean) {
  try { localStorage.setItem(PREF, again ? 'again' : 'hide') } catch { /* stockage indisponible */ }
}

type Step = { target?: string; title: string; text: string; action?: { label: string } }

const stepsFor = (days: number, autoConfigured: boolean): Step[] => [
  { title: tr('Salut, moi c\'est Lim'), text: tr('Je range tes téléchargements. Je te fais le tour de l\'appli en quelques étapes. Tu peux passer quand tu veux.') },
  ...(autoConfigured ? [] : [{
    target: '[data-tour="auto"]', title: tr('D\'abord : le tri auto'),
    text: tr('Je peux ranger tout seul tes prochains téléchargements, quelques jours après leur arrivée. Il est éteint : règle-le maintenant, ou plus tard avec ce bouton.'),
    action: { label: tr('Régler maintenant') },
  }]),
  { target: '[data-tour="scan"]', title: tr('Scanner'), text: tr('Je relis ton dossier Téléchargements et je classe chaque fichier dans un lot. Rien ne bouge tant que tu ne confirmes pas.') },
  { target: '[data-tour="sidebar"]', title: tr('Les lots'), text: tr('« Libérer de la place » : ce qui peut partir sans regret, comme les doublons, les installeurs ou les zips déjà extraits. « Ranger » : ce qui va dans tes dossiers. « À vérifier » : c\'est à toi de juger.') },
  { target: '[data-entry]', title: tr('Les cartes'), text: tr('Clique sur une carte pour la cocher ou la décocher, Maj + clic pour une plage. Espace ouvre l\'aperçu, double-clic ouvre le fichier.') },
  { target: '[data-tour="apply"]', title: tr('Confirmer'), text: tr('Maintiens ce bouton une seconde pour traiter les cartes cochées. Le maintien évite les fausses manœuvres.') },
  { target: '[data-tour="dock"]', title: tr('Le dock'), text: tr('Glisse une ou plusieurs cartes sur un dossier pour les y envoyer. Un clic sur un dossier l\'ouvre dans l\'Explorateur.') },
  { target: '[data-target="quarantine"]', title: tr('La quarantaine'), text: tr('Rien n\'est supprimé tout de suite : tout passe ici pendant {days} jours. Clique dessus pour voir son contenu, remettre un fichier à sa place ou tout vider d\'un coup.', { days }) },
  { target: '[data-tour="history"]', title: tr('Historique'), text: tr('Chaque action s\'annule d\'un clic, même plusieurs jours plus tard.') },
  ...(autoConfigured ? [{ target: '[data-tour="auto"]', title: tr('Tri auto'), text: tr('Je range tout seul les nouveaux téléchargements après quelques jours. Clique ici pour voir ce qui attend son tour et changer les réglages.') }] : []),
  { target: '[data-tour="guide"]', title: tr('C\'est tout !'), text: tr('Je reste ici. Clique sur moi pour revoir le guide quand tu veux.') },
]

const RW = 76, RH = 92, BW = 344, GAP = 14, M = 16
type Rect = { x: number; y: number; w: number; h: number }
type Place = { x: number; y: number; side: 'left' | 'right'; anchor: 'top' | 'bottom' }

function measure(sel?: string): Rect | null {
  if (!sel) return null
  const el = document.querySelector(sel)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return r.width && r.height ? { x: r.x, y: r.y, w: r.width, h: r.height } : null
}

/** Où se poser : sous la cible si possible, sinon au-dessus, à droite ou à gauche ; la bulle part du côté libre. */
function placeFor(t: Rect | null, vw: number, vh: number): Place {
  if (!t) return { x: vw / 2 - (RW + GAP + BW) / 2, y: vh / 2 - RH / 2 - 40, side: 'right', anchor: 'top' }
  const cx = t.x + t.w / 2, cy = t.y + t.h / 2
  const small = t.h < vh * 0.5
  let x: number, y: number, anchor: Place['anchor'] = 'top'
  if (small && vh - (t.y + t.h) >= RH + 220) { x = cx - RW / 2; y = t.y + t.h + GAP }
  else if (small && t.y >= RH + 220) { x = cx - RW / 2; y = t.y - GAP - RH; anchor = 'bottom' }
  else if (vw - (t.x + t.w) >= RW + GAP + BW + 40) { x = t.x + t.w + GAP; y = Math.min(cy - RH / 2, t.y + 120) }
  else { x = t.x - GAP - RW; y = Math.min(cy - RH / 2, t.y + 120) }
  x = Math.min(Math.max(x, M), vw - RW - M)
  y = Math.min(Math.max(y, M), vh - RH - M)
  if (anchor === 'top' && y + 240 > vh) anchor = 'bottom'
  return { x, y, side: x + RW + GAP + BW + M <= vw ? 'right' : 'left', anchor }
}

/** Le robot : tête crème, visière sombre, yeux qui suivent la cible, réacteur sous les pieds. */
function Robot({ look, talking, moving, aim }: { look: { x: number; y: number }; talking: boolean; moving: boolean; aim: { side: -1 | 1; deg: number } | null }) {
  // bras au repos à 45° vers le bas ; pour pointer, on le tourne vers l'angle de la cible
  const turn = (rest: number) => (((aim!.deg - rest) % 360) + 540) % 360 - 180
  const ink = '#1b1a17', cream = '#fbf6ea', eye = '#5ff0e0'
  return (
    <svg viewBox="0 0 80 96" width={RW} height={RH} aria-hidden style={{ overflow: 'visible' }}>
      <defs>
        <radialGradient id="lim-flame" cx="50%" cy="20%" r="80%">
          <stop offset="0%" stopColor="#fff3b0" />
          <stop offset="55%" stopColor="#ff9a3d" />
          <stop offset="100%" stopColor="#ff5a1f" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* réacteur */}
      <motion.ellipse cx="40" cy="88" rx="7" fill="url(#lim-flame)"
        animate={{ ry: moving ? [9, 12, 9] : [4, 5.5, 4], opacity: moving ? 1 : 0.75 }}
        transition={{ duration: moving ? 0.18 : 0.5, repeat: Infinity }} />
      {/* bras : balancement au repos, pointe vers la cible quand Lim s'arrête */}
      {([[-1, 24, 14, 135], [1, 56, 66, 45]] as const).map(([side, x0, x1, rest]) => (
        <g key={side} className="lim-arm" style={{ transform: `rotate(${aim?.side === side ? turn(rest) : 0}deg)`, transformOrigin: `${x0}px 66px` }}>
          <g className={aim?.side === side ? '' : 'lim-sway'} style={{ transformOrigin: `${x0}px 66px` }}>
            <line x1={x0} y1="66" x2={x1} y2="76" stroke={ink} strokeWidth="3.2" strokeLinecap="round" />
            <circle cx={x1 + (x1 - x0) / 10} cy="77" r="3.4" fill="#ff5a1f" stroke={ink} strokeWidth="1.6" />
          </g>
        </g>
      ))}
      {/* corps */}
      <rect x="23" y="58" width="34" height="24" rx="10" fill={cream} stroke={ink} strokeWidth="2.4" />
      <motion.circle cx="40" cy="70" r="4" fill="#ff5a1f" animate={{ opacity: [1, 0.45, 1] }} transition={{ duration: 1.6, repeat: Infinity }} />
      {/* antenne */}
      <line x1="40" y1="14" x2="40" y2="5" stroke={ink} strokeWidth="2.4" strokeLinecap="round" />
      <motion.circle cx="40" cy="4" r="4.2" fill="#ff5a1f" stroke={ink} strokeWidth="1.6"
        animate={{ scale: talking ? [1, 1.25, 1] : 1 }} transition={{ duration: 0.4, repeat: talking ? Infinity : 0 }} />
      {/* tête */}
      <rect x="5" y="30" width="7" height="14" rx="3" fill="#ff5a1f" stroke={ink} strokeWidth="2" />
      <rect x="68" y="30" width="7" height="14" rx="3" fill="#ff5a1f" stroke={ink} strokeWidth="2" />
      <rect x="10" y="14" width="60" height="46" rx="17" fill={cream} stroke={ink} strokeWidth="2.6" />
      <rect x="17" y="22" width="46" height="25" rx="11" fill={ink} />
      {/* yeux : suivent la cible et clignent */}
      <motion.g animate={{ x: look.x, y: look.y }} transition={{ type: 'spring', stiffness: 160, damping: 14 }}>
        <g className="lim-blink">
          <rect x="25" y="29" width="9" height="12" rx="4.5" fill={eye} />
          <rect x="46" y="29" width="9" height="12" rx="4.5" fill={eye} />
          <rect x="27" y="31" width="3" height="3.5" rx="1.5" fill="white" opacity=".85" />
          <rect x="48" y="31" width="3" height="3.5" rx="1.5" fill="white" opacity=".85" />
        </g>
      </motion.g>
      {/* bouche */}
      <motion.rect x="34" width="12" rx="2.5" fill={ink}
        animate={talking ? { height: [2.5, 5, 2, 4.5, 2.5], y: [51, 49.5, 51.2, 49.8, 51] } : { height: 2.5, y: 51 }}
        transition={talking ? { duration: 0.42, repeat: Infinity } : { duration: 0.2 }} />
    </svg>
  )
}

/** Tête de Lim en petit, pour le bouton qui le rappelle. */
export function LimIcon({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="4 0 72 62" width={size} height={size * 62 / 72} aria-hidden>
      <line x1="40" y1="14" x2="40" y2="6" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <circle cx="40" cy="5" r="5" fill="#ff5a1f" />
      <rect x="5" y="30" width="7" height="14" rx="3" fill="#ff5a1f" />
      <rect x="68" y="30" width="7" height="14" rx="3" fill="#ff5a1f" />
      <rect x="10" y="14" width="60" height="46" rx="17" fill="none" stroke="currentColor" strokeWidth="5" />
      <rect x="18" y="23" width="44" height="23" rx="10" fill="currentColor" />
      <rect x="27" y="29" width="8" height="11" rx="4" fill="#5ff0e0" />
      <rect x="45" y="29" width="8" height="11" rx="4" fill="#5ff0e0" />
    </svg>
  )
}

function useTyped(text: string) {
  const [n, setN] = useState(0)
  useEffect(() => {
    setN(0)
    const t = setInterval(() => setN((k) => (k >= text.length ? (clearInterval(t), k) : k + 2)), 16)
    return () => clearInterval(t)
  }, [text])
  return { shown: text.slice(0, n), done: n >= text.length }
}

export function Guide({ open, paused, days, autoConfigured, onAction, onClose }: {
  open: boolean
  paused: boolean
  days: number
  autoConfigured: boolean
  onAction: () => void
  onClose: () => void
}) {
  const [steps, setSteps] = useState<Step[]>([])
  const [i, setI] = useState(0)
  const [rect, setRect] = useState<Rect | null>(null)
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight })
  const [again, setAgain] = useState(false)
  const [moving, setMoving] = useState(false)
  const [tilt, setTilt] = useState(0)
  const prev = useRef<Place | null>(null)
  const bubble = useRef<HTMLDivElement>(null)

  // Au lancement du guide : on ne garde que les étapes dont la cible est à l'écran.
  useLayoutEffect(() => {
    if (!open) return
    setSteps(stepsFor(days, autoConfigured).filter((s) => !s.target || measure(s.target)))
    setI(0)
    setAgain(guidePref() === 'again')
    prev.current = null
  }, [open])  // eslint-disable-line react-hooks/exhaustive-deps

  const step = steps[i]
  useLayoutEffect(() => {
    if (!open || !step) return
    const update = () => { setRect(measure(step.target)); setVp({ w: window.innerWidth, h: window.innerHeight }) }
    update()
    const late = setTimeout(update, 350)  // la cible peut encore s'animer
    window.addEventListener('resize', update)
    return () => { clearTimeout(late); window.removeEventListener('resize', update) }
  }, [open, step])

  const place = placeFor(rect, vp.w, vp.h)
  useEffect(() => {
    const p = prev.current
    prev.current = place
    if (!p || (p.x === place.x && p.y === place.y)) return
    setMoving(true)
    setTilt(Math.max(-16, Math.min(16, (place.x - p.x) / 22)))
    const t = setTimeout(() => { setMoving(false); setTilt(0) }, 700)
    return () => clearTimeout(t)
  }, [place.x, place.y])  // eslint-disable-line react-hooks/exhaustive-deps

  const close = useCallback(() => { setGuidePref(again); onClose() }, [again, onClose])
  const next = useCallback(() => { if (i < steps.length - 1) setI(i + 1); else close() }, [i, steps.length, close])
  const back = useCallback(() => setI((k) => Math.max(0, k - 1)), [])
  const act = useCallback(() => { if (i < steps.length - 1) setI(i + 1); onAction() }, [i, steps.length, onAction])
  const shown = open && !paused && !!steps[i]
  useDialog(shown, bubble)

  useEffect(() => {
    if (!open || paused) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopImmediatePropagation(); close() }
      else if (e.key === 'Enter') { e.preventDefault(); if (steps[i]?.action) act(); else next() }
      else if (e.key === 'ArrowRight') { e.preventDefault(); next() }
      else if (e.key === 'ArrowLeft') back()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, paused, next, back, close, act, steps, i])

  const typed = useTyped(step?.text ?? '')
  const tc = rect ? { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 } : null
  const rc = { x: place.x + RW / 2, y: place.y + 36 }
  const d = tc ? Math.hypot(tc.x - rc.x, tc.y - rc.y) || 1 : 1
  const look = tc ? { x: ((tc.x - rc.x) / d) * 3.2, y: ((tc.y - rc.y) / d) * 2.6 } : { x: 0, y: 0 }
  const aim = !tc || moving ? null : { side: (tc.x < rc.x ? -1 : 1) as -1 | 1, deg: (Math.atan2(tc.y - (place.y + 66), tc.x - rc.x) * 180) / Math.PI }
  const pad = 8
  const spot = rect
    ? { left: rect.x - pad, top: rect.y - pad, width: rect.w + pad * 2, height: rect.h + pad * 2, opacity: 1 }
    : { left: vp.w / 2, top: vp.h / 2, width: 0, height: 0, opacity: 1 }

  return (
    <AnimatePresence>
      {shown && step && (
        <motion.div key="guide" className="fixed inset-0 z-[80]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          {/* voile + projecteur sur la zone expliquée ; bloque les clics pendant la visite */}
          <motion.div
            className="pointer-events-none absolute rounded-2xl"
            initial={false}
            animate={spot}
            transition={{ type: 'spring', stiffness: 170, damping: 24 }}
            style={{ boxShadow: '0 0 0 9999px rgb(10 8 4 / 0.55)', outline: rect ? '2px solid var(--accent)' : 'none', outlineOffset: 0 }}
          />
          <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />

          <motion.div
            className="absolute left-0 top-0"
            style={{ width: RW, height: RH }}
            initial={{ x: vp.w / 2 - RW / 2, y: vp.h + 40 }}
            animate={{ x: place.x, y: place.y }}
            transition={{ type: 'spring', stiffness: 90, damping: 15, mass: 1.1 }}
          >
            <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}>
              <motion.div animate={{ rotate: tilt }} transition={{ type: 'spring', stiffness: 120, damping: 10 }} style={{ originY: '60%' }}>
                <Robot look={look} talking={!typed.done} moving={moving} aim={aim} />
              </motion.div>
            </motion.div>

            <AnimatePresence mode="wait">
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.9, x: place.side === 'right' ? -10 : 10 }}
                animate={{ opacity: 1, scale: 1, x: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ type: 'spring', stiffness: 380, damping: 28, delay: 0.12 }}
                ref={bubble}
                role="dialog"
                aria-modal="true"
                aria-labelledby="lim-title"
                className="glass absolute rounded-[22px] p-5"
                style={{
                  width: BW,
                  [place.side === 'right' ? 'left' : 'right']: RW + GAP,
                  [place.anchor]: -6,
                  transformOrigin: `${place.side === 'right' ? 'left' : 'right'} ${place.anchor}`,
                  background: 'var(--surface-strong)',
                }}
              >
                <div className="mb-1.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                  <span className="text-accent-text">Lim</span> · {i + 1} / {steps.length}
                </div>
                <div id="lim-title" className="text-[19px] font-semibold leading-tight tracking-tight">{step.title}</div>
                <p className="mt-1.5 min-h-[3.6em] text-[13.5px] leading-snug text-ink/85">
                  {typed.shown}
                  {!typed.done && <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-accent" />}
                </p>
                <div className="mt-3 flex gap-1">
                  {steps.map((_, k) => (
                    <span key={k} className="h-1 flex-1 rounded-full transition-colors" style={{ background: k <= i ? 'var(--accent)' : 'var(--line)' }} />
                  ))}
                </div>
                <label className="mt-3.5 flex cursor-pointer select-none items-center gap-2 text-[12.5px] text-muted">
                  <input type="checkbox" checked={again} onChange={(e) => setAgain(e.target.checked)} className="h-3.5 w-3.5 accent-[var(--accent)]" />
                  {tr('Me remontrer au prochain lancement')}
                </label>
                <div className="mt-3.5 flex items-center gap-2">
                  <button type="button" onClick={close} className="whitespace-nowrap rounded-full px-2.5 py-2 text-[13px] font-medium text-muted hover:text-ink">
                    {tr('Passer')}
                  </button>
                  {step.action && (
                    <button type="button" onClick={next} className="ml-auto whitespace-nowrap rounded-full px-2.5 py-2 text-[13px] font-medium text-muted hover:text-ink">
                      {tr('Plus tard')}
                    </button>
                  )}
                  <motion.button
                    type="button"
                    autoFocus
                    whileTap={{ scale: 0.96 }}
                    onClick={step.action ? act : next}
                    className={`${step.action ? '' : 'ml-auto '}flex items-center gap-1.5 whitespace-nowrap rounded-full bg-accent-strong px-4 py-2 text-[13px] font-semibold text-white`}
                  >
                    {step.action ? step.action.label : i < steps.length - 1 ? <>{tr('Suivant')} <ArrowRight size={14} /></> : tr('Terminer')}
                  </motion.button>
                </div>
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
