export type Clip = {
  id: string;
  start: number;
  end: number;
  score: number;
  reasons: string[];
  category: string;
  hook: string;
  title: string;
  caption: string;
  hashtags: string[];
  layout: "crop" | "fit";
  zoom: boolean;
  captions: boolean;
  status: "pending" | "rendering" | "ready" | "error";
  error: string | null;
  version: number;
};

export type Job = {
  id: string;
  status: "queued" | "downloading" | "transcribing" | "analyzing" | "rendering" | "done" | "error";
  progress: number;
  message: string;
  error: string | null;
  engine: "claude" | "heuristic" | null;
  meta: { duration: number; width: number; height: number } | null;
  source: { type: "url"; url: string } | { type: "upload"; filename: string };
  clips: Clip[];
};

export type Options = { num_clips: number; layout: "crop" | "fit"; zoom: boolean; captions: boolean };

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Request failed (${r.status})`);
  return r.json();
}

export function createJob(input: { url: string } | { file: File }, opts: Options): Promise<Job> {
  const fd = new FormData();
  if ("url" in input) fd.append("url", input.url);
  else fd.append("file", input.file);
  for (const [k, v] of Object.entries(opts)) fd.append(k, String(v));
  return fetch("/api/jobs", { method: "POST", body: fd }).then(json<Job>);
}

export const getJob = (id: string) => fetch(`/api/jobs/${id}`).then(json<Job>);

export const editClip = (jobId: string, clipId: string, changes: Partial<Clip>) =>
  fetch(`/api/jobs/${jobId}/clips/${clipId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  }).then(json<Job>);

export const clipUrl = (jobId: string, c: Clip, kind: "video" | "thumb") =>
  `/api/jobs/${jobId}/clips/${c.id}/${kind}?v=${c.version}`;

export const zipUrl = (jobId: string, ids: string[]) => `/api/jobs/${jobId}/download?ids=${ids.join(",")}`;

export const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
