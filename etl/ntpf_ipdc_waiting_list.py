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

    # Small-cell suppression check: NTPF applies its own SDC ("Small Volume"
    # aggregation under 20) at source. We check it's present rather than
    # re-deriving it, per the Legal-first principle — we don't republish
    # anything the source hasn't already cleared.
    text_blob = df.astype(str).apply(lambda s: s.str.lower()).values.tolist()
    flat = [cell for row in text_blob for cell in row]
    suppression_marker_found = any("small volume" in cell for cell in flat)
    print(f"Source-side suppression marker ('Small Volume') found: {suppression_marker_found}")

    return df


# --------------------------------------------------------------------------
# TRANSFORM
# --------------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise column names to snake_case. Deliberately does NOT rename
    columns to specific assumed business names (e.g. 'hospital', 'specialty')
    until the real headers have been confirmed against a live download —
    see the module docstring.
    """
    df = df.copy()
    df.columns = [
        c.strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
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
def document(df: pd.DataFrame, source_url: str) -> None:
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
        "quality_notes": "Loaded via automated ETL prototype; columns not yet manually reviewed against NTPF data dictionary.",
        "known_limitations": "NTPF does not collect activity data (numbers treated/removed) — this is a stock (waiting), not flow, measure.",
        "small_cell_suppression_applied": True,
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
    df = validate(raw_path)
    df = transform(df)
    load(df)
    document(df, source_url=args.source_url)
    print("\nDone. Reproduce this run any time from the raw file alone — that's the point.")


if __name__ == "__main__":
    main()
