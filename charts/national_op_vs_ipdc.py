"""
Chart: national IPDC total vs. national Outpatient (OP) total, latest date.

Simple two-bar comparison — the two national totals sit at genuinely
different scales (OP is roughly 5x IPDC), so this exists specifically to
make that scale difference visible at a glance, alongside the trend charts
which show each dataset's shape over time separately.

Uses PALETTE, not BUCKET_COLORS: this compares two different DATASETS
(list types), not three wait-length buckets within one dataset, so the
green/amber/red traffic-light semantics (Decision 011) don't apply here —
reusing them would incorrectly imply one bar is "the good one."

USAGE:
    python charts/national_op_vs_ipdc.py
"""

import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from style import apply_style, finish_chart, PALETTE, COLOR_TEXT

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "charts"


def get_national_totals(con: duckdb.DuckDBPyConnection):
    """Latest-date national total per list type, Adult — same query shape
    as national_ipdc_trend.py's get_national_trend(), just the most recent
    row for each list_type rather than the full series."""
    query = """
        SELECT f.list_type, d.archive_date, SUM(f.count) AS total_waiting
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE f.is_suppressed_bucket = FALSE
          AND f.adult_child = 'Adult'
          AND d.archive_date = (SELECT MAX(archive_date) FROM warehouse.dim_date)
        GROUP BY f.list_type, d.archive_date
        ORDER BY f.list_type
    """
    return con.execute(query).df()


def plot_comparison(df) -> None:
    if df.empty:
        print("No national data found.")
        return

    apply_style()
    fig, ax = plt.subplots(figsize=(7, 5.5))

    labels = {"ipdc": "Inpatient / Day Case", "op": "Outpatient"}
    colors = {"ipdc": PALETTE[0], "op": PALETTE[2]}

    ordered = df.set_index("list_type").loc[["ipdc", "op"]].reset_index()
    bar_labels = [labels[lt] for lt in ordered["list_type"]]
    bar_colors = [colors[lt] for lt in ordered["list_type"]]

    bars = ax.bar(bar_labels, ordered["total_waiting"], color=bar_colors, width=0.5)
    for bar, value in zip(bars, ordered["total_waiting"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + max(ordered["total_waiting"]) * 0.015,
            f"{int(value):,}", ha="center", va="bottom", fontsize=12, fontweight="bold", color=COLOR_TEXT,
        )

    archive_date = ordered["archive_date"].iloc[0]
    ax.set_title(f"National Waiting List: Outpatient vs. Inpatient/Day Case, {archive_date.strftime('%B %Y')}")
    ax.set_ylabel("Total patients waiting (Adult)")
    ax.set_ylim(0, max(ordered["total_waiting"]) * 1.15)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "national-op-vs-ipdc.png"

    finish_chart(
        fig, str(output_path),
        source="National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data",
        last_updated=str(archive_date.date()),
        methodology_note=(
            "Outpatient appointments (referrals awaiting a first hospital consultation) "
            "and IPDC (inpatient/day-case procedures already scheduled) are different "
            "stages of care and different NTPF datasets — shown together here for scale, "
            "not as parts of one combined total."
        ),
    )


def main():
    con = duckdb.connect(str(DB_PATH))
    df = get_national_totals(con)
    con.close()
    plot_comparison(df)


if __name__ == "__main__":
    main()
