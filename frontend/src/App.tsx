import { useEffect, useState } from "react";
import { createJob, getJob, zipUrl, type Job, type Options } from "./api";
import ClipCard from "./ClipCard";
import { Seg, Toggle } from "./ui";

const useHashJob = () => {
  const read = () => location.hash.match(/^#\/job\/([0-9a-f]{32})$/)?.[1] ?? null;
  const [id, setId] = useState(read);
  useEffect(() => {
    const on = () => setId(read());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  return [id, (v: string | null) => (location.hash = v ? `/job/${v}` : "")] as const;
};

export default function App() {
  const [jobId, setJobId] = useHashJob();
  return (
    <div className="min-h-screen">
      <header className="border-b border-zinc-800/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <button onClick={() => setJobId(null)} className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-fuchsia-500 to-orange-400 text-sm">✂</span>
            ClipForge
          </button>
          {jobId && (
            <button onClick={() => setJobId(null)} className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm hover:bg-zinc-700">
              + New video
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">
        {jobId ? <JobView id={jobId} /> : <NewJob onCreated={setJobId} />}
      </main>
    </div>
  );
}

function NewJob({ onCreated }: { onCreated: (id: string) => void }) {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [opts, setOpts] = useState<Options>({ num_clips: 8, layout: "crop", zoom: true, captions: true });

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      const job = await createJob(file ? { file } : { url }, opts);
      onCreated(job.id);
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl pt-10 text-center">
      <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
        Long video in.{" "}
        <span className="bg-gradient-to-r from-fuchsia-400 to-orange-300 bg-clip-text text-transparent">Viral clips out.</span>
      </h1>
      <p className="mt-4 text-zinc-400">
        Paste a YouTube, Twitch, TikTok, Instagram or Vimeo link — or drop a file. Get ranked 9:16 clips with captions, hooks and hashtags.
      </p>

      <div className="mt-8 space-y-3 text-left">
        <label htmlFor="url" className="sr-only">Video URL</label>
        <input
          id="url"
          value={url}
          onChange={(e) => (setUrl(e.target.value), setFile(null))}
          onKeyDown={(e) => e.key === "Enter" && url && submit()}
          placeholder="https://www.youtube.com/watch?v=…"
          className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3.5 outline-none focus:border-fuchsia-500"
        />
        <label
          onDragOver={(e) => (e.preventDefault(), setDrag(true))}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files[0];
            if (f) (setFile(f), setUrl(""));
          }}
          className={`flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-4 py-8 text-sm transition ${
            drag ? "border-fuchsia-500 bg-fuchsia-500/5" : "border-zinc-800 hover:border-zinc-600"
          }`}
        >
          <input type="file" accept="video/*" className="sr-only" onChange={(e) => e.target.files?.[0] && (setFile(e.target.files[0]), setUrl(""))} />
          {file ? (
            <span className="font-medium text-zinc-200">📹 {file.name} ({(file.size / 1e6).toFixed(0)} MB)</span>
          ) : (
            <span className="text-zinc-400">or <span className="text-zinc-200 underline">upload a video file</span> / drag it here</span>
          )}
        </label>

        <div className="flex flex-wrap items-center gap-2 pt-1 text-sm">
          <select
            aria-label="Number of clips"
            value={opts.num_clips}
            onChange={(e) => setOpts({ ...opts, num_clips: +e.target.value })}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2"
          >
            {[3, 5, 8, 12, 20].map((n) => <option key={n} value={n}>{n} clips</option>)}
          </select>
          <Seg value={opts.layout} onChange={(layout) => setOpts({ ...opts, layout })} options={[["crop", "Face crop"], ["fit", "Blur fit"]]} />
          <Toggle label="Captions" on={opts.captions} set={(captions) => setOpts({ ...opts, captions })} />
          <Toggle label="Zoom" on={opts.zoom} set={(zoom) => setOpts({ ...opts, zoom })} />
        </div>

        <button
          onClick={submit}
          disabled={busy || (!url && !file)}
          className="w-full rounded-xl bg-gradient-to-r from-fuchsia-600 to-orange-500 py-3.5 font-semibold shadow-lg shadow-fuchsia-900/30 transition hover:brightness-110 disabled:opacity-40"
        >
          {busy ? (file ? "Uploading…" : "Starting…") : "Generate clips"}
        </button>
        {err && <p role="alert" className="text-sm text-red-400">{err}</p>}
      </div>
    </div>
  );
}

const STAGES = ["downloading", "transcribing", "analyzing", "rendering", "done"] as const;

function JobView({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const busy = !job || !["done", "error"].includes(job.status) || job.clips.some((c) => c.status === "rendering" || c.status === "pending");
  useEffect(() => {
    let alive = true;
    const tick = () => getJob(id).then((j) => alive && setJob(j), (e) => alive && setErr(e.message));
    tick();
    if (!busy) return () => void (alive = false);
    const t = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [id, busy]);

  if (err) return <p className="text-red-400">{err}</p>;
  if (!job) return <p className="text-zinc-500">Loading…</p>;

  const clips = [...job.clips].sort((a, b) => b.score - a.score);
  const ready = clips.filter((c) => c.status === "ready");
  const toggle = (cid: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(cid) ? n.delete(cid) : n.add(cid);
      return n;
    });

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm text-zinc-500">{job.source.type === "url" ? job.source.url : job.source.filename}</p>
          <h2 className="text-2xl font-bold">
            {job.status === "done" ? `${clips.length} clips, ranked by viral potential` : job.status === "error" ? "Something went wrong" : job.message}
          </h2>
          {job.engine && (
            <p className="mt-1 text-xs text-zinc-500">
              Picked by {job.engine === "claude" ? "Claude" : "local heuristic (set ANTHROPIC_API_KEY for AI ranking)"}
              {job.meta && ` · source ${Math.round(job.meta.duration / 60)} min`}
            </p>
          )}
        </div>
        {clips.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => setSelected(selected.size === ready.length ? new Set() : new Set(ready.map((c) => c.id)))}
              className="rounded-lg bg-zinc-800 px-3 py-2 text-sm hover:bg-zinc-700"
            >
              {selected.size === ready.length && ready.length ? "Clear" : "Select all"}
            </button>
            <a
              href={selected.size ? zipUrl(job.id, [...selected]) : undefined}
              aria-disabled={!selected.size}
              className={`rounded-lg bg-gradient-to-r from-fuchsia-600 to-orange-500 px-4 py-2 text-sm font-semibold ${selected.size ? "" : "pointer-events-none opacity-40"}`}
            >
              Download {selected.size || ""} (.zip)
            </a>
          </div>
        )}
      </div>

      {job.status === "error" && <p role="alert" className="mb-6 rounded-xl bg-red-950/50 p-4 text-sm text-red-300">{job.error}</p>}

      {job.status !== "done" && job.status !== "error" && (
        <div className="mb-8">
          <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
            <div className="h-full bg-gradient-to-r from-fuchsia-500 to-orange-400 transition-all duration-700" style={{ width: `${Math.max(3, job.progress * 100)}%` }} />
          </div>
          <ol className="mt-3 flex justify-between text-xs text-zinc-500">
            {STAGES.slice(job.source.type === "url" ? 0 : 1).map((s) => (
              <li key={s} className={STAGES.indexOf(s) <= STAGES.indexOf(job.status as never) ? "text-zinc-200" : ""}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {clips.map((c, i) => (
          <ClipCard key={c.id} jobId={job.id} clip={c} rank={i + 1} selected={selected.has(c.id)} onToggle={() => toggle(c.id)} onChange={setJob} />
        ))}
      </div>
    </div>
  );
}
