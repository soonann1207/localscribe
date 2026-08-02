from pathlib import Path
from tw.types import TranscriptSegment


def _segments_from_whisper(raw_segments) -> list[TranscriptSegment]:
    return [TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()) for s in raw_segments]


def transcribe(audio_path: Path, model_size: str = "medium") -> list[TranscriptSegment]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    raw_segments, _info = model.transcribe(str(audio_path))
    return _segments_from_whisper(raw_segments)
