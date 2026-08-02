from pathlib import Path
from tw.types import SpeakerSegment


def _segments_from_annotation(annotation) -> list[SpeakerSegment]:
    segments = []
    for turn, _track_id, speaker in annotation.itertracks(yield_label=True):
        segments.append(SpeakerSegment(start=turn.start, end=turn.end, speaker=speaker))
    return segments


def diarize(audio_path: Path, hf_token: str) -> list[SpeakerSegment]:
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
    annotation = pipeline(str(audio_path))
    return _segments_from_annotation(annotation)
