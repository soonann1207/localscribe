import { AlertCircle, CheckCircle2, Clock, Download, Eye, Inbox, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type Job, type JobStatus } from '../api'
import { cx, formatDuration, formatRelativeDay } from '../utils'

const STATUS: Record<JobStatus, { label: string; className: string; Icon: typeof Clock }> = {
  queued: {
    label: 'Queued',
    className: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    Icon: Clock,
  },
  processing: {
    label: 'Transcribing',
    className: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300',
    Icon: Loader2,
  },
  done: {
    label: 'Ready',
    className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
    Icon: CheckCircle2,
  },
  error: {
    label: 'Failed',
    className: 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
    Icon: AlertCircle,
  },
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

function JobRow({
  job,
  selected,
  now,
  onPreview,
  onDelete,
}: {
  job: Job
  selected: boolean
  now: number
  onPreview: () => void
  onDelete: () => void
}) {
  const s = STATUS[job.status]
  let timing = formatRelativeDay(job.submitted_at)
  if (job.status === 'processing' && job.started_at) timing = `Running for ${formatDuration(now - job.started_at)}`
  if (job.status === 'done' && job.started_at && job.finished_at)
    timing = `${formatRelativeDay(job.submitted_at)} · took ${formatDuration(job.finished_at - job.started_at)}`

  return (
    <li
      className={cx(
        'group rounded-xl border bg-white p-4 transition dark:bg-slate-900',
        selected
          ? 'border-indigo-400 ring-2 ring-indigo-500/20 dark:border-indigo-500'
          : 'border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700',
      )}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-medium" title={job.video_name}>
              {job.video_name}
            </h3>
            <span
              className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', s.className)}
            >
              <s.Icon className={cx('size-3', job.status === 'processing' && 'animate-spin')} />
              {s.label}
            </span>
            {job.modified && (
              <span
                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                title="Speakers renamed or cells edited in the app"
              >
                Edited
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{timing}</p>
          {job.status === 'error' && job.error && (
            <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 font-mono text-xs break-words text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
              {job.error}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {job.status === 'done' && (
            <>
              <button
                type="button"
                onClick={onPreview}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
              >
                <Eye className="size-3.5" />
                Preview
              </button>
              <a
                href={api.downloadUrl(job.id)}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                title="Download .docx"
                aria-label="Download .docx"
              >
                <Download className="size-4" />
              </a>
            </>
          )}
          {(job.status === 'done' || job.status === 'error') && (
            <button
              type="button"
              onClick={onDelete}
              className="rounded-lg p-2 text-slate-400 opacity-60 hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 dark:hover:bg-rose-500/10"
              title="Delete job and its transcript"
              aria-label="Delete job"
            >
              <Trash2 className="size-4" />
            </button>
          )}
        </div>
      </div>
      {job.status === 'processing' && (
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-indigo-100 dark:bg-indigo-500/15">
          <div className="h-full w-1/3 animate-[progress_1.6s_ease-in-out_infinite] rounded-full bg-indigo-500" />
        </div>
      )}
    </li>
  )
}

interface Props {
  jobs: Job[] | null
  selectedId: string | null
  onPreview: (job: Job) => void
  onDeleted: () => void
}

export function JobList({ jobs, selectedId, onPreview, onDeleted }: Props) {
  const now = useNow(!!jobs?.some((j) => j.status === 'processing'))
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function remove(job: Job) {
    if (!confirm(`Delete "${job.video_name}" and its transcript? This can't be undone.`)) return
    try {
      await api.deleteJob(job.id)
      setDeleteError(null)
      onDeleted()
    } catch (e) {
      setDeleteError((e as Error).message)
    }
  }

  const active = jobs?.filter((j) => j.status === 'queued' || j.status === 'processing').length ?? 0

  return (
    <section className="min-w-0">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-base font-semibold">Jobs</h2>
        {jobs && jobs.length > 0 && (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {active ? `${active} in progress · ` : ''}
            {jobs.length} total
          </span>
        )}
      </div>
      {deleteError && <p className="mb-2 text-sm text-rose-600">{deleteError}</p>}
      {jobs === null ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-200/60 dark:bg-slate-800/60" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 px-4 py-12 text-center dark:border-slate-700">
          <Inbox className="size-8 text-slate-300 dark:text-slate-600" />
          <p className="text-sm font-medium">No transcriptions yet</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Upload a recording to get started.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {jobs.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              now={now}
              selected={job.id === selectedId}
              onPreview={() => onPreview(job)}
              onDelete={() => remove(job)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
