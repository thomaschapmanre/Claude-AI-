import logging
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ingest, jobs
from .config import CORS_ORIGINS, MAX_UPLOAD_MB

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="ClipForge API")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

JOB_ID = re.compile(r"^[0-9a-f]{32}$")
CLIP_ID = re.compile(r"^c\d{1,3}$")


def _job(job_id: str) -> dict:
    job = jobs.get(job_id) if JOB_ID.match(job_id) else None
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _clip(job: dict, clip_id: str) -> dict:
    clip = next((c for c in job["clips"] if c["id"] == clip_id), None) if CLIP_ID.match(clip_id) else None
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip


@app.post("/api/jobs")
async def create_job(
    url: str | None = Form(None),
    file: UploadFile | None = File(None),
    num_clips: int = Form(8),
    layout: str = Form("crop"),
    zoom: bool = Form(False),
    captions: bool = Form(True),
):
    if bool(url) == bool(file):
        raise HTTPException(400, "Send exactly one of url or file")
    if layout not in ("crop", "fit"):
        raise HTTPException(400, "layout must be crop or fit")
    options = {"num_clips": max(1, min(num_clips, 20)), "layout": layout, "zoom": zoom, "captions": captions}

    if url:
        try:
            source = {"type": "url", "url": ingest.validate_url(url)}
        except ValueError as e:
            raise HTTPException(400, str(e))
        job = jobs.create(source, options)
    else:
        job = jobs.create({"type": "upload", "filename": Path(file.filename or "upload").name}, options)
        dest, size, limit = jobs.job_dir(job["id"]) / "source.mp4", 0, MAX_UPLOAD_MB * 1024 * 1024
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    f.close()
                    dest.unlink()
                    jobs.update(job["id"], status="error", error="File too large", message="Failed")
                    raise HTTPException(413, f"File larger than {MAX_UPLOAD_MB} MB")
                f.write(chunk)
    jobs.start(job["id"])
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _job(job_id)


class ClipEdit(BaseModel):
    start: float | None = None
    end: float | None = None
    hook: str | None = None
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    layout: str | None = None
    zoom: bool | None = None
    captions: bool | None = None


@app.patch("/api/jobs/{job_id}/clips/{clip_id}")
def edit_clip(job_id: str, clip_id: str, body: ClipEdit):
    job = _job(job_id)
    _clip(job, clip_id)
    if body.layout and body.layout not in ("crop", "fit"):
        raise HTTPException(400, "layout must be crop or fit")
    try:
        return jobs.edit_clip(job_id, clip_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/jobs/{job_id}/clips/{clip_id}/{kind}")
def clip_file(job_id: str, clip_id: str, kind: str):
    _clip(_job(job_id), clip_id)
    name = {"video": "clip.mp4", "thumb": "thumb.jpg"}.get(kind)
    path = jobs.job_dir(job_id) / "clips" / clip_id / (name or "")
    if not name or not path.is_file():
        raise HTTPException(404, "Not rendered yet")
    return FileResponse(path, filename=f"{clip_id}.mp4" if kind == "video" else None)


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, ids: str):
    job = _job(job_id)
    try:
        path = jobs.zip_clips(job_id, [i for i in ids.split(",") if CLIP_ID.match(i)])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return FileResponse(path, filename=f"clips_{job['id'][:8]}.zip")


# Serve the built frontend in production (single deployable).
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
