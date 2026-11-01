import subprocess
from pathlib import Path


def extract_audio(video_path: Path, output_path: Path | None = None, speed_factor: float = 1.0) -> Path:
    output_path = output_path or video_path.with_suffix(".wav")
    if output_path == video_path:
        raise ValueError(f"refusing to overwrite input file: {video_path}")

    # -vn: skip decoding video entirely. -nostats/-loglevel error: ffmpeg's
    # progress chatter is captured into memory below, so keep it minimal.
    cmd = ["ffmpeg", "-y", "-nostdin", "-nostats", "-loglevel", "error", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000"]
    if speed_factor != 1.0:
        cmd += ["-filter:a", f"atempo={speed_factor}"]
    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else f"exit code {result.returncode}"
        raise RuntimeError(f"ffmpeg could not read {video_path.name}: {detail}")
    return output_path
