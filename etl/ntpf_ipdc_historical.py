"""
Historical loader: NTPF IPDC Waiting List by Hospital, 2014-2026.

NTPF's Open Data page (https://www.ntpf.ie/waiting-list-data/open-data/)
confirms: "The NTPF has published separate Adult and Child Waiting List
Reports since April 2021." So this covers two real formats:

  - Post-April-2021 files: match the shape already handled in
    ntpf_ipdc_waiting_list.py (ArchiveDate, Adult_Child, HospitalName,
    time-band columns, Total)
  - Pre-2021 files ("...By Group Hospital..."): older format, exact columns
    unconfirmed from this build environment (network restrictions prevented
    inspecting the raw bytes here) — this script INTROSPECTS each year's
    real columns rather than assuming, and loads each year into its own
    raw table so nothing gets silently merged across a format change.

WHY separate tables per year, not one combined table:
Silently unioning differently-shaped data risks producing numbers that look
fine but aren't comparable (e.g. missing Adult/Child split pre-2021, or a
renamed column dropping data). Building the real unified fact table with
that historical logic handled properly is Week 6 work, not this script's
job — this script's job is to get every year's raw data in, verified,
archived, and visible, per the Data is immutable and Everything is code
principles.

USAGE:
    python ntpf_ipdc_historical.py
    python ntpf_ipdc_historical.py --years 2020 2021_jan_mar 2019
"""

import argparse
import subprocess
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "ntpf_ipdc_historical"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "irishhealthdata.duckdb"
LICENSING_REGISTER = REPO_ROOT / "docs" / "LICENSING.md"

SOURCE_NAME = "National Treatment Purchase Fund (NTPF)"
LICENCE = "Re-use of Public Service Information (PSI) — see NTPF Data Protection / Re-use of Public Service Information page"

# Real URLs confirmed directly from the NTPF Open Data page (fetched 2026-08-11).
# NOTE: NTPF re-hosts these under changing /app/uploads/YYYY/MM/ paths when
# they update the page, so these WILL go stale eventually — if a download
# fails with a 404, re-check https://www.ntpf.ie/waiting-list-data/open-data/
# and update the URL below rather than assuming the whole page moved.
YEAR_SOURCES = {
    "2026": "https://www.ntpf.ie/app/uploads/2026/07/OpenData_IPDCNational01.csv",
    "2025": "https://www.ntpf.ie/app/uploads/2026/01/OpenData_IPDCNational01_2025.csv",
    "2024": "https://www.ntpf.ie/app/uploads/2025/01/OpenData_IPDCNational01_2024-1.csv",
    "2023": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational01_2023.csv",
    "2022": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational01_2022.csv",
    "2021_apr_dec": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational01_2021.csv",
    "2021_jan_mar": "https://www.ntpf.ie/app/uploads/2024/10/IPDC-Waiting-List-By-Group-Hospital-2021.csv",
    "2020": "https://www.ntpf.ie/app/uploads/2024/10/IPDC-Waiting-List-By-Group-Hospital-2020.csv",
    "2019": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-by-Group-Hospital-2019.csv",
    "2018": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-by-Group-Hospital-2018.csv",
    "2017": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-By-Group-Hospital-2017.csv",
    "2016": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-By-Group-Hospital-2016.csv",
    "2015": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-By-Group-Hospital-2015.csv",
    "2014": "https://www.ntpf.ie/app/uploads/2025/02/IPDC-Waiting-List-By-Group-Hospital-2014.csv",
}


def download(year_key: str, url: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"ntpf_ipdc_{year_key}.csv"
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
    table_name = f"ntpf_ipdc_historical_{year_key}"
    con.register("df_view", df_clean)
    con.execute(f"CREATE OR REPLACE TABLE raw_loads.{table_name} AS SELECT * FROM df_view")
    con.close()
    print(f"[{year_key}] loaded into raw_loads.{table_name}")


def append_licensing_entry() -> None:
    LICENSING_REGISTER.parent.mkdir(parents=True, exist_ok=True)
    header = "| dataset_id | source | licence | attribution_required | redistribution_allowed | added |\n|---|---|---|---|---|---|\n"
    if not LICENSING_REGISTER.exists():
        LICENSING_REGISTER.write_text("# Licensing Register\n\n" + header)

    entry_id = "ntpf-ipdc-waiting-list-historical-2014-2026"
    existing = LICENSING_REGISTER.read_text()
    if entry_id not in existing:
        row = (
            f"| {entry_id} | {SOURCE_NAME} | {LICENCE} "
            f"| Source: NTPF, Open Data — Waiting List Data (historical) "
            f"| True | {date.today().isoformat()} |\n"
        )
        with open(LICENSING_REGISTER, "a") as f:
            f.write(row)
        print("Licensing register updated with historical dataset entry.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        nargs="*",
        default=list(YEAR_SOURCES.keys()),
        help="Specific year keys to load (default: all, 2014-2026)",
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
        "\nDone. Each year is loaded as its own table (raw_loads.ntpf_ipdc_historical_<year>) "
        "so format differences across years stay visible rather than being silently merged. "
        "Building the real unified time series across all years is the Week 6 database work."
    )


if __name__ == "__main__":
    main()
