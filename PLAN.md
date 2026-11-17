# Plan

This turns [GOALS.md](GOALS.md) into concrete steps. How the repository is
organised and how to build things is in [README.md](README.md),
[CLAUDE.md](CLAUDE.md) and [data-prep/README.md](data-prep/README.md).

## Status

**The workshop dataset is built and validated** (GOALS Part 2): subset
`9ca3c728` (5 selected bins, background 0.002, depth caps 60× SR / 25× LR,
eggNOG-mapper on the best MAG only), validation PASS, workshop run 24.8 min
on 16 threads. Details and per-step times are in [data-prep/TIMING.md](data-prep/TIMING.md).

* data: `data-prep/subsets/9ca3c728/workshop_data/` (`sample_R1.fq.gz` 91 MB,
  `sample_R2.fq.gz` 94 MB, `sample_ont.fq.gz` 1.0 GB)
* reference run: `data-prep/subsets/9ca3c728/run/`

To rebuild (e.g., after changing `SUBSET` or a database): `pixi run submit`
(keep it running); in `data-prep/`, `pixi run jug invalidate --name TASK`
after changing a script; on failure read `data-prep/logs/jug/`, `pixi run jug
cleanup --failed-only` and restart. The full-data results in
`data-prep/runs/full/` are reused.

**`metag-ws` is implemented** (steps 1–15; step 10, GTDB-Tk, results only;
steps 14–15, MetaBAT2 and Galah, added 2026-11-16). On 2026-11-18,
GTDB-Tk moved from step 13 to step 10, right after GUNC (SingleM appraise,
genes and eggNOG-mapper became 11–13; the precomputed folders were renamed to
match). The runs below are from before, with the old numbers.
Checked by hand: `results-for` and the choice of input folders, the menu and
state, the MAG of eggNOG-mapper's step. Arrow-key menu (2026-11-16) checked in a pseudo-terminal (`pixi run test-menu`)
(moving, scrolling in a 12-line terminal, typed steps, quit/Esc/Ctrl-C, the
plain fallback); still to try in real terminals (VS Code, Jupyter, PuTTY,
tmux) and on resizing. End-to-end test (`data-prep/tests/run_all_sim.sh`, 16
threads): all 12 steps PASS, 21.0 min (GUNC 349 s, eggNOG-mapper 345 s).
Precomputed run on the workshop dataset (`run_precomputed.sh`, job
28124971): steps 1–12 PASS, 26.7 min (vs 24.8 min with `pipeline.sh`), 31
bins, step 12 on SemiBin_2 (as in the reference run), 6.0 GB before cleanup.
Step 13 takes ≈130 GB RAM and 40 min with 16 threads (`-m 192`; with
`--skip-results-only`, `-m 64` is enough). Steps 14–15 are in the
precomputed results (job 28394942): 14.1 2 s, 14.2 74 s, 15 < 1 s (≈ 1.3 min
more in total); MetaBAT2 makes 5 bins, all high quality, and Galah 6
clusters (each of the five genomes found by both binners). Not yet in the
end-to-end test (`run_all_sim.sh`).

Galah's conda package depends on `pixi`, so the default environment has its
own `pixi` (0.84.2), which `pixi run -e …` uses once it is activated. On
aqua, in the mqyolo sandbox, pixi ≥ 0.84 refuses environments registered
under the other path of the cache (`/pkg/...` outside, `/mnt/weka/pkg/...`
inside: "the environment directory has moved"), which pixi 0.80 accepted.
For job 28394942 the `conda-meta/pixi_env_prefix` of every environment was
set to the `/mnt/weka` path and restored to `/pkg` afterwards. On the AWS
machine (one path) this does not arise.

**The workshop notes cover every step**, with lecture slides for binning,
CheckM1/CheckM2, GUNC and functional annotation.

Not done yet:

* **Background in the notes**: the TODO notes in
  `materials/metagenomics-workshop.md` (fastp/fastplong, SingleM, assembly,
  polishing, orthology-based annotation, real-data runtimes) and the
  instructor notes on the AWS machine (logging in, activation).
* **Trimming the precomputed bundle** (below).
* **Tests** (below): only the end-to-end `run_all_sim.sh` exists.
* **15-minute target**: 24.8 min is above it (below the 30 min hard limit).
  The remaining cost is mostly fixed (GUNC 5.3 min, eggNOG-mapper 4.0 min,
  DB loading); `results-for` lets participants skip a slow step.
* **CheckM2 database**: aqua's shared DB is the 2021 version; CheckM2 1.1.0
  recommends DB v3 (doi:10.5281/zenodo.14897628), which `pixi run
  download-dbs` installs. Rerun the precomputed results with the downloaded
  databases (`METAG_WS_DB=...`), so that they match the workshop machine.
* **The AWS machine** (below): not built; the database download and the
  setup guide are done (setup/README.md).

## Checked against GOALS.md (2026-11-16)

Met as planned: the five topics of Part 1 with the tools GOALS names, the
dataset construction of Part 2, and `metag-ws` as specified (menu, per-user
state, numbered folders, `_precomputed` folders that never overwrite the
participant's own).

Where we differ from GOALS, on purpose:

* **Step 13 annotates one bin** (`BIN_NAME`, the best by CheckM2), not all of
  them: all bins take ~15 min. GOALS asks that participants "find a function
  of interest across bins"; the notes only search one bin so far (open
  below).
* **Step 10, GTDB-Tk** (taxonomy of the bins), was not in GOALS at first. It
  is the standard bin taxonomy, so it is shown, but results only. Its
  database is not needed on the workshop machine.
* **Steps 14–15** (a second binner, MetaBAT2, with CheckM2 on its bins; and
  dereplication of the bins of both binners with Galah, at 95% ANI, keeping
  bins ≥50% complete and <10% contaminated) were added later. Galah is
  usually used across samples; with one sample, it shows how the two binners
  compare and gives one genome per species. MetaBAT2 is in its own pixi
  environment (`metabat2`): it needs htslib <1.25 and libdeflate 1.22, older
  than samtools 1.25 and fastplong 0.7. Neither needs a database.
* **Runtime** above the 15 min target (see Status).

Still open, against GOALS:

* **Across-bins annotation exercise** (GOALS 5): e.g., eggNOG-mapper on all
  bins in the precomputed results, and a `grep` across them in the notes.
* **Interpreting results** (GOALS 1–2: decide whether reads are fit for use,
  compare the short- and long-read profiles): the commands and "what to look
  at" are there; the background in the notes is still TODO.
* **Public data** (step 1): still copied from `$METAG_WS_DATA`; to download
  from a public record (e.g., Zenodo, citing the original study) instead.
* **AWS machine** ("Workshop support data & tools"): not built. The
  databases can be downloaded from their public sources (`pixi run
  download-dbs`), and the environment finds them through `$METAG_WS_DB` or
  `/opt/metag-ws/db` (setup/activate_databases.sh); setup/README.md is the
  step-by-step guide.

## `metag-ws`: design decisions

1. **Steps and `pipeline.sh`**: `metag-ws` steps follow `pipeline.sh`
   (validated on the workshop dataset), which keeps its own layout because
   the full-data run and the dataset scripts depend on it:

   | # | step | pipeline.sh |
   |---|---|---|
   | 1 | Get data | — |
   | 2.1 / 2.2 | Read QC: short / long | `qc_sr` / `qc_lr` |
   | 3.1 / 3.2 | SingleM: short / long | `profile_sr` / `profile_lr` |
   | 4 | Assembly | `assemble` (without `bwa index`) |
   | 5.1 / 5.2 | Polish: mapping / polypolish | `bwa index` + `polish_aln_r1` + `polish_aln_r2` / `polish` |
   | 6 | Mapping | `map` |
   | 7 | Binning | `bin` |
   | 8 | CheckM2 | `checkm2` |
   | 9 | GUNC | `gunc` |
   | 10 | GTDB-Tk (results only) | — |
   | 11 | SingleM appraise | `appraise` |
   | 12 | Gene prediction (pyrodigal) | `genes` |
   | 13 | eggNOG-mapper | `eggnog` |
   | 14.1 / 14.2 | MetaBAT2 / CheckM2 on its bins | — |
   | 15 | Galah | — |

   Differences: each step writes only into its own folder, so `bwa index`
   writes into the step's folder (`-p 05_POLISH/draft`, `-p
   06_MAPPING/polished`) instead of next to the assembly; no `bash -c` or
   `/usr/bin/time` wrappers; step 12 does not write `all_bins.faa` (nothing
   uses it).
2. **Menu.** Inline, not a full-screen TUI, so it works in any SSH terminal
   and in Jupyter/VS Code terminals: arrow keys (or j/k, PgUp/PgDn,
   Home/End) and Enter, or type a step number (the cursor follows it). It is
   never taller than the terminal (it scrolls; projector fonts make
   terminals short) and is erased once a step is chosen, so the output is
   the same as with the step on the command line. The cursor starts on the
   step **after** the last one used (by any subcommand), which is tagged
   `last used`. Without a terminal (stdin or stdout redirected, `TERM=dumb`)
   or with `METAG_WS_MENU=plain` it falls back to a typed prompt (Enter =
   that same next step). With a step on the command line there is no menu
   (for instructors, scripting).
3. **`results-for N` brings in all steps up to N**, not only N: assemblies,
   contig names and bins differ between runs, so mixing them breaks things
   (e.g., a precomputed BAM with the participant's own polished assembly).
   Afterwards, inputs from a step ≤ N come from `NN_<STEP>_precomputed` and
   all others from the participant's own folders: after `results-for 4`,
   step 5 reads `02_QC_precomputed` and `04_ASSEMBLY_precomputed` and writes
   `05_POLISH`; step 6 then reads the participant's own `05_POLISH`. This
   keeps each chain consistent. Consequence: after `results-for`, commands
   copied from a printed handout no longer work as they are; participants
   should use `show-cmd`.
4. **Step 13 picks its bin with a shell variable**: `BIN_NAME` is set by an
   `awk` one-liner to the best bin (completeness − 5 × contamination) in the
   CheckM2 report step 13 reads (own or precomputed), so the command works
   with no editing although bins are named differently in each run;
   participants can set `BIN_NAME` themselves to annotate another bin.
   eggNOG-mapper's own environment is shown, not hidden (a chance to show
   `pixi run -e`); it works from `~/workshop` because pixi finds the project
   through `$PIXI_PROJECT_MANIFEST`. On the AWS machine, check that it works
   with the shared, read-only installation (otherwise add `--as-is`).
5. **Results-only steps**: `results-for 10` links the precomputed folders
   of steps 1–10 (for comparison) without changing `precomputed_upto`, so the
   other steps keep their inputs. No later step reads its outputs.
   `_run-all` runs it (for the precomputed results); `--skip-results-only`
   skips it.
6. **`_run-all`** (hidden): records finished steps (`DIR/.done/`) so a killed
   run can be resumed, writes `DIR/timings.tsv` (seconds and peak RAM per
   step), and stops at the first failing command. It ignores the user's
   state file.

## Still to do

* **Precomputed bundle**: `run_precomputed.sh` builds it; a
  `make_precomputed.sh` should then remove what participants do not need:
  `.done/`, myloasm's intermediates (`binary_temp/`, `0-`–`3-*/`, ~1 GB; keep
  `assembly_primary.fa`, the graphs and the log) and polypolish's
  `filtered_*.sam` (1.2 GB). Keep `aln_R{1,2}.sam` (1.2 GB), needed to run 5.2
  after `results-for 5.1`.
* **Tests**: the commands in `steps.toml` match the validated ones in
  `pipeline.sh`; `results-for` each step in a fresh directory, and `show-cmd`
  then picks the right input folders; the state file (`last used`, menu starts
  on the next step).

## The AWS machine

One large machine shared by all participants, each with their own user
account; data, software, databases and precomputed results in shared
read-only paths (e.g., `/opt/metag-ws/{data,precomputed,db}`, the defaults of
`metag-ws`), each user's work in their home directory.

1. **Size**: the 24.8 min was measured with 16 threads / 64 GB for one run
   (peak RAM per step ≤ 8.8 GB). With many participants running at once,
   choose CPUs and the per-user thread count (`METAG_WS_THREADS`) together:
   e.g., 30 participants × 8 threads ≈ 240 vCPUs if all run the same step at
   the same time (they will not all do so, and `results-for` lets slow
   participants skip ahead). Time a few simultaneous runs on the chosen
   instance type and update data-prep/TIMING.md.
2. **Databases** on fast local disk (≈ 165 GB: GTDB-Tk 88 GB, eggNOG 51 GB,
   GUNC 13.5 GB, SingleM 9.7 GB, CheckM2 ≈ 3 GB). On a shared machine they
   stay in the page cache once the first user has read them, if there is
   enough RAM: plan RAM for the databases (≈ 36 GB of DIAMOND/SingleM files
   actually read) plus the users' jobs. **Done**: `pixi run download-dbs`
   (setup/download_databases.sh) downloads pinned versions from the public
   sources (not with the tools' downloaders: `singlem data` takes the newest
   metapackage, and `download_eggnog_data.py` points to a host that no longer
   exists). GTDB-Tk is included for completeness, although step 10 is not run
   there.
3. **Software**: one shared `pixi install --frozen` (all environments but
   docs), and `metag-ws` and
   the tools on every user's `PATH` (e.g., activation in `/etc/profile.d/`).
4. **Users**: one account per participant (created from a list); home
   directories need ≈ 5 GB each for a full own run (nothing extra for
   `results-for`, which only creates symlinks).
5. Build it once as an AMI (e.g., with a provisioning script in
   `data-prep/scripts/aws/`), so it can be relaunched for each workshop.

## Open questions

* Number of participants (sets the instance size and the threads per user).
* How participants reach the machine (SSH, Jupyter, VS Code remote): it
  decides how they open the HTML reports (TODO in the notes).
