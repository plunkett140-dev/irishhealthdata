# IrishHealthData.com — Technical Design Document
**Version:** 0.5 (draft) | **Status:** Living document | **Owner:** Plunkett McCullagh
**Last updated:** 2026-08-11

> This document is the single source of truth for what we're building, why, and how. Every major decision should be traceable here. If future-you can't reconstruct the reasoning in five minutes, this document has failed its purpose.

---

## Volume I — Strategy & Architecture

### 1. Vision

**Mission statement**

To build an open, evidence-based, reproducible digital observatory of the Irish healthcare system — one where every statistic, chart, and conclusion is traceable to its original source and independently regenerable.

Unlike a news publication, the project's primary product is *trusted data*. Articles exist to interpret and contextualize that data, not the other way around.

**Success criteria**

The platform should become:
- The reference source for Irish healthcare statistics — measurable via search ranking, backlinks, and citations
- Trusted enough that journalists, policymakers, and academics cite it directly rather than re-deriving numbers
- An archive that still resolves correctly in ten years (stable URLs, versioned data, no link rot)
- A template other public-interest data projects can copy

**How we'll know we're succeeding (not just producing)**
- Number of external citations/backlinks per quarter
- Number of datasets with a *fully automated* refresh (zero manual steps)
- Time-to-update after a source publishes new data (target: <48 hours automated)
- Whether a stranger with no context can reproduce any given chart from the repo alone

Guiding question for every feature: **"Would this still be useful and correct if someone found it in ten years?"**

---

### 2. Design Philosophy

These principles govern every technical decision below them. When in doubt, defer to this section over convenience.

| Principle | Rule |
|---|---|
| **Reproducibility** | No chart is ever hand-made. Every figure has a script that regenerates it from source data. |
| **Source-first** | Primary data always beats secondary. CSO > news summary. OECD > copied table. HSE dataset > screenshot. |
| **Automate early** | If a task recurs monthly and takes >10 minutes, automate it before doing it manually a third time. |
| **Transparency** | Every page shows: Source, Last updated, Methodology, Known limitations. No black boxes. |
| **Simplicity** | Between two options with equal outcomes, pick the simpler one. Complexity is debt, not sophistication. |
| **Legal-first** *(new)* | No dataset goes live until its licence, attribution requirement, and redistribution terms are checked and logged. |

---

### 2a. Architecture Principles

These are Design Philosophy made enforceable — rules a future contributor (including future-you) can't accidentally break.

- **Data is immutable.** Raw data, once downloaded, is never edited in place. A correction produces a new processed version; the raw archive is the permanent record of what was actually received.
- **Everything is code.** No manual editing of datasets, charts, or dashboards. If it exists on the site, a script produced it.
- **Metadata is mandatory.** A dataset without a complete metadata record (Section 6) does not exist as far as the platform is concerned — it cannot be published.
- **Every object has an owner.** Every script, dataset, indicator, and article has a named owner in its metadata — even on a one-person project, write it down. This is what makes a future handover possible.

---

### 2b. Non-goals

Being explicit about what this project will *not* do protects focus and credibility. IrishHealthData.com is **not**:

- another news website
- another health blog or opinion outlet
- an advocacy or lobbying organisation
- a peer-reviewed academic journal
- a patient support or clinical guidance website
- a clinical guideline repository

If a proposed feature or article serves one of the above purposes rather than the evidence-base mission in Section 1, it doesn't belong here — even if it's good content.

---

### 3. Governance & Legal Foundations *(sequenced before Week 1)*

This section was missing from v0.1 and is a prerequisite, not a nice-to-have, because you're publishing health statistics publicly under your own name.

**Data licensing & attribution**
- CSO data: published under a specific open-data licence (PSI licence in Ireland) — check attribution wording requirements per dataset
- HSE / HIQA / NTPF: terms vary by dataset and are *not* uniformly open — some are "available on request" or restrict commercial reuse; check per source before ingesting
- Maintain a `LICENSING.md` register: one row per dataset, licence type, attribution string required, redistribution allowed (Y/N)

**Health-data specific care**
- Aggregate/statistical data (bed counts, waiting list totals) is low-risk
- Any dataset with small cell counts (e.g., rare condition by small geography) can risk re-identification even if "anonymised" — apply a minimum cell-size suppression rule (e.g., suppress or bucket cells <5) before publishing
- Document this rule once, apply it everywhere, log it in the metadata

**Correction & accountability policy**
- A visible, dated corrections log (public-facing) — if a chart is wrong, you say so and show the fix, rather than silently editing
- This is what separates a "trusted source" from "a blog with charts" — decide this before you need it, not after the first error

**Sustainability / bus-factor**
- One paragraph in this doc: what happens to the project if you stop maintaining it for six months? (e.g., repo stays public and forkable, data snapshots remain archived, licence allows others to continue it)
- Even a one-person project should not have undocumented single points of failure

**Editorial standards**

Every article must clearly distinguish three categories of statement, and never blur them:
- **Fact** — supported directly by data, with a source and figure attached
- **Inference** — a conclusion drawn from analysis, explicitly flagged as interpretation
- **Opinion** — a judgement or recommendation, always labelled as such

This is a cheap rule that does a lot of work for credibility — readers (and journalists citing you) should never have to guess which category a sentence falls into.

**Risk register**

A living table, reviewed quarterly, not a one-time exercise:

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HSE/CSO changes dataset format without notice | High | High | Schema validation in ETL fails loudly rather than silently ingesting bad data |
| A source dataset is withdrawn or discontinued | Medium | High | Raw downloads are archived permanently regardless of source availability (per Data is immutable) |
| Licensing terms change on a dataset already in use | Medium | High | Annual licensing register review; recheck before each major site update |
| Solo maintainer burnout / project stalls | High | High | Quarterly roadmap review; repo stays public/forkable so the project can outlive a pause (per Sustainability, above) |
| Small-cell re-identification slips through | Low | High | Suppression rule enforced in ETL validation step, not manually checked per-chart |

---

### 4. Software Decisions

*(Your original reasoning was sound — kept largely intact, tightened.)*

**Language: Python** — chosen over R (smaller production-pipeline ecosystem) and Julia (small community, few healthcare libraries). Python wins on ecosystem maturity, automation tooling, and long-term hiring pool.

**Database: DuckDB** — chosen over PostgreSQL for zero administration, native Parquet support, and git-friendly local-first analytics at the current scale (thousands–millions of rows).
- **Review trigger:** re-evaluate PostgreSQL if (a) the dataset count exceeds ~500, (b) multi-user concurrent editing becomes necessary, or (c) a public write-API is ever needed
- **Owner of trigger check:** [assign a name — even if it's you, write it down] — reviewed quarterly, logged in Decision Log

**Frontend: Next.js** — chosen over WordPress because the platform is a data product with interactive dashboards and programmatic page generation, not a content-management use case.

**Version control: GitHub** — industry standard, integrated issues, GitHub Actions for scheduled automation, public transparency by default.

**Institutional memory: Notion** — documentation, decisions, roadmap, dataset register. Never production data. Scheduled export/backup to avoid single-platform lock-in (add this to a recurring calendar reminder, not just a good intention).

---

### 5. Data Philosophy

The project is not a file archive — it's an evidence base. Every dataset must answer one or more explicit policy questions before it's ingested.

**Example:**

| Dataset | Questions it answers |
|---|---|
| Hospital beds | How many beds exist? Has capacity grown? How does Ireland compare internationally? Does capacity track population growth? |

If a candidate dataset can't be tied to a question like this, it doesn't get prioritized yet — this is what stops "collecting" from becoming the accidental goal.

---

### 6. Metadata Standard

Every dataset requires this record before publication — no exceptions:

```yaml
dataset_id: ""            # slug, e.g. ntpf-waiting-lists
title: ""
owner: ""
source_name: ""
source_url: ""
licence: ""
attribution_required: ""
redistribution_allowed: true/false
variables: []
geography_level: ""       # national / HSE region / county / hospital
update_frequency: ""      # e.g. monthly
download_date: ""
processing_date: ""
citation: ""
quality_notes: ""
known_limitations: ""
small_cell_suppression_applied: true/false
```

This becomes a JSON Schema in `/etl/schema/metadata.schema.json` once implemented — validated automatically so no dataset can be published without a complete record.

---

### 7. Decision Log

*(Format: every entry gets the Future Me Test — carry this forward for every future decision, not just these four.)*

**Decision 001 — Python**
Context: single language needed across ETL, analysis, visualisation, automation.
Alternatives: R, Julia.
Decision: Python.
*Future Me Test:* Revisit if a specific statistical method is R-only and worth the two-language cost.

**Decision 002 — DuckDB**
Context: analytical database without server administration overhead.
Alternatives: PostgreSQL, SQLite.
Decision: DuckDB.
*Future Me Test:* Revisit at ~500 datasets or if concurrent multi-user editing is needed.

**Decision 003 — Next.js**
Context: needs static content + interactive dashboards + strong SEO.
Alternatives: WordPress, Astro, Hugo.
Decision: Next.js.
*Future Me Test:* Revisit if development velocity on content pages becomes the bottleneck vs. a hybrid CMS+dashboard approach.

**Decision 004 — Notion for governance, GitHub for code**
Context: need searchable collaborative documentation, separate from version-controlled artefacts.
Decision: Notion + GitHub split, as above.
*Future Me Test:* Revisit if Notion becomes a silent single point of failure — confirm backup export is actually happening, not just planned.

**Decision 005 — Legal/licensing review gate** *(new)*
Context: publishing health statistics publicly requires a licence and re-identification check per dataset.
Decision: No dataset ships without a completed metadata record (Section 6) and a licensing register entry.
*Future Me Test:* Revisit if the dataset volume makes manual licence-checking a bottleneck — consider a semi-automated licence-flagging step.

**Decision 006 — Organise the site around indicators, not raw datasets** *(CLOSED — decided 2026-08-11, end of Week 5)*

Context: raised in external review. A reader-facing indicator (e.g. "Hospital Bed Occupancy") often depends on multiple underlying datasets. Organising navigation and page structure around indicators rather than raw datasets may be more useful to readers and closer to how journalists/policymakers actually think about the data.

Alternatives:
- (a) Keep dataset as the primary unit; indicators are just charts that reference one or more datasets informally
- (b) Introduce Indicator as a first-class object in the data model, with an explicit `depends_on: [dataset_ids]` field, sitting between Dataset and Chart

Evidence from the Week 5 ETL prototype (NTPF IPDC Waiting List by Hospital, run against live data 2026-08-11): this file contains hospital × Adult/Child × time-band only — **no specialty breakdown**. A genuinely useful reader-facing indicator (e.g. a specialty-specific waiting list picture) will require joining this file with a different, specialty-level NTPF file once one is added. That's a concrete, observed case of one indicator depending on multiple datasets — not a hypothetical.

**Decision: (b).** Indicator becomes a first-class object, sitting between Dataset and Chart, with a `depends_on: [dataset_ids]` field. Reflected in the metadata standard (Section 6) and the Common Data Model (Week 3/6) going forward.

*Future Me Test:* If, after two or three more datasets are added, most indicators still map to exactly one dataset each, the extra schema layer may be adding complexity without payoff — reconsider collapsing it back to option (a) at that point rather than out of inertia.

---

**Decision 008 — Hosting platform: Vercel**

Context: raised 2026-08-12, working through backup/single-point-of-failure risk. Source code and raw data are already safe (pushed to GitHub, and raw data is independently re-downloadable from NTPF as a third fallback). The local DuckDB database is deliberately unbacked-up — it's fully regenerable from the archived raw files in minutes, per the Data is immutable / Everything is code principles, so it isn't treated as data at risk. The real open question was the *live public website*: GitHub hosts source, not a running site, and a laptop-only deployment would be both a single point of failure and inaccessible to other people.

Alternatives considered:
- Self-hosting on a VPS (e.g. DigitalOcean, Linode) — full control, but adds real server administration overhead, directly against the Simplicity principle at this project's current stage
- Netlify — comparable to Vercel for a static/Next.js site, no strong reason to prefer over Vercel specifically

Decision: **Vercel.** Built by the team behind Next.js (already Decision 003), so first-class support for the framework already chosen. Free tier is sufficient at this project's scale. Auto-deploys directly from the GitHub repo on every push — no separate manual upload step, keeping GitHub as the single source of truth per Decision 004.

Consequences: the live site becomes available to anyone with the URL, not dependent on any one laptop. Local development still happens on Plunkett's machine, but nothing about the public site's availability depends on that machine being on or even existing.

*Future Me Test:* Revisit if the project ever needs server-side compute beyond what Vercel's free tier supports (e.g. heavy live database queries rather than precomputed static JSON), or if costs change materially at scale.

### 8. Deferred sections *(intentionally not written yet)*

Two structural ideas came up in review that are real but premature to formalise now:

- ~~**Information Architecture as a dedicated chapter**~~ — Decision 006 is now closed (Indicator is a first-class object). Formalise this as part of the Week 6 database design rather than as a separate document chapter — the hierarchy should live in the schema itself, not be re-described in prose.
- **Versioning Strategy as a dedicated chapter** (dataset versions, metadata versions, site versions, source snapshots). There's nothing to version yet. Revisit after Week 6, once the first real database and dataset exist and there's something concrete to apply a scheme to.

Noting them here so they aren't lost, without inflating the document with structure for things that don't exist yet.

---

## Volume II — Implementation Roadmap to First Published Article

Goal of this roadmap: not "launch a website" — **prove the full pipeline once, end to end, and publish one flagship article built entirely on it.** Everything after that is repetition of a proven pattern.

### Week 1 — Foundation
- GitHub repo created, folder structure finalised (`/data/raw`, `/data/processed`, `/etl`, `/docs`, `/site`)
- Notion workspace structured (Decisions / Dataset Register / Roadmap / Meeting notes)
- This document committed as v0.1 of the Technical Design Document
- **Add:** `LICENSING.md` register created (empty, schema only) and corrections-log policy written (one paragraph, public-facing later)
- Naming conventions, branching strategy, documentation standards agreed

### Week 2 — Data Inventory
- Catalogue first 50 priority datasets: source URL, update frequency, **licence type**, importance ranking
- Flag any datasets with small-cell re-identification risk early, not at publish time

### Week 3 — Common Data Model
- Standardise geography, dates, demographic variables, units, identifiers across all future datasets
- Keep Decision 006 (indicators vs. datasets) open at this stage — don't let the schema quietly foreclose it either way

### Week 4 — Metadata Framework
- Implement the YAML/JSON Schema from Section 6 as an actual validator, not just a template
- No dataset can be loaded into DuckDB without passing this validation

### Week 5 — ETL Prototype (the proof point)
- Pick **one** dataset — NTPF waiting lists is a good choice: public, monthly, well-structured
- Build: Extract (download) → Validate (schema + small-cell check) → Transform (standardise) → Load (DuckDB) → Document (metadata record + licensing register entry)
- Outcome: a reusable template script every future dataset copies
- **Close Decision 006** at the end of this week using what was actually learned building the pipeline against real data

### Week 6 — Database Prototype
- First DuckDB database: dimension tables (date, geography, organisation) + one fact table
- Document relationships — this is the schema everything else extends

### Week 7 — Charting Standards
- Trial Plotly / Altair / Matplotlib against the NTPF data specifically
- Lock: fonts, colour palette, citation placement, footnote format, mobile responsiveness
- Output: a `chart_style.py` or theme file every chart imports — this is what makes "no chart is ever hand-made" actually enforceable

### Week 8 — Website Skeleton
- Home page, dataset page template, indicator page template, article template, basic search
- No public launch — this is scaffolding only

### Week 9 — First Dashboard
- Build the waiting-lists dashboard using the actual pipeline from Weeks 5–7, live-querying DuckDB

### Week 10 — First Flagship Article *(the target milestone)*
- Written entirely from data the platform itself produced — no manually-pasted numbers
- Every chart in the article traces to a script in `/etl` and a dataset in the metadata register
- Includes Source / Last updated / Methodology / Known limitations on every figure, per the Transparency principle
- **This is the Substack-ready piece** — by this point it's backed by a real reproducible pipeline, not just a well-written draft

### Week 11 — Quality Assurance
- Review naming conventions, documentation completeness, metadata completeness, and — critically — try to reproduce every chart in the article from a clean checkout of the repo. If it doesn't reproduce cleanly, it's not done.

### Week 12 — Internal Release (v0.1)
- Share with a small group of clinicians/researchers/technical colleagues *before* the public Substack post goes out
- Fold their feedback into the article and the metadata standard before Week 10's piece goes fully public (or treat Week 10 as the internal draft and publish externally in Week 13)

---

## Immediate Next Actions

1. ~~Confirm project name and repo name~~ — **Done: IrishHealthData.com, owner Plunkett McCullagh**
2. Confirm first dataset (NTPF waiting lists, or alternative)
3. I can scaffold the actual repo folder structure + metadata schema + a working ETL script against the real source data this session — that turns Week 1, most of Week 4, and all of Week 5 into something you can `git add` today rather than plan for later
