"""
Chart: national IPDC waiting list total, across all available years.

Sibling to hospital_trend.py, aggregated across every hospital instead of
one. Same comparability logic applies (pre-2021 rows summed across Case
Type, specialty, and time band per date), plus the same list_type filter
required since Decision 009 added Outpatient (OP) data to the same
fact_waiting_list table (see hospital_trend.py's docstring for the
concrete bug this filter fixes if omitted).

The JOIN to dim_hospital is what keeps the national total correct: it
naturally excludes granularity='national_specialty' rows (hospital_id IS
NULL, from NTPF's separate by-Speciality file), which cover the same
patients from a different cut and would double-count the total if
included — same reasoning as export_dashboard_data.py's get_national_data().

USAGE:
    python charts/national_ipdc_trend.py
"""

import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from style import apply_style, finish_chart, COLOR_PRIMARY

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "charts"


def get_national_trend(con: duckdb.DuckDBPyConnection):
    query = """
        SELECT d.archive_date, SUM(f.count) AS total_waiting
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE f.is_suppressed_bucket = FALSE
          AND f.adult_child = 'Adult'
          AND f.list_type = 'ipdc'
        GROUP BY d.archive_date
        ORDER BY d.archive_date
    """
    return con.execute(query).df()


def plot_trend(df) -> None:
    if df.empty:
        print("No national data found.")
        return

    apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.5))

    ax.plot(df["archive_date"], df["total_waiting"], color=COLOR_PRIMARY, linewidth=2)
    ax.fill_between(df["archive_date"], df["total_waiting"], color=COLOR_PRIMARY, alpha=0.08)

    ax.set_title(f"National IPDC Waiting List, {df['archive_date'].min().year}–{df['archive_date'].max().year}")
    ax.set_ylabel("Total patients waiting (Inpatient + Day Case, Adult)")
    ax.set_xlabel("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "national-ipdc-total-trend.png"

    finish_chart(
        fig, str(output_path),
        source="National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data",
        last_updated=str(df["archive_date"].max().date()),
        methodology_note=(
            "Pre-2021 figures summed across Inpatient + Day Case and all specialties "
            "for comparability with the combined post-2021 reporting format. "
            "National total summed across every hospital, Adult patients."
        ),
    )


def main():
    con = duckdb.connect(str(DB_PATH))
    df = get_national_trend(con)
    con.close()
    plot_trend(df)


if __name__ == "__main__":
    main()
