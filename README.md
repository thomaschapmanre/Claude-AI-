# ClipForge: AI video clipper

Paste a link or upload a long video. You get back ranked 9:16 clips with burned-in captions, a hook, a title, a caption and hashtags, all ready to post on TikTok and Reels.

```
URL / upload ─► download (yt-dlp) ─► transcribe (faster-whisper, word timestamps)
             ─► find moments (Claude + loudness, or local heuristic) ─► snap to word boundaries, 15–60 s
             ─► render (ffmpeg: face-centred crop or blur-fit, push-in zoom, word-by-word captions, hook)
             ─► preview / edit / re-render / batch .zip
```

## 1. Stack and why

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind 4 | Fast builds and a small bundle (~50 KB gzip). One screen: input, progress, clip grid. |
| API | FastAPI | Async uploads, typed request bodies, and it serves the built frontend too, so you deploy one thing. |
| Download | **yt-dlp** | Handles YouTube, Twitch VODs, TikTok, Instagram, Vimeo and direct links. Nothing else is close. |
| Transcription | **faster-whisper** (CTranslate2 Whisper) | Free and runs locally. It gives word-level timestamps, which word-by-word captions need, and it is about 4× faster than openai-whisper. `small` runs on CPU; use `large-v3` on a GPU. |
| Moment detection | **Claude** (`claude-opus-5-5`, structured output) plus audio loudness | Reading a transcript is what finds hooks, punchlines and controversial takes, and an LLM does that best. Loudness spikes (laughter, shouting) are passed in as extra signal. A local heuristic takes over when no key is set or the call fails. |
| Reframe | OpenCV face detection | Samples 8 frames and crops 9:16 around the median face position. |
| Render | ffmpeg + libass | Burns in ASS subtitles (active word highlighted, pop-in), a hook box, and an optional 8% push-in zoom. Output is H.264 1080×1920 at 30 fps with `+faststart`. |
| Jobs | Thread pool + JSON on disk | Needs no infrastructure. See "Scaling" for the upgrade path. |

## 2. Project structure

```
backend/
  app/
    main.py        HTTP API (create job, poll, edit clip, file + zip download), serves frontend/dist
    jobs.py        job store + pipeline orchestration + re-render + zip
    ingest.py      URL validation (SSRF guard), yt-dlp download, ffprobe, audio extract
    transcribe.py  faster-whisper word timestamps, per-second loudness
    highlights.py  Claude scorer, heuristic scorer, snapping, de-duplication
    render.py      face crop / blur-fit, zoom, ASS captions + hook, ffmpeg encode, thumbnail
    config.py      env-driven settings
  tests/           unit tests + end-to-end API test (real ffmpeg, Whisper stubbed)
frontend/
  src/App.tsx      new-job screen, job view (progress, ranking, select, batch download)
  src/ClipCard.tsx preview, score, reasons, copy caption, editor (trim/hook/text/layout/zoom)
  src/api.ts       typed API client
  src/ui.tsx       Toggle / segmented control
Dockerfile         single image: builds frontend, runs API on :8000
```

## 3. Setup and run

You need Python 3.11+, Node 20+, and **ffmpeg with libass** on your PATH (`brew install ffmpeg` or `apt install ffmpeg`).

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # optional; without it the heuristic picks clips
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173 (proxies /api → :8000)
```

The first job downloads the Whisper model, about 500 MB for `small`. Settings are listed in `.env.example`.

**Production (one container):**
```bash
docker build -t clipforge .
docker run -p 8000:8000 -v clipforge-data:/data -e ANTHROPIC_API_KEY=sk-ant-... clipforge
```

**Tests:** `cd backend && pytest -q`. This runs the whole flow through the API: upload → analysis → real 1080×1920 render → edit and re-render → zip.

### API
| Method | Path | |
|---|---|---|
| POST | `/api/jobs` | multipart: `url` **or** `file`, plus `num_clips`, `layout` (`crop`/`fit`), `zoom`, `captions` |
| GET | `/api/jobs/{id}` | status, progress, clips (poll this) |
| PATCH | `/api/jobs/{id}/clips/{cid}` | edit `start/end/hook/title/caption/hashtags/layout/zoom/captions`. Visual changes trigger a re-render. |
| GET | `/api/jobs/{id}/clips/{cid}/video` \| `/thumb` | files |
| GET | `/api/jobs/{id}/download?ids=c1,c2` | zip of the mp4s, plus a `.txt` per clip with its title, caption and hashtags |

## 4. APIs and services

| Need | Default | Free alternative |
|---|---|---|
| Transcription | faster-whisper, local, free | — (paid: Deepgram or AssemblyAI if you want no GPU) |
| Moment picking + copy | Anthropic API (`ANTHROPIC_API_KEY`), a few cents per hour of video | Built-in heuristic (no key). Or point `with_claude` at a self-hosted model. |
| Downloading | yt-dlp, free | — |
| Rendering | ffmpeg, free | — |
| GPU (optional) | Any CUDA box with `WHISPER_DEVICE=cuda` | CPU works, about 1× real-time with `small` |

Some platforms (Instagram, some TikToks) need logged-in cookies. Add yt-dlp's `--cookies` flag in `ingest.download` when you hit that.

## 5. How the "best moments" are chosen

1. **Signals.** You get the word-timed transcript plus per-second loudness. Seconds more than 8 dB above the median are flagged as reaction moments (laughter, shouting, applause).
2. **Claude pass.** Claude gets the timestamped transcript and the loud seconds, and is told to act like an editor who grows clip accounts. It must pick clips that:
   - stand alone with no context
   - start on the hook and end on a payoff
   - don't overlap
   
   It returns start and end times, an on-screen hook, a title, a caption, hashtags, a category, a calibrated 0–100 viral score, and 2–4 reasons tied to what is said. The schema is enforced with structured outputs.
3. **Heuristic pass** (fallback). It scores every sentence-aligned 15–60 s window on:
   - hook strength of the first sentence (questions, numbers, "nobody/secret/mistake…"): 30
   - loudness energy and peaks: 25
   - speaking pace near 3 words/s: 15
   - emotional or high-stakes words: 20
   - ending on a full sentence: 10
   - a 25–45 s length bonus

   Each hit adds a human-readable reason.
4. **Validation.** Every clip is snapped to word boundaries, forced to 15–60 s and padded slightly. Clips overlapping a higher-scored clip by more than 30% are dropped. The rest are sorted by score.

## 6. Turning it into a business

**Pricing** (per-minute processing pricing matches what this costs you to run):
- Free: 30 min/month, watermark, 720p.
- Creator ($19/mo): 300 min, 1080p, no watermark.
- Pro ($49/mo): 1,000 min, priority queue, brand presets, auto-posting.
- Agency ($149+/mo): seats, client workspaces, API access.
- Top-up packs for extra minutes.

**Features that drive revenue, in order:**
1. Accounts and Stripe metering (charge per source minute).
2. Caption style presets and brand kits (font, colours, logo).
3. Speaker tracking with cuts (mediapipe + scene detection) for podcasts with 2+ people.
4. Direct publishing and scheduling to TikTok, Reels and Shorts.
5. B-roll and emoji inserts, plus auto-generated music beds.
6. Learn from results: pull view counts back in and fine-tune scoring for each account.
7. Clip translation and dubbing for non-English markets.
8. A "clipping agency" mode: track channels and auto-clip new uploads within an hour.

**Clipper-side money:** many creators and brands pay per 1K views through clip campaign platforms. Pick creators who run those programs, process their new uploads daily, post your top 3 clips per video, and track which categories win.

## Scaling (when you outgrow one box)

- Move the job queue to Redis + RQ or Celery, with separate GPU workers for Whisper and CPU workers for ffmpeg.
- Move job state to Postgres and files to S3 or R2, served through a CDN.
- Add auth plus per-user job ownership. Today anyone with a job ID can read that job, because IDs are random 128-bit values.
- Delete source files after N days.
