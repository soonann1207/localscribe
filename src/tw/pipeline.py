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
    fields = parse_fields(template_path)
    if not fields:
        raise ValueError(f"template has no headings/fields: {template_path}")

    audio_path = extract_audio(video_path)
    transcript = transcribe(audio_path)
    speakers = diarize(audio_path, os.environ["HF_TOKEN"])
    labeled = align(transcript, speakers)
    labeled_text = "\n".join(f"[{seg.speaker}] {seg.text}" for seg in labeled)

    extract_field_names = [f for f in fields if f != "Raw Transcript"]
    result = extract_fields(labeled_text, extract_field_names, call_model=call_ollama)

    filled = dict(result.filled)
    if "Raw Transcript" in fields:
        filled["Raw Transcript"] = labeled_text

    output_text = assemble(template_path, filled, result.failed_fields)
    output_path = template_path.with_name(template_path.stem + "_filled.md")
    output_path.write_text(output_text)
    return output_path
