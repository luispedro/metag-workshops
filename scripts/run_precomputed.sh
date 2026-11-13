#!/usr/bin/env bash
# Builds the precomputed results (PLAN.md, metag-ws Implementation 8): all
# workshop commands, as `metag-ws show-cmd` prints them, on the workshop
# dataset, into precomputed/ (resumable). In the queue:
#   mqsub --no-email -t 16 -m 64 --hours 2 -- bash scripts/run_precomputed.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/hpc/worker_setup.sh
metag-ws _run-all -o precomputed --data subsets/9ca3c728/workshop_data -t "${THREADS:-16}" "$@"
