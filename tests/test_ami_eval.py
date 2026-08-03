from pyannote.core import Annotation, Segment

from tw.ami_eval import build_hypothesis_annotation, build_reference_annotation, compute_der, compute_wer
from tw.types import SpeakerSegment


def test_compute_wer_identical_strings_is_zero():
    assert compute_wer("hello there world", "hello there world") == 0.0


def test_compute_wer_counts_substitutions():
    wer = compute_wer("hello there world", "hello there earth")
    assert wer > 0.0


def test_compute_wer_ignores_case_and_punctuation():
    reference = "HELLO THERE WORLD"
    hypothesis = "Hello, there world."
    assert compute_wer(reference, hypothesis) == 0.0


def test_build_reference_annotation_from_rows():
    rows = [
        {"begin_time": 0.0, "end_time": 1.0, "speaker_id": "A"},
        {"begin_time": 1.0, "end_time": 2.5, "speaker_id": "B"},
    ]
    annotation = build_reference_annotation(rows)
    assert isinstance(annotation, Annotation)
    labels = list(annotation.itertracks(yield_label=True))
    assert len(labels) == 2
    assert labels[0][2] == "A"
    assert labels[1][2] == "B"


def test_build_hypothesis_annotation_from_speaker_segments():
    segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker="SPEAKER_00"),
        SpeakerSegment(start=1.0, end=2.5, speaker="SPEAKER_01"),
    ]
    annotation = build_hypothesis_annotation(segments)
    labels = list(annotation.itertracks(yield_label=True))
    assert len(labels) == 2
    assert labels[0][2] == "SPEAKER_00"


def test_compute_der_identical_annotations_is_zero():
    ref = Annotation()
    ref[Segment(0.0, 1.0)] = "A"
    ref[Segment(1.0, 2.5)] = "B"

    hyp = Annotation()
    hyp[Segment(0.0, 1.0)] = "SPEAKER_00"
    hyp[Segment(1.0, 2.5)] = "SPEAKER_01"

    der = compute_der(ref, hyp)
    assert der == 0.0


def test_compute_der_penalizes_disagreement():
    ref = Annotation()
    ref[Segment(0.0, 1.0)] = "A"
    ref[Segment(1.0, 2.5)] = "B"

    hyp = Annotation()
    hyp[Segment(0.0, 1.0)] = "SPEAKER_00"
    hyp[Segment(1.0, 2.5)] = "SPEAKER_00"  # wrongly merged into one speaker

    der = compute_der(ref, hyp)
    assert der > 0.0
