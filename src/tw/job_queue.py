import json
import os
import queue
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal

JobStatus = Literal["queued", "processing", "done", "error"]


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


@dataclass
class Job:
    id: str
    video_name: str
    status: JobStatus
    output_path: Path | None = None
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    # Speaker display names (original label -> name). Stored on the job, not
    # per browser session, so every viewer of the shared queue sees the same.
    speaker_names: dict[str, str] = field(default_factory=dict)
    # Editable copy of output_path that speaker renames and in-browser cell
    # edits are applied to. output_path itself stays the pristine pipeline
    # result (its SPEAKER_nn labels are the source of truth for renaming).
    working_output_path: Path | None = None

    @property
    def deliverable_path(self) -> Path | None:
        """The file a user should see/download: the working copy if any."""
        if self.working_output_path and self.working_output_path.exists():
            return self.working_output_path
        return self.output_path

    def to_dict(self) -> dict:
        d = asdict(self)
        d["output_path"] = str(self.output_path) if self.output_path else None
        d["working_output_path"] = str(self.working_output_path) if self.working_output_path else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        # .get() for fields added after the first jobs.json format, so
        # existing history still loads.
        return cls(
            id=d["id"],
            video_name=d["video_name"],
            status=d["status"],
            output_path=Path(d["output_path"]) if d.get("output_path") else None,
            error=d.get("error"),
            submitted_at=d["submitted_at"],
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            speaker_names=d.get("speaker_names") or {},
            # "renamed_output_path": earlier name of this field
            working_output_path=_optional_path(d.get("working_output_path") or d.get("renamed_output_path")),
        )


class JobQueue:
    """Serializes video-processing jobs through one background worker thread.

    One instance is shared by every client of the web server (it is the
    process-wide shared resource, not per-user state).
    """

    def __init__(
        self,
        run_fn: Callable[[Path, Path, float, float], Path],
        max_active: int = 5,
        workdir: Path | None = None,
        output_dir: Path | None = None,
        on_idle: Callable[[], None] | None = None,
    ):
        """`on_idle` runs on the worker thread each time it finishes a job and
        finds nothing else queued (e.g. to unload ML models)."""
        self._run_fn = run_fn
        self._on_idle = on_idle
        self._max_active = max_active
        self._workdir = workdir or Path("job_queue_workdir")
        self._workdir.mkdir(parents=True, exist_ok=True)
        # Deliverables (filled transcripts) live separately from queue
        # bookkeeping (jobs.json), so the output location reads clearly.
        self._output_dir = output_dir or (self._workdir / "outputs")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._jobs_file = self._workdir / "jobs.json"
        self._jobs: dict[str, Job] = {}
        self._pending: dict[str, tuple] = {}
        self._lock = threading.Lock()
        self._task_queue: queue.Queue = queue.Queue()
        self._load_jobs()
        threading.Thread(target=self._worker_loop, daemon=True).start()

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def _load_jobs(self) -> None:
        if not self._jobs_file.exists():
            return
        try:
            raw_jobs = json.loads(self._jobs_file.read_text())
        except json.JSONDecodeError:
            # Don't take the whole app down over a damaged history file;
            # keep it aside for inspection and start fresh.
            self._jobs_file.replace(self._jobs_file.with_suffix(".json.corrupt"))
            return
        for raw in raw_jobs:
            job = Job.from_dict(raw)
            if job.status in ("queued", "processing"):
                # The worker thread that owned this job is gone (process
                # restarted mid-job) - it can't be resumed, so surface it
                # as failed rather than silently hanging forever.
                job.status = "error"
                job.error = "interrupted by server restart"
            self._jobs[job.id] = job
        self._save_jobs()

    def _save_jobs(self) -> None:
        # Write-then-rename so a crash mid-write can't leave a truncated
        # jobs.json (os.replace is atomic on POSIX and Windows).
        tmp = self._jobs_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps([j.to_dict() for j in self._jobs.values()], indent=2))
        os.replace(tmp, self._jobs_file)

    def submit(
        self,
        video_path: Path,
        video_name: str,
        template_path: Path,
        interval_minutes: float,
        speed_factor: float,
        cleanup_dir: Path | None = None,
    ) -> str:
        """Queue a job. `cleanup_dir`, if given, is a per-job scratch directory
        (holding the upload and intermediates) removed once the job ends."""
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.status in ("queued", "processing"))
            if active >= self._max_active:
                raise RuntimeError(f"queue full: {self._max_active} jobs already queued/processing")
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = Job(id=job_id, video_name=video_name, status="queued")
            self._pending[job_id] = (video_path, template_path, interval_minutes, speed_factor, cleanup_dir)
            self._save_jobs()
        self._task_queue.put(job_id)
        return job_id

    def _worker_loop(self) -> None:
        while True:
            job_id = self._task_queue.get()
            with self._lock:
                video_path, template_path, interval_minutes, speed_factor, cleanup_dir = self._pending.pop(job_id)
                self._jobs[job_id].status = "processing"
                self._jobs[job_id].started_at = time.time()
                self._save_jobs()
            try:
                result_path = self._run_fn(video_path, template_path, interval_minutes, speed_factor)
                stable_output = self._output_dir / f"{job_id}_{Path(result_path).name}"
                shutil.copy(result_path, stable_output)
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:  # may have been deleted while processing
                        job.status = "done"
                        job.output_path = stable_output
                        job.finished_at = time.time()
                        self._save_jobs()
                    else:
                        stable_output.unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001 - job errors are reported, not raised
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job.status = "error"
                        job.error = str(e) or type(e).__name__
                        job.finished_at = time.time()
                        self._save_jobs()
            finally:
                video_path.unlink(missing_ok=True)
                if cleanup_dir is not None:
                    shutil.rmtree(cleanup_dir, ignore_errors=True)
            if self._on_idle is not None and self._task_queue.empty():
                try:
                    self._on_idle()
                except Exception:  # noqa: BLE001 - housekeeping must never kill the worker
                    pass

    def get_job(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.submitted_at)

    def update_job(self, job_id: str, **changes) -> Job:
        """Set user-editable fields (speaker_names, working_output_path)."""
        allowed = {"speaker_names", "working_output_path"}
        if not set(changes) <= allowed:
            raise ValueError(f"cannot update {sorted(set(changes) - allowed)}")
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            self._save_jobs()
            return job

    def delete_job(self, job_id: str) -> None:
        """Forget a finished/failed job and delete its output files.

        Raises KeyError for unknown ids and ValueError for queued/processing
        jobs (the worker owns those until they finish)."""
        with self._lock:
            job = self._jobs[job_id]
            if job.status in ("queued", "processing"):
                raise ValueError("cannot delete a job that is still queued or processing")
            del self._jobs[job_id]
            self._save_jobs()
        for path in (job.output_path, job.working_output_path):
            if path is not None:
                path.unlink(missing_ok=True)
