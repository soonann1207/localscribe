Product Requirements Document

# Local Transcript Auto-Fill Tool

**Author:** Soon Ann Chua
**Status:** Draft — v2
**Last updated:** 2026-08-02

---

## 1. Overview

A fully local tool that takes a camera-recorded meeting/call video and a user-supplied template file, transcribes the recording on-device, and automatically fills the template's fields with the relevant content pulled from the transcript — with no audio, video, or transcript data ever leaving the local machine.

This is a time-saving tool, not a meeting-minutes generator. The problem it solves is the manual labor of listening to a recording and typing its content into a required document format by hand. The template is supplied per run, not fixed — different recording types (client calls, internal reviews, case notes, etc.) can use different templates.

This is also a personal portfolio project, intended to demonstrate hands-on experience with local LLM deployment and production-style reliability engineering (structured extraction, validation, controlled hallucination handling) for AI Engineer / Forward Deployed Engineer roles.

## 2. Problem Statement

After a recorded meeting or call, the content needs to end up in a specific document format — but getting it there today means manually listening to (or re-reading) the recording and typing the relevant parts into each field of that template by hand. This is slow, repetitive, and scales badly with recording length or volume. The goal is not to produce generic "meeting minutes" — it's to eliminate the manual transcription/data-entry step, regardless of what template the situation calls for.

## 3. Goals & Success Metrics

| Goal | Metric |
|---|---|
| Reduce time spent manually transcribing recordings into a document | Wall-clock time to produce a filled template drops substantially vs. manual transcription for an equivalent recording |
| Support any template, not one fixed format | Tool accepts a new/different template file per run without code changes |
| Fill template fields accurately from transcript content | Filled fields reflect what was actually said; no fabricated content |
| Handle missing information honestly | Fields with no relevant transcript content are explicitly marked as such, not invented |
| Run entirely on local hardware | Zero network calls to any third-party LLM or transcription API during processing |

## 4. Scope

### 4.1 In scope (v1)

- Accept two inputs per run: a video/audio recording, and a template file
- Extract audio from the video file and transcribe it locally
- Parse the template to identify its fillable fields (section headings)
- Use a local LLM to extract, per field, the relevant transcript content
- Explicitly mark fields with no matching content as "Not mentioned in recording" rather than generating plausible-sounding filler
- Validate that every field defined in the template has a corresponding (possibly empty/not-mentioned) entry in the model's output before writing the final file
- Retry the extraction step on invalid/incomplete model output, bounded to 2 attempts
- Output the original template, unchanged in structure, with each field's content filled in
- Speaker diarization on the extracted audio track (audio-only method), so extracted content can be attributed to a speaker label where relevant

### 4.2 Out of scope (v1)

- Scheduling, folder-watching, or any always-on background process
- Live meeting join (Zoom/Meet/Teams) — input is a pre-recorded file only
- Video-based active speaker detection (lip-sync/visual diarization) — audio-only diarization first; revisit only if accuracy proves insufficient
- Delivery via messaging apps (Telegram/Slack/etc.)
- Any agent framework or automation harness (e.g. OpenClaw)
- A single hardcoded template — template flexibility is a core requirement, not deferred

These are explicitly deferred rather than rejected; see Section 10.

## 5. User Stories

- As the user, I want to supply a recording and a template, and get the template back filled in, so I don't have to manually transcribe the recording's content by hand.
- As the user, I want to use different templates for different types of recordings (e.g. one for client calls, another for internal reviews), so the tool fits how I actually work instead of forcing one fixed format.
- As the user, I want fields with no relevant content in the recording to be clearly marked as such, so I don't mistake a fabricated answer for something that was actually said.
- As the user, I want the entire pipeline to run without any data leaving my machine, so I can use this on recordings I wouldn't be comfortable uploading to a cloud service.
- As the user, I want content attributed to who said it where possible, so filled fields like decisions or follow-ups aren't ambiguous about who's responsible.

## 6. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | System shall accept a video file path and a template file path as input |
| FR-2 | System shall extract the audio track from the video file |
| FR-3 | System shall transcribe the extracted audio to text using a local model |
| FR-4 | System shall parse the template file's section headings into a list of named fields to be filled |
| FR-5 | System shall use a local LLM to extract, for each identified field, the transcript content relevant to that field, as structured (JSON) output keyed by field name |
| FR-6 | System shall mark any field with no relevant transcript content as "Not mentioned in recording" instead of generating unsupported content |
| FR-7 | System shall validate that the model's output contains an entry for every field defined in the template before proceeding |
| FR-8 | On missing fields or invalid output, system shall re-prompt the model with the specific validation error, up to a maximum of 2 retries |
| FR-9 | If all retries are exhausted, system shall flag the recording for manual review rather than delivering incomplete output |
| FR-10 | System shall write the output using the original template's structure, with each field's heading preserved and its content filled in below it |
| FR-11 | System shall run speaker diarization on the extracted audio track, producing speaker-labeled time segments (e.g. `SPEAKER_00`, `SPEAKER_01`) |
| FR-12 | System shall align diarization segments with the transcript's timestamps to produce a speaker-labeled transcript, and use that labeled transcript as the source for field extraction |

## 7. Technical Architecture

| Layer | Component | Notes |
|---|---|---|
| Audio extraction | ffmpeg | Extracts mono WAV from the source video file |
| Transcription | faster-whisper | Local, Python-native, CPU-friendly |
| Speaker diarization | pyannote.audio 3.1 | Local, audio-only; requires a one-time gated HuggingFace download, runs offline after that |
| Diarization/transcript alignment | Hand-rolled (Python) | Merges pyannote's speaker segments with Whisper's timestamped output into a single speaker-labeled transcript |
| Template parsing | Hand-rolled (Python) | Reads section headings from the template file as the field list |
| Field extraction | Ollama, running Llama 3.3 8B | Local inference; structured/JSON output mode, one field-name-to-content mapping per template |
| Validation | Hand-rolled schema check (Python) | Confirms every template field has a corresponding entry in the model's output; drives the retry loop |
| Output assembly | Hand-rolled (Python) | Reinserts filled content into the original template structure |

Pipeline flow:

```
video file → ffmpeg (extract audio)
                 ├─→ faster-whisper (transcribe, timestamped)
                 └─→ pyannote.audio (diarize, speaker-labeled segments)
                            ↓
              align diarization + transcript → speaker-labeled transcript

template file → parse section headings → field list

[speaker-labeled transcript + field list] → Ollama (extract per-field content, JSON mode)
    → validate all fields present → [retry up to 2x on failure]
    → reassemble into template structure → output file
```

## 8. Non-Functional Requirements

- **Privacy:** No transcript, audio, or video data is sent to any external API at any pipeline stage. All inference is local.
- **Reliability:** Output must never claim a field was covered in the recording when it wasn't. Unrecoverable extraction failures must be surfaced explicitly, not silently guessed at.
- **Flexibility:** No template-specific logic should be hardcoded; any template following the heading-based field convention should work without code changes.
- **Performance:** No hard latency requirement for v1 (offline, on-demand processing is acceptable). A ~1 hour recording should complete well within the length of the recording itself on reasonable consumer hardware.
- **Portability:** Output format matches the input template's format — no proprietary viewer required.

## 9. Milestones

| Milestone | Deliverable |
|---|---|
| M1 | ffmpeg audio extraction + faster-whisper transcription working end-to-end on a sample recording |
| M2 | pyannote.audio diarization producing speaker-labeled segments on a sample recording |
| M3 | Diarization output aligned with Whisper transcript into a single speaker-labeled transcript |
| M4 | Template parser correctly identifies fields from a sample template file |
| M5 | Ollama field-extraction producing structured per-field content from the speaker-labeled transcript |
| M6 | Validation + retry logic in place; missing/invalid fields handled correctly |
| M7 | Output assembly reproduces the original template with fields filled, tested against a real recording and a real template |
| M8 (stretch) | Batch mode: process multiple recordings against the same template in one run |

## 10. Risks & Open Questions

| Risk / Question | Notes |
|---|---|
| Template convention (headings-as-fields) may not fit every format the user has | v1 assumes fields are marked by section headings; if real templates use a different structure (e.g. inline blanks, tables), the parser will need to be extended |
| Transcription accuracy on multi-speaker, in-room audio | Camera-captured audio is noisier than a clean per-participant call feed; may need a larger Whisper model or audio pre-processing if quality is poor |
| Diarization accuracy on single-mic, multi-speaker recordings | A single camera mic capturing a room is a harder diarization case than per-participant call feeds; audio-only clustering may confuse similar-sounding voices or split/merge speakers incorrectly. If this proves unreliable, video-based active speaker detection (Section 11) becomes worth revisiting |
| pyannote.audio requires a gated HuggingFace download | One-time setup friction (free account + token); no ongoing network dependency once the model is downloaded |
| Local hardware constraints | Llama 3.3 8B, faster-whisper, and pyannote.audio all need reasonable local compute; fallback to smaller models if needed |
| Field ambiguity | Some transcript content may plausibly belong to more than one field; extraction quality depends on how clearly the template's field names describe what's wanted |
| Retry loop could still fail | If the model consistently produces incomplete output after 2 retries, the recording is flagged rather than force-accepted — by design, but means some recordings may need manual handling |

## 11. Future Considerations (explicitly deferred)

- Scheduled/unattended processing (e.g. watch a folder automatically) — would reintroduce an automation layer such as OpenClaw's cron/trigger-script system, deferred until there's an actual need to run this unattended
- Video-based active speaker detection (lip-sync/visual diarization, e.g. TalkNet-ASD or Light-ASD) — only worth building if audio-only pyannote diarization proves inaccurate on real single-camera, single-mic recordings
- Delivery via Telegram or another messaging channel
- Support for non-heading-based template structures (tables, inline blanks, docx forms)
- Live meeting join support (Zoom/Meet/Teams) if the input source shifts from camera recordings to screen-shared calls
