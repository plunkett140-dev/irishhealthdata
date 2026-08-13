"""
Chart: waiting-time band breakdown for one hospital, over time.

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

USAGE:
    python charts/hospital_band_breakdown.py "Beaumont Hospital"
"""

import re
import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from style import apply_style, finish_chart, PALETTE

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "charts"

BUCKET_ORDER = ["Under 6 Months", "6-12 Months", "12+ Months"]
BUCKET_COLORS = {
    "Under 6 Months": PALETTE[0],
    "6-12 Months": PALETTE[4],
    "12+ Months": PALETTE[1],
}


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


def get_band_breakdown(con: duckdb.DuckDBPyConnection, hospital_name: str) -> pd.DataFrame:
    query = """
        SELECT d.archive_date, f.time_band, f.count
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE h.hospital_name = ?
          AND f.is_suppressed_bucket = FALSE
          AND f.adult_child = 'Adult'
    """
    df = con.execute(query, [hospital_name]).df()
    if df.empty:
        return df

    df["bucket"] = df["time_band"].apply(classify_band)

    unknown = df[df["bucket"] == "Unknown"]
    if not unknown.empty:
        print(f"WARNING: {len(unknown)} rows had unrecognised time_band values, "
              f"not included in chart: {unknown['time_band'].unique()}")
        df = df[df["bucket"] != "Unknown"]

    grouped = df.groupby(["archive_date", "bucket"], as_index=False)["count"].sum()
    wide = grouped.pivot(index="archive_date", columns="bucket", values="count").fillna(0)
    for b in BUCKET_ORDER:
        if b not in wide.columns:
            wide[b] = 0
    return wide[BUCKET_ORDER].reset_index()


def plot_band_breakdown(df: pd.DataFrame, hospital_name: str) -> None:
    if df.empty:
        print(f"No data found for '{hospital_name}'.")
        return

    apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.5))

    for bucket in BUCKET_ORDER:
        ax.plot(df["archive_date"], df[bucket], label=bucket,
                color=BUCKET_COLORS[bucket], linewidth=2)

    ax.set_title(f"{hospital_name}: Waiting List by Length of Wait, "
                 f"{df['archive_date'].min().year}\u2013{df['archive_date'].max().year}")
    ax.set_ylabel("Patients waiting (Adult)")
    ax.legend(loc="upper left", frameon=False)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = hospital_name.lower().replace(" ", "-").replace("'", "")
    output_path = OUTPUT_DIR / f"{slug}-band-breakdown.png"

    finish_chart(
        fig, str(output_path),
        source="National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data",
        last_updated=str(df["archive_date"].max().date()),
        methodology_note=(
            "Time bands vary in exact boundaries pre/post-2021 reporting change; "
            "grouped here into Under 6 / 6-12 / 12+ months by starting wait length "
            "for comparability across the full period."
        ),
    )


def main():
    if len(sys.argv) < 2:
        print('Usage: python charts/hospital_band_breakdown.py "Hospital Name"')
        sys.exit(1)

    hospital_name = sys.argv[1]
    con = duckdb.connect(str(DB_PATH))
    df = get_band_breakdown(con, hospital_name)
    con.close()
    plot_band_breakdown(df, hospital_name)


if __name__ == "__main__":
    main()
