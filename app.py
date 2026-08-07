"""Streamlit UI for localscribe. Runs entirely on-device; upload a
recording, get the fixed coding-transcript template filled back.

Processing is serialized through a single background worker (queue of
up to MAX_ACTIVE_JOBS), shared across everyone on the LAN using this
app — not per-browser-tab. Uploaded videos are deleted once a job
finishes; only the filled output is kept, in-memory, for download.

Run: uv run streamlit run app.py
Access from other devices on your home network at http://<this-machine's-LAN-IP>:8501
"""

import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from tw.cli import preflight_check
from tw.interval_transcript import run as run_interval_transcript
from tw.job_queue import JobQueue
from tw.speaker_rename import extract_speakers_from_file, rename_speakers_in_file

TEMPLATE_PATH = Path(__file__).parent / "templates" / "coding_transcription_template.docx"
INTERVAL_MINUTES = 5.0
MAX_ACTIVE_JOBS = 5

st.set_page_config(page_title="localscribe", page_icon="🎙️")
st.title("localscribe")
st.caption("Fill the coding transcript template from a recording — fully local, nothing leaves this machine.")

problems = preflight_check()
if problems:
    for p in problems:
        st.error(p)
    st.stop()


@st.cache_resource
def get_job_queue() -> JobQueue:
    # Shared across every session connected to this app instance (this is
    # the "shared resource" case for st.cache_resource, not per-user state).
    # Project-relative, not system temp: outputs and jobs.json need to
    # survive across app restarts, and macOS periodically sweeps /tmp.
    workdir = Path(__file__).parent / "job_queue_data"
    return JobQueue(run_fn=run_interval_transcript, max_active=MAX_ACTIVE_JOBS, workdir=workdir)


job_queue = get_job_queue()

st.session_state.setdefault("renamed_output_paths", {})  # job_id -> renamed Path
st.session_state.setdefault("uploader_key", 0)

st.download_button(
    "Download blank template",
    data=TEMPLATE_PATH.read_bytes(),
    file_name=TEMPLATE_PATH.name,
    help="For reference only — the app always uses this fixed template, you can't upload a different one.",
)

video_files = st.file_uploader(
    "Video or audio recording(s)",
    type=["mp4", "mov", "m4v", "wav", "m4a"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}",
)
SPEED_FACTOR = 1.0  # removed from UI: not validated as reliable yet, see AMI eval harness

if st.button("Queue", type="primary", disabled=not video_files):
    for video_file in video_files:
        tmp = Path(tempfile.mkdtemp())
        video_path = tmp / video_file.name
        video_path.write_bytes(video_file.getvalue())
        try:
            job_queue.submit(video_path, video_file.name, TEMPLATE_PATH, INTERVAL_MINUTES, SPEED_FACTOR)
            st.success(f"Queued: {video_file.name}")
        except RuntimeError as e:
            st.error(f"{video_file.name}: {e}")
    # Bump the uploader's key so it resets to empty on the natural rerun
    # that already follows a button click. An explicit st.rerun() here
    # collides with the run_every fragment below (stale fragment-id spam
    # in the server log), so don't add one.
    st.session_state.uploader_key += 1


@st.fragment(run_every="3s")
def show_jobs():
    jobs = job_queue.list_jobs()
    if not jobs:
        return

    st.subheader("Jobs")
    for job in reversed(jobs):
        submitted = datetime.fromtimestamp(job.submitted_at).strftime("%H:%M:%S")
        with st.container(border=True):
            st.write(f"**{job.video_name}** — {job.status} (queued {submitted})")

            if job.status == "error":
                st.error(job.error)

            if job.status == "done":
                speakers = sorted(extract_speakers_from_file(job.output_path))
                if speakers:
                    with st.form(f"rename_form_{job.id}"):
                        new_names = {label: st.text_input(label, value=label, key=f"name_{job.id}_{label}") for label in speakers}
                        submitted_rename = st.form_submit_button("Apply names")
                    if submitted_rename:
                        mapping = {old: new.strip() for old, new in new_names.items() if new.strip() and new.strip() != old}
                        renamed_path = job.output_path.with_name(job.output_path.stem + "_renamed" + job.output_path.suffix)
                        rename_speakers_in_file(job.output_path, mapping, renamed_path)
                        st.session_state.renamed_output_paths[job.id] = renamed_path
                        st.success("Names applied.")

                download_path = st.session_state.renamed_output_paths.get(job.id, job.output_path)
                download_name = f"{Path(job.video_name).stem}_transcript{download_path.suffix}"
                st.download_button(
                    "Download result",
                    data=download_path.read_bytes(),
                    file_name=download_name,
                    key=f"download_{job.id}",
                )


show_jobs()
