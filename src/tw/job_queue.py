import json
import queue
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal

JobStatus = Literal["queued", "processing", "done", "error"]


@dataclass
class Job:
    id: str
    video_name: str
    status: JobStatus
    output_path: Path | None = None
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["output_path"] = str(self.output_path) if self.output_path else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(
            id=d["id"],
            video_name=d["video_name"],
            status=d["status"],
            output_path=Path(d["output_path"]) if d["output_path"] else None,
            error=d["error"],
            submitted_at=d["submitted_at"],
        )


class JobQueue:
    """Serializes video-processing jobs through one background worker thread.

    Shared across all Streamlit sessions when constructed via st.cache_resource
    (this is the "shared resource across users" case, not per-user state).
    """

    def __init__(
        self,
        run_fn: Callable[[Path, Path, float, float], Path],
        max_active: int = 5,
        workdir: Path | None = None,
        output_dir: Path | None = None,
    ):
        self._run_fn = run_fn
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

    def _load_jobs(self) -> None:
        if not self._jobs_file.exists():
            return
        for raw in json.loads(self._jobs_file.read_text()):
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
        self._jobs_file.write_text(json.dumps([j.to_dict() for j in self._jobs.values()], indent=2))

    def submit(
        self,
        video_path: Path,
        video_name: str,
        template_path: Path,
        interval_minutes: float,
        speed_factor: float,
    ) -> str:
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.status in ("queued", "processing"))
            if active >= self._max_active:
                raise RuntimeError(f"queue full: {self._max_active} jobs already queued/processing")
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = Job(id=job_id, video_name=video_name, status="queued")
            self._pending[job_id] = (video_path, template_path, interval_minutes, speed_factor)
            self._save_jobs()
        self._task_queue.put(job_id)
        return job_id

    def _worker_loop(self) -> None:
        while True:
            job_id = self._task_queue.get()
            with self._lock:
                video_path, template_path, interval_minutes, speed_factor = self._pending.pop(job_id)
                self._jobs[job_id].status = "processing"
                self._save_jobs()
            try:
                result_path = self._run_fn(video_path, template_path, interval_minutes, speed_factor)
                stable_output = self._output_dir / f"{job_id}_{Path(result_path).name}"
                shutil.copy(result_path, stable_output)
                with self._lock:
                    self._jobs[job_id].status = "done"
                    self._jobs[job_id].output_path = stable_output
                    self._save_jobs()
            except Exception as e:  # noqa: BLE001 - job errors are reported, not raised
                with self._lock:
                    self._jobs[job_id].status = "error"
                    self._jobs[job_id].error = str(e)
                    self._save_jobs()
            finally:
                video_path.unlink(missing_ok=True)

    def get_job(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.submitted_at)
