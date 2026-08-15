"""
Chart: national waiting list trend for one specialty (e.g. Orthopaedics),
by wait-length bucket, full 2014-2026 range.

DATA SOURCES COMBINED (documented, not silently merged):
  - 2014-2021: from the "IPDC Waiting List by Hospital" file, which DOES
    include a specialty breakdown per hospital at this point. Summed across
    ALL hospitals here to get a national total per specialty.
  - 2021-2026: from NTPF's SEPARATE "IPDC Waiting List by Speciality" file,
    which is national-only (no hospital breakdown) — confirmed by
    inspecting the real downloaded file (2026-08-12): columns are
    ArchiveDate, Adult_Child, Speciality, time bands, Total. No hospital
    column exists in this file at all.

IMPORTANT LIMITATION: this gives a NATIONAL trend only. Hospital-specific
specialty trends (e.g. "Orthopaedics at Galway") are only available for
2014-2021 — NTPF's current format doesn't publish that combination.

USAGE:
    python charts/national_specialty_trend.py "Orthopaedics"
"""

import re
import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from style import apply_style, finish_chart, BUCKET_COLORS

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "charts"

BUCKET_ORDER = ["Under 6 Months", "6-12 Months", "12+ Months"]


def classify_band(time_band: str) -> str:
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


def get_national_specialty_trend(con: duckdb.DuckDBPyConnection, specialty_name: str) -> pd.DataFrame:
    """Sums across ALL hospitals for hospital_specialty rows (pre-2021) and
    uses national_specialty rows directly (2021+) — both filtered to one
    specialty, both excluding the suppression bucket."""
    query = """
        SELECT d.archive_date, f.time_band, f.count, f.granularity
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_specialty s ON f.specialty_id = s.specialty_id
        WHERE s.specialty_name = ?
          AND f.is_suppressed_bucket = FALSE
          AND f.adult_child = 'Adult'
          AND f.granularity IN ('hospital_specialty', 'national_specialty')
    """
    df = con.execute(query, [specialty_name]).df()
    if df.empty:
        return df

    df["bucket"] = df["time_band"].apply(classify_band)
    unknown = df[df["bucket"] == "Unknown"]
    if not unknown.empty:
        print(f"WARNING: {len(unknown)} rows had unrecognised time_band values: {unknown['time_band'].unique()}")
        df = df[df["bucket"] != "Unknown"]

    # This SUM is exactly what makes hospital-level pre-2021 rows into a
    # national total: grouping only by date+bucket, not by hospital.
    grouped = df.groupby(["archive_date", "bucket"], as_index=False)["count"].sum()
    wide = grouped.pivot(index="archive_date", columns="bucket", values="count").fillna(0)
    for b in BUCKET_ORDER:
        if b not in wide.columns:
            wide[b] = 0
    return wide[BUCKET_ORDER].reset_index()


def plot_trend(df: pd.DataFrame, specialty_name: str) -> None:
    if df.empty:
        print(f"No data found for specialty '{specialty_name}'. Check exact name in warehouse.dim_specialty.")
        return

    apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for bucket in BUCKET_ORDER:
        ax.plot(df["archive_date"], df[bucket], label=bucket, color=BUCKET_COLORS[bucket], linewidth=2)

    ax.set_title(f"{specialty_name}: National Waiting List by Length of Wait, "
                 f"{df['archive_date'].min().year}\u2013{df['archive_date'].max().year}")
    ax.set_ylabel("Patients waiting nationally (Adult)")
    ax.legend(loc="upper left", frameon=False)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = specialty_name.lower().replace(" ", "-")
    output_path = OUTPUT_DIR / f"national-{slug}-trend.png"

    finish_chart(
        fig, str(output_path),
        source="National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data (by Hospital, pre-2021; by Speciality, 2021+)",
        last_updated=str(df["archive_date"].max().date()),
        methodology_note=(
            "National total: 2014-2021 summed across all hospitals from the Hospital file's "
            "specialty breakdown; 2021-2026 from NTPF's separate national Speciality file."
        ),
    )


def main():
    if len(sys.argv) < 2:
        print('Usage: python charts/national_specialty_trend.py "Specialty Name"')
        print("Tip: check exact names with: duckdb data/processed/irishhealthdata.duckdb "
              '-c "SELECT specialty_name FROM warehouse.dim_specialty ORDER BY specialty_name;"')
        sys.exit(1)

    specialty_name = sys.argv[1]
    con = duckdb.connect(str(DB_PATH))
    df = get_national_specialty_trend(con, specialty_name)
    con.close()
    plot_trend(df, specialty_name)


if __name__ == "__main__":
    main()
