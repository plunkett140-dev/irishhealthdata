// Mirrors charts/style.py exactly, so the interactive dashboard and the
// static matplotlib charts never visually diverge on hospital data. If a
// color changes here, it should change there too (and vice versa).

export const COLOR_PRIMARY = "#0B5FA5";
export const COLOR_SECONDARY = "#D9541F";
export const COLOR_MUTED = "#8A8D93";
export const PALETTE = ["#0B5FA5", "#D9541F", "#2E8B57", "#7B4FA0", "#C9A227"];

// Matches BUCKET_COLORS in charts/hospital_band_breakdown.py
export const BUCKET_COLORS: Record<string, string> = {
  "Under 6 Months": PALETTE[0],
  "6-12 Months": PALETTE[4],
  "12+ Months": PALETTE[1],
};
