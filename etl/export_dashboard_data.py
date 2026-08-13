"""
Week 8: Export the warehouse to static JSON for the interactive dashboard.

Per Decision 008 in the Technical Design Document, the live site never
queries DuckDB directly — the database only exists on the machine that
builds it. This script is the boundary: it reads warehouse.fact_waiting_list
(built by build_warehouse_schema.py) and writes one static JSON file per
hospital plus an index file, both under site/public/data/hospitals/, for
Next.js to serve as plain static assets.

Reuses the exact same queries and bucketing rule as the existing matplotlib
scripts (charts/hospital_trend.py for the total, charts/hospital_band_
breakdown.py for the band breakdown, both now sourcing classify_band /
slugify_hospital_name from wait_time_buckets.py) so the interactive chart
and the static PNGs can never silently disagree on a number.

Every export covers BOTH populations NTPF publishes (Adult and Child), keyed
under a "populations" object in each JSON file, so the dashboard can offer a
toggle rather than silently dropping Child data (as the original matplotlib
scripts did). Not every hospital has both: e.g. Children's Health Ireland
has Child rows only, most general hospitals have far more Adult than Child
rows. A population with zero rows for a given hospital gets an empty series
rather than being omitted, so the frontend can show an explicit "no data"
state instead of a missing key.

Rerun this after every warehouse rebuild (i.e. every time new NTPF data is
ingested) and commit the changed JSON — Vercel redeploys automatically on
push per Decision 008.

USAGE:
    python etl/export_dashboard_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wait_time_buckets import BUCKET_ORDER, classify_band, slugify_hospital_name

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "data" / "hospitals"

SOURCE = "National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data"
METHODOLOGY_NOTE = (
    "Pre-2021 figures summed across Inpatient + Day Case and all specialties "
    "for comparability with the combined post-2021 reporting format. Time "
    "bands grouped into Under 6 / 6-12 / 12+ months by starting wait length, "
    "since NTPF's own band boundaries changed at the same point (2022+ files "
    "use 0-6/6-12/12-18/18+ months; pre-2021 files use 0-3/3-6/6-9/9-12/12+ "
    "months) and are not directly comparable band-for-band."
)
KNOWN_LIMITATIONS = (
    "Adult and Child are NTPF's own classification (no further age "
    "breakdown is published). A hospital with no patients in a population "
    "shows an empty chart for that toggle rather than being hidden."
)

POPULATIONS = ["Adult", "Child"]
TOP_SPECIALTIES_COUNT = 15


def get_hospital_names(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every real hospital with data in EITHER population, so a hospital
    that's Child-only (e.g. Children's Health Ireland) or Adult-only still
    appears in the dropdown."""
    rows = con.execute("""
        SELECT DISTINCT h.hospital_name
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE f.is_suppressed_bucket = FALSE
        ORDER BY h.hospital_name
    """).fetchall()
    return [r[0] for r in rows]


def _rows_to_series_df(df: pd.DataFrame) -> pd.DataFrame:
    """Shared aggregation: raw (archive_date, time_band, count) rows -> one
    row per archive_date with total + the three bucket sums."""
    if df.empty:
        return df

    df["bucket"] = df["time_band"].apply(classify_band)
    df = df[df["bucket"] != "Unknown"]
    if df.empty:
        return df

    grouped = df.groupby(["archive_date", "bucket"], as_index=False)["count"].sum()
    wide = grouped.pivot(index="archive_date", columns="bucket", values="count").fillna(0)
    for b in BUCKET_ORDER:
        if b not in wide.columns:
            wide[b] = 0
    wide = wide[BUCKET_ORDER]
    wide["total"] = wide[BUCKET_ORDER].sum(axis=1)
    return wide.reset_index().sort_values("archive_date")


def get_hospital_data(con: duckdb.DuckDBPyConnection, hospital_name: str, adult_child: str) -> pd.DataFrame:
    """One row per archive_date with total + the three bucket sums, for one
    hospital and one population — same filters (is_suppressed_bucket =
    FALSE) as charts/hospital_trend.py and charts/hospital_band_breakdown.py,
    generalised to take adult_child as a parameter instead of hardcoding
    'Adult'."""
    query = """
        SELECT d.archive_date, f.time_band, f.count
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE h.hospital_name = ?
          AND f.is_suppressed_bucket = FALSE
          AND f.adult_child = ?
    """
    df = con.execute(query, [hospital_name, adult_child]).df()
    return _rows_to_series_df(df)


def get_national_data(con: duckdb.DuckDBPyConnection, adult_child: str) -> pd.DataFrame:
    """One row per archive_date, summed across every real hospital for one
    population (i.e. the true national total for that population). The JOIN
    to dim_hospital is what keeps this correct: it naturally excludes
    granularity='national_specialty' rows (hospital_id IS NULL, from NTPF's
    separate by-Speciality file), which cover the same patients from a
    different cut and would double-count the total if included alongside
    the hospital-level rows."""
    query = """
        SELECT d.archive_date, f.time_band, f.count
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_hospital h ON f.hospital_id = h.hospital_id
        WHERE f.is_suppressed_bucket = FALSE
          AND f.adult_child = ?
    """
    df = con.execute(query, [adult_child]).df()
    return _rows_to_series_df(df)


def get_national_specialty_breakdown(con: duckdb.DuckDBPyConnection, adult_child: str) -> tuple[pd.DataFrame, str]:
    """Total waiting per specialty, nationally, for one population, broken
    down by the same Under 6 / 6-12 / 12+ month buckets used everywhere else
    on the site, at the most recent archive_date available for THAT
    population in the specialty-level data (Adult and Child don't
    necessarily share a latest date). Mirrors the source combination in
    charts/national_specialty_trend.py: pre-2021 rows come from the
    by-Hospital file's specialty breakdown (granularity 'hospital_specialty',
    summed across hospitals here), 2021+ rows come from NTPF's separate
    by-Speciality file (granularity 'national_specialty', already
    national-only). Unlike get_national_data, this deliberately does NOT
    join dim_hospital, since 'national_specialty' rows have no hospital_id
    and would be dropped by that join."""
    latest_date = con.execute("""
        SELECT MAX(d.archive_date)
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        WHERE f.granularity IN ('hospital_specialty', 'national_specialty')
          AND f.adult_child = ?
    """, [adult_child]).fetchone()[0]

    if latest_date is None:
        return pd.DataFrame(), None

    query = """
        SELECT s.specialty_name, f.time_band, f.count
        FROM warehouse.fact_waiting_list f
        JOIN warehouse.dim_date d ON f.date_id = d.date_id
        JOIN warehouse.dim_specialty s ON f.specialty_id = s.specialty_id
        WHERE f.is_suppressed_bucket = FALSE
          AND f.adult_child = ?
          AND d.archive_date = ?
    """
    df = con.execute(query, [adult_child, latest_date]).df()

    df["bucket"] = df["time_band"].apply(classify_band)
    df = df[df["bucket"] != "Unknown"]
    if df.empty:
        return df, latest_date.strftime("%Y-%m-%d")

    grouped = df.groupby(["specialty_name", "bucket"], as_index=False)["count"].sum()
    wide = grouped.pivot(index="specialty_name", columns="bucket", values="count").fillna(0)
    for b in BUCKET_ORDER:
        if b not in wide.columns:
            wide[b] = 0
    wide = wide[BUCKET_ORDER]
    wide["total"] = wide[BUCKET_ORDER].sum(axis=1)
    wide = wide.sort_values("total", ascending=False).reset_index()
    return wide, latest_date.strftime("%Y-%m-%d")


def series_df_to_json(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"last_updated": None, "series": []}
    series = [
        {
            "date": row["archive_date"].strftime("%Y-%m-%d"),
            "total": int(row["total"]),
            "under_6": int(row["Under 6 Months"]),
            "six_to_12": int(row["6-12 Months"]),
            "twelve_plus": int(row["12+ Months"]),
        }
        for _, row in df.iterrows()
    ]
    return {"last_updated": df["archive_date"].max().strftime("%Y-%m-%d"), "series": series}


def specialty_df_to_json(df: pd.DataFrame, last_updated: str | None) -> dict:
    total_specialties = len(df)
    top_df = df.head(TOP_SPECIALTIES_COUNT)
    return {
        "last_updated": last_updated,
        "known_limitations": (
            f"Showing the {len(top_df)} largest specialties by current "
            f"waiting list volume, out of {total_specialties} specialties "
            f"tracked for this population."
            if total_specialties
            else "No specialty-level data available for this population."
        ),
        "items": [
            {
                "specialty_name": row["specialty_name"],
                "total": int(row["total"]),
                "under_6": int(row["Under 6 Months"]),
                "six_to_12": int(row["6-12 Months"]),
                "twelve_plus": int(row["12+ Months"]),
            }
            for _, row in top_df.iterrows()
        ],
    }


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    print("Exporting national totals (Adult + Child)...")
    national_record = {
        "hospital_name": "National",
        "slug": "national",
        "source": SOURCE,
        "methodology_note": METHODOLOGY_NOTE + " National total is summed "
        "across every hospital (excluding NTPF's separate by-Speciality "
        "file, which would double-count).",
        "known_limitations": KNOWN_LIMITATIONS,
        "populations": {
            pop: series_df_to_json(get_national_data(con, pop)) for pop in POPULATIONS
        },
    }
    national_path = REPO_ROOT / "site" / "public" / "data" / "national.json"
    national_path.parent.mkdir(parents=True, exist_ok=True)
    national_path.write_text(json.dumps(national_record, indent=2))
    for pop in POPULATIONS:
        print(f"  {pop}: {len(national_record['populations'][pop]['series'])} points")
    print(f"  wrote {national_path.relative_to(REPO_ROOT)}")

    print("\nExporting national specialty breakdown (Adult + Child)...")
    specialty_record = {
        "source": SOURCE,
        "methodology_note": (
            "National total per specialty at the most recent date for that "
            "population, broken down into Under 6 / 6-12 / 12+ months by "
            "starting wait length (same bucket rule as the other charts on "
            "this page). Pre-2021: summed across all hospitals from the "
            "by-Hospital file's specialty breakdown. 2021+: NTPF's separate "
            "by-Speciality file (national totals only, no hospital "
            "breakdown)."
        ),
        "populations": {},
    }
    for pop in POPULATIONS:
        df, last_updated = get_national_specialty_breakdown(con, pop)
        specialty_record["populations"][pop] = specialty_df_to_json(df, last_updated)
        print(f"  {pop}: {len(specialty_record['populations'][pop]['items'])} of {len(df)} specialties")
    specialty_path = REPO_ROOT / "site" / "public" / "data" / "national_by_specialty.json"
    specialty_path.write_text(json.dumps(specialty_record, indent=2))
    print(f"  wrote {specialty_path.relative_to(REPO_ROOT)}")

    hospital_names = get_hospital_names(con)
    print(f"\nExporting {len(hospital_names)} hospitals (Adult + Child)...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for hospital_name in hospital_names:
        slug = slugify_hospital_name(hospital_name)
        populations = {
            pop: series_df_to_json(get_hospital_data(con, hospital_name, pop))
            for pop in POPULATIONS
        }
        record = {
            "hospital_name": hospital_name,
            "slug": slug,
            "source": SOURCE,
            "methodology_note": METHODOLOGY_NOTE,
            "known_limitations": KNOWN_LIMITATIONS,
            "populations": populations,
        }
        out_path = OUTPUT_DIR / f"{slug}.json"
        out_path.write_text(json.dumps(record, indent=2))
        index.append({"slug": slug, "hospital_name": hospital_name})
        counts = ", ".join(f"{pop}={len(populations[pop]['series'])}" for pop in POPULATIONS)
        print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({counts})")

    con.close()

    index.sort(key=lambda h: h["hospital_name"])
    index_path = OUTPUT_DIR / "index.json"
    index_path.write_text(json.dumps(index, indent=2))
    print(f"\nWrote {index_path.relative_to(REPO_ROOT)} ({len(index)} hospitals)")


if __name__ == "__main__":
    main()
