export type Tone = "neutral" | "ok" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-300",
  ok: "bg-emerald-50 text-emerald-800 ring-emerald-300",
  danger: "bg-rose-50 text-rose-800 ring-rose-300",
};

export function StatusBadge({ tone, label, title }: { tone: Tone; label: string; title?: string }) {
  return (
    <span
      role="status"
      title={title}
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${toneClasses[tone]}`}
    >
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      {label}
    </span>
  );
}
