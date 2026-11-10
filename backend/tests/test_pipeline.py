"""End-to-end through the HTTP API with real ffmpeg rendering; only Whisper is stubbed."""
import subprocess
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from test_core import _transcript


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app import config, jobs, main, transcribe

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    monkeypatch.setattr(transcribe, "transcribe", lambda wav, on_progress=None: _transcript())
    return TestClient(main.app)


def _wait(client, job_id, cond, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if cond(job):
            return job
        time.sleep(0.5)
    raise AssertionError(f"timed out: {job['status']} {job.get('error')}")


def test_upload_to_zip(client, tmp_path):
    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=100",
                    "-f", "lavfi", "-i", "sine=f=220:d=100", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", str(src)], check=True)
    with src.open("rb") as f:
        r = client.post("/api/jobs", files={"file": ("in.mp4", f, "video/mp4")}, data={"num_clips": "2", "zoom": "true"})
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    job = _wait(client, jid, lambda j: j["status"] in ("done", "error"))
    assert job["status"] == "done", job["error"]
    assert job["engine"] == "heuristic" and len(job["clips"]) == 2
    c = job["clips"][0]
    assert c["status"] == "ready"

    out = tmp_path / jid / "clips" / c["id"] / "clip.mp4"
    dims = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert dims == "1080,1920"
    assert client.get(f"/api/jobs/{jid}/clips/{c['id']}/video").status_code == 200

    # edit -> re-render bumps version
    r = client.patch(f"/api/jobs/{jid}/clips/{c['id']}", json={"hook": "New hook", "layout": "fit"})
    assert r.status_code == 200
    _wait(client, jid, lambda j: j["clips"][0]["version"] == 2 and j["clips"][0]["status"] == "ready")

    r = client.get(f"/api/jobs/{jid}/download", params={"ids": ",".join(x["id"] for x in job["clips"])})
    assert r.status_code == 200
    (tmp_path / "out.zip").write_bytes(r.content)
    names = zipfile.ZipFile(tmp_path / "out.zip").namelist()
    assert sum(n.endswith(".mp4") for n in names) == 2 and sum(n.endswith(".txt") for n in names) == 2


def test_rejects_bad_input(client):
    assert client.post("/api/jobs", data={"url": "file:///etc/passwd"}).status_code == 400
    assert client.post("/api/jobs", data={"url": "http://127.0.0.1/x"}).status_code == 400
    assert client.post("/api/jobs", data={}).status_code == 400
    assert client.get("/api/jobs/../../etc").status_code == 404
