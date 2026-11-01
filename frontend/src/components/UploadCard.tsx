import { FileAudio, FileVideo, Loader2, UploadCloud, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { api, type Health, type UploadResult } from '../api'
import { cx, formatBytes } from '../utils'

interface Props {
  health: Health | null
  onQueued: (results: UploadResult[]) => void
}

const AUDIO_EXT = new Set(['.wav', '.m4a', '.mp3'])

function extOf(name: string) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

export function UploadCard({ health, onQueued }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const allowed = health?.allowed_extensions ?? ['.mp4', '.mov', '.m4v', '.wav', '.m4a']
  const maxBytes = (health?.max_upload_mb ?? 2048) * 1024 * 1024
  const blocked = health !== null && !health.ok
  const uploading = progress !== null

  function addFiles(list: FileList | null) {
    if (!list) return
    setError(null)
    const rejected: string[] = []
    const accepted = Array.from(list).filter((f) => {
      if (!allowed.includes(extOf(f.name))) rejected.push(`${f.name} (unsupported type)`)
      else if (f.size > maxBytes) rejected.push(`${f.name} (over ${health?.max_upload_mb ?? 2048} MB)`)
      else return true
      return false
    })
    if (rejected.length) setError(`Skipped: ${rejected.join(', ')}`)
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size))
      return [...prev, ...accepted.filter((f) => !seen.has(f.name + f.size))]
    })
  }

  async function submit() {
    if (!files.length) return
    setError(null)
    setProgress(0)
    try {
      const results = await api.upload(files, setProgress)
      const failed = results.filter((r) => r.error)
      if (failed.length) setError(failed.map((r) => `${r.file}: ${r.error}`).join(' · '))
      // Keep only the files that failed, so they can be retried.
      setFiles((prev) => prev.filter((f) => failed.some((r) => r.file === f.name)))
      onQueued(results)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setProgress(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const totalSize = files.reduce((n, f) => n + f.size, 0)

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-4">
        <h2 className="text-base font-semibold">New transcription</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {health
            ? `Split into ${health.interval_minutes}-minute intervals · up to ${health.max_active_jobs} jobs at a time`
            : '\u00a0'}
        </p>
      </div>

      <button
        type="button"
        disabled={blocked || uploading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!blocked && !uploading) addFiles(e.dataTransfer.files)
        }}
        className={cx(
          'flex w-full min-w-0 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-center transition',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500',
          dragging
            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
            : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800/50',
          (blocked || uploading) && 'cursor-not-allowed opacity-60',
        )}
      >
        <span className="grid size-12 place-items-center rounded-full bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300">
          <UploadCloud className="size-6" />
        </span>
        <span className="text-sm font-medium">
          Drop recordings here or <span className="text-indigo-600 dark:text-indigo-400">browse</span>
        </span>
        <span className="max-w-full text-xs break-words text-slate-500 dark:text-slate-400">
          {allowed.join(', ')} · up to {formatBytes(maxBytes)} each
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={allowed.join(',')}
        className="hidden"
        onChange={(e) => addFiles(e.target.files)}
      />

      {files.length > 0 && (
        <ul className="mt-4 space-y-2">
          {files.map((f) => {
            const Icon = AUDIO_EXT.has(extOf(f.name)) ? FileAudio : FileVideo
            return (
              <li
                key={f.name + f.size}
                className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800/60"
              >
                <Icon className="size-4 shrink-0 text-slate-400" />
                <span className="min-w-0 flex-1 truncate">{f.name}</span>
                <span className="shrink-0 text-xs text-slate-500">{formatBytes(f.size)}</span>
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}
                  className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-40 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                  aria-label={`Remove ${f.name}`}
                >
                  <X className="size-4" />
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {uploading && (
        <div className="mt-4">
          <div className="mb-1 flex justify-between text-xs text-slate-500">
            <span>Uploading…</span>
            <span>{Math.round((progress ?? 0) * 100)}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-indigo-600 transition-[width]"
              style={{ width: `${(progress ?? 0) * 100}%` }}
            />
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">{error}</p>}

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {files.length ? `${files.length} file${files.length > 1 ? 's' : ''} · ${formatBytes(totalSize)}` : ''}
        </span>
        <button
          type="button"
          onClick={submit}
          disabled={!files.length || uploading || blocked}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading && <Loader2 className="size-4 animate-spin" />}
          {uploading ? 'Uploading' : 'Transcribe'}
        </button>
      </div>
    </section>
  )
}
