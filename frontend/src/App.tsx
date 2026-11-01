import { AlertTriangle, CheckCircle2, FileDown, Lock, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api, type Health, type Job, type UploadResult } from './api'
import { JobList } from './components/JobList'
import { TranscriptPanel } from './components/TranscriptPanel'
import { UploadCard } from './components/UploadCard'
import { cx } from './utils'

const JOB_POLL_MS = 3000
const HEALTH_POLL_MS = 30000

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-indigo-600" />
      <g className="fill-white">
        <rect x="7" y="13" width="3" height="6" rx="1.5" />
        <rect x="12" y="9" width="3" height="14" rx="1.5" />
        <rect x="17" y="6" width="3" height="20" rx="1.5" />
        <rect x="22" y="11" width="3" height="10" rx="1.5" />
      </g>
    </svg>
  )
}

function HealthPill({ health, error }: { health: Health | null; error: string | null }) {
  if (error)
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-2.5 py-1 text-xs font-medium text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">
        <AlertTriangle className="size-3.5" /> Server unreachable
      </span>
    )
  if (!health)
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
        <Loader2 className="size-3.5 animate-spin" /> Checking
      </span>
    )
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        health.ok
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
          : 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
      )}
    >
      {health.ok ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
      {health.ok ? 'Ready' : 'Setup needed'}
    </span>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [previewJob, setPreviewJob] = useState<Job | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await api.jobs())
    } catch {
      /* transient; the health pill reports a dead server */
    }
  }, [])

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health())
      setHealthError(null)
    } catch (e) {
      setHealthError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    refreshHealth()
    refreshJobs()
    const h = setInterval(refreshHealth, HEALTH_POLL_MS)
    // Poll only while the tab is visible; refresh as soon as it comes back.
    const j = setInterval(() => document.visibilityState === 'visible' && refreshJobs(), JOB_POLL_MS)
    const onVisible = () => document.visibilityState === 'visible' && refreshJobs()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(h)
      clearInterval(j)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [refreshHealth, refreshJobs])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  function onQueued(results: UploadResult[]) {
    const ok = results.filter((r) => r.job_id).length
    if (ok) setToast(`Queued ${ok} recording${ok > 1 ? 's' : ''} for transcription`)
    refreshJobs()
  }

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur dark:border-slate-800/80 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3 sm:px-6">
          <Logo />
          <div className="min-w-0 flex-1">
            <h1 className="text-base leading-tight font-semibold">localscribe</h1>
            <p className="hidden items-center gap-1 text-xs text-slate-500 sm:flex dark:text-slate-400">
              <Lock className="size-3" /> Fully on-device — recordings never leave this machine
            </p>
          </div>
          <HealthPill health={health} error={healthError} />
          <a
            href={api.templateUrl}
            className="hidden items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 sm:inline-flex dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            title="The fixed coding-transcript template every job fills (reference only)"
          >
            <FileDown className="size-3.5" /> Blank template
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6">
        {health && !health.ok && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
            <p className="mb-1 flex items-center gap-2 font-semibold">
              <AlertTriangle className="size-4" /> The server isn't ready to transcribe yet
            </p>
            <ul className="ml-6 list-disc space-y-0.5">
              {health.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
            <UploadCard health={health} onQueued={onQueued} />
          </div>
          <JobList
            jobs={jobs}
            selectedId={previewJob?.id ?? null}
            onPreview={setPreviewJob}
            onDeleted={() => {
              refreshJobs()
              setPreviewJob(null)
            }}
          />
        </div>
      </main>

      {previewJob && <TranscriptPanel job={previewJob} onClose={() => setPreviewJob(null)} onChanged={refreshJobs} />}

      {toast && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white shadow-lg dark:bg-white dark:text-slate-900">
          {toast}
        </div>
      )}
    </div>
  )
}
