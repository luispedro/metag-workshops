# Plan: building the workshop dataset

This turns [GOALS.md](GOALS.md) into concrete steps. Everything runs in the
pixi environment of this repository. The whole construction, from the
full-data run to the validated toy dataset, is one [Jug](https://jug.readthedocs.io)
task graph (`jugfile.py`); [jug_hpc](https://github.com/luispedro/jug_hpc)
submits a right-sized aqua queue job for each task once it is ready, with the
resources in `jug_hpc.toml`.

## Environment

`pixi install --all` creates two environments (latest bioconda releases as of
2026-11-04):

| tool | version | env |
|---|---|---|
| fastp / fastplong | 1.4.0 / 0.7.1 | default |
| SingleM | 0.21.4 | default |
| myloasm | 0.7.0 | default |
| bwa / polypolish / samtools | 0.7.19 / 0.7.1 / 1.25 | default |
| SemiBin2 | 2.6.0 | default |
| CheckM2 / GUNC | 1.1.0 / 1.1.1 | default |
| pyrodigal | 3.7.1 | default |
| eggNOG-mapper | 2.1.15 | `eggnog` |
| minimap2, seqkit, skani, pandas | 2.31, 2.14.0, 0.4.0, 3.0.6 | default (dataset construction only) |

eggNOG-mapper 2.1.15 requires diamond <2.1, and GUNC 1.1.1 requires diamond
2.1.24, so eggNOG-mapper has its own environment (`pixi run -e eggnog
emapper.py ...`).

Databases are set in `pixi.toml` (`[activation.env]`) and point to the shared
copies in `/work/microbiome/db`:

| variable | database |
|---|---|
| `SINGLEM_METAPACKAGE_PATH` | S6.5.0 GTDB r232 (S7.5.0 needs a newer SingleM than 0.21.4, which only reads metapackage format 6) |
| `CHECKM2DB` | `CheckM2_database/uniref100.KO.1.dmnd` (2021; **older than the v3 DB recommended for CheckM2 1.1.0**) |
| `GUNC_DB` | `gunc/1.0.1/gunc_db_2.0.4.dmnd` (proGenomes 2.1) |
| `EGGNOG_DATA_DIR` | `eggnog-mapper/2.1.12` (eggNOG 5.0.2, current for emapper 2.1.x) |

## Scripts

| file | what |
|---|---|
| `jugfile.py` | the task graph (below) and the dataset parameters (`SUBSET`) |
| `jug_hpc.toml` | resources of each task (one jug_hpc class per full-data step); `tests/jug_hpc.toml` for test mode |
| `scripts/hpc/qsub` | `qsub` for jug_hpc inside the mqyolo sandbox (which has only `mqsub`): translates the `#PBS` header into `mqsub` options |
| `scripts/hpc/worker_setup.sh` | run by every worker: activates the pixi environment |
| `scripts/pipeline.sh` | the workshop pipeline, step by step (`qc_sr qc_lr profile_sr profile_lr assemble polish map bin checkm2 gunc appraise genes eggnog`); `--only STEP` runs one step; writes `timings.tsv`; can fake slow steps (below) |
| `scripts/select_bins.py` | summarises bins (CheckM2, GUNC, depth, SingleM taxonomy) and proposes a selection |
| `scripts/make_subset.sh` + `select_reads.py` | extract the workshop reads |
| `scripts/validate.py` | compares the workshop run with the full run (GOALS step 5) |
| `tests/smoke_test.sh` | simulates a 3-genome community from GTDB genomes (and runs `pipeline.sh` on it) |

`pipeline.sh` is both the full-data run and what participants run, so the
workshop commands are the ones that were validated. The commands in each
`step_*` function are what the handout should show.

## Running it

```bash
pixi run submit                   # keep running (e.g., in tmux) until done
pixi run jug status               # progress
pixi run jug shell                # value(validation)['report'], ...
```

`pixi run submit` runs `jug-hpc submit`, which polls Jug (every minute,
backing off to 5 min while nothing changes) and submits a worker for each
class with a ready task; each class (`jug_hpc.toml`) holds one task, so its
worker runs that task and exits. jug_hpc's cluster settings (PBS, the `-P`
project) are in `~/.config/jug_hpc/cluster.toml`. Jug keeps the results in
`jugfile.jugdata/` (a `file_keepalive:` store, set in `jug_hpc.toml` and
`.jugrc`), and jug_hpc keeps the jobs it submitted in `.jug_hpc/jobs.json`, so
the submitter can be stopped and restarted at any time. Worker logs are in
`logs/jug/<class>-<job>.log`, PBS's own in `logs/jug/scheduler/`. Before
changing resources, check with `pixi run jug-hpc check` (which class runs
which task) and `pixi run jug-hpc submit --dry-run` (the job scripts).

jug and jug_hpc are installed from git (`[pypi-dependencies]` in
`pixi.toml`; jug_hpc needs features of jug that are not released yet);
`pixi.lock` pins the commits.

Failures are not retried automatically: the submitter stops (exit status 1)
when only failed tasks are left, or when 3 jobs of a class in a row fail.
A worker killed at the walltime leaves its task's lock, which the
`file_keepalive:` store turns into a failure after 30 min. Read the log, fix
the cause, `pixi run jug cleanup --failed-only`, restart `pixi run submit`.
Jug does not notice changes to the scripts: after changing one,
`pixi run jug invalidate --name TASK` (this also invalidates everything
downstream).

Test mode runs the same graph on the simulated community (`tests/jugrun/`,
jugdir `tests/jugfile.jugdata/`, logs in `tests/logs/`; `tests/` is a separate
jug_hpc project, with one 16-CPU class for all tasks), as an end-to-end check
before the multi-day full run:

```bash
pixi run bash tests/smoke_test.sh   # once, to simulate tests/sim/ (or submit it with mqsub)
pixi run submit-test
pixi run status-test
```

## The task graph

```
full_qc_sr ─┬────────────────────── full_profile_sr ───────────┐
full_qc_lr ─┼─ full_profile_lr ─────────────────────────── full_appraise ─┐
            └─ full_assemble ─ full_polish ─ full_map ─ full_bin ─┬─ full_checkm2 ─┤
              (full_qc_sr ──┘)  └─ full_map_lr ─┐                 └─ full_gunc ────┤
                                                │                                  │
                         make_subset ◄──────────┴───────────── select_bins ◄───────┘
                              │
                         workshop_run ── validate
```

| task | CPUs | RAM (GB) | walltime (h) |
|---|---|---|---|
| full_qc_sr / full_qc_lr | 16 | 32 | 24 / 48 |
| full_profile_sr / full_profile_lr | 32 | 64 | 48 |
| full_assemble | 64 | 500 | 48 |
| full_polish / full_map | 64 | 128 | 48 |
| full_bin | 32 | 128 | 48 |
| full_checkm2 / full_gunc / full_appraise | 32 | 128 / 128 / 64 | 24 |
| full_map_lr | 32 | 64 | 48 |
| select_bins / validate | 1 / 4 | 8 / 16 | 1 |
| make_subset | 16 | 64 | 24 |
| workshop_run | 16 (`WORKSHOP_THREADS`: match the workshop machines) | 64 | 4 |

### 1. Full pipeline on the full data (`full_*` tasks)

Each task runs `pipeline.sh --only STEP` into `runs/full/` (no annotation;
polishing uses `--cleanup` to delete the large `bwa mem -a` SAM files).
`full_map_lr` maps the raw ONT reads to the polished assembly with minimap2
(needed for step 3), in parallel with binning.

Risk: a single task taking longer than 48 h. The most likely is `full_assemble`
(myloasm on ~70 GB of gzipped soil ONT reads). If it does, options are
myloasm `--kmc` (faster k-mer counting, recommended by myloasm for soil, but
needs `myloasm-kmc`, which is not on bioconda), or rerunning from myloasm's
intermediate files. `full_profile_lr` could also be split into several Jug
tasks with SingleM's `--read-chunk-size/--read-chunk-number`.

### 2. Select bins (`select_bins`)

Runs `scripts/select_bins.py` into `subsets/<tag>/selection/`. `<tag>` is a hash
of `SUBSET` (in `jugfile.py`) and of the manual selection, so each attempt in
step 6 gets its own directory and nothing upstream is rerun.

* Candidates: CheckM2 completeness ≥ 90%, contamination ≤ 5% (MIMAG high
  quality), GUNC pass. Thresholds are options (`--min-completeness`,
  `--max-contamination`). If too few bins pass, relax to ≥ 70% / ≤ 10%.
* Abundance: candidates are split into 5 strata of log short-read depth, one
  bin per stratum, so the selection goes from the least to the most abundant
  *good* bin.
* Taxonomy: within a stratum, the bin from the least-represented phylum, then
  class, wins (taxonomy = the most-covered lineage in the SingleM profile of
  the bin).
* Review `subsets/<tag>/selection/bins_summary.tsv`. To choose the bins by hand
  (e.g. to include an interesting lineage), list them in
  `selection_manual.txt` (repository root, committed): this changes the tag,
  and the downstream tasks run again for the new selection. This is the one
  manual decision.

### 3–4. Extract reads and add background (`make_subset`)

`scripts/make_subset.sh`, with `max_depth_sr`, `max_depth_lr`, `background`
and `seed` from `SUBSET`, into `subsets/<tag>/workshop_data/`.

* Short reads: from the full-run BAM (paired `bwa mem` to the whole polished
  assembly), every pair with a primary alignment of either mate to a selected
  contig. Mapping to the whole assembly, not just the selected bins, keeps reads
  from related organisms from being pulled in.
* Long reads: raw ONT reads mapped with `minimap2 -x map-ont` to the whole
  polished assembly (`full_map_lr`), keeping reads whose primary alignment
  is to a selected contig.
* Downsampling: bins above `--max-depth-*` are downsampled to that depth. The
  fractions are written to `selection/reads_{sr,lr}.tsv` and copied to
  `workshop_data/` so the distortion of relative abundances is recorded.
* Background: a fraction `--background` of all *other raw* reads (unmapped,
  mapped to other bins, or failing QC), so participants see unbinned contigs,
  taxa without bins in SingleM, and realistic QC reports.
* Read selection is a deterministic hash of the read name, so reruns give the
  same dataset; reads keep their original order in the FASTQ files.
* Output: `workshop_data/sample_R1.fq.gz`, `sample_R2.fq.gz`,
  `sample_ont.fq.gz`.

### 5–6. Validate and time (`workshop_run`, `validate`)

`workshop_run` runs the whole `pipeline.sh` on the toy data into
`subsets/<tag>/run/`, from scratch, with `WORKSHOP_THREADS` threads in a job of
that size, so `timings.tsv` reflects the workshop machines. `validate` runs
`validate.py`, which writes `validation.md` and checks:

1. each selected bin is recovered (skani ANI ≥ 99%, aligned fraction ≥ 50%),
   completeness within 5 points, contamination at most 2 points higher, GUNC
   pass, and the same SingleM taxonomy as in the full run;
2. the genus of each selected bin is in the short- and long-read SingleM
   profiles;
3. all expected output files exist and are not empty;
4. the total time in `timings.tsv`: target ≤ 15 min, hard limit 30 min
   (above 30 the workshop becomes difficult; validation fails only then).

A FAIL is a result (`value(validation)['passed']`), not a task error. Adjust
`SUBSET` in `jugfile.py` and run `pixi run submit` again until it passes:

| problem | change |
|---|---|
| too slow, everything scales with read count | lower `max_depth_sr/_lr` (but keep ≥ ~20× LR for myloasm and ≥ ~15× SR for polishing) |
| too slow in eggNOG-mapper / GUNC / CheckM2 | fewer bins (`n_bins`), or `--sensmode fast` for emapper |
| a selected bin falls apart | raise its depth cap, or swap it for another bin from the same stratum |
| too clean (no unbinned contigs, no extra taxa) | raise `background` |
| background produces bins that hurt runtime | lower `background` |
| one substep is still too slow after all of the above | fake it (below) |

### Fallback: faking a slow step

We'd rather avoid it, but a step that is too slow can be faked: participants
see the commands and get pre-computed results.

```bash
pixi run bash scripts/pipeline.sh ... --precomputed subsets/<tag>/run --fake eggnog,gunc
```

prints the commands of the faked steps and copies their outputs from a
previous run on the workshop data; `timings.tsv` marks them `precomputed`
(and validation then times only the steps that really ran). This only works
if the earlier steps reproduce that run, especially the bins and their names
(`SemiBin_N`). Check that by running the workshop pipeline twice and comparing
`binning/output_bins`. Faking the last steps (`eggnog`, then `gunc`) is the
safest option.

## Open points

* **Data access**: `full_data/` now holds the reads directly. The short reads
  are readable; the ONT file (70.5 GB) and two DB files (GUNC
  `gunc_db_2.0.4.dmnd`, eggNOG `eggnog_proteins.dmnd`) are on the slower storage
  tier, and first reads block for a long time (tens of minutes so far).
* **CheckM2 database**: the shared DB is the 2021 version. CheckM2 1.1.0
  recommends DB v3 (doi:10.5281/zenodo.14897628).
* **Workshop machine size**: the 15-minute target depends on the participants'
  CPUs/RAM. `jugfile.py` assumes 16 CPUs (`WORKSHOP_THREADS`) / 64 GB.
* **Database speed**: because of the tiered storage, the first read of a
  database can stall for a long time. For the workshop, the databases should be
  on local or fast disk; their loading is part of the measured time for
  GUNC/CheckM2/eggNOG-mapper.
* SemiBin2 is run with `--sequencing-type long_read` because the contigs come
  from a long-read assembly (SemiBin2 then uses its long-read clustering);
  coverage comes from the short reads only, as in GOALS.md.
