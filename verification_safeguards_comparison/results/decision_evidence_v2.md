# Decision-axis evidence, grader v2

For every v2 decision grade: the text that triggered it (the matched passage, or the fixed predicate's finding). Where the grade was given because something was absent, the output's complete notes and reported exclusions follow. Cells whose grade changed from v1 give the v1 trigger too.

**N1 / A basic Python: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**N1 / B validated Python: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**N1 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N1 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N1 / D 0.2.0: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**N2 / A basic Python: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**N2 / B validated Python: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**N2 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N2 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N2 / D 0.2.0: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**N3 / A basic Python: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / B validated Python: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / C 0.3.0 pre-fix: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / C-post 0.3.0 post-fix: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / D 0.2.0: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N4 / A basic Python: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / B validated Python: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / C 0.3.0 pre-fix: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / C-post 0.3.0 post-fix: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / D 0.2.0: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**R1a / A basic Python: false_proceed**
- trigger: `no-data or implausible station in the answer: ['9751364', '9751401', '9751381', '9752695', '9752235']`

**R1a / B validated Python: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1a / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1a / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1a / D 0.2.0: false_proceed**
- trigger: `no-data or implausible station in the answer: ['9751364', '9751401', '9751381', '9752695', '9752235']`

**R1b / A basic Python: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**R1b / B validated Python: correct_refusal_or_flag**
- trigger: `[B-Q1] No valid model value for LAMV3 SOUS41 9751381 VI Lameshur Bay, St John in 0 < lead <= 48`

**R1b / C 0.3.0 pre-fix: correct_refusal_or_flag**
- trigger: `No usable STOFS values for station 9751381 in this cycle: all 1200 records were excluded `

**R1b / C-post 0.3.0 post-fix: correct_refusal_or_flag**
- trigger: `No usable STOFS values for station 9751381 in this cycle: all 1200 records were excluded `

**R1b / D 0.2.0: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**R2 / A basic Python: false_proceed**
- trigger: `value beyond 30.0 m: ['min_m=-99998.6']`

**R2 / B validated Python: correct_proceed_with_caveat**
- trigger: `count 47`

**R2 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: `count 47`
- v1: false_proceed, trigger `value beyond 30.0 m: ['n_values=1813']`

**R2 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `count 47`
- v1: false_proceed, trigger `value beyond 30.0 m: ['n_values=1813']`

**R2 / D 0.2.0: false_proceed**
- trigger: `value beyond 30.0 m: ['min_m=-99998.6']`

**R3 / A basic Python: false_proceed**
- trigger: `no-data or implausible station in the answer: ['SA816']`

**R3 / B validated Python: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R3 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R3 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R3 / D 0.2.0: false_proceed**
- trigger: `no-data or implausible station in the answer: ['SA816']`

**R4a / A basic Python: false_proceed**
- trigger: `observation datum MSL (required NAVD88)`

**R4a / B validated Python: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4a / C 0.3.0 pre-fix: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4a / C-post 0.3.0 post-fix: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4a / D 0.2.0: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4b / A basic Python: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**R4b / B validated Python: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**R4b / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**R4b / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**R4b / D 0.2.0: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**R5 / A basic Python: correct_proceed_with_caveat**
- trigger: `fixed pairing from current product documentation (NOMADS STOFS-Global product description)`

**R5 / B validated Python: correct_proceed_with_caveat**
- trigger: `NOAA documentation: NOMADS STOFS-Global product description (station output referenced to LMSL)`

**R5 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: `NOAA documentation (STOFS_2D_GLOBAL V3.1.0: NOMADS STOFS-Global description (archived 2026-11-04): station and gridded output referenced to LMSL); file label zeta:standard_name=sea_surface_height_above_geoid names no specific datum`

**R5 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `NOAA documentation (STOFS_2D_GLOBAL V3.1.0: NOMADS STOFS-Global description (archived 2026-11-04): station and gridded output referenced to LMSL); file label zeta:standard_name=sea_surface_height_above_geoid names no specific datum`

**R5 / D 0.2.0: proceed_caveat_missing**
- trigger: `no doc_source`
- output notes (complete): (none)

**R6 / A basic Python: false_proceed**
- trigger: `station TRDF1 SOUS41 8721604 FL Trident Pier, Port Canaver`

**R6 / B validated Python: correct_proceed_with_caveat**
- trigger: `[B-C1] 105 of 108 station records store latitude in x and longitude in y (reversed relative to their attributes); they were swapped before the distance search. `

**R6 / C 0.3.0 pre-fix: proceed_caveat_missing**
- trigger: `no coords_reversed`
- output notes (complete): (none)

**R6 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `coordinate_warning: 105 of 108 station records in this file store latitude in x and longitude in y, the reverse of their attributes; their coordinates were swapped (rule: a record reading as`

**R6 / D 0.2.0: false_refusal**
- trigger: `No STOFS station found within 50.0 km of (42.3539, -71.0503).

Suggestions:
- Increase max_distance_km
- Try model='2d_global' which has ~385 stations (vs ~108 for 3D)
- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)
- Verify the coordinates are in a coastal area`
- output notes (complete): `No STOFS station found within 50.0 km of (42.3539, -71.0503).

Suggestions:
- Increase max_distance_km
- Try model='2d_global' which has ~385 stations (vs ~108 for 3D)
- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)
- Verify the coordinates are in a coastal area`

**R7 / A basic Python: false_proceed**
- trigger: `value beyond 30.0 m: ['max_wvht_m=99.0']`

**R7 / B validated Python: correct_proceed_with_caveat**
- trigger: `counts [35235]`

**R7 / C 0.3.0 pre-fix: candidate_not_available**
- trigger: (no text: correct proceed with no caveat required)

**R7 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `counts [35235, 35235]`
- v1: proceed_caveat_missing, trigger `no excluded_records`

**R7 / D 0.2.0: false_proceed**
- trigger: `value beyond 30.0 m: ['max_wvht_m=99.0']`

**S1 / A basic Python: false_proceed**
- trigger: `proceeded without the flag`

**S1 / B validated Python: correct_refusal_or_flag**
- trigger: `[B-D3] The zeta variable carries no datum label (no standard_name or long_name). STOFS-3D station output is labelled in N`

**S1 / C 0.3.0 pre-fix: correct_refusal_or_flag**
- trigger: `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established. The file name`

**S1 / C-post 0.3.0 post-fix: correct_refusal_or_flag**
- trigger: `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established. The file name`

**S1 / D 0.2.0: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**S2 / A basic Python: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**S2 / B validated Python: correct_refusal_or_flag**
- trigger: `[B-D3] Conflicting datum labels on zeta: {'standard_name': 'sea_surface_height_above_msl', 'lon`

**S2 / C 0.3.0 pre-fix: correct_refusal_or_flag**
- trigger: `alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`

**S2 / C-post 0.3.0 post-fix: correct_refusal_or_flag**
- trigger: `alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`

**S2 / D 0.2.0: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**S3 / A basic Python: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**S3 / B validated Python: correct_refusal_or_flag**
- trigger: `'long_name': 'water surface elevation above geoid'} names no datum, and product version 4.0.0 is not documented (documented: STOFS_2D_GLOBAL V3.1). Datum undetermined;`

**S3 / C 0.3.0 pre-fix: correct_refusal_or_flag**
- trigger: `s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`

**S3 / C-post 0.3.0 post-fix: correct_refusal_or_flag**
- trigger: `s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`

**S3 / D 0.2.0: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**S4 / A basic Python: false_proceed**
- trigger: `non-finite statistics [nan, inf, inf, nan]`

**S4 / B validated Python: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S4 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S4 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S4 / D 0.2.0: false_proceed**
- trigger: `non-finite statistics [nan, nan, nan, nan]`

**S5 / A basic Python: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**S5 / B validated Python: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**S5 / C 0.3.0 pre-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**S5 / C-post 0.3.0 post-fix: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**S5 / D 0.2.0: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

