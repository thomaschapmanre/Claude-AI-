export function Toggle({ label, on, set }: { label: string; on: boolean; set: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => set(!on)}
      className={`rounded-lg border px-3 py-2 text-sm ${on ? "border-fuchsia-500/60 bg-fuchsia-500/10 text-fuchsia-200" : "border-zinc-800 bg-zinc-900 text-zinc-400"}`}
    >
      {on ? "✓ " : ""}{label}
    </button>
  );
}

export function Seg<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: [T, string][] }) {
  return (
    <div className="flex rounded-lg border border-zinc-800 bg-zinc-900 p-0.5">
      {options.map(([v, l]) => (
        <button key={v} type="button" aria-pressed={v === value} onClick={() => onChange(v)}
          className={`rounded-md px-3 py-1.5 text-sm ${v === value ? "bg-zinc-700 text-white" : "text-zinc-400"}`}>
          {l}
        </button>
      ))}
    </div>
  );
}
