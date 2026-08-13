"""
Shared wait-band bucketing and hospital-name-slug rules.

Single source of truth so the matplotlib charts (charts/) and the JSON
export for the interactive dashboard (etl/export_dashboard_data.py) can
never silently diverge on what "Under 6 Months" or a hospital's slug means.

WHY BUCKETS, NOT RAW TIME BANDS:
NTPF's own band boundaries changed at the same point as the other format
changes (confirmed from real data):
  - 2022+ hospital-level files: 0-6, 6-12, 12-18, 18+ months
  - Pre-2021 files: 0-3, 3-6, 6-9, 9-12, 12+ months
Plotting the raw bands as separate lines across the full date range would
silently compare "0-6 months" against "0-3 months" as if they were the same
series — a real error, not a cosmetic one. Instead, every band is mapped
into one of three buckets that ARE comparable across the whole range:

  Under 6 Months   - normal/expected wait
  6-12 Months      - moderate wait
  12+ Months       - long wait (the category worth flagging)

Bucket assignment is based on the band's STARTING month, extracted from the
label itself (e.g. "12-18 Months" starts at 12, "18 Months +" starts at 18,
"9-12 Months" starts at 9) rather than exact string matching — robust to
minor label wording differences between years, while still being an
explicit, checkable rule rather than a guess.
"""

import re

BUCKET_ORDER = ["Under 6 Months", "6-12 Months", "12+ Months"]


def classify_band(time_band: str) -> str:
    """Extract the starting month number from a band label and bucket it.
    Returns 'Unknown' (never silently dropped) if no number is found, so
    unexpected label formats surface rather than vanish."""
    if not isinstance(time_band, str):
        return "Unknown"
    match = re.match(r"\s*(\d+)", time_band)
    if not match:
        return "Unknown"
    start_month = int(match.group(1))
    if start_month < 6:
        return "Under 6 Months"
    elif start_month < 12:
        return "6-12 Months"
    else:
        return "12+ Months"


def slugify_hospital_name(hospital_name: str) -> str:
    """Matches the filenames already published under site/charts/, e.g.
    "St. Michael's Hospital Dun Laoghaire" -> "st.-michaels-hospital-dun-laoghaire"."""
    return hospital_name.lower().replace(" ", "-").replace("'", "")
