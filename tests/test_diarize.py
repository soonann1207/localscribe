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


def _write_wav(path, samples, channels=1, rate=16000):
    import struct
    import wave

    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_load_wav_mono_scales_to_float(tmp_path):
    from tw.diarize import load_wav_mono

    path = tmp_path / "a.wav"
    _write_wav(path, [0, 16384, -32768, 32767])
    samples, rate = load_wav_mono(path)
    assert rate == 16000
    assert samples.shape == (1, 4)
    assert samples.dtype.name == "float32"
    assert samples[0].tolist() == [0.0, 0.5, -1.0, 32767 / 32768]


def test_load_wav_mono_downmixes_stereo(tmp_path):
    from tw.diarize import load_wav_mono

    path = tmp_path / "s.wav"
    _write_wav(path, [16384, 0, 0, 16384], channels=2)
    samples, _ = load_wav_mono(path)
    assert samples.shape == (1, 2)
    assert samples[0].tolist() == [0.25, 0.25]


def test_load_wav_mono_reads_across_chunks(tmp_path, monkeypatch):
    import tw.diarize as d

    monkeypatch.setattr(d, "_READ_FRAMES", 3)
    path = tmp_path / "c.wav"
    _write_wav(path, list(range(10)))
    samples, _ = d.load_wav_mono(path)
    assert samples.shape == (1, 10)
    assert round(float(samples[0, 9]) * 32768) == 9
