import wave
from functools import lru_cache
from pathlib import Path

from tw.types import SpeakerSegment

_READ_FRAMES = 1 << 20  # decode in ~1M-sample chunks to avoid a 2x transient copy


def _segments_from_annotation(annotation) -> list[SpeakerSegment]:
    segments = []
    for turn, _track_id, speaker in annotation.itertracks(yield_label=True):
        segments.append(SpeakerSegment(start=turn.start, end=turn.end, speaker=speaker))
    return segments


def load_wav_mono(audio_path: Path):
    """Read a 16-bit PCM WAV (what tw.audio.extract_audio writes) into a
    float32 array of shape (channels=1, samples) without torchcodec/ffmpeg.

    Passing pyannote a preloaded waveform avoids its torchcodec decoder,
    which needs FFmpeg shared libraries matching the exact torch build and
    fails at runtime when they don't (e.g. in slim Docker images). Memory is
    unchanged: pyannote holds the full waveform either way (~230 MB/hour).
    """
    import numpy as np

    with wave.open(str(audio_path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM WAV, got {8 * wav.getsampwidth()}-bit: {audio_path}")
        channels, sample_rate, n_frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
        out = np.empty(n_frames * channels, dtype=np.float32)
        pos = 0
        while chunk := wav.readframes(_READ_FRAMES):
            samples = np.frombuffer(chunk, dtype="<i2")
            out[pos : pos + samples.size] = samples
            pos += samples.size
    out = out[:pos]
    out *= 1.0 / 32768.0
    if channels > 1:
        out = out.reshape(-1, channels).mean(axis=1, dtype=np.float32)
    return out.reshape(1, -1), sample_rate


@lru_cache(maxsize=1)
def _load_pipeline(hf_token: str):
    # pyannote.audio >= 4 API (token=, .speaker_diarization); see pyproject pin.
    from pyannote.audio import Pipeline

    return Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)


def diarize(audio_path: Path, hf_token: str) -> list[SpeakerSegment]:
    import torch

    samples, sample_rate = load_wav_mono(audio_path)
    waveform = torch.from_numpy(samples)  # shares memory with the numpy array
    output = _load_pipeline(hf_token)({"waveform": waveform, "sample_rate": sample_rate})
    return _segments_from_annotation(output.speaker_diarization)


def release_pipeline() -> None:
    _load_pipeline.cache_clear()
