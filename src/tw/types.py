from dataclasses import dataclass, replace


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class SpeakerSegment:
    start: float
    end: float
    speaker: str


@dataclass
class LabeledSegment:
    start: float
    end: float
    speaker: str
    text: str


def rescale_segment_times(segments: list, factor: float) -> list:
    if factor == 1.0:
        return list(segments)
    return [replace(seg, start=seg.start / factor, end=seg.end / factor) for seg in segments]
