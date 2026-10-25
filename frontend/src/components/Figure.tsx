export type FigureTone = "ink" | "over" | "under";

const TONE_CLASS: Record<FigureTone, string> = {
  ink: "text-ink",
  over: "text-over",
  under: "text-under",
};

/** One headline figure: a label, a large value and a plain-language caption, under a rule. */
export function Figure({
  label,
  value,
  caption,
  tone = "ink",
}: {
  label: string;
  value: string;
  caption: string;
  tone?: FigureTone;
}) {
  return (
    <section role="group" aria-label={label} className="border-t border-rule pt-4">
      <h2 className="text-sm text-muted">{label}</h2>
      <p className={`mt-1 text-3xl font-medium tabular-nums ${TONE_CLASS[tone]}`}>{value}</p>
      <p className="mt-1 text-sm text-muted">{caption}</p>
    </section>
  );
}
