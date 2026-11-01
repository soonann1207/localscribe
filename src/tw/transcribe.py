from functools import lru_cache
from pathlib import Path

from tw.types import TranscriptSegment


def _segments_from_whisper(raw_segments) -> list[TranscriptSegment]:
    return [TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()) for s in raw_segments]


@lru_cache(maxsize=2)
def _load_model(model_size: str):
    # Loading the medium model takes seconds and ~1.5GB RAM; the job queue
    # runs jobs back-to-back in one process, so reuse it across jobs.
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: Path, model_size: str = "medium", language: str = "en") -> list[TranscriptSegment]:
    model = _load_model(model_size)
    raw_segments, _info = model.transcribe(str(audio_path), language=language)
    return _segments_from_whisper(raw_segments)


def release_model() -> None:
    _load_model.cache_clear()
