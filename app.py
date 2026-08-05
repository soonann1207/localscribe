"""Streamlit UI for localscribe. Runs entirely on-device; upload a
recording + template, get the filled document back.

Run: uv run streamlit run app.py
Access from other devices on your home network at http://<this-machine's-LAN-IP>:8501
"""

import tempfile
from pathlib import Path

import streamlit as st

from tw.cli import preflight_check
from tw.pipeline import run

st.set_page_config(page_title="localscribe", page_icon="🎙️")
st.title("localscribe")
st.caption("Fill a template from a recorded meeting/call — fully local, nothing leaves this machine.")

problems = preflight_check()
if problems:
    for p in problems:
        st.error(p)
    st.stop()

video_file = st.file_uploader("Video or audio recording", type=["mp4", "mov", "m4v", "wav", "m4a"])
template_file = st.file_uploader("Template (Markdown or Word)", type=["md", "docx"])
speed_factor = st.slider(
    "Speed factor",
    min_value=1.0,
    max_value=2.0,
    value=1.0,
    step=0.5,
    help="Speeds up transcription/diarization. 1.0 = normal (most accurate). Higher = faster, unvalidated accuracy trade-off.",
)

if st.button("Run", type="primary", disabled=not (video_file and template_file)):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video_path = tmp / video_file.name
        video_path.write_bytes(video_file.getvalue())
        template_path = tmp / template_file.name
        template_path.write_bytes(template_file.getvalue())

        with st.spinner("Processing — this can take a while for long recordings"):
            try:
                output_path = run(video_path, template_path, speed_factor=speed_factor)
            except Exception as e:
                st.error(f"Failed: {e}")
                st.stop()

        st.success(f"Done: {output_path.name}")
        st.download_button(
            "Download result",
            data=output_path.read_bytes(),
            file_name=output_path.name,
        )
