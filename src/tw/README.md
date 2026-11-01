# tw

## Overview

The `tw` package is the local pipeline. It turns a recorded meeting or call
into a filled document, entirely on-device. It extracts audio with ffmpeg,
transcribes with faster-whisper, diarizes speakers with pyannote, and aligns
transcript segments to speakers. It then does one of two things:

- fills a DOCX interval table with per-interval transcripts (`interval_transcript.py`, used by the web UI), or
- fills Markdown/DOCX template headings from fields extracted by a local Ollama LLM (`pipeline.py`, used by the CLI).

It also provides the web app's HTTP API (`server.py`), a thread-backed job
queue, transcript preview parsing, in-place DOCX cell editing, speaker
renaming, and evaluation helpers (WER/DER, LLM-judge verdicts).

## Interface

Data types (`types.py`)
- `TranscriptSegment(start, end, text)`, `SpeakerSegment(start, end, speaker)`, `LabeledSegment(start, end, speaker, text)`: dataclasses.
- `rescale_segment_times(segments, factor) -> list`

Pipeline stages
- `audio.extract_audio(video_path, output_path=None, speed_factor=1.0) -> Path`
- `transcribe.transcribe(audio_path, model_size="medium", language="en") -> list[TranscriptSegment]`, `transcribe.release_model()`
- `diarize.diarize(audio_path, hf_token) -> list[SpeakerSegment]`, `diarize.release_pipeline()`
- `align.align(transcript, speakers) -> list[LabeledSegment]`
- `align.format_transcript(segments) -> str`
- `align.bucket_by_interval(segments, interval_seconds=300.0) -> dict[int, str]`

Interval-transcript pipeline (web UI)
- `interval_transcript.fill_interval_table(template_path, buckets, output_path) -> Path`
- `interval_transcript.run(video_path, template_path, interval_minutes=5.0, speed_factor=1.0) -> Path`
- `interval_transcript.release_models()`: frees the cached models, runs `gc` and `malloc_trim`
- `python -m tw.interval_transcript --video --template [--interval-minutes] [--speed-factor]`

Field-extraction pipeline (CLI)
- `pipeline.run(video_path, template_path, speed_factor=1.0) -> Path`
- `template.parse_fields(template_path) -> list[str]`, `template.HEADING_RE`
- `docx_template.parse_fields_docx(template_path) -> list[str]`
- `docx_template.assemble_docx(template_path, filled, failed_fields, output_path) -> Path`
- `assemble.assemble(template_path, filled, failed_fields) -> str`, `assemble.HEADING_RE`
- `extract.extract_fields(labeled_transcript, fields, call_model) -> ExtractResult`
- `extract.build_prompt(...)`, `extract.call_ollama(prompt, model="llama3.1:8b") -> str`
- `extract.ExtractResult(filled, failed_fields)`, `extract.MAX_RETRIES = 2`
- `validate.validate(output, fields) -> ValidationResult`, `validate.ValidationResult(ok, missing, invalid)`
- `cli.parse_args(argv)` with flags `--video`, `--template`, `--speed-factor`
- `cli.preflight_check(require_ollama=True) -> list[str]`, `cli.main(argv) -> int`

Web server (`server.py`)
- `create_app(settings=None, run_fn=None, preflight=None, on_idle=None) -> FastAPI`, `main()` (the `localscribe-server` script)
- `Settings` (from `LOCALSCRIBE_*` env vars), `safe_filename(name)`, `document_version(path)`
- Routes: `GET /api/health`, `GET /api/template`, `GET|POST /api/jobs`, `GET|DELETE /api/jobs/{id}`, `GET /api/jobs/{id}/transcript`, `PUT /api/jobs/{id}/speakers`, `GET|PUT /api/jobs/{id}/document`, `POST /api/jobs/{id}/document/revert`, `GET /api/jobs/{id}/download`. Serves `frontend/dist` at `/`.

Preview and editing
- `transcript_preview.read_interval_transcript(path) -> list[Interval]`, `parse_turns(text) -> list[Turn]`, `intervals_to_dicts(...)`
- `doc_edit.read_table(path) -> {header, rows}`, `apply_cell_edits(path, edits, output_path)`, `set_cell_text(cell, text)`, `CellEdit(row, col, text)`

Job queue (`job_queue.py`)
- `JobStatus = Literal["queued", "processing", "done", "error"]`
- `Job(id, video_name, status, output_path, error, submitted_at, started_at, finished_at, speaker_names, working_output_path)`, `Job.deliverable_path`, `to_dict()` / `from_dict()`
- `JobQueue(run_fn, max_active=5, workdir=None, output_dir=None, on_idle=None)` with `submit(..., cleanup_dir=None) -> str`, `get_job`, `list_jobs`, `update_job(job_id, **changes)`, `delete_job(job_id)`

Speaker renaming (`speaker_rename.py`)
- `extract_speaker_labels(text) -> set[str]`, `rename_speakers_in_text(text, mapping) -> str`
- `rename_tags_in_text(text, mapping)`: renames arbitrary `[name]` tags at once, so swaps work
- `clean_speaker_name(name) -> str`
- `extract_speakers_from_file(path) -> set[str]`, `rename_speakers_in_file(path, mapping, output_path, rename=rename_speakers_in_text) -> Path`

Evaluation helpers
- `ami_eval.compute_wer`, `ami_eval.compute_der`, `ami_eval.build_reference_annotation`, `ami_eval.build_hypothesis_annotation`
- `judge.build_judge_prompt`, `judge.parse_verdict`, `judge.judge_match`

## Invariants

- `align.align`: the speaker with the largest overlap wins. Overlap must be strictly greater than the current best, so ties go to the first speaker. A segment with no positive overlap is labeled `UNKNOWN`.
- `align.format_transcript`: consecutive same-speaker segments merge into one turn, formatted `[HH:MM:SS] [speaker] text`, with turns separated by a blank line. `speaker_rename._SPEAKER_TAG_RE` and transcript previews depend on this format.
- `align.bucket_by_interval`: a segment's 1-based interval is `int(start // interval_seconds) + 1`, so it is bucketed by start time only.
- `interval_transcript.fill_interval_table`: uses `doc.tables[0]`. Raises `ValueError` if the header has no `Transcription` column. Removes `Int N` rows that have no speech and appends rows for intervals not in the template.
- `audio.extract_audio`: raises `ValueError` if `output_path == video_path`, and `RuntimeError("ffmpeg could not read ...")` on decode failure. Output is mono, 16 kHz, with the video stream skipped.
- `interval_transcript.run`: writes `<video_stem>_filled.docx` next to the input recording, never into `templates/`. It always deletes the intermediate WAV.
- `assemble.assemble` and `docx_template.assemble_docx`: raise `ValueError` for a heading that is in neither `filled` nor `failed_fields`. `failed_fields` takes priority.
- `extract.extract_fields`: makes at most `MAX_RETRIES + 1` model calls and keeps valid fields across attempts.
- `JobQueue.submit`: raises `RuntimeError("queue full: ...")` once `max_active` jobs are queued or processing. A single worker thread processes jobs FIFO.
- `JobQueue._load_jobs`: jobs that were `queued` or `processing` at load time become `error` ("interrupted by server restart"). An unparseable `jobs.json` is renamed to `jobs.json.corrupt`.
- `JobQueue.delete_job`: raises `ValueError` for queued or processing jobs. `JobQueue.update_job` only accepts `speaker_names` and `working_output_path`.
- `JobQueue`: `on_idle` runs on the worker thread after a job when nothing else is queued. Its exceptions are swallowed.
- `server`: renames and cell edits only touch the working copy, never `output_path`. `PUT /document` returns 409 when `base_version` is not the current `document_version`. `PUT /speakers` returns 422 for unknown labels or duplicate names.
- `doc_edit.apply_cell_edits`: row 0 (the header) and out-of-range cells raise `ValueError`.
- `JobQueue.get_job`: raises `KeyError` for an unknown id.
- `speaker_rename`: only `[SPEAKER_<n>]` and `[UNKNOWN]` tags are recognized.
- `pipeline.run` and `interval_transcript.run`: read `os.environ["HF_TOKEN"]` and raise `KeyError` if it is unset.

## Side Effects

- `audio.extract_audio`: runs the `ffmpeg` subprocess and writes a `.wav` file (by default next to the input).
- `transcribe.transcribe` and `diarize.diarize`: download and load models (faster-whisper `medium`; `pyannote/speaker-diarization-3.1`, gated, which needs `HF_TOKEN`).
- `extract.call_ollama`: calls the local Ollama server.
- `cli.preflight_check`: reads `HF_TOKEN`, checks `PATH`, and runs `ollama list`.
- `pipeline.run` (CLI): writes `<template_stem>_filled.(md|docx)` next to the template.
- `transcribe` and `diarize`: keep loaded models in an `lru_cache` until `release_*()` is called.
- `JobQueue`: creates `workdir` and `output_dir`, starts a daemon worker thread, atomically rewrites `<workdir>/jobs.json` (temp file + `os.replace`) on every state change, copies results to `<output_dir>/<job_id>_<name>`, and deletes the input video and `cleanup_dir` after each job.
- `server`: streams uploads to `<data_dir>/uploads/job_*/` and deletes stale ones at startup. Writes working copies to `<output_dir>/<job_id>_working.docx`.
- `speaker_rename.rename_speakers_in_file`: writes `output_path`.

## Verification

- Run: `uv run pytest`
