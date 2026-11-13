import { useState, type CSSProperties } from 'react'
import { thumbUrl } from '../api'
import { tr } from '../i18n'
import { family } from '../lib'

/** Icône de repli : une feuille cornée teintée selon la famille de fichier. */
export function Glyph({ ext, isDir, scale = 1 }: { ext: string; isDir: boolean; scale?: number }) {
  const f = family(ext, isDir)
  const Icon = f.icon
  const style = { '--c': f.color } as CSSProperties
  if (isDir) {
    return (
      <div className="tint absolute inset-0 grid place-items-center" style={style}>
        <Icon className="text-c" size={42 * scale} strokeWidth={1.3} />
      </div>
    )
  }
  return (
    <div className="tint absolute inset-0 flex flex-col items-center justify-center gap-2" style={style}>
      <div
        className="tint-strong relative"
        style={{ width: 44 * scale, height: 56 * scale, borderRadius: 5 * scale, clipPath: 'polygon(0 0, 68% 0, 100% 24%, 100% 100%, 0 100%)' }}
      >
        <div
          className="absolute right-0 top-0"
          style={{ width: '32%', height: '24%', background: 'color-mix(in oklab, var(--c) 45%, var(--paper))', clipPath: 'polygon(0 0, 100% 100%, 0 100%)' }}
        />
        <Icon className="text-c absolute inset-0 m-auto" size={20 * scale} strokeWidth={1.6} />
      </div>
      <span
        className="font-mono uppercase tracking-wider"
        style={{ color: 'color-mix(in oklab, var(--c) 60%, var(--ink))', fontSize: Math.max(11, 10.5 * scale), padding: '1px 6px', borderRadius: 4, background: 'color-mix(in oklab, var(--c) 14%, transparent)' }}
      >
        {ext ? ext.slice(1, 6) : tr('fichier')}
      </span>
    </div>
  )
}

/** Miniature Windows si elle existe, sinon la feuille cornée. `url` remplace la miniature d'un élément du plan. */
export function Thumb({ entry, url, px = 256, scale = 1, dim = false }: {
  entry: { id?: number; ext: string; is_dir: boolean }
  url?: string
  px?: number
  scale?: number
  dim?: boolean
}) {
  const [state, setState] = useState<'loading' | 'ok' | 'none'>('loading')
  const cover = family(entry.ext, entry.is_dir).cover
  return (
    <>
      <Glyph ext={entry.ext} isDir={entry.is_dir} scale={scale} />
      {state !== 'none' && (
        <img
          src={url ?? thumbUrl(entry.id ?? -1, px)}
          alt=""
          loading="lazy"
          decoding="async"
          draggable={false}
          onLoad={() => setState('ok')}
          onError={() => setState('none')}
          className={`absolute inset-0 h-full w-full transition-[opacity,filter] duration-300 ${cover ? 'object-cover' : 'object-contain p-2'} ${dim ? 'grayscale' : ''}`}
          style={{ opacity: state === 'ok' ? 1 : 0, background: state === 'ok' && !cover ? 'var(--paper)' : undefined }}
        />
      )}
    </>
  )
}
