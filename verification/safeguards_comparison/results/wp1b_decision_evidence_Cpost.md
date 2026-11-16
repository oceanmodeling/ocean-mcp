# Arm C-post: text that triggered every decision grade (primary grading)

Where a grade was given because something was absent, the output's complete notes and reported exclusions follow.

**N1 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N2 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N3 / C-post: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N4 / C-post: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**R1a / C-post: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1b / C-post: correct_refusal_or_flag**
- trigger: `No usable STOFS values for station 9751381 in this cycle: all 1200 records were excluded `

**R2 / C-post: false_proceed**
- trigger: `value beyond 30.0 m: ['n_values=1813']`

**R3 / C-post: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R4a / C-post: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4b / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**R5 / C-post: correct_proceed_with_caveat**
- trigger: `NOAA documentation (STOFS_2D_GLOBAL V3.1.0: NOMADS STOFS-Global description (archived 2026-11-04): station and gridded output referenced to LMSL); file label zeta:standard_name=sea_surface_height_above_geoid names no specific datum`

**R6 / C-post: correct_proceed_with_caveat**
- trigger: `coordinate_warning: 105 of 108 station records in this file store latitude in x and longitude in y, the reverse of their attributes; their coordinates were swapped (rule: a record reading as`

**R7 / C-post: proceed_caveat_missing**
- trigger: `no excluded_records`
- output notes (complete): `hint: Only the most recent 5000 rows are returned (max_records, up to 5000). The summary statistics are computed over every row of the file.`
- exclusions recorded by the frozen adapter: `[]`
- A3 value trigger, frozen: `maximum WVHT over the 5000 returned rows = 5.35 (row time 2024-12-15 17:40)`
- A3 value trigger, amended: `summary: {"units": "m", "covers": "all 52692 rows of the file", "missing": 35235, "valid": 17457, "max": 6.32, "max_time": "2024-10-10 08:10"}`

**S1 / C-post: correct_refusal_or_flag**
- trigger: `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established. The file name`

**S2 / C-post: correct_refusal_or_flag**
- trigger: `alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`
- A2 lenient: correct_refusal_or_flag (`alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`)

**S3 / C-post: correct_refusal_or_flag**
- trigger: `s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`
- A2 lenient: correct_refusal_or_flag (`s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`)

**S4 / C-post: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S5 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

