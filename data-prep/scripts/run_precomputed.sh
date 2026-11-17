#!/usr/bin/env bash
# Builds the precomputed results (PLAN.md, "Precomputed bundle"): all
# workshop commands, as `metag-ws show-cmd` prints them, on the workshop
# dataset, into precomputed/ (resumable). In the queue (step 10, GTDB-Tk,
# needs ~130 GB of RAM and 40 min; with --skip-results-only, -m 64 is enough):
#   mqsub --no-email -t 16 -m 192 --hours 4 -- bash data-prep/scripts/run_precomputed.sh
# (from the repository root: in the mqyolo sandbox, only the folder mqsub is
# run from is writable, and pixi writes .pixi/ there)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/hpc/worker_setup.sh
metag-ws _run-all -o precomputed --data subsets/9ca3c728/workshop_data -t "${THREADS:-16}" "$@"
