"""
Chart: total IPDC waiting list for one hospital, across all available years.

Comparability note (documented, not silently assumed — see chat log and
Technical Design Document):
  - 2022+ hospital-level files report ONE combined Inpatient+Day Case total
    per hospital per time-band (that's what "IPDC" means).
  - Pre-2021 files report Inpatient and Day Case as SEPARATE rows per
    hospital/specialty/time-band (via the Case_Type column).
  - To get a genuinely comparable "total people waiting at this hospital"
    figure across the full 2014-2026 range, pre-2021 rows must be SUMMED
    across Case_Type (and across specialty, and across time-band) per
    hospital per archive_date. This script does that explicitly rather
    than charting a partial/wrong number.

USAGE:
    python charts/hospital_trend.py "Galway University Hospitals"
"""

import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
from style import apply_style, finish_chart, COLOR_PRIMARY
from wait_time_buckets import slugify_hospital_name

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "charts"


def get_trend(con: duckdb.DuckDBPyConnection, hospital_name: str):
    """One row per archive_date: total people waiting at this hospital,
    summed across case type, specialty, and time band — the only version
    of this number that's comparable across the full date range.

    list_type = 'ipdc' is required, not optional: fact_waiting_list also
    holds Outpatient (OP) rows since the OP dataset was added (Decision
    009), in the same table distinguished only by this column. Without
    this filter, this query silently sums IPDC + OP together — confirmed
    as a real bug (2026-08-15): re-running without the filter reproduced
    exactly 69,390 for Beaumont Hospital, which is 12,536 (IPDC) + 56,854
    (OP), not a real "total waiting" figure for anything. This chart is
    titled and documented as IPDC specifically; it must stay that way."""
    query = """
        SELECT d.archive_date, SUM(f.count) AS total_waiting
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE h.hospital_name = ?
          AND f.is_suppressed_bucket = FALSE
          AND f.adult_child = 'Adult'
          AND f.list_type = 'ipdc'
        GROUP BY d.archive_date
        ORDER BY d.archive_date
    """
    return con.execute(query, [hospital_name]).df()


def plot_trend(df, hospital_name: str) -> None:
    if df.empty:
        print(f"No data found for '{hospital_name}'. Check the exact name in warehouse.dim_hospital.")
        return

    apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.5))

    ax.plot(df["archive_date"], df["total_waiting"], color=COLOR_PRIMARY, linewidth=2)
    ax.fill_between(df["archive_date"], df["total_waiting"], color=COLOR_PRIMARY, alpha=0.08)

    ax.set_title(f"{hospital_name}: Total IPDC Waiting List, {df['archive_date'].min().year}\u2013{df['archive_date'].max().year}")
    ax.set_ylabel("Total patients waiting (Inpatient + Day Case, Adult)")
    ax.set_xlabel("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify_hospital_name(hospital_name)
    output_path = OUTPUT_DIR / f"{slug}-trend.png"

    finish_chart(
        fig, str(output_path),
        source="National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data",
        last_updated=str(df["archive_date"].max().date()),
        methodology_note=(
            "Pre-2021 figures summed across Inpatient + Day Case and all specialties "
            "for comparability with the combined post-2021 reporting format."
        ),
    )


def main():
    if len(sys.argv) < 2:
        print('Usage: python charts/hospital_trend.py "Hospital Name"')
        print("Tip: check exact names with: duckdb data/processed/irishhealthdata.duckdb "
              '-c "SELECT hospital_name FROM warehouse.dim_hospital ORDER BY hospital_name;"')
        sys.exit(1)

    hospital_name = sys.argv[1]
    con = duckdb.connect(str(DB_PATH))
    df = get_trend(con, hospital_name)
    con.close()
    plot_trend(df, hospital_name)


if __name__ == "__main__":
    main()
