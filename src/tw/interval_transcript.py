import argparse
import os
import re
from pathlib import Path

from docx import Document

_INT_ROW_RE = re.compile(r"^Int (\d+)$")


def fill_interval_table(template_path: Path, buckets: dict[int, str], output_path: Path) -> Path:
    doc = Document(template_path)
    table = doc.tables[0]

    header = [c.text.strip() for c in table.rows[0].cells]
    transcription_col = header.index("Transcription")

    for row in table.rows[1:]:
        match = _INT_ROW_RE.match(row.cells[0].text.strip())
        if not match:
            continue
        interval_num = int(match.group(1))
        row.cells[transcription_col].text = buckets.get(interval_num, "Not mentioned in recording")

    doc.save(output_path)
    return output_path


def run(video_path: Path, template_path: Path, interval_minutes: float = 5.0, speed_factor: float = 1.0) -> Path:
    # Local imports: keeps this module importable (and its pure fill_interval_table
    # testable) without faster-whisper/pyannote/ffmpeg installed.
    from tw.align import align, bucket_by_interval
    from tw.audio import extract_audio
    from tw.diarize import diarize
    from tw.transcribe import transcribe
    from tw.types import rescale_segment_times

    audio_path = extract_audio(video_path, speed_factor=speed_factor)
    transcript = transcribe(audio_path)
    speakers = diarize(audio_path, os.environ["HF_TOKEN"])
    transcript = rescale_segment_times(transcript, speed_factor)
    speakers = rescale_segment_times(speakers, speed_factor)
    labeled = align(transcript, speakers)

    buckets = bucket_by_interval(labeled, interval_seconds=interval_minutes * 60)

    output_path = template_path.with_name(template_path.stem + "_filled.docx")
    return fill_interval_table(template_path, buckets, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--interval-minutes", type=float, default=5.0)
    parser.add_argument("--speed-factor", type=float, default=1.0)
    args = parser.parse_args()

    output_path = run(args.video, args.template, args.interval_minutes, args.speed_factor)
    print(f"wrote {output_path}")
