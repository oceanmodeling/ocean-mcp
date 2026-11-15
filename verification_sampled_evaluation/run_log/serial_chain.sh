#!/usr/bin/env bash
# One CPU-heavy process at a time (after two crashes with parallel jobs), low priority.
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
echo "start $(date -u +%FT%TZ)" > run_log/serial_chain.log
nice -n 19 python3 -I phase2/run_sessions.py --jobs 1 >> run_log/run_sessions.out 2>&1
echo "sessions exit $? $(date -u +%FT%TZ)" >> run_log/serial_chain.log
A="--models data/archive/models --coops data/archive/coops --meta data/archive/meta --lists phase0/coops"
R=.envs/ref/bin/python
nice -n 19 $R -I reference/classify.py $A --out reference/results/w24_8 --lead-end 24.8 > run_log/classify_w24_8.out 2>&1
echo "w24_8 exit $? $(date -u +%FT%TZ)" >> run_log/serial_chain.log
nice -n 19 $R -I reference/classify.py $A --out reference/results/w48 --lead-end 48 > run_log/classify_w48.out 2>&1
echo "w48 exit $? $(date -u +%FT%TZ)" >> run_log/serial_chain.log
nice -n 19 $R -I reference/classify.py $A --out reference/results/noanomaly_w49_7 --only-variant cwl.noanomaly > run_log/classify_noan.out 2>&1
echo "noanomaly exit $? $(date -u +%FT%TZ)" >> run_log/serial_chain.log
echo "done $(date -u +%FT%TZ)" >> run_log/serial_chain.log
