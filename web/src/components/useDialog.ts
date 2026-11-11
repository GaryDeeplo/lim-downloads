import { useEffect, type RefObject } from 'react'

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

/** Fenêtre modale au clavier : le focus y entre à l'ouverture, Tab y reste, et revient d'où il venait à la fermeture. */
export function useDialog(open: boolean, ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return
    const before = document.activeElement as HTMLElement | null
    const items = () => [...(ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])]
    const enter = requestAnimationFrame(() => {
      const el = ref.current
      if (el && !el.contains(document.activeElement)) (items()[0] ?? el).focus()
    })
    const onKey = (e: KeyboardEvent) => {
      const el = ref.current
      if (e.key !== 'Tab' || !el) return
      const list = items()
      if (!list.length) return
      const first = list[0], last = list[list.length - 1]
      if (!el.contains(document.activeElement)) { e.preventDefault(); first.focus() }
      else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      cancelAnimationFrame(enter)
      document.removeEventListener('keydown', onKey)
      if (before && document.contains(before)) before.focus()
    }
  }, [open, ref])
}
