import shutil
import subprocess
import pytest
from tw.audio import extract_audio

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@requires_ffmpeg
def test_extract_audio_produces_wav(tmp_path):
    video_path = tmp_path / "silence.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-shortest", str(video_path),
        ],
        check=True,
        capture_output=True,
    )

    audio_path = extract_audio(video_path)

    assert audio_path.exists()
    assert audio_path.suffix == ".wav"
    assert audio_path.stat().st_size > 0


def test_extract_audio_refuses_to_overwrite_input(tmp_path):
    wav_path = tmp_path / "recording.wav"
    wav_path.write_bytes(b"fake wav data")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        extract_audio(wav_path)
