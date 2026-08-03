"""AMI-corpus-based eval: reconstructs a short continuous audio clip from a
meeting's individually-clipped SDM (single distant mic) utterances, runs it
through our own transcribe()/diarize(), and scores against AMI's reference
transcript (WER) and reference speaker segments (DER).

Usage:
    uv run python eval/run_ami_eval.py --meeting-id EN2002c --max-seconds 240
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf
from datasets import load_dataset

from tw.ami_eval import build_hypothesis_annotation, build_reference_annotation, compute_der, compute_wer
from tw.audio import extract_audio
from tw.diarize import diarize
from tw.transcribe import transcribe
from tw.types import rescale_segment_times


def fetch_meeting_rows(meeting_id: str, max_seconds: float) -> list[dict]:
    # begin_time/end_time are absolute session time, not meeting-relative,
    # so we can't cut off by comparing them directly to max_seconds. Rows
    # for one meeting appear contiguously in the stream, so we collect the
    # whole block, then take a chronological prefix relative to its own start.
    ds = load_dataset("edinburghcstr/ami", "sdm", split="test", streaming=True)
    rows = []
    seen_target = False
    for row in ds:
        if row["meeting_id"] == meeting_id:
            rows.append(row)
            seen_target = True
        elif seen_target:
            break

    if not rows:
        raise ValueError(f"no rows found for meeting_id={meeting_id}")

    rows.sort(key=lambda r: r["begin_time"])
    start = rows[0]["begin_time"]
    return [r for r in rows if r["end_time"] - start <= max_seconds]


def reconstruct_audio(rows: list[dict], output_path: Path) -> list[dict]:
    sample_rate = rows[0]["audio"]["sampling_rate"]
    start_offset = rows[0]["begin_time"]
    chunks = []
    cursor_sec = 0.0
    adjusted_rows = []

    for row in rows:
        begin = row["begin_time"] - start_offset
        end = row["end_time"] - start_offset
        gap = max(0.0, begin - cursor_sec)
        if gap > 0:
            chunks.append(np.zeros(int(gap * sample_rate), dtype=np.float32))
            cursor_sec += gap

        audio = np.asarray(row["audio"]["array"], dtype=np.float32)
        chunks.append(audio)
        cursor_sec += len(audio) / sample_rate

        adjusted_rows.append({"begin_time": cursor_sec - len(audio) / sample_rate, "end_time": cursor_sec, "speaker_id": row["speaker_id"]})

    full_audio = np.concatenate(chunks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, full_audio, sample_rate)
    return adjusted_rows


def run_eval(meeting_id: str, max_seconds: float, save_details: Path | None, speed_factor: float = 1.0) -> None:
    print(f"Fetching {meeting_id} (up to {max_seconds}s) from AMI sdm test split...")
    rows = fetch_meeting_rows(meeting_id, max_seconds)
    print(f"Got {len(rows)} utterances, reconstructing continuous audio...")

    audio_path = Path("samples/ami_eval") / f"{meeting_id}.wav"
    adjusted_rows = reconstruct_audio(rows, audio_path)
    reference_text = " ".join(row["text"] for row in rows)

    transcribe_path = audio_path
    if speed_factor != 1.0:
        transcribe_path = Path("samples/ami_eval") / f"{meeting_id}_speed{speed_factor}.wav"
        print(f"Speeding up audio by {speed_factor}x...")
        extract_audio(audio_path, output_path=transcribe_path, speed_factor=speed_factor)

    print("Running transcribe()...")
    transcript = transcribe(transcribe_path)
    if speed_factor != 1.0:
        transcript = rescale_segment_times(transcript, speed_factor)
    hypothesis_text = " ".join(seg.text for seg in transcript)

    print("Running diarize()...")
    speakers = diarize(transcribe_path, os.environ["HF_TOKEN"])
    if speed_factor != 1.0:
        speakers = rescale_segment_times(speakers, speed_factor)

    wer = compute_wer(reference_text, hypothesis_text)
    ref_annotation = build_reference_annotation(adjusted_rows)
    hyp_annotation = build_hypothesis_annotation(speakers)
    der = compute_der(ref_annotation, hyp_annotation)

    print(f"\n=== {meeting_id} ({adjusted_rows[-1]['end_time']:.0f}s reconstructed, speed_factor={speed_factor}) ===")
    print(f"WER (word error rate): {wer:.1%}")
    print(f"DER (diarization error rate): {der:.1%}")
    print(f"reference word count: {len(reference_text.split())}")
    print(f"hypothesis word count: {len(hypothesis_text.split())}")

    if save_details:
        import jiwer

        word_output = jiwer.process_words(reference_text, hypothesis_text)
        save_details.parent.mkdir(parents=True, exist_ok=True)
        save_details.write_text(
            json.dumps(
                {
                    "reference_text": reference_text,
                    "hypothesis_text": hypothesis_text,
                    "hits": word_output.hits,
                    "substitutions": word_output.substitutions,
                    "insertions": word_output.insertions,
                    "deletions": word_output.deletions,
                },
                indent=2,
            )
        )
        print(f"Details written to {save_details}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting-id", default="EN2002c")
    parser.add_argument("--max-seconds", type=float, default=240.0)
    parser.add_argument("--save-details", type=Path, default=None)
    parser.add_argument("--speed-factor", type=float, default=1.0)
    args = parser.parse_args()
    run_eval(args.meeting_id, args.max_seconds, args.save_details, args.speed_factor)
