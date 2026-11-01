import { renderAsync } from 'docx-preview'
import { Loader2 } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

interface Props {
  /** URL of the .docx to render; change it (e.g. a version query) to re-render. */
  src: string
}

/**
 * Renders the actual .docx the user will download, laid out as Word pages
 * (page size, margins, table borders, fonts) using docx-preview, entirely
 * client-side. Pages are zoomed down to fit narrow screens.
 */
export function DocxView({ src }: Props) {
  const outerRef = useRef<HTMLDivElement>(null)
  const docRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    const controller = new AbortController()
    setState('loading')
    setError(null)
    ;(async () => {
      try {
        const res = await fetch(src, { signal: controller.signal, cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        if (controller.signal.aborted || !docRef.current) return
        docRef.current.innerHTML = ''
        await renderAsync(blob, docRef.current, undefined, {
          className: 'docx',
          inWrapper: true,
          breakPages: true,
          ignoreLastRenderedPageBreak: true,
          renderHeaders: true,
          renderFooters: true,
          experimental: true,
        })
        if (!controller.signal.aborted) setState('ready')
      } catch (e) {
        if (controller.signal.aborted) return
        setError((e as Error).message)
        setState('error')
      }
    })()
    return () => controller.abort()
  }, [src])

  // Fit the widest page into the available width.
  useLayoutEffect(() => {
    const outer = outerRef.current
    if (!outer || state !== 'ready') return
    const fit = () => {
      const pages = docRef.current?.querySelectorAll<HTMLElement>('section.docx') ?? []
      const pageWidth = Math.max(0, ...Array.from(pages, (p) => p.offsetWidth))
      if (!pageWidth) return
      setZoom(Math.min(1, (outer.clientWidth - 32) / pageWidth))
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(outer)
    return () => ro.disconnect()
  }, [state])

  return (
    <div ref={outerRef} className="docx-host relative min-h-full bg-slate-200/70 dark:bg-slate-950">
      {state === 'loading' && (
        <div className="absolute inset-0 grid place-items-center text-sm text-slate-500">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" /> Rendering document…
          </span>
        </div>
      )}
      {state === 'error' && (
        <p className="m-5 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
          Couldn't render the document: {error}. You can still download it.
        </p>
      )}
      <div
        ref={docRef}
        style={{ zoom }}
        className={state === 'ready' ? 'opacity-100 transition-opacity' : 'opacity-0'}
      />
    </div>
  )
}
