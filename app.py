"""Streamlit UI for localscribe. Runs entirely on-device; upload a
recording, get the fixed coding-transcript template filled back.

Run: uv run streamlit run app.py
Access from other devices on your home network at http://<this-machine's-LAN-IP>:8501
"""

import tempfile
from pathlib import Path

import streamlit as st

from tw.cli import preflight_check
from tw.interval_transcript import run
from tw.speaker_rename import extract_speakers_from_file, rename_speakers_in_file

TEMPLATE_PATH = Path(__file__).parent / "templates" / "coding_transcription_template.docx"
INTERVAL_MINUTES = 5.0

st.set_page_config(page_title="localscribe", page_icon="🎙️")
st.title("localscribe")
st.caption("Fill the coding transcript template from a recording — fully local, nothing leaves this machine.")

problems = preflight_check()
if problems:
    for p in problems:
        st.error(p)
    st.stop()

st.session_state.setdefault("output_path", None)
st.session_state.setdefault("speakers", None)
st.session_state.setdefault("renamed_output_path", None)

st.download_button(
    "Download blank template",
    data=TEMPLATE_PATH.read_bytes(),
    file_name=TEMPLATE_PATH.name,
    help="For reference only — the app always uses this fixed template, you can't upload a different one.",
)

video_file = st.file_uploader("Video or audio recording", type=["mp4", "mov", "m4v", "wav", "m4a"])
speed_factor = st.slider(
    "Speed factor",
    min_value=1.0,
    max_value=2.0,
    value=1.0,
    step=0.5,
    help="Speeds up transcription/diarization. 1.0 = normal (most accurate). Higher = faster, unvalidated accuracy trade-off.",
)

if st.button("Run", type="primary", disabled=not video_file):
    # A persistent temp dir (not auto-deleted): the output file must still
    # exist on later reruns, e.g. when the rename form below is submitted.
    tmp = Path(tempfile.mkdtemp())
    video_path = tmp / video_file.name
    video_path.write_bytes(video_file.getvalue())

    with st.spinner("Processing — this can take a while for long recordings"):
        try:
            output_path = run(video_path, TEMPLATE_PATH, interval_minutes=INTERVAL_MINUTES, speed_factor=speed_factor)
        except Exception as e:
            st.error(f"Failed: {e}")
            st.stop()

    st.session_state.output_path = output_path
    st.session_state.speakers = sorted(extract_speakers_from_file(output_path))
    st.session_state.renamed_output_path = None

if st.session_state.output_path:
    st.success(f"Done: {st.session_state.output_path.name}")

    if st.session_state.speakers:
        st.subheader("Speakers detected")
        with st.form("rename_speakers_form"):
            new_names = {}
            for label in st.session_state.speakers:
                new_names[label] = st.text_input(label, value=label, key=f"name_{label}")
            renamed_submitted = st.form_submit_button("Apply names")

        if renamed_submitted:
            mapping = {old: new.strip() for old, new in new_names.items() if new.strip() and new.strip() != old}
            renamed_path = st.session_state.output_path.with_name(
                st.session_state.output_path.stem + "_renamed" + st.session_state.output_path.suffix
            )
            rename_speakers_in_file(st.session_state.output_path, mapping, renamed_path)
            st.session_state.renamed_output_path = renamed_path
            st.success("Names applied.")

    download_path = st.session_state.renamed_output_path or st.session_state.output_path
    st.download_button(
        "Download result",
        data=download_path.read_bytes(),
        file_name=download_path.name,
    )
