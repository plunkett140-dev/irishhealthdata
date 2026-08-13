"""
Loader: NTPF IPDC Waiting List by Speciality, 2021-2026.

This is a SEPARATE file from "IPDC Waiting List by Hospital" (already loaded
via ntpf_ipdc_historical.py). The Hospital file has no specialty breakdown
for 2022+; this Speciality file should. Real URLs confirmed from the NTPF
Open Data page (fetched 2026-08-12) — exact column structure NOT yet
confirmed (network restrictions in the build sandbox prevented inspecting
the raw CSV), so this script introspects columns at runtime same as
ntpf_ipdc_historical.py, rather than assuming a shape.

USAGE:
    python ntpf_ipdc_speciality.py
"""

import subprocess
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "ntpf_ipdc_speciality"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "irishhealthdata.duckdb"
LICENSING_REGISTER = REPO_ROOT / "docs" / "LICENSING.md"

SOURCE_NAME = "National Treatment Purchase Fund (NTPF)"
LICENCE = "Re-use of Public Service Information (PSI) — see NTPF Data Protection / Re-use of Public Service Information page"

# Confirmed from https://www.ntpf.ie/waiting-list-data/open-data/ (2026-08-12)
YEAR_SOURCES = {
    "2026": "https://www.ntpf.ie/app/uploads/2026/07/OpenData_IPDCNational02.csv",
    "2025": "https://www.ntpf.ie/app/uploads/2026/01/OpenData_IPDCNational02_2025.csv",
    "2024": "https://www.ntpf.ie/app/uploads/2025/01/OpenData_IPDCNational02_2024-1.csv",
    "2023": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational02_2023-1.csv",
    "2022": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational02_2022.csv",
    "2021_apr_dec": "https://www.ntpf.ie/app/uploads/2024/10/OpenData_IPDCNational02_2021.csv",
}


def download(year_key: str, url: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"ntpf_ipdc_speciality_{year_key}.csv"
    if raw_path.exists():
        print(f"[{year_key}] already downloaded, skipping fetch")
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
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        cleaned = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
        numeric = pd.to_numeric(cleaned, errors="coerce")
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
    table_name = f"ntpf_ipdc_speciality_{year_key}"
    con.register("df_view", df_clean)
    con.execute(f"CREATE OR REPLACE TABLE raw_loads.{table_name} AS SELECT * FROM df_view")
    con.close()
    print(f"[{year_key}] loaded into raw_loads.{table_name}")


def append_licensing_entry() -> None:
    LICENSING_REGISTER.parent.mkdir(parents=True, exist_ok=True)
    header = "| dataset_id | source | licence | attribution_required | redistribution_allowed | added |\n|---|---|---|---|---|---|\n"
    if not LICENSING_REGISTER.exists():
        LICENSING_REGISTER.write_text("# Licensing Register\n\n" + header)
    entry_id = "ntpf-ipdc-waiting-list-speciality-2021-2026"
    existing = LICENSING_REGISTER.read_text()
    if entry_id not in existing:
        row = (
            f"| {entry_id} | {SOURCE_NAME} | {LICENCE} "
            f"| Source: NTPF, Open Data — Waiting List Data (by Speciality) "
            f"| True | {date.today().isoformat()} |\n"
        )
        with open(LICENSING_REGISTER, "a") as f:
            f.write(row)
        print("Licensing register updated with speciality dataset entry.")


def main():
    print("Loading NTPF IPDC Waiting List by Speciality, 2021-2026\n")
    for year_key, url in YEAR_SOURCES.items():
        raw_path = download(year_key, url)
        load_year(year_key, raw_path)
        print()
    append_licensing_entry()
    print("Done. Inspect the printed column reports above before building any chart —")
    print("exact structure wasn't verified in the build environment.")


if __name__ == "__main__":
    main()
