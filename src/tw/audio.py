import subprocess
from pathlib import Path


def extract_audio(video_path: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or video_path.with_suffix(".wav")
    if output_path == video_path:
        raise ValueError(f"refusing to overwrite input file: {video_path}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-ac", "1", "-ar", "16000", str(output_path)],
        check=True,
        capture_output=True,
    )
    return output_path
