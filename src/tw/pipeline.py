import os
from pathlib import Path

from tw.align import align, format_transcript
from tw.assemble import assemble
from tw.audio import extract_audio
from tw.diarize import diarize
from tw.docx_template import assemble_docx, parse_fields_docx
from tw.extract import call_ollama, extract_fields
from tw.template import parse_fields
from tw.transcribe import transcribe
from tw.types import rescale_segment_times


def run(video_path: Path, template_path: Path, speed_factor: float = 1.0) -> Path:
    is_docx = template_path.suffix.lower() == ".docx"
    fields = parse_fields_docx(template_path) if is_docx else parse_fields(template_path)
    if not fields:
        raise ValueError(f"template has no headings/fields: {template_path}")

    audio_path = extract_audio(video_path, speed_factor=speed_factor)
    transcript = transcribe(audio_path)
    speakers = diarize(audio_path, os.environ["HF_TOKEN"])
    transcript = rescale_segment_times(transcript, speed_factor)
    speakers = rescale_segment_times(speakers, speed_factor)
    labeled = align(transcript, speakers)
    labeled_text = format_transcript(labeled)

    extract_field_names = [f for f in fields if f != "Raw Transcript"]
    result = extract_fields(labeled_text, extract_field_names, call_model=call_ollama)

    filled = dict(result.filled)
    if "Raw Transcript" in fields:
        filled["Raw Transcript"] = labeled_text

    if is_docx:
        output_path = template_path.with_name(template_path.stem + "_filled.docx")
        assemble_docx(template_path, filled, result.failed_fields, output_path)
    else:
        output_text = assemble(template_path, filled, result.failed_fields)
        output_path = template_path.with_name(template_path.stem + "_filled.md")
        output_path.write_text(output_text)
    return output_path
