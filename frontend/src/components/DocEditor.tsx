import { Loader2, RotateCcw, Save, X } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api, ConflictError, type DocumentTable } from '../api'
import { cx } from '../utils'

interface Props {
  jobId: string
  onSaved: () => void
  onCancel: () => void
  onDirtyChange: (dirty: boolean) => void
}

/** Textarea that grows with its content, so a cell looks like a Word cell. */
function AutoTextarea({
  value,
  onChange,
  changed,
  label,
}: {
  value: string
  onChange: (v: string) => void
  changed: boolean
  label: string
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${el.scrollHeight}px`
  }, [value])
  return (
    <textarea
      ref={ref}
      value={value}
      aria-label={label}
      onChange={(e) => onChange(e.target.value)}
      rows={1}
      className={cx(
        'block w-full resize-none overflow-hidden bg-transparent px-1.5 py-1 leading-snug outline-none',
        'focus:bg-indigo-50/70 focus:ring-2 focus:ring-indigo-500/40',
        changed && 'bg-amber-50',
      )}
    />
  )
}

/**
 * Edit the document's table in place, on a Word-like page. Header row is
 * read-only; every other cell is editable. Saves only changed cells, with
 * an optimistic-concurrency version so two people can't overwrite each
 * other silently.
 */
export function DocEditor({ jobId, onSaved, onCancel, onDirtyChange }: Props) {
  const [doc, setDoc] = useState<DocumentTable | null>(null)
  const [cells, setCells] = useState<string[][]>([])
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [saving, setSaving] = useState(false)

  async function load() {
    setError(null)
    setConflict(false)
    try {
      const d = await api.document(jobId)
      setDoc(d)
      setCells(d.rows.map((r) => [...r]))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  const changed = useMemo(() => {
    const out: { row: number; col: number; text: string }[] = []
    if (!doc) return out
    cells.forEach((r, i) =>
      r.forEach((text, j) => {
        if (text !== doc.rows[i][j]) out.push({ row: i + 1, col: j, text })
      }),
    )
    return out
  }, [cells, doc])

  useEffect(() => onDirtyChange(changed.length > 0), [changed.length, onDirtyChange])

  // Browser-level guard for unsaved edits (tab close / reload).
  useEffect(() => {
    if (!changed.length) return
    const handler = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [changed.length])

  async function save() {
    if (!doc || !changed.length) return
    setSaving(true)
    setError(null)
    try {
      await api.saveDocument(jobId, doc.version, changed)
      onDirtyChange(false)
      onSaved()
    } catch (e) {
      if (e instanceof ConflictError) setConflict(true)
      else setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function revertAll() {
    if (!confirm('Discard ALL edits and speaker names for this transcript and go back to the original output?')) return
    setSaving(true)
    try {
      await api.revertDocument(jobId)
      onDirtyChange(false)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  function cancel() {
    if (changed.length && !confirm('Discard your unsaved changes?')) return
    onDirtyChange(false)
    onCancel()
  }

  // Ctrl/Cmd+S saves.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        e.preventDefault()
        save()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const colWidths = (header: string[]) =>
    header.map((h) => (/transcription/i.test(h) ? 'auto' : /time/i.test(h) ? '5.5rem' : '7.5rem'))

  return (
    <div className="flex min-h-full flex-col bg-slate-200/70 dark:bg-slate-950">
      {/* Toolbar */}
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white/95 px-4 py-2 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
        <span className="text-xs text-slate-600 dark:text-slate-300">
          {changed.length ? (
            <>
              <span className="font-semibold text-amber-700 dark:text-amber-400">{changed.length}</span> unsaved cell
              {changed.length > 1 ? 's' : ''}
            </>
          ) : (
            'Click any cell to edit · Ctrl/⌘+S to save'
          )}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={revertAll}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-rose-600 disabled:opacity-50 dark:hover:bg-slate-800"
            title="Discard every edit and speaker name; restore the original transcript"
          >
            <RotateCcw className="size-3.5" /> Revert to original
          </button>
          <button
            type="button"
            onClick={cancel}
            className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            <X className="size-3.5" /> {changed.length ? 'Discard' : 'Done'}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!changed.length || saving}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />} Save
          </button>
        </div>
        {conflict && (
          <p className="w-full rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
            Someone else changed this document since you opened it, so your edits were not saved.{' '}
            <button type="button" onClick={load} className="font-semibold underline">
              Reload latest
            </button>{' '}
            (copy anything you want to keep first).
          </p>
        )}
        {error && <p className="w-full text-xs text-rose-600">{error}</p>}
      </div>

      {/* Page */}
      <div className="overflow-x-auto px-3 py-6 sm:px-6">
        {!doc ? (
          <div className="grid h-40 place-items-center text-sm text-slate-500">
            {error ? null : <Loader2 className="size-5 animate-spin" />}
          </div>
        ) : (
          <div
            className="mx-auto min-w-[560px] max-w-[816px] bg-white px-6 py-10 text-[13px] text-black shadow-[0_1px_3px_rgb(15_23_42/0.12),0_8px_24px_rgb(15_23_42/0.10)] sm:px-[72px] sm:py-[72px]"
            style={{ fontFamily: '"Times New Roman", Times, serif' }}
          >
            <table className="w-full table-fixed border-collapse">
              <colgroup>
                {colWidths(doc.header).map((w, i) => (
                  <col key={i} style={{ width: w }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {doc.header.map((h, j) => (
                    <th key={j} className="border border-black px-1.5 py-1 text-left font-normal">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cells.map((row, i) => (
                  <tr key={i}>
                    {row.map((text, j) => (
                      <td key={j} className="border border-black p-0 align-top">
                        <AutoTextarea
                          value={text}
                          label={`${doc.header[j] ?? 'Column'} — ${row[0] || `row ${i + 1}`}`}
                          changed={text !== doc.rows[i][j]}
                          onChange={(v) =>
                            setCells((prev) =>
                              prev.map((r, ri) => (ri === i ? r.map((c, ci) => (ci === j ? v : c)) : r)),
                            )
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
