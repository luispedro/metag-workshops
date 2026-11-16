#!/usr/bin/env bash
# End-to-end test of `metag-ws _run-all` (the commands participants see) on
# the simulated community (tests/sim/, from tests/smoke_test.sh). In the queue:
#   mqsub --no-email -t 16 -m 64 --hours 2 -- bash data-prep/tests/run_all_sim.sh --skip-results-only
# (from the repository root, see scripts/run_precomputed.sh)
# (step 13, GTDB-Tk, needs ~130 GB of RAM: for it, use -m 192 and no
# --skip-results-only).
# The run goes to tests/ws_run/ (resumable: finished steps are skipped).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/hpc/worker_setup.sh
metag-ws _run-all -o tests/ws_run --data tests/sim -t "${THREADS:-16}" "$@"
