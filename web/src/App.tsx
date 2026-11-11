import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { api, type ApplyResult, type AutoStatus, type Entry, type History, type JobStart, type Plan } from './api'
import { BucketView, type Sort, type Zoom } from './components/BucketView'
import { Dock, type Received } from './components/Dock'
import { FlightLayer, type Flight, type Rect } from './components/Flights'
import { HistoryPanel, QuickLook, Toast, type ToastData } from './components/Panels'
import { QuarantineView } from './components/QuarantineView'
import { Guide, guidePref } from './components/Guide'
import { AutoPanel } from './components/AutoPanel'
import { ScanState } from './components/ScanState'
import { Header, Sidebar } from './components/Sidebar'
import { fmtBytes, plural, TARGET_STYLE } from './lib'

const MAX_FLIGHTS = 40

const rectOf = (el: Element): Rect => {
  const r = el.getBoundingClientRect()
  return { x: r.x, y: r.y, w: r.width, h: r.height }
}
const onScreen = (r: Rect) => r.y + r.h > 0 && r.y < window.innerHeight && r.w > 0
const cardEl = (id: number) => document.querySelector(`[data-entry="${id}"]`)
const targetRect = (key: string): Rect => {
  const el = document.querySelector(`[data-target="${key}"]`)
  return el ? rectOf(el) : { x: window.innerWidth / 2, y: window.innerHeight - 60, w: 0, h: 0 }
}
const loadedSrc = (el: Element | null) => {
  const img = el?.querySelector('img')
  return img && img.complete && img.naturalWidth > 0 && img.style.opacity !== '0' ? img.currentSrc : null
}

function readZoom(): Zoom {
  try { return (localStorage.getItem('dm.zoom') as Zoom) || 'm' } catch { return 'm' }
}

/** Image affichée sous le curseur pendant un glisser : la miniature + le nombre d'éléments. */
function dragGhost(card: HTMLElement, count: number): HTMLElement {
  const ghost = document.createElement('div')
  ghost.style.cssText = 'position:fixed;top:-1000px;left:-1000px;width:120px;height:90px;border-radius:14px;overflow:hidden;box-shadow:0 12px 30px rgb(0 0 0 / .35);'
  const thumb = card.querySelector('.aspect-\\[4\\/3\\]')?.cloneNode(true) as HTMLElement | undefined
  if (thumb) { thumb.style.cssText = 'width:100%;height:100%;position:relative;'; ghost.appendChild(thumb) }
  if (count > 1) {
    const badge = document.createElement('div')
    badge.textContent = String(count)
    badge.style.cssText = 'position:absolute;top:6px;right:6px;background:#c2410c;color:#fff;font:600 12px "IBM Plex Mono",monospace;padding:2px 7px;border-radius:99px;'
    ghost.appendChild(badge)
  }
  document.body.appendChild(ghost)
  return ghost
}

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [showQuarantine, setShowQuarantine] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  const guideShown = useRef(false)
  const [selection, setSelection] = useState<Record<string, Set<number>>>({})
  const [received, setReceived] = useState<Received>({})
  const [bumps, setBumps] = useState<Record<string, number>>({})
  const [flights, setFlights] = useState<Flight[]>([])
  const [hiddenIds, setHiddenIds] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<ToastData | null>(null)
  const [history, setHistory] = useState<History | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [peek, setPeek] = useState<Entry | null>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [zoom, setZoom] = useState<Zoom>(readZoom)
  const [sort, setSort] = useState<Sort>('size')
  const [auto, setAuto] = useState<AutoStatus | null>(null)
  const [autoOpen, setAutoOpen] = useState(false)
  const [guidePaused, setGuidePaused] = useState(false)
  const [room, setRoom] = useState(1000)
  const mainRef = useRef<HTMLElement>(null)
  const lastAutoEvent = useRef<number | null>(null)
  const [transfers, setTransfers] = useState<Record<number, { target: string; total: number; done: number; ids: number[] }>>({})

  const hovered = useRef<Entry | null>(null)
  const lastClicked = useRef<number | null>(null)
  const planRef = useRef(plan)
  const activeRef = useRef(activeKey)
  const selectionRef = useRef(selection)
  const busyRef = useRef(busy)
  const quarantineRef = useRef(showQuarantine)
  quarantineRef.current = showQuarantine
  planRef.current = plan
  activeRef.current = activeKey
  selectionRef.current = selection
  busyRef.current = busy

  const buckets = useMemo(() => plan?.buckets ?? [], [plan])
  const active = buckets.find((b) => b.key === activeKey) ?? null
  const ready = plan?.status === 'ready'
  const receiving = useMemo(() => new Set(flights.map((f) => f.target)), [flights])
  const transferIds = useMemo(() => new Set(Object.values(transfers).flatMap((t) => t.ids)), [transfers])
  const progress = useMemo(() => {
    const acc: Record<string, [number, number]> = {}
    for (const t of Object.values(transfers)) {
      const a = (acc[t.target] ??= [0, 0])
      a[0] += t.done
      a[1] += t.total
    }
    return Object.fromEntries(Object.entries(acc).map(([k, [d, tot]]) => [k, tot ? d / tot : 0]))
  }, [transfers])

  const loadHistory = useCallback(() => { api.history().then(setHistory).catch(() => {}) }, [])

  const loadPlan = useCallback(async () => {
    const p = await api.plan()
    setPlan(p)
    if (p.status === 'ready' && p.buckets) {
      const bs = p.buckets
      setSelection(Object.fromEntries(bs.map((b) => [b.key, new Set(b.entries.filter((e) => e.checked).map((e) => e.id))])))
      setActiveKey((k) =>
        k && bs.some((b) => b.key === k && b.entries.length) ? k : (bs.find((b) => b.action && b.entries.length) ?? bs.find((b) => b.entries.length))?.key ?? null)
    }
    return p
  }, [])

  useEffect(() => { loadPlan(); loadHistory() }, [loadPlan, loadHistory])

  // Lim se présente à la première utilisation (et aux suivantes si on le lui a demandé), une fois le dossier scanné.
  useEffect(() => {
    if (!ready || guideShown.current) return
    guideShown.current = true
    if (guidePref() === 'hide') return
    const t = setTimeout(() => setGuideOpen(true), 900)
    return () => clearTimeout(t)
  }, [ready])

  /* ——— Tri automatique : statut + prévenir quand il a rangé quelque chose ——— */
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const a = await api.auto()
        if (!alive) return
        setAuto(a)
        const last = a.events.at(-1)
        if (lastAutoEvent.current === null) lastAutoEvent.current = last?.id ?? 0
        else if (last && last.id > lastAutoEvent.current) {
          lastAutoEvent.current = last.id
          const n = last.batches.reduce((s, b) => s + b.done, 0)
          setToast({
            id: Date.now(),
            text: `Tri auto : ${plural(n, 'élément')} rangé${n > 1 ? 's' : ''}`,
            detail: last.batches.map((b) => b.label.replace('Auto · ', '')).join(' · '),
            color: 'var(--c-images)',
            undoBatch: last.batches.length === 1 ? last.batches[0].batch_id : undefined,
          })
          api.plan().then((p) => p.status === 'ready' && setPlan(p))
          loadHistory()
        }
      } catch { /* serveur arrêté : on réessaie au prochain tour */ }
    }
    tick()
    const t = setInterval(tick, 20000)
    return () => { alive = false; clearInterval(t) }
  }, [loadHistory])

  /* ——— Panneau du tri auto : réglages, ce qui attend, passe immédiate ——— */
  const openAuto = useCallback(() => {
    setAutoOpen(true)
    api.auto().then((a) => {
      setAuto(a)
      if (a.enabled && !a.preview && !a.computing) api.previewAuto().then(setAuto).catch(() => {})
    }).catch(() => {})
  }, [])

  // Pendant que l'aperçu se calcule, on suit de près
  useEffect(() => {
    if (!autoOpen || !auto?.computing) return
    const t = setTimeout(() => { api.auto().then(setAuto).catch(() => {}) }, 1500)
    return () => clearTimeout(t)
  }, [autoOpen, auto])

  const updateAuto = useCallback(async (patch: { enabled?: boolean; delay_hours?: number; actions?: string[] }) => {
    try { setAuto(await api.updateAuto(patch)) } catch (e) { notifyError(e) }
  }, [])

  const runAutoNow = useCallback(async () => {
    try {
      const r = await api.runAuto()
      const a = await api.auto()
      lastAutoEvent.current = a.events.at(-1)?.id ?? lastAutoEvent.current
      setAuto(a)
      if (!r.batches.length) {
        setToast({ id: Date.now(), text: 'Rien à ranger pour l\'instant', detail: 'Les fichiers en attente n\'ont pas encore atteint le délai.', color: 'var(--c-images)' })
        return
      }
      const n = r.batches.reduce((s, b) => s + b.done, 0)
      setToast({ id: Date.now(), text: `Tri auto : ${plural(n, 'élément')} rangé${n > 1 ? 's' : ''}`, color: 'var(--c-images)',
                 detail: r.batches.map((b) => b.label.replace('Auto · ', '')).join(' · '),
                 undoBatch: r.batches.length === 1 ? r.batches[0].batch_id : undefined })
      api.plan().then((p) => p.status === 'ready' && setPlan(p))
      loadHistory()
    } catch (e) { notifyError(e) }
  }, [loadHistory])

  useEffect(() => {
    if (plan?.status !== 'scanning') return
    const t = setTimeout(loadPlan, 350)
    return () => clearTimeout(t)
  }, [plan, loadPlan])

  const startScan = useCallback(async () => {
    try {
      await api.scan()
      setPlan((p) => (p ? { ...p, status: 'scanning', phase: '', buckets: undefined } : p))
    } catch (e) {
      setToast({ id: Date.now(), text: 'Scan impossible', detail: e instanceof Error ? e.message : String(e), color: 'var(--c-pdf)', error: true })
    }
    loadPlan()
  }, [loadPlan])

  const notifyError = (e: unknown) =>
    setToast({ id: Date.now(), text: 'Action impossible', detail: e instanceof Error ? e.message : String(e), color: 'var(--c-pdf)', error: true })

  /* ——— Actions : déplacer / mettre en quarantaine, avec envol des miniatures vers le dossier ——— */
  const showResult = useCallback((res: ApplyResult) => {
    if (!planRef.current?.buckets) return
    if (!res.done) {
      notifyError(res.failed[0]?.error ?? 'aucun élément déplacé')
      return
    }
    const byId = new Map(planRef.current.buckets.flatMap((b) => b.entries.map((e) => [e.id, e] as const)))
    const moved = new Set(res.moved)
    const to = targetRect(res.target)
    let fl: Flight[] = []
    for (const id of res.moved) {
      const el = cardEl(id)
      const e = byId.get(id)
      if (!el || !e || fl.length >= MAX_FLIGHTS) continue
      const rect = rectOf(el)
      if (!onScreen(rect)) continue
      fl.push({ key: `f${res.batch_id}-${id}`, from: rect, to, src: loadedSrc(el), ext: e.ext, isDir: e.is_dir,
                delay: fl.length * 0.035, reverse: false, target: res.target, weight: 1, bytes: e.size, entryId: id })
    }
    if (!fl.length) {  // rien de visible à l'écran : un seul vol symbolique depuis le centre
      const e = byId.get(res.moved[0])
      const main = document.querySelector('[data-main]')
      const m = main ? rectOf(main) : { x: 0, y: 0, w: window.innerWidth, h: window.innerHeight }
      fl = [{ key: `f${res.batch_id}`, from: { x: m.x + m.w / 2 - 80, y: m.y + m.h / 3, w: 160, h: 120 }, to, src: null,
              ext: e?.ext ?? '', isDir: e?.is_dir ?? false, delay: 0, reverse: false, target: res.target, weight: 0,
              bytes: 0, entryId: res.moved[0] }]
    }
    const last = fl[fl.length - 1]
    last.weight += res.moved.length - fl.reduce((a, f) => a + f.weight, 0)
    last.bytes += res.bytes - fl.reduce((a, f) => a + f.bytes, 0)

    setFlights((f) => [...f, ...fl])
    setPlan((p) => p && { ...p, buckets: p.buckets?.map((b) => ({ ...b, entries: b.entries.filter((e) => !moved.has(e.id)) })) })
    setSelection((sel) => Object.fromEntries(Object.entries(sel).map(([k, s]) => [k, new Set([...s].filter((id) => !moved.has(id)))])))
    const label = planRef.current.targets.find((t) => t.key === res.target)?.label ?? res.target
    setToast({
      id: Date.now(),
      text: `${plural(res.done, 'élément')} → ${label}`,
      detail: `${fmtBytes(res.bytes)}${res.errors ? ` · ${res.errors} ignoré(s) : ${res.failed[0].error}` : ''}`,
      color: TARGET_STYLE[res.target].color,
      undoBatch: res.batch_id,
    })
    loadHistory()
  }, [loadHistory])

  const followJob = useCallback(async (start: JobStart) => {
    setTransfers((t) => ({ ...t, [start.job]: { target: start.target, total: start.total, done: 0, ids: start.ids } }))
    const label = planRef.current?.targets.find((t) => t.key === start.target)?.label ?? start.target
    setToast({ id: Date.now(), text: `Transfert vers ${label} lancé`, detail: `${fmtBytes(start.total)} · tu peux continuer à trier`,
               color: TARGET_STYLE[start.target].color })
    try {
      for (;;) {
        await new Promise((r) => setTimeout(r, 500))
        const job = await api.job(start.job)
        setTransfers((t) => ({ ...t, [start.job]: { ...t[start.job], done: job.done } }))
        if (job.status === 'done' && job.result) { showResult(job.result); break }
        if (job.status === 'error') { notifyError(job.error); break }
      }
    } catch (e) {
      notifyError(e)
    } finally {
      setTransfers((t) => { const n = { ...t }; delete n[start.job]; return n })
    }
  }, [showResult])

  const runAction = useCallback(async (ids: number[], target?: string) => {
    if (!ids.length || busyRef.current || !planRef.current?.buckets) return
    const t = target && planRef.current.targets.find((x) => x.key === target)
    if (t && !t.available) {
      setToast({ id: Date.now(), text: `${t.label} indisponible`, detail: t.hint, color: TARGET_STYLE[t.key].color, error: true })
      return
    }
    setBusy(true)
    try {
      const res = await api.apply(ids, target)
      if ('job' in res) followJob(res)
      else showResult(res)
    } catch (e) {
      notifyError(e)
    } finally {
      setBusy(false)
    }
  }, [followJob, showResult])

  const onLand = useCallback((f: Flight) => {
    setFlights((fs) => fs.filter((x) => x.key !== f.key))
    if (f.reverse) {
      setHiddenIds((h) => { const n = new Set(h); n.delete(f.entryId); return n })
      return
    }
    setReceived((r) => ({ ...r, [f.target]: { n: (r[f.target]?.n ?? 0) + f.weight, bytes: (r[f.target]?.bytes ?? 0) + f.bytes } }))
    setBumps((b) => ({ ...b, [f.target]: (b[f.target] ?? 0) + 1 }))
  }, [])

  /* ——— Annulation : les fichiers ressortent du dossier et reprennent leur place ——— */
  const undo = useCallback(async (batchId: number) => {
    try {
      const res = await api.undo(batchId)
      setToast({ id: Date.now(), text: `${plural(res.restored, 'élément')} remis dans Téléchargements`, color: 'var(--c-neutral)',
                 detail: res.errors ? `${res.errors} erreur(s)` : undefined, error: res.errors > 0 })
      loadHistory()
      if (res.rescan) { startScan(); return }
      if (!res.ids.length) return
      const p = await api.plan()
      const ids = new Set(res.ids)
      const restored = (p.buckets ?? []).flatMap((b) => b.entries.filter((e) => ids.has(e.id)).map((e) => [b.key, e] as const))
      setHiddenIds((h) => new Set([...h, ...ids]))
      setPlan(p)
      setSelection((sel) => {
        const next = { ...sel }
        for (const [k, e] of restored) if (e.checked) next[k] = new Set([...(next[k] ?? []), e.id])
        return next
      })
      const cur = activeRef.current
      if (!restored.some(([k]) => k === cur) && restored.length) setActiveKey(restored[0][0])
      if (res.target) {
        const t = res.target
        const bytes = restored.reduce((a, [, e]) => a + e.size, 0)
        setReceived((r) => ({ ...r, [t]: { n: Math.max(0, (r[t]?.n ?? 0) - res.ids.length), bytes: Math.max(0, (r[t]?.bytes ?? 0) - bytes) } }))
      }
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const from = targetRect(res.target ?? 'quarantine')
        const fl: Flight[] = []
        const unhide: number[] = []
        for (const [, e] of restored) {
          const el = cardEl(e.id)
          const r = el && rectOf(el)
          if (!r || !onScreen(r) || fl.length >= MAX_FLIGHTS || !res.target) { unhide.push(e.id); continue }
          fl.push({ key: `r${batchId}-${e.id}`, from, to: r, src: loadedSrc(el), ext: e.ext, isDir: e.is_dir, delay: fl.length * 0.03,
                    reverse: true, target: res.target, weight: 1, bytes: e.size, entryId: e.id })
        }
        setHiddenIds((h) => { const n = new Set(h); unhide.forEach((id) => n.delete(id)); return n })
        setFlights((f) => [...f, ...fl])
      }))
    } catch (e) {
      notifyError(e)
    }
  }, [loadHistory, startScan])

  const purge = useCallback(async () => {
    try {
      const r = await api.purge()
      setToast({ id: Date.now(), text: r.batches ? `${fmtBytes(r.bytes)} supprimés définitivement` : 'Rien d\'assez ancien à purger',
                 color: TARGET_STYLE.quarantine.color })
      loadHistory()
    } catch (e) { notifyError(e) }
  }, [loadHistory])

  const emptyQuarantine = useCallback(async () => {
    try {
      const r = await api.purge(true)
      setToast({ id: Date.now(), text: `Quarantaine vidée : ${fmtBytes(r.bytes)} libérés`, color: TARGET_STYLE.quarantine.color,
                 detail: `${plural(r.batches, 'lot')} supprimé${r.batches > 1 ? 's' : ''} définitivement (le reçu garde noms et liens).` })
      loadHistory()
    } catch (e) { notifyError(e) }
  }, [loadHistory])

  const purgeBatch = useCallback(async (id: number) => {
    try {
      const r = await api.purgeBatch(id)
      setToast({ id: Date.now(), text: `${fmtBytes(r.bytes)} libérés`, detail: 'Supprimé définitivement de la quarantaine (le reçu garde nom et lien).',
                 color: TARGET_STYLE.quarantine.color })
      loadHistory()
    } catch (e) { notifyError(e) }
  }, [loadHistory])

  /* ——— Quarantaine dans l'appli : un fichier ressort, et reprend sa place dans son lot ——— */
  const restoreItem = useCallback(async (op: number, name: string) => {
    try {
      const res = await api.restoreItem(op)
      setToast({ id: Date.now(), text: `« ${res.name} » remis dans Téléchargements`, color: 'var(--c-neutral)',
                 detail: res.rescan ? 'Relance un scan pour le retrouver dans les lots.' : undefined })
      loadHistory()
      if (res.ids.length) {
        const p = await api.plan()
        const ids = new Set(res.ids)
        setPlan(p)
        setSelection((sel) => {
          const next = { ...sel }
          for (const b of p.buckets ?? []) for (const e of b.entries) if (ids.has(e.id) && e.checked) next[b.key] = new Set([...(next[b.key] ?? []), e.id])
          return next
        })
      }
      return true
    } catch (e) {
      notifyError(e instanceof Error ? new Error(`${name} : ${e.message}`) : e)
      return false
    }
  }, [loadHistory])

  const selectBucket = useCallback((k: string) => { setActiveKey(k); setShowQuarantine(false) }, [])

  /* ——— Sélection ——— */
  const toggle = useCallback((id: number, shift: boolean, ordered: Entry[]) => {
    const key = activeRef.current
    if (!key) return
    const cur = new Set(selectionRef.current[key] ?? [])
    const ids = ordered.map((e) => e.id)
    const from = lastClicked.current === null ? -1 : ids.indexOf(lastClicked.current)
    const to = ids.indexOf(id)
    if (shift && from >= 0 && to >= 0) {
      const on = !cur.has(id)
      for (const x of ids.slice(Math.min(from, to), Math.max(from, to) + 1)) on ? cur.add(x) : cur.delete(x)
    } else if (cur.has(id)) cur.delete(id)
    else cur.add(id)
    lastClicked.current = id
    setSelection((sel) => ({ ...sel, [key]: cur }))
  }, [])

  const selectAll = useCallback(() => {
    const b = planRef.current?.buckets?.find((x) => x.key === activeRef.current)
    if (b) setSelection((sel) => ({ ...sel, [b.key]: new Set(b.entries.map((e) => e.id)) }))
  }, [])
  const selectNone = useCallback(() => {
    const k = activeRef.current
    if (k) setSelection((sel) => ({ ...sel, [k]: new Set() }))
  }, [])

  /* ——— Glisser-déposer vers le dock ——— */
  const onDragStart = useCallback((ev: DragEvent, e: Entry) => {
    const sel = selectionRef.current[activeRef.current ?? ''] ?? new Set<number>()
    const ids = sel.has(e.id) ? [...sel] : [e.id]
    ev.dataTransfer.setData('application/x-dm-ids', JSON.stringify(ids))
    ev.dataTransfer.effectAllowed = 'move'
    const ghost = dragGhost(ev.currentTarget as HTMLElement, ids.length)
    ev.dataTransfer.setDragImage(ghost, 60, 45)
    setTimeout(() => ghost.remove(), 0)
    setDragging(true)
  }, [])
  const onDragEnd = useCallback(() => setDragging(false), [])

  const onOpen = useCallback((id: number) => { api.open(id).catch(notifyError) }, [])
  const onKeeper = useCallback((id: number) => {
    const k = planRef.current?.buckets?.flatMap((b) => b.entries).find((e) => e.id === id)
    if (k) setPeek(k)
    else setToast({ id: Date.now(), text: 'Exemplaire gardé déjà rangé', detail: 'Relance un scan pour le retrouver.', color: 'var(--c-documents)' })
  }, [])

  // Place disponible pour le dock : il rétrécit ses dossiers plutôt que de déborder
  useEffect(() => {
    const el = mainRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setRoom(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const onHover = useCallback((e: Entry | null) => { hovered.current = e }, [])
  const changeZoom = useCallback((z: Zoom) => { setZoom(z); try { localStorage.setItem('dm.zoom', z) } catch { /* stockage indisponible */ } }, [])

  /* ——— Clavier : Espace = aperçu, Échap = fermer, Ctrl+A = tout sélectionner ——— */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (e.key === 'Escape') { setPeek(null); setHistoryOpen(false); setAutoOpen(false); setGuidePaused(false); return }
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === ' ' && (hovered.current || tag !== 'BUTTON')) { e.preventDefault(); setPeek((p) => (p ? null : hovered.current)) }
      else if (tag === 'BUTTON') return
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a' && !quarantineRef.current) { e.preventDefault(); selectAll() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectAll])

  const activeDone = history?.batches.filter((b) => b.state === 'done').length ?? 0

  return (
    <div className="grain mat flex h-full flex-col">
      <Header
        root={plan?.root ?? ''}
        buckets={ready ? buckets : []}
        scanning={plan?.status === 'scanning'}
        historyCount={activeDone}
        auto={auto}
        onAuto={openAuto}
        onScan={startScan}
        onHistory={() => { loadHistory(); setHistoryOpen(true) }}
        onGuide={() => { setShowQuarantine(false); setHistoryOpen(false); setPeek(null); setGuideOpen(true) }}
      />
      <div className="flex min-h-0 flex-1">
        {ready && <Sidebar buckets={buckets} activeKey={showQuarantine ? null : activeKey} onSelect={selectBucket}
          quarantine={history?.quarantine ?? null} quarantineActive={showQuarantine} onQuarantine={() => setShowQuarantine(true)} />}
        <main ref={mainRef} data-main className="relative flex min-w-0 flex-1 flex-col">
          {ready && showQuarantine ? (
            <QuarantineView
              refresh={history}
              onRestoreItem={restoreItem}
              onRestoreBatch={undo}
              onPurgeBatch={purgeBatch}
              onEmpty={emptyQuarantine}
              onExplorer={() => { api.openTarget('quarantine').catch(notifyError) }}
            />
          ) : ready && active ? (
            <BucketView
              bucket={active}
              targets={plan!.targets}
              selected={selection[active.key] ?? new Set()}
              hiddenIds={hiddenIds}
              transferIds={transferIds}
              zoom={zoom}
              sort={sort}
              busy={busy}
              onZoom={changeZoom}
              onSort={setSort}
              onToggle={toggle}
              onSelectAll={selectAll}
              onSelectNone={selectNone}
              onApply={() => runAction([...(selection[active.key] ?? [])])}
              onOpen={onOpen}
              onPeek={setPeek}
              onKeeper={onKeeper}
              onHover={onHover}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
            />
          ) : (
            <ScanState scanning={plan?.status === 'scanning'} phase={plan?.phase ?? ''} error={plan?.error ?? null} onScan={startScan} />
          )}
          {ready && (
            <>
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-bg via-bg/80 to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-4 z-30 flex justify-center">
                <Dock
                  targets={plan!.targets}
                  room={room}
                  received={received}
                  bumps={bumps}
                  defaultTarget={active?.target ?? null}
                  dragging={dragging}
                  receiving={receiving}
                  progress={progress}
                  onDropIds={(t, ids) => { setDragging(false); runAction(ids, t) }}
                  onOpen={(k) => {
                    const t = plan!.targets.find((x) => x.key === k)
                    if (k === 'quarantine') setShowQuarantine(true)
                    else if (t && !t.available) setToast({ id: Date.now(), text: `${t.label} indisponible`, detail: t.hint, color: TARGET_STYLE[k].color })
                    else api.openTarget(k).catch(notifyError)
                  }}
                />
              </div>
            </>
          )}
        </main>
      </div>
      <FlightLayer flights={flights} onLand={onLand} />
      <Toast toast={toast} onUndo={undo} onClose={() => setToast(null)} />
      <HistoryPanel open={historyOpen} history={history} onClose={() => setHistoryOpen(false)} onUndo={undo} onPurge={purge} onPurgeBatch={purgeBatch}
        onShowQuarantine={() => { setHistoryOpen(false); setShowQuarantine(true) }}
        onReceipts={() => { api.openReceipts().catch(notifyError) }} />
      <AutoPanel open={autoOpen} auto={auto} onClose={() => { setAutoOpen(false); setGuidePaused(false) }} onUpdate={updateAuto}
        onRefresh={() => { api.previewAuto().then(setAuto).catch(notifyError) }} onRunNow={runAutoNow}
        onUndo={(id) => { undo(id).then(() => api.auto().then(setAuto)).catch(() => {}) }} />
      <Guide open={guideOpen} paused={guidePaused} days={history?.quarantine_days ?? 30} autoConfigured={auto?.configured ?? true}
        onAction={() => { setGuidePaused(true); openAuto() }} onClose={() => setGuideOpen(false)} />
      <QuickLook entry={peek} bucket={peek ? buckets.find((b) => b.entries.some((e) => e.id === peek.id))?.title : undefined} onClose={() => setPeek(null)} onOpen={onOpen} onReveal={(id) => { api.reveal(id).catch(notifyError) }} />
    </div>
  )
}
