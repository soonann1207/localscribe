from pathlib import Path
from tw.cli import parse_args, preflight_check


def test_parse_args_requires_video_and_template():
    args = parse_args(["--video", "rec.mp4", "--template", "t.md"])
    assert args.video == Path("rec.mp4")
    assert args.template == Path("t.md")


def test_parse_args_speed_factor_defaults_to_one():
    args = parse_args(["--video", "rec.mp4", "--template", "t.md"])
    assert args.speed_factor == 1.0


def test_parse_args_speed_factor_can_be_overridden():
    args = parse_args(["--video", "rec.mp4", "--template", "t.md", "--speed-factor", "2.0"])
    assert args.speed_factor == 2.0


def test_preflight_check_flags_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None if name == "ffmpeg" else "/usr/bin/ollama")

    class FakeResult:
        stdout = "llama3.1:8b:latest\n"

    # Hermetic: never shell out to a real `ollama` from a unit test.
    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    problems = preflight_check()
    assert any("ffmpeg" in p for p in problems)


def test_preflight_check_skips_ollama_when_not_required(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    assert preflight_check(require_ollama=False) == []


def test_preflight_check_reports_broken_ollama_instead_of_crashing(monkeypatch):
    import subprocess

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv("HF_TOKEN", "fake-token")

    def boom(*a, **k):
        raise FileNotFoundError("ollama")

    monkeypatch.setattr(subprocess, "run", boom)
    problems = preflight_check()
    assert any("ollama list" in p for p in problems)


def test_preflight_check_passes_when_tools_and_model_present(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    class FakeResult:
        stdout = "llama3.1:8b:latest\n"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    assert preflight_check() == []


def test_preflight_check_flags_missing_hf_token(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    class FakeResult:
        stdout = "llama3.1:8b:latest\n"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    monkeypatch.delenv("HF_TOKEN", raising=False)
    problems = preflight_check()
    assert any("HF_TOKEN" in p for p in problems)
