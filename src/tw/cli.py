import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill a template from a recorded meeting/call.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    return parser.parse_args(argv)


def preflight_check() -> list[str]:
    problems = []
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg not found on PATH (brew install ffmpeg)")
    if shutil.which("ollama") is None:
        problems.append("ollama not found on PATH")
    else:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "llama3.3" not in result.stdout:
            problems.append("llama3.3 model not pulled (ollama pull llama3.3)")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems = preflight_check()
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        return 1

    from tw.pipeline import run

    output_path = run(args.video, args.template)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
