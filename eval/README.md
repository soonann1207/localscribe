# eval

## Overview

Two standalone evaluation scripts that measure pipeline quality against
public meeting datasets. They are not used by the app at runtime.

- `run_ami_eval.py`: streams one AMI meeting, stitches its clips into a WAV, runs `tw.transcribe` and `tw.diarize`, and prints WER and DER.
- `run_qmsum_eval.py`: feeds local QMSum transcripts to `tw.extract.extract_fields`, then grades each answer with the `tw.judge` LLM judge.

## Interface

- `run_ami_eval.fetch_meeting_rows(meeting_id, max_seconds) -> list[dict]`
- `run_ami_eval.reconstruct_audio(rows, output_path) -> list[dict]`
- `run_ami_eval.run_eval(meeting_id, max_seconds, save_details, speed_factor=1.0)`
- CLI: `uv run python eval/run_ami_eval.py --meeting-id EN2002c --max-seconds 240 [--save-details PATH] [--speed-factor F]`
- `run_qmsum_eval.load_examples(data_dir, limit) -> list[dict]`
- `run_qmsum_eval.run_eval(data_dir, limit, details_path)`
- CLI: `uv run python eval/run_qmsum_eval.py --data-dir samples/QMSum/data/Academic/test --limit 5 [--save-details PATH]`

## Invariants

- `fetch_meeting_rows`: raises `ValueError` if no rows match the meeting. Keeps only rows that end within `max_seconds` of the meeting's first utterance.
- `reconstruct_audio`: overlapping utterances are laid end to end, never padded. The sample rate is taken from the first row.
- `run_ami_eval.run_eval`: reads `HF_TOKEN` with no fallback. DER is computed against the re-timed rows.
- `run_qmsum_eval.run_eval`: a missing field is scored as `[NOT EXTRACTED]`. Raises `ZeroDivisionError` when no fields are found.

## Side Effects

- `run_ami_eval`: streams `edinburghcstr/ami` from the Hugging Face Hub, writes `samples/ami_eval/*.wav`, and optionally writes a details JSON.
- `run_qmsum_eval`: reads `*.json` from `--data-dir`, calls local Ollama (via `tw.extract.call_ollama`), and optionally writes a details JSON.

## Verification

- Install the extras with `uv sync --extra eval`, then run the scripts as shown above. There are no unit tests for this folder.
