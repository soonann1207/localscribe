from functools import lru_cache
from pathlib import Path

from tw.types import SpeakerSegment


def _segments_from_annotation(annotation) -> list[SpeakerSegment]:
    segments = []
    for turn, _track_id, speaker in annotation.itertracks(yield_label=True):
        segments.append(SpeakerSegment(start=turn.start, end=turn.end, speaker=speaker))
    return segments


@lru_cache(maxsize=1)
def _load_pipeline(hf_token: str):
    # pyannote.audio >= 4 API (token=, .speaker_diarization); see pyproject pin.
    from pyannote.audio import Pipeline

    return Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)


def diarize(audio_path: Path, hf_token: str) -> list[SpeakerSegment]:
    output = _load_pipeline(hf_token)(str(audio_path))
    return _segments_from_annotation(output.speaker_diarization)


def release_pipeline() -> None:
    _load_pipeline.cache_clear()
