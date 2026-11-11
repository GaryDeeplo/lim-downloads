import { motion } from 'motion/react'
import { ScanSearch } from 'lucide-react'
import { useEffect, useState } from 'react'

const PHASES = ['Indexation', 'Fichiers incomplets', 'Recherche des doublons', 'Vérification des zips', 'Classement']

export function ScanState({ scanning, phase, error, onScan }: { scanning: boolean; phase: string; error: string | null; onScan: () => void }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!scanning) return
    const t0 = Date.now()
    const t = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(t)
  }, [scanning])

  if (!scanning) {
    return (
      <div className="grid flex-1 place-items-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-md text-center">
          <div className="text-[54px] font-[650] leading-[0.95] tracking-[-0.04em]">Fais le tri.</div>
          <p className="mt-4 text-[15px] text-muted">
            Le dossier est analysé en quelques secondes. Rien ne bouge tant que tu ne l'as pas confirmé.
          </p>
          {error && <p className="mt-3 font-mono text-[12px] text-[var(--c-pdf)]">{error}</p>}
          <motion.button
            type="button"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={onScan}
            className="mt-7 inline-flex items-center gap-2.5 rounded-full bg-accent-strong px-7 py-3.5 text-[15px] font-semibold text-white shadow-lg"
          >
            <ScanSearch size={18} /> Scanner Téléchargements
          </motion.button>
        </motion.div>
      </div>
    )
  }

  const step = Math.max(0, PHASES.indexOf(phase))
  return (
    <div className="flex flex-1 flex-col px-8 pt-8">
      <div className="mb-6 flex items-end gap-6">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent-text">scan en cours · {elapsed.toFixed(1)} s</div>
          <div className="mt-2 text-[42px] font-[640] leading-none tracking-[-0.035em]">{phase || 'Démarrage'}…</div>
        </div>
        <div className="mb-1.5 ml-auto flex gap-1.5">
          {PHASES.map((p, i) => (
            <motion.span
              key={p}
              title={p}
              className="h-1.5 rounded-full"
              animate={{ width: i === step ? 36 : 12, background: i <= step ? 'var(--accent)' : 'var(--line)' }}
            />
          ))}
        </div>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(172px, 1fr))' }}>
        {Array.from({ length: 24 }, (_, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            className="sweep relative overflow-hidden rounded-[18px] border border-line bg-surface p-1.5"
          >
            <div className="aspect-[4/3] rounded-[13px] bg-line" />
            <div className="mx-1.5 mb-1 mt-2.5 h-2.5 w-3/4 rounded bg-line" />
            <div className="mx-1.5 mb-1 h-2 w-1/3 rounded bg-line" />
          </motion.div>
        ))}
      </div>
    </div>
  )
}
