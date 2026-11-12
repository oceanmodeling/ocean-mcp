#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
A="--models data/archive/models --coops data/archive/coops --meta data/archive/meta --lists phase0/coops"
R=.envs/ref/bin/python
$R -I reference/classify.py $A --out reference/results/w24_8 --lead-end 24.8 > run_log/classify_w24_8.out 2>&1
$R -I reference/classify.py $A --out reference/results/w48 --lead-end 48 > run_log/classify_w48.out 2>&1
$R -I reference/classify.py $A --out reference/results/noanomaly_w49_7 --only-variant cwl.noanomaly > run_log/classify_noan.out 2>&1
echo done > run_log/classify_rest.done
