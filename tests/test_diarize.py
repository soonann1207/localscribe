from types import SimpleNamespace
from tw.diarize import _segments_from_annotation

class FakeAnnotation:
    def __init__(self, tracks):
        self._tracks = tracks

    def itertracks(self, yield_label=False):
        for turn, track_id, speaker in self._tracks:
            yield turn, track_id, speaker


def test_segments_from_annotation_converts_tracks():
    turn1 = SimpleNamespace(start=0.0, end=1.5)
    turn2 = SimpleNamespace(start=1.5, end=3.0)
    annotation = FakeAnnotation([
        (turn1, "A", "SPEAKER_00"),
        (turn2, "B", "SPEAKER_01"),
    ])
    result = _segments_from_annotation(annotation)
    assert result[0].start == 0.0
    assert result[0].end == 1.5
    assert result[0].speaker == "SPEAKER_00"
    assert result[1].speaker == "SPEAKER_01"
