// Mirrors add_footer() in charts/style.py — every chart on the site shows
// Source / Last updated / Methodology, per the Transparency principle in
// the Technical Design Document. Not optional, so this is a single shared
// component rather than something each chart re-implements.

interface ChartFooterProps {
  source: string;
  lastUpdated: string;
  methodologyNote?: string;
  knownLimitations?: string;
}

export function ChartFooter({
  source,
  lastUpdated,
  methodologyNote,
  knownLimitations,
}: ChartFooterProps) {
  return (
    <div className="mt-2 border-t border-zinc-200 pt-2 text-xs leading-relaxed text-zinc-500">
      <p>
        Source: {source} | Last updated: {lastUpdated}
      </p>
      {methodologyNote && <p className="mt-1">{methodologyNote}</p>}
      {knownLimitations && (
        <p className="mt-1">Known limitations: {knownLimitations}</p>
      )}
    </div>
  );
}
