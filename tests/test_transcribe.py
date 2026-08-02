from types import SimpleNamespace
from tw.transcribe import _segments_from_whisper

def test_segments_from_whisper_converts_raw_segments():
    raw = [
        SimpleNamespace(start=0.0, end=1.2, text=" hello there "),
        SimpleNamespace(start=1.2, end=2.5, text="how are you"),
    ]
    result = _segments_from_whisper(raw)
    assert result[0].start == 0.0
    assert result[0].end == 1.2
    assert result[0].text == "hello there"
    assert result[1].text == "how are you"
