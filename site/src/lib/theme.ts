// Mirrors charts/style.py exactly, so the interactive dashboard and the
// static matplotlib charts never visually diverge on hospital data. If a
// color changes here, it should change there too (and vice versa).

// Brand palette per Decision 011: Irish flag green as primary, the
// existing coral kept for the "12+ Months" bucket (verified it still reads
// well against the new primary). PALETTE[2] changed from the old
// "#2E8B57" (sea green) to avoid sitting right next to the new green
// COLOR_PRIMARY in any future multi-series chart.
export const COLOR_PRIMARY = "#169B62";
export const COLOR_SECONDARY = "#D9541F";
export const COLOR_MUTED = "#8A8D93";
export const PALETTE = ["#169B62", "#D9541F", "#2C6E8C", "#7B4FA0", "#C9A227"];

// Irish flag orange — a one-off brand accent for the logo/wordmark only.
// Deliberately NOT part of PALETTE or BUCKET_COLORS: chart data should
// never use it, so it can't be confused with a data series.
export const COLOR_ACCENT = "#FF883E";

// Semantic traffic-light scheme (Decision 011) for the three wait-length
// buckets — replaces the old arbitrary PALETTE-index assignment. Matches
// BUCKET_COLORS in charts/style.py.
export const BUCKET_COLORS: Record<string, string> = {
  "Under 6 Months": COLOR_PRIMARY, // green
  "6-12 Months": "#EF9F27",        // amber
  "12+ Months": COLOR_SECONDARY,   // coral/red
};
