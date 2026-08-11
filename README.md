# IrishHealthData.com

Open, reproducible, evidence-based digital observatory of the Irish healthcare system.

Owner: Plunkett McCullagh

## Principles

No chart is ever hand-made. Every figure is regenerable from source data by an
independent analyst. See `docs/technical-design-document.md` for the full
strategy, governance, and architecture rationale.

## Structure

```
data/raw/        - Archived source files, verbatim, never edited (immutable)
data/processed/  - DuckDB database and derived tables
etl/             - Extract-Transform-Load scripts, one per dataset
etl/schema/      - Metadata JSON Schema — no dataset ships without passing this
docs/            - Technical Design Document, metadata records, LICENSING.md
site/            - Next.js frontend (not yet scaffolded)
```

## Running the first ETL pipeline

```bash
pip install -r requirements.txt
python etl/ntpf_ipdc_waiting_list.py --source-url https://www.ntpf.ie/app/uploads/2026/07/OpenData_IPDCNational01.csv
```

Verify the current download link on the NTPF Open Data page before running —
links are re-issued per year: https://www.ntpf.ie/waiting-list-data/open-data/

On first real run, **read the printed column report** before trusting anything
downstream — the transform step standardises column names generically rather
than assuming specific NTPF headers, since those weren't independently
verified against a live file during scaffolding.

## Status

Week 5 prototype (Technical Design Document roadmap). Pipeline logic tested
against a synthetic sample matching the expected NTPF format. Not yet run
against the live file — do that next, inspect the column report, and tighten
`transform()` with real column names if useful.
