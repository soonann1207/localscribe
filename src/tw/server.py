"""HTTP API + static web UI for localscribe.

Replaces the former Streamlit app. One process-wide JobQueue serializes
transcription through a single background worker, shared by everyone on
the LAN using the app. Everything runs on-device.

Run locally:  uv run localscribe-server        (http://localhost:8000)
Dev frontend: cd frontend && npm run dev        (proxies /api to :8000)
"""

import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tw.cli import preflight_check
from tw.doc_edit import CellEdit, apply_cell_edits, read_table
from tw.job_queue import Job, JobQueue
from tw.speaker_rename import (
    clean_speaker_name,
    extract_speakers_from_file,
    rename_speakers_in_file,
    rename_tags_in_text,
)
from tw.transcript_preview import intervals_to_dicts, read_interval_transcript

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".wav", ".m4a", ".mp3"}
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_CHUNK = 1024 * 1024


@dataclass
class Settings:
    data_dir: Path
    template_path: Path
    static_dir: Path
    interval_minutes: float = 5.0
    max_active_jobs: int = 5
    max_upload_bytes: int = 2048 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("LOCALSCRIBE_DATA_DIR", PROJECT_ROOT)),
            template_path=Path(
                os.environ.get(
                    "LOCALSCRIBE_TEMPLATE", PROJECT_ROOT / "templates" / "coding_transcription_template.docx"
                )
            ),
            static_dir=Path(os.environ.get("LOCALSCRIBE_STATIC_DIR", PROJECT_ROOT / "frontend" / "dist")),
            interval_minutes=float(os.environ.get("LOCALSCRIBE_INTERVAL_MINUTES", "5")),
            max_active_jobs=int(os.environ.get("LOCALSCRIBE_MAX_ACTIVE_JOBS", "5")),
            max_upload_bytes=int(os.environ.get("LOCALSCRIBE_MAX_UPLOAD_MB", "2048")) * 1024 * 1024,
        )


def safe_filename(name: str | None) -> str:
    """Basename only, with characters that are awkward on disk replaced.
    The original name is still shown in the UI (Job.video_name)."""
    base = Path(name or "upload").name
    cleaned = re.sub(r"[^\w.\- ]+", "_", base).strip(" .")
    return cleaned[:150] or "upload"


class SpeakerNamesBody(BaseModel):
    names: dict[str, str]


class CellEditBody(BaseModel):
    row: int
    col: int
    text: str


class DocumentEditBody(BaseModel):
    base_version: str
    edits: list[CellEditBody]


def document_version(path: Path) -> str:
    """Changes whenever the file is rewritten; used for edit-conflict checks."""
    st = path.stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def _job_json(job: Job) -> dict:
    return {
        "id": job.id,
        "video_name": job.video_name,
        "status": job.status,
        "error": job.error,
        "submitted_at": job.submitted_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "speaker_names": job.speaker_names,
        "modified": bool(job.working_output_path and job.working_output_path.exists()),
    }


def create_app(
    settings: Settings | None = None,
    run_fn: Callable[[Path, Path, float, float], Path] | None = None,
    preflight: Callable[[], list[str]] | None = None,
    on_idle: Callable[[], None] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if run_fn is None:
        from tw.interval_transcript import release_models
        from tw.interval_transcript import run as run_fn

        on_idle = on_idle or release_models
    if preflight is None:

        def preflight() -> list[str]:
            # The interval pipeline never calls the LLM: don't require Ollama.
            return preflight_check(require_ollama=False)

    uploads_dir = settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    # Scratch dirs from a crashed run (their jobs were marked failed on load).
    for stale in uploads_dir.glob("job_*"):
        shutil.rmtree(stale, ignore_errors=True)
    job_queue = JobQueue(
        run_fn=run_fn,
        max_active=settings.max_active_jobs,
        workdir=settings.data_dir / "job_queue_data",
        output_dir=settings.data_dir / "outputs",
        on_idle=on_idle,
    )

    app = FastAPI(title="localscribe", docs_url="/api/docs", openapi_url="/api/openapi.json")
    # Serializes read-modify-write of working copies across request threads.
    edit_lock = threading.Lock()
    app.state.job_queue = job_queue
    app.state.settings = settings

    def get_job_or_404(job_id: str) -> Job:
        try:
            return job_queue.get_job(job_id)
        except KeyError:
            raise HTTPException(404, "job not found") from None

    def get_done_job(job_id: str) -> Job:
        job = get_job_or_404(job_id)
        if job.status != "done" or job.output_path is None or not job.output_path.exists():
            raise HTTPException(409, "job has no output yet")
        return job

    def working_copy(job: Job) -> Path:
        """Path of the job's editable copy, created from the pristine output on
        first use. Callers must hold edit_lock."""
        path = job_queue.output_dir / f"{job.id}_working.docx"
        if job.working_output_path is None or not job.working_output_path.exists():
            shutil.copy(job.output_path, path)
            job_queue.update_job(job.id, working_output_path=path)
            return path
        return job.working_output_path

    @app.get("/api/health")
    def health() -> dict:
        problems = preflight()
        return {
            "ok": not problems,
            "problems": problems,
            "max_active_jobs": settings.max_active_jobs,
            "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "interval_minutes": settings.interval_minutes,
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        }

    @app.get("/api/template")
    def download_template() -> FileResponse:
        return FileResponse(settings.template_path, media_type=DOCX_MEDIA_TYPE, filename=settings.template_path.name)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [_job_json(j) for j in reversed(job_queue.list_jobs())]

    @app.post("/api/jobs", status_code=201)
    async def create_jobs(files: list[UploadFile]) -> dict:
        problems = preflight()
        if problems:
            raise HTTPException(503, "; ".join(problems))
        results = []
        for upload in files:
            name = safe_filename(upload.filename)
            if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
                results.append({"file": upload.filename, "error": f"unsupported file type: {Path(name).suffix or '?'}"})
                continue
            job_dir = Path(tempfile.mkdtemp(prefix="job_", dir=uploads_dir))
            video_path = job_dir / name
            try:
                size = 0
                with video_path.open("wb") as out:  # stream to disk; never hold a 2GB upload in RAM
                    while chunk := await upload.read(_CHUNK):
                        size += len(chunk)
                        if size > settings.max_upload_bytes:
                            raise ValueError(f"file exceeds {settings.max_upload_bytes // (1024 * 1024)} MB limit")
                        out.write(chunk)
                job_id = job_queue.submit(
                    video_path,
                    upload.filename or name,
                    settings.template_path,
                    settings.interval_minutes,
                    1.0,  # speed factor: not exposed, not validated as reliable (see AMI eval)
                    cleanup_dir=job_dir,
                )
                results.append({"file": upload.filename, "job_id": job_id})
            except (ValueError, RuntimeError) as e:
                shutil.rmtree(job_dir, ignore_errors=True)
                results.append({"file": upload.filename, "error": str(e)})
            finally:
                await upload.close()
        return {"results": results}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        return _job_json(get_job_or_404(job_id))

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str) -> None:
        get_job_or_404(job_id)
        try:
            job_queue.delete_job(job_id)
        except ValueError as e:
            raise HTTPException(409, str(e)) from None

    @app.get("/api/jobs/{job_id}/transcript")
    def get_transcript(job_id: str) -> dict:
        job = get_done_job(job_id)
        intervals = read_interval_transcript(job.deliverable_path)
        return {
            "job": _job_json(job),
            "version": document_version(job.deliverable_path),
            "interval_minutes": settings.interval_minutes,
            "speakers": sorted(extract_speakers_from_file(job.output_path)),
            "speaker_names": job.speaker_names,
            "intervals": intervals_to_dicts(intervals),
        }

    @app.put("/api/jobs/{job_id}/speakers")
    def set_speaker_names(job_id: str, body: SpeakerNamesBody) -> dict:
        job = get_done_job(job_id)
        labels = extract_speakers_from_file(job.output_path)
        unknown = set(body.names) - labels
        if unknown:
            raise HTTPException(422, f"unknown speaker labels: {sorted(unknown)}")
        desired = {label: clean_speaker_name(body.names.get(label, "")) or label for label in labels}
        if len(set(desired.values())) != len(desired):
            raise HTTPException(422, "two speakers can't have the same name")
        with edit_lock:
            job = job_queue.get_job(job_id)
            # Rename from each speaker's *current* display name to the new one,
            # in the working copy, so earlier cell edits are kept.
            current = {label: job.speaker_names.get(label, label) for label in labels}
            mapping = {current[label]: desired[label] for label in labels if current[label] != desired[label]}
            if mapping:
                path = working_copy(job)
                rename_speakers_in_file(path, mapping, path, rename=rename_tags_in_text)
            names = {label: name for label, name in desired.items() if name != label}
            job = job_queue.update_job(job_id, speaker_names=names)
        return _job_json(job)

    @app.get("/api/jobs/{job_id}/document")
    def get_document(job_id: str) -> dict:
        job = get_done_job(job_id)
        path = job.deliverable_path
        return {"version": document_version(path), **read_table(path)}

    @app.put("/api/jobs/{job_id}/document")
    def edit_document(job_id: str, body: DocumentEditBody) -> dict:
        get_done_job(job_id)
        with edit_lock:
            job = job_queue.get_job(job_id)
            if document_version(job.deliverable_path) != body.base_version:
                raise HTTPException(409, "the document changed since you opened it; reload to see the latest version")
            path = working_copy(job)
            try:
                apply_cell_edits(path, [CellEdit(e.row, e.col, e.text) for e in body.edits], path)
            except ValueError as e:
                raise HTTPException(422, str(e)) from None
            return {"version": document_version(path), **read_table(path)}

    @app.post("/api/jobs/{job_id}/document/revert")
    def revert_document(job_id: str) -> dict:
        """Discard all edits and speaker names: back to the pipeline output."""
        job = get_done_job(job_id)
        with edit_lock:
            if job.working_output_path is not None:
                job.working_output_path.unlink(missing_ok=True)
            job = job_queue.update_job(job_id, speaker_names={}, working_output_path=None)
        return _job_json(job)

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str) -> FileResponse:
        job = get_done_job(job_id)
        path = job.deliverable_path
        return FileResponse(path, media_type=DOCX_MEDIA_TYPE, filename=f"{Path(job.video_name).stem}_transcript.docx")

    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="ui")

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "tw.server:create_app",
        factory=True,
        host=os.environ.get("LOCALSCRIBE_HOST", "0.0.0.0"),
        port=int(os.environ.get("LOCALSCRIBE_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
