import os
from pathlib import Path

from tw.align import align
from tw.assemble import assemble
from tw.audio import extract_audio
from tw.diarize import diarize
from tw.extract import call_ollama, extract_fields
from tw.template import parse_fields
from tw.transcribe import transcribe


def run(video_path: Path, template_path: Path) -> Path:
    audio_path = extract_audio(video_path)
    transcript = transcribe(audio_path)
    speakers = diarize(audio_path, os.environ["HF_TOKEN"])
    labeled = align(transcript, speakers)
    labeled_text = "\n".join(f"[{seg.speaker}] {seg.text}" for seg in labeled)

    fields = parse_fields(template_path)
    result = extract_fields(labeled_text, fields, call_model=call_ollama)

    output_text = assemble(template_path, result.filled, result.failed_fields)
    output_path = template_path.with_name(template_path.stem + "_filled.md")
    output_path.write_text(output_text)
    return output_path
