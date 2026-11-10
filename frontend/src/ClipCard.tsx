import { useState } from "react";
import { Seg, Toggle } from "./ui";
import { clipUrl, editClip, fmt, type Clip, type Job } from "./api";

const scoreColor = (s: number) => (s >= 80 ? "bg-emerald-500" : s >= 60 ? "bg-amber-500" : "bg-zinc-600");

type Props = { jobId: string; clip: Clip; rank: number; selected: boolean; onToggle: () => void; onChange: (j: Job) => void };

export default function ClipCard({ jobId, clip: c, rank, selected, onToggle, onChange }: Props) {
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const post = `${c.caption}\n\n${c.hashtags.join(" ")}`;

  return (
    <article className={`overflow-hidden rounded-2xl border bg-zinc-900 transition ${selected ? "border-fuchsia-500" : "border-zinc-800"}`}>
      <div className="relative aspect-[9/16] bg-black">
        {c.status === "ready" ? (
          <video key={c.version} src={clipUrl(jobId, c, "video")} poster={clipUrl(jobId, c, "thumb")} controls playsInline preload="none" className="h-full w-full object-cover" />
        ) : (
          <div className="grid h-full place-items-center text-sm text-zinc-500">
            {c.status === "error" ? <span className="px-4 text-center text-red-400">{c.error}</span> : <span className="animate-pulse">Rendering…</span>}
          </div>
        )}
        <div className="pointer-events-none absolute left-2 top-2 flex gap-1.5">
          <span className="rounded-md bg-black/70 px-2 py-1 text-xs font-bold">#{rank}</span>
          <span className={`rounded-md px-2 py-1 text-xs font-bold ${scoreColor(c.score)}`}>{c.score}</span>
        </div>
        <label className="absolute right-2 top-2 grid h-8 w-8 cursor-pointer place-items-center rounded-md bg-black/70">
          <input type="checkbox" checked={selected} onChange={onToggle} disabled={c.status !== "ready"} aria-label={`Select clip ${rank}`} className="h-4 w-4 accent-fuchsia-500" />
        </label>
      </div>

      <div className="space-y-3 p-4">
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span className="rounded bg-zinc-800 px-2 py-0.5 capitalize text-zinc-300">{c.category}</span>
          <span>{fmt(c.start)}–{fmt(c.end)} · {Math.round(c.end - c.start)}s</span>
        </div>
        <h3 className="font-semibold leading-snug">{c.title}</h3>
        <ul className="space-y-1 text-xs text-zinc-400">
          {c.reasons.map((r) => <li key={r}>• {r}</li>)}
        </ul>
        <div className="rounded-lg bg-zinc-950 p-2.5 text-xs text-zinc-300">
          <p className="whitespace-pre-wrap">{post}</p>
          <button onClick={() => navigator.clipboard.writeText(post).then(() => (setCopied(true), setTimeout(() => setCopied(false), 1200)))}
            className="mt-2 text-fuchsia-300 hover:underline">
            {copied ? "Copied ✓" : "Copy caption"}
          </button>
        </div>
        <div className="flex gap-2 text-sm">
          <button onClick={() => setEditing(!editing)} className="flex-1 rounded-lg bg-zinc-800 py-2 hover:bg-zinc-700">{editing ? "Close" : "Edit"}</button>
          {c.status === "ready" && (
            <a href={clipUrl(jobId, c, "video")} download className="flex-1 rounded-lg bg-zinc-100 py-2 text-center font-medium text-zinc-900 hover:bg-white">Download</a>
          )}
        </div>
        {editing && <Editor jobId={jobId} clip={c} onSaved={(j) => (onChange(j), setEditing(false))} />}
      </div>
    </article>
  );
}

function Editor({ jobId, clip, onSaved }: { jobId: string; clip: Clip; onSaved: (j: Job) => void }) {
  const [d, setD] = useState({ ...clip, tags: clip.hashtags.join(" ") });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const field = "w-full rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-sm outline-none focus:border-fuchsia-500";

  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      const { tags, ...rest } = d;
      onSaved(await editClip(jobId, clip.id, {
        start: rest.start, end: rest.end, hook: rest.hook, title: rest.title, caption: rest.caption,
        hashtags: tags.split(/\s+/).filter(Boolean).map((t) => (t.startsWith("#") ? t : `#${t}`)),
        layout: rest.layout, zoom: rest.zoom, captions: rest.captions,
      }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 border-t border-zinc-800 pt-3 text-xs text-zinc-400">
      <div className="grid grid-cols-2 gap-2">
        <label>Start (s)<input type="number" step="0.5" value={d.start} onChange={(e) => setD({ ...d, start: +e.target.value })} className={field} /></label>
        <label>End (s)<input type="number" step="0.5" value={d.end} onChange={(e) => setD({ ...d, end: +e.target.value })} className={field} /></label>
      </div>
      <label className="block">On-screen hook<input value={d.hook} onChange={(e) => setD({ ...d, hook: e.target.value })} className={field} placeholder="Leave empty for none" /></label>
      <label className="block">Title<input value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} className={field} /></label>
      <label className="block">Caption<textarea rows={2} value={d.caption} onChange={(e) => setD({ ...d, caption: e.target.value })} className={field} /></label>
      <label className="block">Hashtags<input value={d.tags} onChange={(e) => setD({ ...d, tags: e.target.value })} className={field} /></label>
      <div className="flex flex-wrap gap-2">
        <Seg value={d.layout} onChange={(layout) => setD({ ...d, layout })} options={[["crop", "Face crop"], ["fit", "Blur fit"]]} />
        <Toggle label="Captions" on={d.captions} set={(captions) => setD({ ...d, captions })} />
        <Toggle label="Zoom" on={d.zoom} set={(zoom) => setD({ ...d, zoom })} />
      </div>
      <button onClick={save} disabled={busy} className="w-full rounded-lg bg-fuchsia-600 py-2 text-sm font-semibold text-white hover:bg-fuchsia-500 disabled:opacity-50">
        {busy ? "Saving…" : "Save & re-render"}
      </button>
      {err && <p role="alert" className="text-red-400">{err}</p>}
    </div>
  );
}
