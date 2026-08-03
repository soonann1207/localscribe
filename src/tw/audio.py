import subprocess
from pathlib import Path


def extract_audio(video_path: Path, output_path: Path | None = None, speed_factor: float = 1.0) -> Path:
    output_path = output_path or video_path.with_suffix(".wav")
    if output_path == video_path:
        raise ValueError(f"refusing to overwrite input file: {video_path}")

    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-ac", "1", "-ar", "16000"]
    if speed_factor != 1.0:
        cmd += ["-filter:a", f"atempo={speed_factor}"]
    cmd.append(str(output_path))

    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
