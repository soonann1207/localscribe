from dataclasses import dataclass


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
