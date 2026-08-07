import threading
import time
from pathlib import Path

import pytest

from tw.job_queue import JobQueue


def _wait_for(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_submit_returns_job_id_and_job_completes(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / "result.docx"
        output.write_text("fake result")
        return output

    q = JobQueue(run_fn=fake_run, max_active=5, workdir=tmp_path / "workdir")
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    job_id = q.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)
    assert job_id

    assert _wait_for(lambda: q.get_job(job_id).status == "done")
    job = q.get_job(job_id)
    assert job.output_path.exists()
    assert job.output_path.read_text() == "fake result"


def test_completed_job_deletes_input_video(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / "result.docx"
        output.write_text("fake result")
        return output

    q = JobQueue(run_fn=fake_run, max_active=5, workdir=tmp_path / "workdir")
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    job_id = q.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)
    assert _wait_for(lambda: q.get_job(job_id).status == "done")

    assert not video_path.exists()


def test_failed_job_records_error_and_still_deletes_video(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        raise ValueError("boom")

    q = JobQueue(run_fn=fake_run, max_active=5, workdir=tmp_path / "workdir")
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    job_id = q.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)
    assert _wait_for(lambda: q.get_job(job_id).status == "error")

    job = q.get_job(job_id)
    assert "boom" in job.error
    assert not video_path.exists()


def test_submit_rejects_when_max_active_reached(tmp_path):
    release = threading.Event()

    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        release.wait(timeout=5.0)
        output = tmp_path / f"{video_path.name}.docx"
        output.write_text("done")
        return output

    q = JobQueue(run_fn=fake_run, max_active=2, workdir=tmp_path / "workdir")

    ids = []
    for i in range(2):
        video_path = tmp_path / f"video{i}.mp4"
        video_path.write_bytes(b"fake video")
        ids.append(q.submit(video_path, f"video{i}.mp4", Path("template.docx"), 5.0, 1.0))

    # one job is processing (blocked on release), the other is queued behind it:
    # both count toward max_active, so a third submission must be rejected.
    assert _wait_for(lambda: q.get_job(ids[0]).status == "processing" or q.get_job(ids[1]).status == "processing")

    overflow_video = tmp_path / "overflow.mp4"
    overflow_video.write_bytes(b"fake video")
    with pytest.raises(RuntimeError, match="queue full"):
        q.submit(overflow_video, "overflow.mp4", Path("template.docx"), 5.0, 1.0)

    release.set()
    assert _wait_for(lambda: all(q.get_job(j).status == "done" for j in ids))


def test_completed_job_frees_slot_for_new_submission(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / f"{video_path.name}.docx"
        output.write_text("done")
        return output

    q = JobQueue(run_fn=fake_run, max_active=1, workdir=tmp_path / "workdir")

    video1 = tmp_path / "video1.mp4"
    video1.write_bytes(b"fake video")
    job1 = q.submit(video1, "video1.mp4", Path("template.docx"), 5.0, 1.0)
    assert _wait_for(lambda: q.get_job(job1).status == "done")

    video2 = tmp_path / "video2.mp4"
    video2.write_bytes(b"fake video")
    job2 = q.submit(video2, "video2.mp4", Path("template.docx"), 5.0, 1.0)
    assert job2

    assert _wait_for(lambda: q.get_job(job2).status == "done")


def test_output_written_to_dedicated_output_dir(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / "result.docx"
        output.write_text("fake result")
        return output

    output_dir = tmp_path / "outputs"
    q = JobQueue(run_fn=fake_run, max_active=5, workdir=tmp_path / "workdir", output_dir=output_dir)
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    job_id = q.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)
    assert _wait_for(lambda: q.get_job(job_id).status == "done")

    job = q.get_job(job_id)
    assert job.output_path.parent == output_dir
    assert job.output_path.parent != tmp_path / "workdir"


def test_jobs_persist_across_queue_instances(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / "result.docx"
        output.write_text("fake result")
        return output

    workdir = tmp_path / "workdir"
    q1 = JobQueue(run_fn=fake_run, max_active=5, workdir=workdir)
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")
    job_id = q1.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)
    assert _wait_for(lambda: q1.get_job(job_id).status == "done")

    # Simulate a server restart: a fresh JobQueue pointed at the same workdir
    # should recover the completed job from disk, not start with an empty list.
    q2 = JobQueue(run_fn=fake_run, max_active=5, workdir=workdir)
    jobs = q2.list_jobs()
    assert any(j.id == job_id and j.status == "done" for j in jobs)
    restored = q2.get_job(job_id)
    assert restored.output_path.exists()
    assert restored.output_path.read_text() == "fake result"


def test_interrupted_jobs_marked_as_error_on_reload(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / "result.docx"
        output.write_text("fake result")
        return output

    workdir = tmp_path / "workdir"
    workdir.mkdir(parents=True)
    (workdir / "jobs.json").write_text(
        '[{"id": "abc", "video_name": "stuck.mp4", "status": "processing", '
        '"output_path": null, "error": null, "submitted_at": 1.0}]'
    )

    q = JobQueue(run_fn=fake_run, max_active=5, workdir=workdir)
    job = q.get_job("abc")
    assert job.status == "error"
    assert "interrupted" in job.error.lower()


def test_list_jobs_returns_all_submitted_jobs(tmp_path):
    def fake_run(video_path, template_path, interval_minutes, speed_factor):
        output = tmp_path / f"{video_path.name}.docx"
        output.write_text("done")
        return output

    q = JobQueue(run_fn=fake_run, max_active=5, workdir=tmp_path / "workdir")
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")
    job_id = q.submit(video_path, "video.mp4", Path("template.docx"), 5.0, 1.0)

    jobs = q.list_jobs()
    assert any(j.id == job_id for j in jobs)
    assert next(j for j in jobs if j.id == job_id).video_name == "video.mp4"
