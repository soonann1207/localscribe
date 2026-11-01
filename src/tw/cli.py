import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill a template from a recorded meeting/call.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument(
        "--speed-factor",
        type=float,
        default=1.0,
        help="Speed up audio before transcription/diarization (e.g. 2.0 = 2x speed, faster but less accurate)",
    )
    return parser.parse_args(argv)


def preflight_check(require_ollama: bool = True) -> list[str]:
    """Return human-readable problems that would make a pipeline run fail.

    The interval-transcript pipeline (web UI) never calls the LLM, so it
    passes require_ollama=False; the field-extraction CLI needs Ollama.
    """
    problems = []
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg not found on PATH (brew install ffmpeg / apt install ffmpeg)")
    if require_ollama:
        if shutil.which("ollama") is None:
            problems.append("ollama not found on PATH")
        else:
            try:
                result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.SubprocessError) as e:
                problems.append(f"could not run `ollama list`: {e}")
            else:
                if "llama3.1:8b" not in result.stdout:
                    problems.append("llama3.1:8b model not pulled (ollama pull llama3.1:8b)")
    if not os.environ.get("HF_TOKEN"):
        problems.append(
            "HF_TOKEN not set (required for pyannote diarization — accept the "
            "pyannote/speaker-diarization-3.1 license on Hugging Face, then export HF_TOKEN)"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems = preflight_check()
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        return 1

    from tw.pipeline import run

    output_path = run(args.video, args.template, speed_factor=args.speed_factor)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
