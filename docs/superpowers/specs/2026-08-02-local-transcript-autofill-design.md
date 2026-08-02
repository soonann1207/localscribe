# Local Transcript Auto-Fill Tool — Design

**Date:** 2026-08-02
**Status:** Approved for planning
**Source PRD:** `../../../Local Meeting Summarizer - PRD.md`

## Purpose

Scope the full v1 pipeline (PRD milestones M1–M7) into a concrete implementation
design: project structure, module interfaces, and the implementation-level
decisions the PRD leaves open.

## Environment

- Target machine: M4 Mac Mini, 32GB RAM, macOS 26.5.1
- No CUDA. `faster-whisper` (CTranslate2) runs CPU-only on Apple Silicon —
  fast enough on M4 for `medium` / `distil-large-v3` well under real-time.
- Ollama uses Metal natively on Apple Silicon — Llama 3.3 8B runs fast, 32GB
  RAM leaves headroom to run whisper + pyannote + ollama without swapping.
- `ffmpeg` not yet installed on dev machine (`brew install ffmpeg` needed).
- `ollama` installed; Llama 3.3 8B not yet pulled.
- pyannote.audio gated HuggingFace model: no token set up yet (part of M2).

## Project structure

uv-managed Python package:

```
transcription_workflow/
  pyproject.toml
  src/tw/
    cli.py         # argparse entry: --video, --template
    audio.py       # ffmpeg extraction
    transcribe.py  # faster-whisper wrapper
    diarize.py     # pyannote.audio wrapper
    align.py       # merge transcript + speaker segments
    template.py    # parse markdown headings -> field list
    extract.py     # Ollama structured extraction + retry loop
    validate.py    # schema check (drives retry)
    assemble.py    # reinsert content into template, mark failed fields
    pipeline.py    # orchestrates the above per PRD flow diagram
  tests/
    test_align.py
    test_template.py
    test_validate.py
    test_assemble.py
    fixtures/
  docs/superpowers/specs/
  .env.example     # HF_TOKEN, OLLAMA_MODEL
```

Each pipeline stage is one module with one primary function. `align.py`,
`template.py`, `validate.py`, and `assemble.py` are pure (no external
process/model calls) and unit-testable in isolation. `audio.py`,
`transcribe.py`, `diarize.py`, and `extract.py` wrap external
tools/models and are exercised via a manual integration test, not the
default fast suite.

## Module interfaces

- `audio.extract_audio(video_path: Path) -> Path`
  Extracts mono 16kHz WAV via ffmpeg.
- `transcribe.transcribe(audio_path: Path) -> list[TranscriptSegment]`
  `TranscriptSegment(start: float, end: float, text: str)` via faster-whisper.
- `diarize.diarize(audio_path: Path, hf_token: str) -> list[SpeakerSegment]`
  `SpeakerSegment(start: float, end: float, speaker: str)` via pyannote.audio,
  auto-detected speaker count (no fixed count input).
- `align.align(transcript: list[TranscriptSegment], speakers: list[SpeakerSegment]) -> list[LabeledSegment]`
  `LabeledSegment(start, end, speaker, text)`. Segment-level majority-overlap:
  each transcript segment is assigned the speaker with the most time-overlap
  in that segment's window.
- `template.parse_fields(template_path: Path) -> list[str]`
  Reads markdown heading lines as ordered field names.
- `extract.extract_fields(labeled_transcript: str, fields: list[str], model: str) -> ExtractResult`
  Single Ollama call (JSON mode) returning one object keyed by all field
  names. Internally retries on validation failure per below.
- `validate.validate(output: dict, fields: list[str]) -> ValidationResult`
  `ValidationResult(ok: bool, missing: list[str], invalid: list[str])`.
- `assemble.assemble(template_path: Path, filled: dict[str, str], failed_fields: list[str]) -> str`
  Reinserts content under each heading; failed fields get
  `[NEEDS MANUAL REVIEW]` instead of fabricated content.
- `pipeline.run(video_path: Path, template_path: Path) -> Path`
  Orchestrates all stages per the PRD flow diagram, returns output file path.

## Key implementation decisions (not fixed by PRD)

1. **Alignment strategy**: segment-level majority-overlap, not word-level.
   Simpler, and Whisper segments are sentence-length so boundary error is
   rarely more than one sentence.
2. **Extraction call shape**: one Ollama call per recording producing a
   single JSON object with all field keys — not one call per field. Matches
   FR-5's "one field-name-to-content mapping", fewer calls, consistent
   context across fields.
3. **Retry strategy (FR-8)**: full re-prompt each retry — resend transcript +
   field list + the specific validation error (which fields missing/invalid).
   Stateless and simple; Llama 3.3 8B's context window comfortably fits a
   ~1hr meeting transcript plus field list.
4. **Failure handling (FR-9)**: after 2 exhausted retries, only the
   still-failing fields are marked `[NEEDS MANUAL REVIEW]` in the output
   file — the rest of the successfully extracted fields are still written.
   A summary banner at the top of the output lists which fields need review.
   (Chosen over refusing to write any output at all, to keep partial
   successful extraction usable.)
5. **Preflight check**: CLI validates ffmpeg/ollama/model availability
   before starting any processing, fails fast with a clear message rather
   than partway through a long transcription run.
6. **Diarization speaker count**: auto-detected by pyannote, no
   `--num-speakers` flag in v1 — matches the "different recording types"
   flexibility goal without extra CLI surface.
7. **CLI**: stdlib `argparse`, two required args (`--video`, `--template`).
   No extra CLI framework dependency.
8. **Template format (v1)**: Markdown only. Headings define fields; content
   after upstream heading and before the next heading is that field's slot.

## Testing approach

- TDD on the four pure modules (`align`, `template`, `validate`, `assemble`)
  — deterministic, no external services, run in the default fast suite.
- `audio`, `transcribe`, `diarize`, `extract`, and `pipeline` get a manual
  integration test using a real sample recording + template (user-supplied),
  run on demand — not part of the default fast suite since it needs
  ffmpeg/faster-whisper/pyannote/ollama installed and models downloaded.

## Milestone order

Unchanged from PRD Section 9 (M1–M7); each milestone maps to one or two of
the modules above, giving incremental, independently testable slices:

- M1: `audio.py` + `transcribe.py`
- M2: `diarize.py` (+ HF token setup)
- M3: `align.py`
- M4: `template.py`
- M5: `extract.py`
- M6: `validate.py` + retry loop in `extract.py`
- M7: `assemble.py` + `pipeline.py` end-to-end, tested against real data
- M8 (stretch, out of this spec's scope): batch mode

## Out of scope (per PRD Section 4.2 / 11)

Unchanged from PRD — no scheduling, no live meeting join, no video-based
diarization, no messaging delivery, no agent framework, no non-markdown
template formats, no fixed speaker count input.
