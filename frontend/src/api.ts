export type JobStatus = 'queued' | 'processing' | 'done' | 'error'

export interface Job {
  id: string
  video_name: string
  status: JobStatus
  error: string | null
  submitted_at: number
  started_at: number | null
  finished_at: number | null
  speaker_names: Record<string, string>
  /** true once speakers were renamed or cells edited (a working copy exists) */
  modified: boolean
}

export interface Health {
  ok: boolean
  problems: string[]
  max_active_jobs: number
  max_upload_mb: number
  interval_minutes: number
  allowed_extensions: string[]
}

export interface Turn {
  timestamp: string
  speaker: string
  text: string
}

export interface Interval {
  label: string
  number: number | null
  turns: Turn[]
}

export interface Transcript {
  job: Job
  version: string
  interval_minutes: number
  speakers: string[]
  speaker_names: Record<string, string>
  intervals: Interval[]
}

export interface DocumentTable {
  version: string
  header: string[]
  /** body rows (table row 1..n); cell [i][j] is table row i+1, column j */
  rows: string[][]
}

export interface CellEdit {
  row: number
  col: number
  text: string
}

export class ConflictError extends Error {}

export interface UploadResult {
  file: string
  job_id?: string
  error?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw res.status === 409 ? new ConflictError(detail) : new Error(detail || `HTTP ${res.status}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  health: () => request<Health>('/api/health'),
  jobs: () => request<Job[]>('/api/jobs'),
  transcript: (id: string) => request<Transcript>(`/api/jobs/${id}/transcript`),
  deleteJob: (id: string) => request<void>(`/api/jobs/${id}`, { method: 'DELETE' }),
  setSpeakerNames: (id: string, names: Record<string, string>) =>
    request<Job>(`/api/jobs/${id}/speakers`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ names }),
    }),
  document: (id: string) => request<DocumentTable>(`/api/jobs/${id}/document`),
  saveDocument: (id: string, baseVersion: string, edits: CellEdit[]) =>
    request<DocumentTable>(`/api/jobs/${id}/document`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_version: baseVersion, edits }),
    }),
  revertDocument: (id: string) => request<Job>(`/api/jobs/${id}/document/revert`, { method: 'POST' }),
  downloadUrl: (id: string) => `/api/jobs/${id}/download`,
  templateUrl: '/api/template',

  /** XHR rather than fetch so we get upload progress for multi-GB videos. */
  upload(files: File[], onProgress: (fraction: number) => void): Promise<UploadResult[]> {
    return new Promise((resolve, reject) => {
      const form = new FormData()
      files.forEach((f) => form.append('files', f, f.name))
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/jobs')
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText)
          if (xhr.status >= 200 && xhr.status < 300) resolve(body.results)
          else reject(new Error(body.detail ?? `HTTP ${xhr.status}`))
        } catch {
          reject(new Error(`HTTP ${xhr.status}`))
        }
      }
      xhr.onerror = () => reject(new Error('Network error during upload'))
      xhr.send(form)
    })
  },
}
