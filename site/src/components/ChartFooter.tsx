// Per-chart footer shows only the Source, per the Transparency principle
// in the Technical Design Document. Last updated / Methodology / Known
// limitations used to repeat under every chart on the page — now shown
// once at the bottom of the page instead (see PageFooter.tsx), since
// they're identical across every chart for a given list type/population
// and repeating them five times over was noise, not transparency.

interface ChartFooterProps {
  source: string;
}

export function ChartFooter({ source }: ChartFooterProps) {
  return (
    <p className="mt-2 border-t border-zinc-200 pt-2 text-xs leading-relaxed text-zinc-500">
      Source: {source}
    </p>
  );
}
