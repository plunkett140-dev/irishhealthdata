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

# --------------------------------------------------------------------------
# HOSPITAL NAME CANONICALISATION
# --------------------------------------------------------------------------
# Found by manual inspection of the real dim_hospital output (2026-08-12).
# These are NOT typos to silently fix in code — they're documented here so
# the reasoning is traceable, per the "no black box" principle. Two kinds:
#   1. Genuine renames over the 2014-2026 window (hospital upgraded to
#      University status, or gained a location suffix)
#   2. The 2019 Children's Health Act merger (Temple Street, Crumlin, and
#      Tallaght children's sites became one entity, Children's Health
#      Ireland) — NTPF's own Open Data documentation states this explicitly
# A canonical name is chosen (generally the most recent/current one) and
# all historical variants map to it, so a multi-year trend for one real
# hospital isn't silently fragmented across two dim_hospital rows.
HOSPITAL_ALIASES = {
    "Galway University Hospital": "Galway University Hospitals",
    "Connolly Hospital": "Connolly Hospital Blanchardstown",
    "Kerry General Hospital": "University Hospital Kerry",
    "Letterkenny General Hospital": "Letterkenny University Hospital",
    "St. Michael's Hospital": "St. Michael's Hospital Dun Laoghaire",
    "Tallaght Hospital": "Tallaght University Hospital",
    "Tallaght Children's Hospital": "Children's Health Ireland",
    "Temple Street Children's University Hospital": "Children's Health Ireland",
    "Childrens University Hospital Temple Street": "Children's Health Ireland",
    "National Childrens Hospital at Tallaght University Hospital": "Children's Health Ireland",
    "Our Lady's Children's Hospital Crumlin": "Children's Health Ireland",
    "Cork University Maternity Hospital ": "Cork University Maternity Hospital",  # trailing-space duplicate
    "National Orthopaedic Hospital Cappagh": "Cappagh National Orthopaedic Hospital",
    "Lourdes Orthopaedic Hospital Kilcreene": "Kilcreene Regional Orthopaedic Hospital",
    "Mayo General Hospital": "Mayo University Hospital",
    "Portiuncula Hospital": "Portiuncula University Hospital",
    "Roscommon Hospital": "Roscommon University Hospital",
    "Sligo Regional Hospital": "Sligo University Hospital",
}

# NOT a real hospital — this is NTPF's Statistical Disclosure Control bucket
# for specialty/hospital combinations with fewer than 20 people waiting (see
# the "More information on Open Data publications" note on the Open Data
# page). It must never be treated as a dimension member alongside real
# hospitals — excluded from dim_hospital entirely, tracked separately.
SUPPRESSED_BUCKET_LABEL = "Small Volume Hospitals"


def canonicalise_hospital_name(name):
    if name is None:
        return name
    name = HOSPITAL_ALIASES.get(name, name)
    return name


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

    unified = pd.concat(frames, ignore_index=True)

    # Apply canonicalisation before any dimension is built, so renames/mergers
    # collapse correctly rather than needing a second pass later.
    unified["hospital_name"] = unified["hospital_name"].apply(canonicalise_hospital_name)

    # The SDC suppression bucket is data (it tells us suppression happened)
    # but is not a hospital. Flag it rather than silently dropping the rows —
    # dropping would misrepresent total waiting-list volume; keeping it
    # mixed into dim_hospital would misrepresent it as a real location.
    is_suppressed = unified["hospital_name"] == SUPPRESSED_BUCKET_LABEL
    n_suppressed = is_suppressed.sum()
    if n_suppressed:
        print(f"\nNote: {n_suppressed} rows are NTPF's 'Small Volume Hospitals' SDC "
              f"suppression bucket, not a real hospital — flagged via is_suppressed_bucket, "
              f"excluded from dim_hospital.")
    unified["is_suppressed_bucket"] = is_suppressed

    return unified


def parse_archive_date(series: pd.Series) -> pd.Series:
    """NTPF's date format changed too: 2018+ files use DD/MM/YYYY, but
    2014-2017 files use ISO format (YYYY-MM-DD) — confirmed by inspecting
    raw_loads.ntpf_ipdc_historical_2016 directly. A single format string
    silently drops one era's dates (pd.to_datetime with errors='coerce'
    returns NaT, no error raised) — try both explicitly rather than
    assuming one format covers all years."""
    parsed = pd.to_datetime(series, format="%d/%m/%Y", errors="coerce")
    still_missing = parsed.isna() & series.notna()
    if still_missing.any():
        parsed.loc[still_missing] = pd.to_datetime(
            series[still_missing], format="%Y-%m-%d", errors="coerce"
        )
    return parsed


def build_schema(con: duckdb.DuckDBPyConnection, unified: pd.DataFrame) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS warehouse")

    # --- dim_date ---
    unified["archive_date_parsed"] = parse_archive_date(unified["archive_date"])
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

    # --- dim_hospital (real hospitals only — suppression bucket excluded) ---
    dim_hospital = (
        unified.loc[~unified["is_suppressed_bucket"], ["hospital_name", "hospital_group", "hospital_hipe"]]
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

    fact_cols = ["fact_id", "date_id", "hospital_id", "specialty_id", "case_type", "adult_child", "time_band", "count", "granularity", "source_year_key", "is_suppressed_bucket"]
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
