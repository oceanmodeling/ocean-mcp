# WP7 scratch status (outside the repository; survives WSL restarts)
- Task A: done (verification_manuscript_facts/figures/fig5_*).
- Task C code: committed f5ab1fd on fix/stofs-post-wp5; wheel verification_post_wp5/dist/ sha256 afb8be50d4bd025a07207b9aa3b67e4a733c3c9350bf65064c0b9c32f9cbd0cc.
  Tests: CPython 3.13 384 passed; 3.11/3.12 not run (offline: pydantic-core cp311/cp312 wheels not in uv cache). ruff check/format pass.
- Task B: scratch copy in taskB/ (archive bodies and .envs hard-linked; code and outputs copied); run_all.sh serial.
- Task B started 2026-11-12T19:48:44Z; log taskB/run_all.log
- Task B stopped at step 4 (results/a1 missing in a from-scratch tree; run_all.sh defect). Steps 0-3 reproduced (12/12 reference files identical). Resumed 2026-11-12T22:20:33Z with steps 4-9 (resume_from_step4.sh) after mkdir results/a1 in the scratch copy only.
- Task B finished 2026-11-13T14:33:57Z: 94/94 regenerated files identical; 6 committed files not produced by run_all (5 .gz copies, station_table_3d_post.md); defect: results/a1 not created. 121/121 sessions valid.
- Task C regression 1 started 2026-11-13T14:39:43Z
- Task C regression 1 done; regression 2 started 2026-11-13T16:20:30Z
