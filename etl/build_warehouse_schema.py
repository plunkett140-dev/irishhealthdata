"""
Week 6: Build the unified dimension/fact schema for NTPF IPDC waiting list data.

Reads the per-year raw_loads.ntpf_ipdc_historical_<year> tables (created by
ntpf_ipdc_historical.py) and normalises three confirmed real formats into one
long-format fact table plus dimension tables:

  ERA A (2022-2026, and 2021_apr_dec): hospital-level, wide time-bands.
      ArchiveDate, Adult_Child, HospitalName, <band columns>, Total
      No specialty/case-type breakdown.

  ERA B (2018-2020, 2021_jan_mar): specialty-level, long format.
      Archive_Date, Hospital_Group, Hospital_HIPE, Hospital_Name,
      Specialty_HIPE, Specialty_Name, Case_Type, Adult_Child, Age_Profile,
      Time_Bands, Total

  ERA C (2014-2017): same shape as Era B, older naming.
      'Archive Date','Group','Hospital HIPE','Hospital','Specialty HIPE',
      'Specialty'/'Speciality','Case Type','Adult/Child',
      'Age Categorisation'/'Age Profile','Time Bands','Count'/'Total'

KNOWN LIMITATION (documented, not silently papered over): time-band
boundaries differ across eras (e.g. Era A uses 0-6/6-12/12-18/18+ months;
Era B/C use 0-3/3-6/6-9/9-12/12+ months). This script preserves the
time_band label as-published rather than forcing bands into a common
bucket scheme — reconciling that is a genuine analysis decision, not an
ETL one, and forcing it here would hide a real methodological choice.
See Decision 007 in the Technical Design Document.

Output tables (schema: warehouse):
  dim_date(date_id, archive_date, year, month)
  dim_hospital(hospital_id, hospital_name, hospital_group, hospital_hipe)
  dim_specialty(specialty_id, specialty_name, specialty_hipe)
  fact_waiting_list(fact_id, date_id, hospital_id, specialty_id, case_type,
                     adult_child, time_band, count, granularity, source_year_key)

granularity is 'hospital' (Era A, no specialty breakdown) or
'hospital_specialty' (Era B/C). specialty_id is NULL for 'hospital' rows —
this is the concrete, queryable form of Decision 006 (Indicator as
first-class object): an indicator that needs specialty-level detail must
filter to granularity='hospital_specialty' and accept it's only available
for years with that data.
"""

from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "irishhealthdata.duckdb"

ERA_A_YEARS = {"2021_apr_dec", "2022", "2023", "2024", "2025", "2026"}
ERA_B_YEARS = {"2018", "2019", "2020", "2021_jan_mar"}
ERA_C_YEARS = {"2014", "2015", "2016", "2017"}

BAND_COLUMNS_ERA_A = ["0-6 Months", "6-12 Months", "12-18 Months", "18 Months +"]


def normalise_era_a(df: pd.DataFrame, year_key: str) -> pd.DataFrame:
    """Hospital-level wide format -> long format via melt. Total is dropped
    (it's the sum of the bands present, not an independent observation)."""
    df = df.rename(columns={"ArchiveDate": "archive_date", "Adult_Child": "adult_child", "HospitalName": "hospital_name"})
    id_vars = ["archive_date", "adult_child", "hospital_name"]
    present_bands = [c for c in BAND_COLUMNS_ERA_A if c in df.columns]
    long = df.melt(id_vars=id_vars, value_vars=present_bands, var_name="time_band", value_name="count")
    long["hospital_group"] = None
    long["hospital_hipe"] = None
    long["specialty_name"] = None
    long["specialty_hipe"] = None
    long["case_type"] = None
    long["granularity"] = "hospital"
    long["source_year_key"] = year_key
    return long


def normalise_era_b(df: pd.DataFrame, year_key: str) -> pd.DataFrame:
    df = df.rename(columns={
        "Archive_Date": "archive_date", "Hospital_Group": "hospital_group",
        "Hospital_HIPE": "hospital_hipe", "Hospital_Name": "hospital_name",
        "Specialty_HIPE": "specialty_hipe", "Specialty_Name": "specialty_name",
        "Case_Type": "case_type", "Adult_Child": "adult_child",
        "Time_Bands": "time_band", "Total": "count",
    })
    df["granularity"] = "hospital_specialty"
    df["source_year_key"] = year_key
    return df


def normalise_era_c(df: pd.DataFrame, year_key: str) -> pd.DataFrame:
    rename_map = {
        "Archive Date": "archive_date", "Group": "hospital_group",
        "Hospital HIPE": "hospital_hipe", "Hospital": "hospital_name",
        "Specialty HIPE": "specialty_hipe", "Specialty": "specialty_name",
        "Speciality": "specialty_name",  # 2017 spelling variant
        "Case Type": "case_type", "Adult/Child": "adult_child",
        "Time Bands": "time_band", "Count": "count", "Total": "count",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["granularity"] = "hospital_specialty"
    df["source_year_key"] = year_key
    return df


def load_all_years(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'raw_loads' AND table_name LIKE 'ntpf_ipdc_historical_%'"
    ).fetchall()

    frames = []
    for (table_name,) in tables:
        year_key = table_name.replace("ntpf_ipdc_historical_", "")
        df = con.execute(f"SELECT * FROM raw_loads.{table_name}").df()
        # Drop the loader's own bookkeeping columns before normalising
        df = df.drop(columns=[c for c in ["_source_year_key", "_source_url", "_loaded_date"] if c in df.columns])

        if year_key in ERA_A_YEARS:
            normalised = normalise_era_a(df, year_key)
        elif year_key in ERA_B_YEARS:
            normalised = normalise_era_b(df, year_key)
        elif year_key in ERA_C_YEARS:
            normalised = normalise_era_c(df, year_key)
        else:
            print(f"WARNING: unrecognised year_key '{year_key}', skipping")
            continue

        keep_cols = [
            "archive_date", "hospital_group", "hospital_hipe", "hospital_name",
            "specialty_hipe", "specialty_name", "case_type", "adult_child",
            "time_band", "count", "granularity", "source_year_key",
        ]
        for col in keep_cols:
            if col not in normalised.columns:
                normalised[col] = None
        frames.append(normalised[keep_cols])
        print(f"[{year_key}] normalised: {len(normalised)} rows, granularity={normalised['granularity'].iloc[0]}")

    return pd.concat(frames, ignore_index=True)


def build_schema(con: duckdb.DuckDBPyConnection, unified: pd.DataFrame) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS warehouse")

    # --- dim_date ---
    unified["archive_date_parsed"] = pd.to_datetime(
        unified["archive_date"], format="%d/%m/%Y", errors="coerce"
    )
    dim_date = (
        unified[["archive_date_parsed"]]
        .drop_duplicates()
        .dropna()
        .rename(columns={"archive_date_parsed": "archive_date"})
        .reset_index(drop=True)
    )
    dim_date["date_id"] = dim_date.index + 1
    dim_date["year"] = pd.to_datetime(dim_date["archive_date"]).dt.year
    dim_date["month"] = pd.to_datetime(dim_date["archive_date"]).dt.month
    con.register("dim_date_view", dim_date)
    con.execute("CREATE OR REPLACE TABLE warehouse.dim_date AS SELECT date_id, archive_date, year, month FROM dim_date_view")

    # --- dim_hospital ---
    dim_hospital = (
        unified[["hospital_name", "hospital_group", "hospital_hipe"]]
        .drop_duplicates(subset=["hospital_name"])
        .dropna(subset=["hospital_name"])
        .reset_index(drop=True)
    )
    dim_hospital["hospital_id"] = dim_hospital.index + 1
    con.register("dim_hospital_view", dim_hospital)
    con.execute("CREATE OR REPLACE TABLE warehouse.dim_hospital AS SELECT hospital_id, hospital_name, hospital_group, hospital_hipe FROM dim_hospital_view")

    # --- dim_specialty ---
    dim_specialty = (
        unified[["specialty_name", "specialty_hipe"]]
        .drop_duplicates(subset=["specialty_name"])
        .dropna(subset=["specialty_name"])
        .reset_index(drop=True)
    )
    dim_specialty["specialty_id"] = dim_specialty.index + 1
    con.register("dim_specialty_view", dim_specialty)
    con.execute("CREATE OR REPLACE TABLE warehouse.dim_specialty AS SELECT specialty_id, specialty_name, specialty_hipe FROM dim_specialty_view")

    # --- fact_waiting_list ---
    fact = unified.merge(dim_date[["archive_date", "date_id"]], left_on="archive_date_parsed", right_on="archive_date", how="left", suffixes=("", "_dim"))
    fact = fact.merge(dim_hospital[["hospital_name", "hospital_id"]], on="hospital_name", how="left")
    fact = fact.merge(dim_specialty[["specialty_name", "specialty_id"]], on="specialty_name", how="left")
    fact["fact_id"] = range(1, len(fact) + 1)

    fact_cols = ["fact_id", "date_id", "hospital_id", "specialty_id", "case_type", "adult_child", "time_band", "count", "granularity", "source_year_key"]
    con.register("fact_view", fact[fact_cols])
    con.execute("CREATE OR REPLACE TABLE warehouse.fact_waiting_list AS SELECT * FROM fact_view")


def main():
    con = duckdb.connect(str(DB_PATH))
    print("Loading and normalising all years from raw_loads ...\n")
    unified = load_all_years(con)
    print(f"\nTotal normalised rows across all years: {len(unified)}")

    print("\nBuilding warehouse schema (dim_date, dim_hospital, dim_specialty, fact_waiting_list) ...")
    build_schema(con, unified)

    for t in ["dim_date", "dim_hospital", "dim_specialty", "fact_waiting_list"]:
        count = con.execute(f"SELECT COUNT(*) FROM warehouse.{t}").fetchone()[0]
        print(f"  warehouse.{t}: {count} rows")

    con.close()
    print("\nDone. Query warehouse.fact_waiting_list joined to the dim_ tables for real analysis —")
    print("no more hand-written per-file SQL against raw_loads needed.")


if __name__ == "__main__":
    main()
