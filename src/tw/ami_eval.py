from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate

from tw.types import SpeakerSegment


def _normalization_transform():
    import jiwer

    return jiwer.Compose(
        [
            jiwer.ExpandCommonEnglishContractions(),
            jiwer.ToLowerCase(),
            jiwer.RemovePunctuation(),
            jiwer.RemoveMultipleSpaces(),
            jiwer.Strip(),
            jiwer.ReduceToListOfListOfWords(),
        ]
    )


def compute_wer(reference: str, hypothesis: str) -> float:
    import jiwer

    transform = _normalization_transform()
    return jiwer.wer(reference, hypothesis, reference_transform=transform, hypothesis_transform=transform)


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
