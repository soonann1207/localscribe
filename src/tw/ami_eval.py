from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate

from tw.types import SpeakerSegment


def compute_wer(reference: str, hypothesis: str) -> float:
    import jiwer

    return jiwer.wer(reference, hypothesis)


def build_reference_annotation(rows: list[dict]) -> Annotation:
    annotation = Annotation()
    for row in rows:
        annotation[Segment(row["begin_time"], row["end_time"])] = row["speaker_id"]
    return annotation


def build_hypothesis_annotation(segments: list[SpeakerSegment]) -> Annotation:
    annotation = Annotation()
    for seg in segments:
        annotation[Segment(seg.start, seg.end)] = seg.speaker
    return annotation


def compute_der(reference: Annotation, hypothesis: Annotation) -> float:
    metric = DiarizationErrorRate()
    return metric(reference, hypothesis)
