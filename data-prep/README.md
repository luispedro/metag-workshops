# Preparing the workshop dataset

How the workshop dataset (a reduced version of one soil sample) and the
precomputed results for `metag-ws results-for` were built. None of this is
needed to attend or run the workshop. The goals are in
[`../GOALS.md`](../GOALS.md) (Part 2), the plan and status in
[`../PLAN.md`](../PLAN.md), the measured run times in [`TIMING.md`](TIMING.md).

| file | what |
|---|---|
| `jugfile.py` | the [Jug](https://jug.readthedocs.io) task graph: full-data run → `select_bins` → `make_subset` → `workshop_run` → `validate`; dataset parameters in `SUBSET` |
| `jug_hpc.toml` | resources per task for [jug_hpc](https://github.com/luispedro/jug_hpc); `tests/jug_hpc.toml` for test mode |
| `scripts/pipeline.sh` | the pipeline used to build and validate the dataset (`step_*` functions); writes `timings.tsv` |
| `scripts/select_bins.py`, `make_subset.sh`, `select_reads.py`, `validate.py` | bin selection, read extraction, validation |
| `scripts/run_precomputed.sh` | the precomputed results: every `metag-ws` command, on the workshop dataset, into `precomputed/` |
| `scripts/hpc/` | queue submission from the mqyolo sandbox (`qsub` shim, worker setup) |
| `tests/` | simulated 3-genome community (`smoke_test.sh`) and end-to-end tests (`pixi run submit-test`, `run_all_sim.sh`) |

Everything runs in the pixi environment of the repository root
(`../pixi.toml`). The tasks run from this directory:

```bash
pixi run submit         # build/rebuild the dataset (jug_hpc; keep it running)
pixi run status         # progress (jug status)
pixi run submit-test    # the same on the simulated data
```

Not in git (`.gitignore`): the full data (`full_data/`), the runs (`runs/`,
`subsets/`, `precomputed/`), Jug's state (`jugfile.jugdata/`, `.jug_hpc/`) and
the logs (`logs/`). The workshop dataset is `subsets/9ca3c728/workshop_data/`.
