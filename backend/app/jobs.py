"""Job store (JSON on disk) and the processing pipeline.

shortcut: in-process thread pool + JSON files, single server only.
Upgrade to Redis + RQ/Celery workers and Postgres when running more than one API instance.
"""
import json
import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import highlights, ingest, render, transcribe
from .config import DATA_DIR, WORKERS

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=WORKERS)
_lock = threading.Lock()
_jobs: dict[str, dict] = {}

EDITABLE = {"start", "end", "hook", "title", "caption", "hashtags", "layout", "zoom", "captions"}
VISUAL = {"start", "end", "hook", "layout", "zoom", "captions"}


def job_dir(job_id: str) -> Path:
    return DATA_DIR / job_id


def _save(job: dict) -> None:
    p = job_dir(job["id"]) / "job.json"
    p.with_suffix(".tmp").write_text(json.dumps(job))
    p.with_suffix(".tmp").replace(p)


def get(job_id: str) -> dict | None:
    with _lock:
        if job_id not in _jobs:
            p = job_dir(job_id) / "job.json"
            if not p.exists():
                return None
            _jobs[job_id] = json.loads(p.read_text())
        return json.loads(json.dumps(_jobs[job_id]))  # copy


def update(job_id: str, **fields) -> None:
    with _lock:
        _jobs[job_id].update(fields)
        _save(_jobs[job_id])


def update_clip(job_id: str, clip_id: str, **fields) -> None:
    with _lock:
        for c in _jobs[job_id]["clips"]:
            if c["id"] == clip_id:
                c.update(fields)
        _save(_jobs[job_id])


def create(source: dict, options: dict) -> dict:
    job = {
        "id": uuid.uuid4().hex, "created": time.time(), "source": source, "options": options,
        "status": "queued", "progress": 0.0, "message": "Queued", "error": None,
        "meta": None, "engine": None, "clips": [],
    }
    job_dir(job["id"]).mkdir(parents=True, exist_ok=True)
    with _lock:
        _jobs[job["id"]] = job
        _save(job)
    return job


def start(job_id: str) -> None:
    _pool.submit(_run, job_id)


def _run(job_id: str) -> None:
    d = job_dir(job_id)
    job = get(job_id)
    try:
        if job["source"]["type"] == "url":
            update(job_id, status="downloading", message="Downloading video…", progress=0.02)
            src = ingest.download(job["source"]["url"], d)
        else:
            src = d / "source.mp4"
        meta = ingest.probe(src)
        update(job_id, meta=meta, status="transcribing", message="Transcribing…", progress=0.1)

        wav = ingest.extract_audio(src, d)
        tr = transcribe.transcribe(wav, lambda p: update(job_id, progress=round(0.1 + 0.5 * p, 3)))
        (d / "transcript.json").write_text(json.dumps(tr))
        loud = transcribe.loudness_per_second(wav)
        wav.unlink(missing_ok=True)

        update(job_id, status="analyzing", message="Finding the best moments…", progress=0.62)
        found, engine = highlights.find_highlights(tr, loud, job["options"]["num_clips"])
        if not found:
            raise RuntimeError("No usable speech found in this video")
        opts = job["options"]
        clips = [
            {**c, "id": f"c{i + 1}", "layout": opts["layout"], "zoom": opts["zoom"], "captions": opts["captions"],
             "status": "pending", "error": None, "version": 0}
            for i, c in enumerate(found)
        ]
        update(job_id, clips=clips, engine=engine, status="rendering", message="Rendering clips…", progress=0.65)

        words = [w for s in tr["segments"] for w in s["words"]]
        for i, c in enumerate(clips):
            _render_one(job_id, c, src, meta, words)
            update(job_id, progress=round(0.65 + 0.35 * (i + 1) / len(clips), 3))
        update(job_id, status="done", message="Done", progress=1.0)
    except Exception as e:
        log.exception("job %s failed", job_id)
        update(job_id, status="error", error=str(e), message="Failed")


def _render_one(job_id: str, clip: dict, src: Path, meta: dict, words: list[dict]) -> None:
    update_clip(job_id, clip["id"], status="rendering", error=None)
    try:
        render.render_clip(src, meta, words, clip, job_dir(job_id) / "clips" / clip["id"])
        update_clip(job_id, clip["id"], status="ready", version=clip.get("version", 0) + 1)
    except Exception as e:
        log.exception("render %s/%s failed", job_id, clip["id"])
        update_clip(job_id, clip["id"], status="error", error=str(e))


def edit_clip(job_id: str, clip_id: str, changes: dict) -> dict:
    job = get(job_id)
    clip = next(c for c in job["clips"] if c["id"] == clip_id)
    changes = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
    if "start" in changes or "end" in changes:
        s, e = changes.get("start", clip["start"]), changes.get("end", clip["end"])
        if not (0 <= s < e <= job["meta"]["duration"] + 0.5) or not (3 <= e - s <= 180):
            raise ValueError("Clip must be 3–180 s and inside the video")
    rerender = any(clip.get(k) != v for k, v in changes.items() if k in VISUAL)
    update_clip(job_id, clip_id, **changes)
    if rerender:
        d = job_dir(job_id)
        words = [w for s in json.loads((d / "transcript.json").read_text())["segments"] for w in s["words"]]
        update_clip(job_id, clip_id, status="rendering")
        _pool.submit(_render_one, job_id, {**clip, **changes}, d / "source.mp4", job["meta"], words)
    return get(job_id)


def zip_clips(job_id: str, clip_ids: list[str]) -> Path:
    job = get(job_id)
    d = job_dir(job_id)
    staging = d / "zip"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    for i, c in enumerate(sorted(job["clips"], key=lambda c: -c["score"])):
        f = d / "clips" / c["id"] / "clip.mp4"
        if c["id"] in clip_ids and c["status"] == "ready" and f.exists():
            name = f"{i + 1:02d}_score{c['score']}_{c['id']}"
            (staging / f"{name}.mp4").hardlink_to(f)
            tags = " ".join(c["hashtags"])
            (staging / f"{name}.txt").write_text(f"{c['title']}\n\n{c['caption']}\n\n{tags}\n")
    if not any(staging.iterdir()):
        raise ValueError("No ready clips selected")
    return Path(shutil.make_archive(str(d / "clips"), "zip", staging))
