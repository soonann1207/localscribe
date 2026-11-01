import time
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from tw.server import Settings, create_app, safe_filename

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "coding_transcription_template.docx"


def _fake_run(video_path, template_path, interval_minutes, speed_factor):
    from tw.interval_transcript import fill_interval_table

    out = video_path.with_name(video_path.stem + "_filled.docx")
    return fill_interval_table(
        template_path,
        {1: "[00:00:01] [SPEAKER_00] hello\n\n[00:00:04] [SPEAKER_01] hi there", 2: "[00:05:02] [SPEAKER_00] bye"},
        out,
    )


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", template_path=TEMPLATE, static_dir=tmp_path / "nostatic")
    app = create_app(settings, run_fn=_fake_run, preflight=lambda: [])
    return TestClient(app)


def _wait_done(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def _upload(client, name="meeting.mp4", data=b"fake video"):
    r = client.post("/api/jobs", files=[("files", (name, data, "video/mp4"))])
    assert r.status_code == 201
    return r.json()["results"][0]


def test_safe_filename_strips_paths_and_odd_chars():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("my video (1).mp4") == "my video _1_.mp4"
    assert safe_filename("") == "upload"


def test_health_reports_problems(tmp_path):
    settings = Settings(data_dir=tmp_path, template_path=TEMPLATE, static_dir=tmp_path / "x")
    c = TestClient(create_app(settings, run_fn=_fake_run, preflight=lambda: ["ffmpeg missing"]))
    body = c.get("/api/health").json()
    assert body["ok"] is False and body["problems"] == ["ffmpeg missing"]
    r = c.post("/api/jobs", files=[("files", ("a.mp4", b"x", "video/mp4"))])
    assert r.status_code == 503


def test_upload_rejects_unsupported_extension(client):
    result = _upload(client, name="notes.txt")
    assert "unsupported" in result["error"]


def test_full_flow_preview_rename_download(client, tmp_path):
    job_id = _upload(client)["job_id"]
    job = _wait_done(client, job_id)
    assert job["status"] == "done"

    # upload scratch dir is cleaned up after the job
    assert list((tmp_path / "data" / "uploads").iterdir()) == []

    preview = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert preview["speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert [i["number"] for i in preview["intervals"]] == [1, 2]
    assert preview["intervals"][0]["turns"][1] == {"timestamp": "00:00:04", "speaker": "SPEAKER_01", "text": "hi there"}

    r = client.put(f"/api/jobs/{job_id}/speakers", json={"names": {"SPEAKER_00": " [Mom] ", "SPEAKER_01": ""}})
    assert r.status_code == 200
    assert r.json()["speaker_names"] == {"SPEAKER_00": "Mom"}

    preview = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert preview["intervals"][0]["turns"][0]["speaker"] == "Mom"
    assert preview["speakers"] == ["SPEAKER_00", "SPEAKER_01"]  # original labels stay renameable

    r = client.get(f"/api/jobs/{job_id}/download")
    assert r.status_code == 200
    assert 'meeting_transcript.docx' in r.headers["content-disposition"]
    out = tmp_path / "dl.docx"
    out.write_bytes(r.content)
    assert "[Mom] hello" in Document(out).tables[0].rows[1].cells[1].text

    # clearing names reverts to the original output
    client.put(f"/api/jobs/{job_id}/speakers", json={"names": {}})
    preview = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert preview["intervals"][0]["turns"][0]["speaker"] == "SPEAKER_00"


def test_rename_rejects_unknown_labels(client):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    r = client.put(f"/api/jobs/{job_id}/speakers", json={"names": {"SPEAKER_99": "x"}})
    assert r.status_code == 422


def test_delete_job(client):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_transcript_404_and_409(client, tmp_path):
    assert client.get("/api/jobs/nope/transcript").status_code == 404


def test_template_download(client):
    r = client.get("/api/template")
    assert r.status_code == 200
    assert r.content == TEMPLATE.read_bytes()


def test_rename_twice_and_swap_keeps_edits(client):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    client.put(f"/api/jobs/{job_id}/speakers", json={"names": {"SPEAKER_00": "Mom", "SPEAKER_01": "Dad"}})

    doc = client.get(f"/api/jobs/{job_id}/document").json()
    r = client.put(
        f"/api/jobs/{job_id}/document",
        json={"base_version": doc["version"], "edits": [{"row": 1, "col": 2, "text": "Q1-a"}]},
    )
    assert r.status_code == 200
    assert r.json()["rows"][0][2] == "Q1-a"

    # swap names: edits made in between must survive
    client.put(f"/api/jobs/{job_id}/speakers", json={"names": {"SPEAKER_00": "Dad", "SPEAKER_01": "Mom"}})
    doc = client.get(f"/api/jobs/{job_id}/document").json()
    assert doc["rows"][0][2] == "Q1-a"
    assert doc["rows"][0][1].startswith("[00:00:01] [Dad] hello")
    assert client.get(f"/api/jobs/{job_id}").json()["modified"] is True


def test_duplicate_speaker_names_rejected(client):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    r = client.put(f"/api/jobs/{job_id}/speakers", json={"names": {"SPEAKER_00": "Sam", "SPEAKER_01": "Sam"}})
    assert r.status_code == 422


def test_document_edit_conflict_and_revert(client):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    v0 = client.get(f"/api/jobs/{job_id}/document").json()["version"]
    ok = client.put(f"/api/jobs/{job_id}/document", json={"base_version": v0, "edits": [{"row": 1, "col": 3, "text": "note"}]})
    assert ok.status_code == 200

    stale = client.put(f"/api/jobs/{job_id}/document", json={"base_version": v0, "edits": [{"row": 1, "col": 3, "text": "x"}]})
    assert stale.status_code == 409

    bad = client.put(
        f"/api/jobs/{job_id}/document",
        json={"base_version": ok.json()["version"], "edits": [{"row": 0, "col": 0, "text": "x"}]},
    )
    assert bad.status_code == 422

    assert client.post(f"/api/jobs/{job_id}/document/revert").json()["modified"] is False
    assert client.get(f"/api/jobs/{job_id}/document").json()["rows"][0][3] == ""


def test_edited_document_is_what_preview_and_download_show(client, tmp_path):
    job_id = _upload(client)["job_id"]
    _wait_done(client, job_id)
    v = client.get(f"/api/jobs/{job_id}/document").json()["version"]
    client.put(
        f"/api/jobs/{job_id}/document",
        json={"base_version": v, "edits": [{"row": 1, "col": 1, "text": "[00:00:01] [SPEAKER_00] corrected text"}]},
    )
    preview = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert preview["intervals"][0]["turns"] == [{"timestamp": "00:00:01", "speaker": "SPEAKER_00", "text": "corrected text"}]
    out = tmp_path / "dl.docx"
    out.write_bytes(client.get(f"/api/jobs/{job_id}/download").content)
    assert Document(out).tables[0].rows[1].cells[1].text == "[00:00:01] [SPEAKER_00] corrected text"
