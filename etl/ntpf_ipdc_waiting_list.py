"""
ETL prototype: NTPF IPDC Waiting List by Hospital
Technical Design Document Week 5 proof point (Decision 006 closes at the end of this run).

Pipeline: Extract -> Validate -> Transform -> Load -> Document
This is the reusable template every future dataset should copy.

USAGE:
    python ntpf_ipdc_waiting_list.py --source-url <csv-url>
    python ntpf_ipdc_waiting_list.py --source-file /path/to/local.csv

NOTE: This script introspects the CSV's actual columns at runtime rather than
hardcoding assumed NTPF column names. The exact headers weren't verifiable from
within the build sandbox (network + binary-fetch restrictions) — on first real
run, inspect the printed column report before trusting the transform step blindly.
"""

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "metadata.schema.json"
DB_PATH = PROCESSED_DIR / "irishhealthdata.duckdb"
LICENSING_REGISTER = REPO_ROOT / "docs" / "LICENSING.md"

DATASET_ID = "ntpf-ipdc-waiting-list-by-hospital"
SOURCE_NAME = "National Treatment Purchase Fund (NTPF)"
SOURCE_PAGE = "https://www.ntpf.ie/waiting-list-data/open-data/"
LICENCE = "Re-use of Public Service Information (PSI) — see NTPF Data Protection / Re-use of Public Service Information page"
ATTRIBUTION = "Source: National Treatment Purchase Fund (NTPF), Open Data — Waiting List Data"


# --------------------------------------------------------------------------
# EXTRACT
# --------------------------------------------------------------------------
def extract(source_url: str = None, source_file: str = None) -> Path:
    """Download (or load) the raw CSV and archive it verbatim, unmodified."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    raw_path = RAW_DIR / f"{DATASET_ID}_{today}.csv"

    if source_file:
        content = Path(source_file).read_bytes()
    elif source_url:
        print(f"Downloading {source_url} ...")
        resp = requests.get(source_url, timeout=30)
        resp.raise_for_status()
        content = resp.content
    else:
        raise ValueError("Provide either --source-url or --source-file")

    raw_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    print(f"Raw file archived: {raw_path} (sha256: {checksum[:12]}...)")
    return raw_path


# --------------------------------------------------------------------------
# VALIDATE
# --------------------------------------------------------------------------
def validate(raw_path: Path) -> pd.DataFrame:
    """
    Load the raw CSV and report its actual structure. NTPF files have varied
    slightly over the years (see the Open Data page's per-year download list),
    so we introspect rather than assume.
    """
    df = pd.read_csv(raw_path)

    print("\n--- Column report (inspect before trusting the transform step) ---")
    for col in df.columns:
        print(f"  {col!r}: {df[col].dtype}, {df[col].nunique()} unique values")
    print(f"Rows: {len(df)}")

    if df.empty:
        raise ValueError("Downloaded file has no rows — refusing to proceed.")

    # Small-cell suppression check: some NTPF files apply SDC via a "Small
    # Volume" text marker; this hospital-level file does not appear to (it's
    # aggregated enough that suppression isn't triggered). We detect rather
    # than assume, per the Legal-first principle — never assert a suppression
    # guarantee the source data doesn't actually demonstrate.
    text_blob = df.astype(str).apply(lambda s: s.str.lower()).values.tolist()
    flat = [cell for row in text_blob for cell in row]
    suppression_marker_found = any(
        marker in cell for cell in flat for marker in ("small volume", "<5", "n/a")
    )
    print(f"Source-side suppression marker found: {suppression_marker_found}")

    return df, suppression_marker_found


# --------------------------------------------------------------------------
# TRANSFORM
# --------------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Confirmed against a real download (2026-08-11). This file is
    hospital-level, wide-format: one row per hospital per Adult/Child list,
    with each waiting-time band as its own column. No Specialty or Case_Type
    breakdown exists at this level.

    Two fixes applied here based on the real data:
      1. Column names standardised to snake_case.
      2. Numeric columns (waiting counts) arrive as text with comma thousands
         separators (e.g. "5,434") and must be parsed to integers — pandas
         reads them as strings by default, which would silently break any
         downstream sum/comparison if left as-is.
    """
    df = df.copy()

    rename_map = {
        "ArchiveDate": "archive_date",
        "Adult_Child": "adult_child",
        "HospitalName": "hospital_name",
        "0-6 Months": "months_0_6",
        "6-12 Months": "months_6_12",
        "12-18 Months": "months_12_18",
        "18 Months +": "months_18_plus",
        "Total": "total",
    }
    df = df.rename(columns=rename_map)
    # Fallback for any columns not in the known map (keeps script from
    # silently dropping data if NTPF changes headers in a future month)
    df.columns = [
        rename_map.get(c, c.strip().lower().replace(" ", "_").replace("-", "_"))
        for c in df.columns
    ]

    numeric_cols = ["months_0_6", "months_6_12", "months_12_18", "months_18_plus", "total"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.replace(",", "", regex=False).str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "archive_date" in df.columns:
        df["archive_date"] = pd.to_datetime(
            df["archive_date"], format="%d/%m/%Y", errors="coerce"
        ).dt.date

    return df


# --------------------------------------------------------------------------
# LOAD
# --------------------------------------------------------------------------
def load(df: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw_loads")
    table_name = DATASET_ID.replace("-", "_")
    con.register("df_view", df)
    con.execute(f"CREATE OR REPLACE TABLE raw_loads.{table_name} AS SELECT * FROM df_view")
    row_count = con.execute(f"SELECT COUNT(*) FROM raw_loads.{table_name}").fetchone()[0]
    con.close()
    print(f"Loaded {row_count} rows into {DB_PATH} -> raw_loads.{table_name}")


# --------------------------------------------------------------------------
# DOCUMENT
# --------------------------------------------------------------------------
def document(df: pd.DataFrame, source_url: str, suppression_marker_found: bool) -> None:
    """Write the metadata record (validated against the JSON Schema) and
    append a row to the licensing register."""
    today = date.today().isoformat()
    metadata = {
        "dataset_id": DATASET_ID,
        "title": "IPDC Waiting List by Hospital",
        "owner": "Plunkett McCullagh",
        "source_name": SOURCE_NAME,
        "source_url": source_url or SOURCE_PAGE,
        "licence": LICENCE,
        "attribution_required": ATTRIBUTION,
        "redistribution_allowed": True,
        "variables": list(df.columns),
        "geography_level": "hospital",
        "update_frequency": "monthly",
        "download_date": today,
        "processing_date": today,
        "citation": f"{SOURCE_NAME}, Open Data — Waiting List Data, accessed {today}",
        "quality_notes": (
            "Confirmed against live download 2026-08-11: wide-format, one row per "
            "hospital per Adult/Child list, no specialty breakdown at this level. "
            "Numeric columns arrive as comma-formatted text and are parsed to "
            "integers in transform()."
        ),
        "known_limitations": (
            "NTPF does not collect activity data (numbers treated/removed) — this is "
            "a stock (waiting), not flow, measure. No specialty-level breakdown in "
            "this particular file (see NTPF Open Data page for specialty-level files "
            "if needed later)."
        ),
        "small_cell_suppression_applied": suppression_marker_found,
    }

    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    _validate_against_schema(metadata, schema)

    metadata_path = REPO_ROOT / "docs" / f"{DATASET_ID}.metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata written and validated: {metadata_path}")

    _append_licensing_register(metadata)


def _validate_against_schema(instance: dict, schema: dict) -> None:
    """Minimal dependency-free schema check (required fields + basic types).
    Swap for `jsonschema.validate()` once the package is added to requirements."""
    missing = [f for f in schema.get("required", []) if f not in instance]
    if missing:
        raise ValueError(f"Metadata record missing required fields: {missing}")
    allowed = set(schema.get("properties", {}).keys())
    extra = set(instance.keys()) - allowed
    if extra:
        raise ValueError(f"Metadata record has undeclared fields: {extra}")


def _append_licensing_register(metadata: dict) -> None:
    LICENSING_REGISTER.parent.mkdir(parents=True, exist_ok=True)
    header = "| dataset_id | source | licence | attribution_required | redistribution_allowed | added |\n|---|---|---|---|---|---|\n"
    if not LICENSING_REGISTER.exists():
        LICENSING_REGISTER.write_text("# Licensing Register\n\n" + header)

    row = (
        f"| {metadata['dataset_id']} | {metadata['source_name']} | {metadata['licence']} "
        f"| {metadata['attribution_required']} | {metadata['redistribution_allowed']} "
        f"| {metadata['download_date']} |\n"
    )
    existing = LICENSING_REGISTER.read_text()
    if metadata["dataset_id"] not in existing:
        with open(LICENSING_REGISTER, "a") as f:
            f.write(row)
        print(f"Licensing register updated: {LICENSING_REGISTER}")
    else:
        print("Licensing register already has an entry for this dataset — skipped duplicate row.")


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", help="Direct URL to the NTPF CSV")
    parser.add_argument("--source-file", help="Path to an already-downloaded CSV")
    args = parser.parse_args()

    if not args.source_url and not args.source_file:
        print(
            "No source given. Example real source (verify current link on "
            f"{SOURCE_PAGE} before use):\n"
            "  https://www.ntpf.ie/app/uploads/2026/07/OpenData_IPDCNational01.csv\n",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_path = extract(source_url=args.source_url, source_file=args.source_file)
    df, suppression_marker_found = validate(raw_path)
    df = transform(df)
    load(df)
    document(df, source_url=args.source_url, suppression_marker_found=suppression_marker_found)
    print("\nDone. Reproduce this run any time from the raw file alone — that's the point.")


if __name__ == "__main__":
    main()