import { AlignLeft, Check, Copy, Download, FilePen, FileText, Loader2, Pencil, Search, Users, X } from 'lucide-react'
import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, type Job, type Transcript } from '../api'
import { cx, minutesToClock, speakerColor } from '../utils'
import { DocEditor } from './DocEditor'
import { DocxView } from './DocxView'

type View = 'document' | 'reader'
const VIEW_KEY = 'localscribe.previewView'

function loadView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === 'reader' ? 'reader' : 'document'
  } catch {
    return 'document'
  }
}

interface Props {
  job: Job
  onClose: () => void
  onChanged: () => void
}

function highlight(text: string, query: string): ReactNode {
  if (!query) return text
  const lower = text.toLowerCase()
  const q = query.toLowerCase()
  const parts: ReactNode[] = []
  let i = 0
  let hit = lower.indexOf(q)
  while (hit !== -1) {
    parts.push(text.slice(i, hit), <mark key={hit}>{text.slice(hit, hit + q.length)}</mark>)
    i = hit + q.length
    hit = lower.indexOf(q, i)
  }
  parts.push(text.slice(i))
  return parts
}

export function TranscriptPanel({ job, onClose, onChanged }: Props) {
  const [data, setData] = useState<Transcript | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [draftNames, setDraftNames] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [view, setViewState] = useState<View>(loadView)
  const [docVersion, setDocVersion] = useState(0)
  const [editingDoc, setEditingDoc] = useState(false)
  const [docDirty, setDocDirty] = useState(false)
  const onDirtyChange = useCallback((d: boolean) => setDocDirty(d), [])

  function requestClose() {
    if (docDirty && !confirm('You have unsaved edits. Close anyway?')) return
    onClose()
  }

  async function onDocSaved() {
    setEditingDoc(false)
    setDocVersion((v) => v + 1)
    try {
      setData(await api.transcript(job.id))
    } catch (e) {
      setError((e as Error).message)
    }
    onChanged()
  }

  function setView(v: View) {
    setViewState(v)
    try {
      localStorage.setItem(VIEW_KEY, v)
    } catch {
      /* storage unavailable: preference just isn't remembered */
    }
  }

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    setEditing(false)
    setEditingDoc(false)
    setDocDirty(false)
    setHidden(new Set())
    api
      .transcript(job.id)
      .then((t) => !cancelled && setData(t))
      .catch((e) => !cancelled && setError((e as Error).message))
    return () => {
      cancelled = true
    }
  }, [job.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !editing && !editingDoc && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, editing, editingDoc])

  // Turns carry display names (after renaming); map both labels and names
  // back to a stable color index per original speaker label.
  const colorIndex = useMemo(() => {
    const map = new Map<string, number>()
    data?.speakers.forEach((label, i) => {
      const idx = label === 'UNKNOWN' ? -1 : i
      map.set(label, idx)
      const name = data.speaker_names[label]
      if (name) map.set(name, idx)
    })
    return map
  }, [data])

  const displayName = (label: string) => data?.speaker_names[label] || label

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.intervals
      .map((interval) => ({
        ...interval,
        turns: interval.turns.filter(
          (t) =>
            !hidden.has(t.speaker) && (!q || t.text.toLowerCase().includes(q) || t.speaker.toLowerCase().includes(q)),
        ),
      }))
      .filter((i) => i.turns.length > 0)
  }, [data, query, hidden])

  const stats = useMemo(() => {
    const words = new Map<string, number>()
    data?.intervals.forEach((i) =>
      i.turns.forEach((t) =>
        words.set(t.speaker, (words.get(t.speaker) ?? 0) + t.text.split(/\s+/).filter(Boolean).length),
      ),
    )
    return words
  }, [data])
  const totalWords = [...stats.values()].reduce((a, b) => a + b, 0)
  const matchCount = filtered.reduce((n, i) => n + i.turns.length, 0)

  function startEditing() {
    if (!data) return
    setDraftNames(Object.fromEntries(data.speakers.map((l) => [l, data.speaker_names[l] ?? ''])))
    setEditing(true)
  }

  async function saveNames() {
    setSaving(true)
    try {
      await api.setSpeakerNames(job.id, draftNames)
      setData(await api.transcript(job.id))
      setHidden(new Set())
      setEditing(false)
      setDocVersion((v) => v + 1)
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function copyText() {
    if (!data) return
    const text = data.intervals
      .map((i) => `${i.label}\n\n${i.turns.map((t) => `[${t.timestamp}] [${t.speaker}] ${t.text}`).join('\n\n')}`)
      .join('\n\n\n')
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function toggleSpeaker(name: string) {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const intervalMinutes = data?.interval_minutes ?? 5

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={`Transcript of ${job.video_name}`}
    >
      <button
        type="button"
        aria-label="Close preview"
        onClick={requestClose}
        className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]"
      />

      <aside
        className={cx(
          'relative flex h-full w-full flex-col bg-white shadow-2xl transition-[max-width] dark:bg-slate-900',
          view === 'document' ? 'max-w-5xl' : 'max-w-3xl',
        )}
      >
        {/* Header */}
        <header className="border-b border-slate-200 px-5 pt-4 pb-3 dark:border-slate-800">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium tracking-wide text-indigo-600 uppercase dark:text-indigo-400">
                Transcript preview
              </p>
              <h2 className="truncate text-lg font-semibold" title={job.video_name}>
                {job.video_name}
              </h2>
              {data && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {data.intervals.length} intervals · {data.speakers.length} speakers · {totalWords.toLocaleString()}{' '}
                  words
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={copyText}
              disabled={!data}
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 disabled:opacity-40 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              title="Copy transcript as text"
            >
              {copied ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}
            </button>
            <a
              href={api.downloadUrl(job.id)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-500"
            >
              <Download className="size-3.5" />
              .docx
            </a>
            <button
              type="button"
              onClick={requestClose}
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              aria-label="Close"
            >
              <X className="size-5" />
            </button>
          </div>

          {/* View switch */}
          <div className="mt-3 flex items-center gap-2">
            <div
              className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium dark:bg-slate-800"
              role="tablist"
            >
              {(
                [
                  ['document', 'Document', FileText],
                  ['reader', 'Reader', AlignLeft],
                ] as const
              ).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  role="tab"
                  aria-selected={view === value}
                  disabled={editingDoc}
                  onClick={() => setView(value)}
                  className={cx(
                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 transition',
                    view === value
                      ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white'
                      : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
                  )}
                >
                  <Icon className="size-3.5" />
                  {label}
                </button>
              ))}
            </div>
            {view === 'document' && !editingDoc && (
              <button
                type="button"
                onClick={() => {
                  setEditing(false)
                  setEditingDoc(true)
                }}
                className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <FilePen className="size-3.5" /> Edit document
              </button>
            )}
            {editingDoc && (
              <span className="ml-auto text-xs font-medium text-indigo-600 dark:text-indigo-400">Editing document</span>
            )}
          </div>

          {/* Speakers */}
          {data && data.speakers.length > 0 && (
            <div className="mt-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                  <Users className="size-3.5" /> Speakers{' '}
                  {editing ? '— enter display names' : view === 'reader' ? '— click to show/hide' : ''}
                </span>
                {editingDoc ? null : !editing ? (
                  <button
                    type="button"
                    onClick={startEditing}
                    className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
                  >
                    <Pencil className="size-3" /> Rename
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={saveNames}
                      disabled={saving}
                      className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
                    >
                      {saving && <Loader2 className="size-3 animate-spin" />} Save names
                    </button>
                  </div>
                )}
              </div>
              {editing ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {data.speakers.map((label, i) => (
                    <label key={label} className="flex items-center gap-2">
                      <span
                        className={cx(
                          'shrink-0 rounded-md px-2 py-1 font-mono text-[11px] ring-1',
                          speakerColor(label === 'UNKNOWN' ? -1 : i),
                        )}
                      >
                        {label}
                      </span>
                      <input
                        value={draftNames[label] ?? ''}
                        onChange={(e) => setDraftNames((d) => ({ ...d, [label]: e.target.value }))}
                        onKeyDown={(e) => e.key === 'Enter' && saveNames()}
                        placeholder="e.g. Interviewer"
                        className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-800"
                      />
                    </label>
                  ))}
                </div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {data.speakers.map((label, i) => {
                    const name = displayName(label)
                    const off = hidden.has(name)
                    const share = totalWords ? Math.round(((stats.get(name) ?? 0) / totalWords) * 100) : 0
                    return (
                      <button
                        key={label}
                        type="button"
                        onClick={() => view === 'reader' && toggleSpeaker(name)}
                        className={cx(
                          'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition',
                          speakerColor(label === 'UNKNOWN' ? -1 : i),
                          view === 'reader' && off && 'opacity-35 line-through',
                          view === 'document' && 'cursor-default',
                        )}
                        title={name !== label ? `${label} → ${name}` : label}
                      >
                        {name}
                        <span className="opacity-60">{share}%</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Search */}
          {view === 'reader' && (
            <div className="relative mt-3">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search transcript…"
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pr-20 pl-9 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-800"
              />
              {(query || hidden.size > 0) && data && (
                <span className="absolute top-1/2 right-3 -translate-y-1/2 text-xs text-slate-500">
                  {matchCount} turns
                </span>
              )}
            </div>
          )}
        </header>

        {/* Body */}
        {view === 'document' ? (
          <div className="flex-1 overflow-y-auto">
            {editingDoc ? (
              <DocEditor
                jobId={job.id}
                onSaved={onDocSaved}
                onCancel={() => setEditingDoc(false)}
                onDirtyChange={onDirtyChange}
              />
            ) : (
              <DocxView src={`${api.downloadUrl(job.id)}?v=${docVersion}`} />
            )}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {error && (
              <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
                {error}
              </p>
            )}
            {!data && !error && (
              <div className="space-y-3">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
                ))}
              </div>
            )}
            {data && data.intervals.length === 0 && (
              <p className="py-12 text-center text-sm text-slate-500">No speech was detected in this recording.</p>
            )}
            {data && data.intervals.length > 0 && filtered.length === 0 && (
              <p className="py-12 text-center text-sm text-slate-500">No turns match your filters.</p>
            )}
            {filtered.map((interval) => {
              const start = interval.number !== null ? (interval.number - 1) * intervalMinutes : null
              return (
                <section key={interval.label} className="mb-6">
                  <div className="sticky top-0 z-10 -mx-5 mb-2 flex items-baseline gap-2 bg-white/90 px-5 py-1.5 backdrop-blur dark:bg-slate-900/90">
                    <h3 className="text-sm font-semibold">
                      {interval.number !== null ? `Interval ${interval.number}` : interval.label}
                    </h3>
                    {start !== null && (
                      <span className="font-mono text-xs text-slate-500">
                        {minutesToClock(start)}–{minutesToClock(start + intervalMinutes)}
                      </span>
                    )}
                  </div>
                  <ol className="space-y-3">
                    {interval.turns.map((turn, i) => (
                      <Fragment key={i}>
                        <li className="grid grid-cols-[4rem_minmax(0,1fr)] gap-3 sm:grid-cols-[4.5rem_minmax(0,1fr)]">
                          <span className="pt-0.5 font-mono text-xs text-slate-400 tabular-nums">{turn.timestamp}</span>
                          <div className="min-w-0">
                            {turn.speaker && (
                              <span
                                className={cx(
                                  'mb-1 inline-block rounded-md px-1.5 py-0.5 text-[11px] font-semibold ring-1',
                                  speakerColor(colorIndex.get(turn.speaker) ?? -1),
                                )}
                              >
                                {highlight(turn.speaker, query.trim())}
                              </span>
                            )}
                            <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                              {highlight(turn.text, query.trim())}
                            </p>
                          </div>
                        </li>
                      </Fragment>
                    ))}
                  </ol>
                </section>
              )
            })}
          </div>
        )}
      </aside>
    </div>
  )
}
