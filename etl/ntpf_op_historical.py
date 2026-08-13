"""
Historical loader: NTPF Outpatient (OP) Waiting List by Hospital, 2018-2026.

Sibling script to ntpf_ipdc_historical.py, same loader pattern. Investigated
directly against real files before writing this (2026-08-13) — see the
Technical Design Document Decision Log for the full writeup. Key findings
that shaped this script:

  - OP data does NOT go back to 2014 like IPDC. NTPF's Open Data page lists
    2014-2017 as year-selector options but has no actual download links for
    them — confirmed by checking the page directly, not assumed. This
    script only covers 2018-2026, the years that actually exist.

  - The two format eras exactly mirror IPDC's eras, at the same split point:
      ERA A (2021_apr_dec-2026): wide format, hospital-only.
          ArchiveDate, Adult_Child, HospitalName, <band columns>, Total
      ERA B/C (2018-2021_jan_mar): long format, hospital + specialty
          breakdown, finer bands (0-3/3-6/6-9/9-12/12+ months).
          Archive_Date/Group/Hospital_HIPE/Hospital/Speciality/Adult_Child/
          Age_Profile/Time_Bands/Total (naming varies slightly by year,
          same as IPDC's pre-2021 quirks).

  - The one real structural difference from IPDC: OP has NO Case_Type
    (Inpatient/Day Case) column at any era, in the hospital file or the
    speciality file. This makes sense — outpatient appointments are a
    single appointment type, there's no inpatient/day-case split to make.
    IPDC's pre-2021 long-format files DO have Case_Type; OP's equivalent
    files don't.

Like ntpf_ipdc_historical.py, this script introspects each year's real
columns rather than assuming a shape, and loads each year into its own
raw_loads table so format differences across years stay visible rather than
being silently merged. Building the unified fact table is
build_warehouse_schema.py's job, not this script's.

USAGE:
    python ntpf_op_historical.py
    python ntpf_op_historical.py --years 2020 2021_jan_mar 2019
"""

import argparse
import subprocess
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "ntpf_op_historical"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "irishhealthdata.duckdb"
LICENSING_REGISTER = REPO_ROOT / "docs" / "LICENSING.md"

SOURCE_NAME = "National Treatment Purchase Fund (NTPF)"
LICENCE = "Re-use of Public Service Information (PSI) — see NTPF Data Protection / Re-use of Public Service Information page"

# Real URLs confirmed directly from the NTPF Open Data page (fetched
# 2026-08-13). Same caveat as ntpf_ipdc_historical.py: NTPF re-hosts these
# under changing /app/uploads/YYYY/MM/ paths when they update the page — if
# a download fails with a 404, re-check
# https://www.ntpf.ie/waiting-list-data/open-data/ and update the URL below.
# No 2014-2017 entries: confirmed these years have no OP download links,
# unlike IPDC which goes back to 2014.
YEAR_SOURCES = {
    "2026": "https://www.ntpf.ie/app/uploads/2026/07/OpenData_OPNational01.csv",
    "2025": "https://www.ntpf.ie/app/uploads/2026/01/OpenData_OPNational01_2025.csv",
    "2024": "https://www.ntpf.ie/app/uploads/2025/01/OpenData_OPNational01_2024-1.csv",
    "2023": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_OPNational01_2023-2.csv",
    "2022": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_OPNational01_2022.csv",
    "2021_apr_dec": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_OPNational01_2021-1.csv",
    "2021_jan_mar": "https://www.ntpf.ie/app/uploads/2024/10/OP-Waiting-List-By-Group-Hospital-2021-1.csv",
    "2020": "https://www.ntpf.ie/app/uploads/2024/10/OP-Waiting-List-by-Group-Hospital-2020.csv",
    "2019": "https://www.ntpf.ie/app/uploads/2025/02/OP-Waiting-List-by-Group-Hospital-2019.csv",
    "2018": "https://www.ntpf.ie/app/uploads/2025/02/OP-Waiting-List-by-Group-Hospital-2018.csv",
}


def download(year_key: str, url: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"ntpf_op_{year_key}.csv"
    if raw_path.exists():
        print(f"[{year_key}] already downloaded, skipping fetch: {raw_path}")
        return raw_path

    print(f"[{year_key}] downloading {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except requests.exceptions.ConnectionError:
        print(f"[{year_key}] requests failed (SSL) — retrying via curl ...")
        result = subprocess.run(["curl", "-L", "-s", "-f", url], capture_output=True)
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"[{year_key}] both requests and curl failed for {url}")
        content = result.stdout

    raw_path.write_bytes(content)
    return raw_path


def clean_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip comma thousands separators from any column that looks numeric
    once cleaned, without assuming exact column names (these vary by year).
    Deliberately does not gate on dtype == object: pandas can store text
    columns as StringDtype rather than classic object dtype depending on
    version/settings, which would silently skip every column if checked."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        cleaned = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
        numeric = pd.to_numeric(cleaned, errors="coerce")
        # Only convert if the vast majority of values parsed as numbers —
        # avoids wrongly converting genuine text columns (hospital names etc).
        if numeric.notna().mean() > 0.9:
            df[col] = numeric
    return df


def load_year(year_key: str, raw_path: Path) -> None:
    df = pd.read_csv(raw_path)
    df.columns = [c.strip() for c in df.columns]

    print(f"[{year_key}] columns: {list(df.columns)} | rows: {len(df)}")

    df_clean = clean_numeric_columns(df)
    df_clean["_source_year_key"] = year_key
    df_clean["_source_url"] = YEAR_SOURCES[year_key]
    df_clean["_loaded_date"] = date.today().isoformat()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw_loads")
    table_name = f"ntpf_op_historical_{year_key}"
    con.register("df_view", df_clean)
    con.execute(f"CREATE OR REPLACE TABLE raw_loads.{table_name} AS SELECT * FROM df_view")
    con.close()
    print(f"[{year_key}] loaded into raw_loads.{table_name}")


def append_licensing_entry() -> None:
    LICENSING_REGISTER.parent.mkdir(parents=True, exist_ok=True)
    header = "| dataset_id | source | licence | attribution_required | redistribution_allowed | added |\n|---|---|---|---|---|---|\n"
    if not LICENSING_REGISTER.exists():
        LICENSING_REGISTER.write_text("# Licensing Register\n\n" + header)

    entry_id = "ntpf-op-waiting-list-historical-2018-2026"
    existing = LICENSING_REGISTER.read_text()
    if entry_id not in existing:
        row = (
            f"| {entry_id} | {SOURCE_NAME} | {LICENCE} "
            f"| Source: NTPF, Open Data — Waiting List Data (Outpatient, historical) "
            f"| True | {date.today().isoformat()} |\n"
        )
        with open(LICENSING_REGISTER, "a") as f:
            f.write(row)
        print("Licensing register updated with OP historical dataset entry.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        nargs="*",
        default=list(YEAR_SOURCES.keys()),
        help="Specific year keys to load (default: all, 2018-2026)",
    )
    args = parser.parse_args()

    print(f"Loading years: {args.years}\n")
    for year_key in args.years:
        if year_key not in YEAR_SOURCES:
            print(f"Skipping unknown year key: {year_key}")
            continue
        raw_path = download(year_key, YEAR_SOURCES[year_key])
        load_year(year_key, raw_path)
        print()

    append_licensing_entry()

    print(
        "\nDone. Each year is loaded as its own table (raw_loads.ntpf_op_historical_<year>) "
        "so format differences across years stay visible rather than being silently merged. "
        "Building the real unified time series across all years (alongside IPDC) is "
        "build_warehouse_schema.py's job."
    )


if __name__ == "__main__":
    main()
