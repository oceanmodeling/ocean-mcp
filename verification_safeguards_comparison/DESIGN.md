# WP1 design freeze: scientific-safeguards comparison

Frozen before arms C and D were run on any task. The machine-readable versions are authoritative:
`tasks/tasks.json`, `references/references.json`, `grader/grade.py` and `grader/adapters.py`.

## 1. How the MCP arms run on archived bytes (Phase 0)

- **Mechanism.** `replay/ocean_replay_launcher.py` is outside every package. It starts the server as
  `<env python> -I ocean_replay_launcher.py --mode replay --archive A [--archive B] -m <module>`.
  Before the package is imported it patches, at class level:
  - `httpx.AsyncHTTPTransport.handle_async_request` and `httpx.HTTPTransport.handle_request`. Every
    client in these packages ends there, including the packages' own `RetryTransport` subclasses,
    which call `super().handle_async_request`.
  - In replay mode, `socket.getaddrinfo`, `socket.create_connection` and `socket.socket.connect` /
    `connect_ex`. DNS is answered only for archived hosts; this is needed because erddap-mcp's SSRF
    guard resolves the host before each request.

  It then runs the package's own `__main__` with `runpy`. No package source is changed.
- **Matching.** Matching uses method, scheme, host, port and path, plus the multiset of query
  parameters minus `application`. The CO-OPS API documents `application` as a log identifier (base
  archive e0020). Three rules apply, in this order:
  1. exact match;
  2. HEAD answered from the archived GET;
  3. CO-OPS `water_level` slicing. A request whose parameters equal those of an archived *master*,
     except `begin_date`/`end_date`, gets the master's records in [begin, end] in the master's own
     byte layout. The layout is proven by a byte-exact round trip of the master. A request outside
     the master's requested range is a miss.

  Stacked archives are searched in order, so a synthetic overlay replaces a real file for one task.
- **Fail loudly.** A miss raises `ReplayMiss`. It is logged to the session's `http_log.jsonl`, printed to
  stderr, and makes the session invalid (exit 3). Every replay session also runs inside `unshare -rn`
  (a network namespace without network). The harness records that outbound connections fail
  ("Network is unreachable").
- **Proof** (`phase0/`, `phase0/phase0_check.json`, rerun by `phase0/verify_phase0.py`):
  - **Boston reproduction.** The 2026-10-30 12z comparisons ran through a real stdio session against
    the WP0 stofs-mcp 0.3.0 wheel: both models, 0–48 h and the two nowcasts. The session made 8
    requests, all served, with 0 misses and 0 network attempts. n, bias, RMSE, every statistic and
    all 480/480/60/240 series points are identical to the archived live responses (commit `31e7f6a`).
    The only differences are `retrieved_at`, counters added after `31e7f6a`, and the 2D datum-source
    wording added in `52f5ae6`.
  - **stofs-mcp 0.2.0 from PyPI** replays a station call.
  - **Fail-loud checks.** stofs 0.3.0 and ww3-mcp 0.1.2 each fail loudly on an unarchived URL; that
    is the ww3 check, not R7. erddap-mcp's DNS lookup of an unarchived host is blocked by the
    in-process guard even outside the namespace.
- **Inputs.** All inputs were acquired as follows (`replay/fetch_inputs.py`, `run_log/fetch_inputs_record.jsonl`):
  - Seeded by copy from the Boston package and WP0: the 2026-10-30 2D and 3D station files, the
    CO-OPS Boston MSL response of 2026-11-04 and `41009h2024.txt`. Checksums were verified.
  - Recorded in record mode on 2026-11-06, sequentially with 4 s pauses: the other inputs.
  - The three new S3 files and the MUR subset have the same SHA-256 that `MANUSCRIPT_SECOND_REVIEW.md`
    recorded.
  - The Boston MSL download of 2026-11-06 is identical, on all 721 overlapping records, to the
    2026-11-04 archive (still preliminary, unrevised).

## 2. Arms

| Arm | Definition |
|---|---|
| A | xarray (default decoding) and pandas used as documented. Fixed datum pairing from current documentation: STOFS-2D and STOFS-3D LMSL against CO-OPS MSL. No domain rules |
| B | A plus rules implemented here from NOAA documentation and CF conventions, each cited in a comment (`arms/B/arm_b.py`). Does not import, copy or paraphrase Ocean-MCP |
| C | Real MCP stdio sessions, replay mode:<br>• stofs-mcp 0.3.0 (WP0 wheel `29fcb737…dafdd`)<br>• coops-mcp 0.1.1 and erddap-mcp 0.1.2 (PyPI)<br>• R7: ww3-mcp 0.1.3 from `verification_ww3_history_fix/dist/` if present at Phase 2, else "candidate not available" |
| D | The same sessions:<br>• stofs-mcp 0.2.0 (PyPI)<br>• coops-mcp 0.1.1 and erddap-mcp 0.1.2<br>• R7: ww3-mcp 0.1.2 (PyPI) |

Arms A and B run with `python -I` in an environment where no Ocean-MCP package, `mcp` or `httpx` is
importable (checked in each run log). Arms A and B read the same archived bytes as the sessions, from
the same archive stack. For CO-OPS they read the same master and select the window themselves.

## 3. Tasks (18 graded rows; 16 task identifiers)

Plain-language statements are in `tasks/tasks.json`. "All records" means the whole station file,
nowcast and forecast.

| ID | Class | Task | Inputs (archive entry, sha256 prefix) |
|---|---|---|---|
| N1 | nominal | 2D vs CO-OPS, Boston, 2026-10-30 12z, 0 < lead ≤ 48 h | 2D file e0001 `f1ed4e59`; CO-OPS MSL e0003 `c207c801` (+ e0010 `25ad6659`) |
| N2 | nominal | 3D vs CO-OPS, Boston, same window | 3D e0002 `46608194`; e0003, e0010; NAVD e0011 `29297072` |
| N3 | nominal | Ian residual maximum, Fort Myers 8725520, 27–29 Sep 2022 | water level e0014 `28fc9699`; predictions e0015 `302a36f1` |
| N4 | nominal | MUR SST subset: cells, finite cells, range | info e0016 `9c517f7b`; subset e0017 `3eb504b5` |
| R1a | real defect | 3D: five highest station maxima over all records | e0002 |
| R1b | real defect | 3D vs CO-OPS at 9751381, 0–48 h | e0002; MSL e0012 `ec9668ca`; NAVD e0013 `35e759cb` |
| R2 | real defect | 2D: minimum at 8571421 over all records | e0001 |
| R3 | real defect | 2D: station with the highest maximum | e0001 |
| R4a | real defect | 3D vs CO-OPS, Boston, cycle 2026-08-16 12z (v2.1.18, NAVD88) | e0006 `f78e84ef`; NAVD e0008 `29192c30`; MSL e0009 `14b73c35` |
| R4b | real defect | 3D vs CO-OPS, Boston, cycle 2026-08-17 12z (v3.1.4, LMSL); same workflow as R4a | e0007 `f47962fa`; e0009; e0008 |
| R5 | real defect | 2D: vertical datum of the station output, and its source | e0001 |
| R6 | real defect | 3D 2026-02-18: station nearest the Boston gauge (42.3539, −71.0503) | e0005 `d13345a3` |
| R7 | real defect | NDBC 41009, 2024: highest WVHT | e0004 `f149d373` |
| S1 | synthetic | N2 with zeta `standard_name` and `long_name` deleted | S1 e0001 `6e159109` |
| S2 | synthetic | N2 with `long_name` "…above navd88" (`standard_name` msl) | S2 e0001 `b7648fc6` |
| S3 | synthetic | N1 with title/comments `STOFS_2D_GLOBAL.V4.0.0` | S3 e0001 `e153e8e6` |
| S4 | synthetic | N1 with five observation `v` fields set to "", "NaN", "Infinity", "-Infinity", "" | S4 e0001 `1831ebea` |
| S5 | synthetic | N2 with the CF standard name `sea_surface_height_above_mean_sea_level` and long_name "…above mean sea level" | S5 e0001 `46e35f2f` |

Refinements against the brief, with reasons:

- **R1 and R4 are graded as two rows each.**
  - R1(a) and R1(b) ask different things.
  - R4's two cycles need different observation datums. One row per cycle shows which cycle a
    workflow gets wrong.
- **R1a, R2 and R3 use all records of the file**, because the max tool and the station product use
  the whole file.
  - For R2 and R3, restricting to lead > 0 gives the same answer.
  - For R1a it gives the same five stations with smaller maxima (both are in `computed_values.json`).
- **Arm D's window.** stofs-mcp 0.2.0 has no lead window. Arm D's compare calls are the nearest
  equivalent: `hours_to_compare` 54 (2D) or 72 (3D) from the file start. They are labelled so, and
  their values are recorded as "not supported", never as wrong numbers.
- **N3 has no residual tool in coops-mcp.** Arms C and D retrieve both series through MCP. The
  residual comes from a frozen client join (`grader/adapters.py: residual_join`).

## 4. Reference outcomes and their sources

Classes of source:

- **IND**: archived independent recalculation.
- **DOC**: NOAA documentation.
- **PHY**: physical bound.
- **CON**: construction of the mutation.
- **RECALC**: recalculated by `references/derive_references.py`. This is pure Python on raw stored
  values, imports no arm or Ocean-MCP code, and reproduces byte-identically on rerun. Same author as
  the arms: a weaker class.

Quotes are in `references/references.json` → `sources`.

| ID | Values (tolerance) | Decision | Source |
|---|---|---|---|
| N1 | n 480; bias −0.00050; RMSE 0.12300; MAE 0.09999 m; r 0.99338 (1 cm; r 0.001) | proceed with caveat: labels compatible, realizations not shown equivalent | IND (Boston), DOC (NOMADS) |
| N2 | n 480; bias −0.14300; RMSE 0.24555; MAE 0.20861 m; r 0.99132 | proceed with caveat | IND, DOC (SCN 26-51, portal) |
| N3 | +2.209 m at 2022-09-28 22:18 (tied 22:30; either accepted), MLLW (1 mm) | proceed | IND (second review D1) |
| N4 | 17,061 cells; 9,301 finite; 22.199–23.983 degree_C (exact; 0.001) | proceed (nulls are missing) | IND (second review D3; same bytes) |
| R1a | Eastport 3.300, Cutler 2.756, Bar Harbor 2.302, Boston 2.067, Portland 2.037 m (1 mm) | proceed, reporting the exclusion of the five 1e7 + c stations | RECALC + PHY. Any bound between 3.30 m and 9,999,999.41 m gives the same answer |
| R1b | not applicable | refuse, naming invalid model values (all 1,200 records are no-data codes) | PHY + CON |
| R2 | min −0.109 m (1 mm) | proceed, reporting the 47 dry records (−99998.6) excluded | RECALC + PHY |
| R3 | SA852, 5.053 m (1 mm) | proceed, reporting SA816 (90.7–136.2 m) excluded | RECALC + PHY. Any bound between 5.81 m and 90.75 m gives the same answer |
| R4a | n 480; bias −0.1235; RMSE 0.2676; MAE 0.2141 m; r 0.99713 (with CO-OPS NAVD) | proceed (NAVD88 vs NAVD; caveat accepted, not required) | RECALC + DOC (file label, SCN 26-51, portal) |
| R4b | n 480; bias −0.0354; RMSE 0.2111; MAE 0.1852 m; r 0.99590 (with CO-OPS MSL) | proceed with caveat | RECALC + DOC |
| R5 | not applicable | proceed with caveat: LMSL, attributed to NOAA documentation (the label "above geoid" names no datum) | DOC (NOMADS) |
| R6 | 8443970 Boston, 0.0016 km after reading x as latitude (0.1 km) | proceed with caveat: coordinates stored reversed and corrected (or flagged) | CON (file, CO-OPS metadata), second review C2 |
| R7 | 6.32 m, 2024-10-10 08:10 UTC (1 mm) | proceed, reporting the exclusion of 9-filled values (WVHT 99.00 in 35,235 of 52,692 rows) | DOC (NDBC) + RECALC; ERDDAP gives the same maximum and 17,457 valid rows |
| S1 | if proceeding: N2 values | refuse naming the missing label, **or** proceed with the missing label stated and the datum attributed to documentation | CON, DOC |
| S2 | not applicable | refuse (conflict) **only** | CON |
| S3 | not applicable | refuse (undocumented version) **only** | CON, DOC |
| S4 | n 475; bias +0.00065; RMSE 0.12267; MAE 0.09968 m; r 0.99340 | proceed, reporting the 5 excluded observations | CON + RECALC |
| S5 | N2 values | proceed with caveat; a refusal is a false refusal | CON, CF |

S1 to S3 justification (also in `references.json`):

- **S1 (refusal or flagged proceed).** The product version is identifiable (`stofs.v3.1.6` in
  `history`), and SCN 26-51 documents LMSL for v3.1 station output. The datum is therefore
  unlabelled, not unknown.
- **S2 (refusal only).** One of the file's own labels is wrong, so neither label can be trusted.
- **S3 (refusal only).** The 2D label names no datum, and V4.0.0 is not documented, so the datum is
  truly unknown. STOFS-3D changed datum at a version boundary in 2026, so carrying V3.1's datum
  forward is not safe.

## 5. Grading (`grader/grade.py`; 22 self-tests in `grader/test_grader.py` pass)

- **Values.**
  - Outcomes: within tolerance, outside tolerance, not returned, or not applicable (the reference
    is a refusal, or S1 was refused).
  - Not supported covers a missing capability, including arm D's nearest-equivalent calls.
  - Candidate not available applies to R7 arm C if ww3-mcp 0.1.3 does not exist.
- **Metadata.** Fields: datum label(s), units, product version (where the task asks), and the datum's
  stated source.
  - Primary rule: correct if every required field is present and accepted, and the datum source is
    of the accepted class. For STOFS-2D the source must cite documentation; a source citing only the
    file label is wrong. Incomplete if a field is missing. Wrong if a stated value is wrong.
  - A **strict** variant also requires a source for units and version. It is reported in a separate
    column.
- **Decision.** Outcomes:
  - correct proceed;
  - correct proceed with the required caveat;
  - **proceed, caveat missing** (added);
  - correct refusal or flag naming the cause;
  - **refusal, cause not named** (added);
  - false proceed;
  - false refusal;
  - not supported;
  - error.

  The rules:
  - A proceed that pairs incompatible datums (e.g. LMSL model vs CO-OPS NAVD) is a false proceed.
  - So is a proceed that ranks or reports no-data or implausible values, or reports the wrong
    station.
  - Detection uses fixed regular expressions and predicates, written before any arm. Each grade
    stores the text that triggered it.
- **No composite score.** Counts are per arm and axis, with false proceeds, false refusals and
  "not supported" shown separately.

## 6. Known limits of this design (to be repeated in the report)

- The same author and assistant wrote every arm, the references and the grader. The designer had read:
  - the hardening and audit reports;
  - stofs-mcp 0.3.0's source, including its 50 m bound and sentinel rule;
  - 0.3.0's archived outputs for R1, R2 and R3.

  Arm B's rules were written from NOAA documentation and physical reasoning. Its constants differ (a
  30 m bound; a domain test for reversed coordinates). It cannot be called blind.
- Before the freeze, the adapters were checked only for parsing, on the Phase 0 transcripts. These
  are 0.3.0's N1/N2 output, which the brief required in Phase 0, and a 0.2.0 Boston station call
  that is not a task.
- The set is small: 16 identifiers, 18 rows. Most tasks use one station or one file. S1 to S5 are
  synthetic. The 2026-10-30 observations were preliminary when archived.
