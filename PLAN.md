# Plan

This turns [GOALS.md](GOALS.md) into concrete steps.

## Status

**The workshop dataset is built and validated** (GOALS Part 2): subset
`9ca3c728` (5 selected bins, background 0.002, depth caps 60× SR / 25× LR,
eggNOG-mapper on the best MAG only), validation PASS, workshop run 24.8 min
on 16 threads. Details and per-step times are in [data-prep/TIMING.md](data-prep/TIMING.md).

* data: `data-prep/subsets/9ca3c728/workshop_data/` (`sample_R1.fq.gz`,
  `sample_R2.fq.gz`, `sample_ont.fq.gz`, 1.2 GB)
* reference run (the future precomputed results): `data-prep/subsets/9ca3c728/run/`

Still open from the dataset work:

* **15-minute target**: 24.8 min is above the target (below the 30 min hard
  limit). The remaining cost is mostly fixed (GUNC 5.3 min, eggNOG-mapper
  4.0 min, DB loading). `metag-ws jump-to` (below) makes this less critical:
  participants can skip a slow step instead of waiting.
* **CheckM2 database**: the shared DB is the 2021 version; CheckM2 1.1.0
  recommends DB v3 (doi:10.5281/zenodo.14897628). Install it for the AWS
  machine and rerun the reference run with it.

### Reference: how the dataset is built

Everything for building the dataset is in [`data-prep/`](data-prep/) (see
its README): the Jug task graph, the scripts, the tests and, not in git, the
runs. It uses the pixi environment of the repository root (`pixi install
--all`; eggNOG-mapper is in its own `eggnog` environment because of a diamond
version conflict with GUNC). Databases are set in `pixi.toml`
(`[activation.env]`) and point to `/work/microbiome/db`.

To rebuild (e.g., after changing `SUBSET` or a database): `pixi run submit`
(keep it running); in `data-prep/`, `pixi run jug invalidate --name TASK`
after changing a script; on failure read `data-prep/logs/jug/`, `pixi run jug
cleanup --failed-only` and restart. The full-data results in
`data-prep/runs/full/` are reused.


## Next: `metag-ws`, the workshop helper (GOALS: "Workshop support data & tools")

A Python command-line tool, installed with pixi, that runs on the workshop
machine. For each workshop step it can print the command (`show-cmd`), print
the command with each argument explained (`explain-cmd`), or bring in the
precomputed results (`results-for`).

**Status (2026-11-13):** implemented in `metag-ws/` (`metag_ws/steps.toml`:
commands, explanations, what to look at; `metag_ws/cli.py`), installed in the
default pixi environment. Checked by hand: `results-for` and the choice of
input folders, the menu and state, step 12's MAG. End-to-end test
(`data-prep/tests/run_all_sim.sh`, `_run-all` on `data-prep/tests/sim/`, 16 threads): all 12
steps PASS, 21.0 min (GUNC 349 s, eggNOG-mapper 345 s). Precomputed run on
the workshop dataset: `data-prep/scripts/run_precomputed.sh` → `data-prep/precomputed/`
(job 28124971): all steps PASS, 26.7 min (vs 24.8 min with `pipeline.sh`),
31 bins, step 12 on SemiBin_2 (as in the reference run), 6.0 GB before
cleanup. Docs (9) started: the workshop notes in `materials/` have the
commands of every step and how to use `metag-ws`. Not done yet:
`make_precomputed.sh` (Implementation 8), the rest of the docs (9), tests (10).

### Design

1. **Steps** (as in GOALS; `pipeline.sh` step in the last column):

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
   | 10 | SingleM appraise | `appraise` |
   | 11 | Gene prediction (pyrodigal) | `genes` |
   | 12 | eggNOG-mapper | `eggnog` |

   A step can be given as `5` (all its substeps) or `5.2`.
2. **Invocation.** `metag-ws <subcommand> [STEP]`: with a step (`metag-ws
   show-cmd 5.2`) there is no menu (for instructors, slides, scripting);
   without one it shows the menu.
3. **Menu.** A numbered list; the last step used (by any subcommand) is
   highlighted and the **next** step is the default (Enter selects it). The
   state is per user, in `$XDG_STATE_HOME/metag-ws/state.json` (default
   `~/.local/state/metag-ws/`).
4. **Folder layout.** Each participant works in their own directory
   (`~/workshop`, override with `METAG_WS_DIR`), with one folder per step,
   zero-padded so that `ls` lists them in order:

   ```
   01_DATA  02_QC  03_SINGLEM  04_ASSEMBLY  05_POLISH  06_MAPPING
   07_BINNING  08_CHECKM2  09_GUNC  10_APPRAISE  11_GENES  12_EGGNOG
   ```

   Substeps share their step's folder (`02_QC` has the short- and long-read
   QC). **Each step writes only into its own folder** and only reads from
   earlier ones. This needs a few command changes compared with
   `pipeline.sh`, where `bwa index` writes next to the assembly: step 5.1
   uses `bwa index -p 05_POLISH/draft 04_ASSEMBLY/assembly_primary.fa`, and
   step 6 `bwa index -p 06_MAPPING/polished 05_POLISH/polished.fa`.
5. **`results-for N`** never touches the participant's own folders. For each
   step up to and including N it creates `NN_<STEP>_precomputed`, a symlink
   to the shared read-only copy (`$METAG_WS_PRECOMPUTED/NN_<STEP>`). That
   takes no time and no disk, and it is safe because no step writes into
   the folders it reads. It brings in all steps up to N, not only N:
   assemblies, contig names and bins differ between runs, so mixing them
   breaks things (e.g., a precomputed BAM with the participant's own
   polished assembly). It then prints the note that the precomputed results
   may not be exactly the same as the participant's own, and records N in
   the state file (`precomputed_upto`).
6. **Inputs after `results-for`.** `show-cmd` and `explain-cmd` print the
   commands with the input folders filled in: inputs from a step ≤
   `precomputed_upto` come from `NN_<STEP>_precomputed`, all others from the
   participant's own folders. For example, after `results-for 4`, step 5
   reads `02_QC_precomputed` and `04_ASSEMBLY_precomputed` and writes
   `05_POLISH`; step 6 then reads the participant's own `05_POLISH` and
   `02_QC_precomputed`. This keeps each chain consistent. A comment line
   above the command says which inputs are precomputed. If a needed input
   folder does not exist, they say which step to run first (or to use
   `results-for`). Consequence: after `results-for`, commands copied from a
   printed handout (which use the participants' own folders) no longer work
   as they are; participants should use `show-cmd`.
7. **Commands are what participants type**, not `pipeline.sh` internals: no
   `bash -c`/`/usr/bin/time` wrappers, concrete file names
   (`01_DATA/sample_R1.fq.gz`), the thread count from the machine
   configuration, database paths as the environment variables set by pixi
   (`$CHECKM2DB`, ...). Step 12 shows the command for a named MAG instead
   of the `awk` one-liner: the best bin (completeness − 5 × contamination)
   in the CheckM2 report that step 12 reads (own or precomputed), filled in
   by `metag-ws` (and the same in `_run-all`, whose bins may be named
   differently). `explain-cmd` explains how to choose it from that report.
   eggNOG-mapper is in its own pixi environment, and step 12 shows this
   instead of hiding it (a chance to show `pixi run -e`): `pixi run -e
   eggnog emapper.py ...`, which works from `~/workshop` because pixi finds
   the project through `$PIXI_PROJECT_MANIFEST` (set by the activation). On
   the AWS machine, check that it works for participants with the shared,
   read-only installation (otherwise add `--as-is`, which never installs).
   Step 11 does not write `all_bins.faa` (nothing uses it; one loop line less).
8. **"Get data" (step 1)**: for now, copy the reads from the shared data
   directory into `01_DATA/` (`cp $METAG_WS_DATA/*.fq.gz 01_DATA/`).
   The workshop dataset is 1.2 GB (`sample_R1.fq.gz` 91 MB,
   `sample_R2.fq.gz` 94 MB, `sample_ont.fq.gz` 1.0 GB). **Placeholder:** make
   it public (e.g., Zenodo, citing the original study) and download it from
   there instead.

### Implementation

1. **Package** `metag-ws/` (own `pyproject.toml`, `[project.scripts]
   metag-ws = "metag_ws.cli:main"`), installed into the default pixi
   environment with `[pypi-dependencies] metag-ws = { path = "./metag-ws",
   editable = true }`. Dependencies: Python stdlib (`argparse`, `tomllib`,
   `json`, `shutil`) plus `rich` for the menu highlighting and
   `explain-cmd` formatting. Plain numbered prompt (no full-screen TUI) so it
   works in any SSH terminal and in Jupyter/VS Code terminals.
2. **Step definitions** in one data file, `metag_ws/steps.toml`: for each
   step its number, title, command(s), per-argument explanations
   (`explain-cmd`), the outputs (paths relative to the working directory, as
   in `outputs_of` in `pipeline.sh`), and what to look at in the outputs (a
   line or two, shown after `show-cmd`/`explain-cmd`).
3. **`show-cmd`**: prints the command(s) ready to copy: plain text, with
   no box or prompt characters that would break copy-paste.
4. **`explain-cmd`**: the command, then each argument with its explanation
   (e.g., `--environment soil` → pretrained model, why not training;
   `bwa mem -a` → all alignments, needed by polypolish; `-l 1000` →
   minimum read length).
5. **`results-for`**: creates the `_precomputed` symlinks, prints the note,
   updates the state file. It does not ask for confirmation, since it
   does not overwrite anything; if a `_precomputed` symlink already exists
   it is left as it is.
6. **Configuration**: shared data and precomputed directories, the working
   directory and the thread count from environment variables, with defaults
   for the AWS machine, set through `pixi.toml` (`[activation.env]` or a
   separate feature for the AWS machine).
7. **Hidden `metag-ws _run-all`** (not listed in `--help`), for testing and
   for generating the precomputed results:

   ```
   metag-ws _run-all -o DIR [--data DIR] [-t THREADS] [--until STEP]
   ```

   It runs the commands of all steps, in order, into `DIR`, using exactly
   what `show-cmd` prints (same code path, with all inputs from `DIR`'s own
   folders; it ignores and does not change the user's state file). `--data`
   points step 1 at other reads (e.g., the simulated `data-prep/tests/sim/`). Like
   `pipeline.sh`, it records finished steps (`DIR/.done/`) so a killed run
   can be resumed, writes `DIR/timings.tsv` (seconds and peak RAM per
   step), and stops at the first failing command. Run it as a queue job
   (`mqsub -t 16 -m 64 -- metag-ws _run-all ...`).
8. **Precomputed bundle**, in the new folder layout:
   `metag-ws _run-all -o precomputed --data subsets/9ca3c728/workshop_data`,
   then `data-prep/scripts/make_precomputed.sh` removes what participants do not
   need: `.done/`, myloasm's intermediates (`binary_temp/`, `0-`–`3-*/`,
   ~1 GB; keep `assembly_primary.fa`, the graphs and the log) and
   polypolish's `filtered_*.sam` (1.2 GB). Keep `aln_R{1,2}.sam` (1.2 GB),
   needed to run 5.2 after `results-for 5.1`. This run also checks that the
   commands participants see work, and gives new timings (data-prep/TIMING.md), since
   the commands now differ a little from `pipeline.sh` (which keeps its
   layout: the full-data run and the dataset scripts depend on it).
9. **Docs**: participant-facing usage (`metag-ws --help` and the workshop
   notes, `materials/metagenomics-workshop.md`, which build the slides and
   the handouts; `pixi run check-commands` checks that their commands are
   those of `steps.toml`); instructor notes on the AWS machine.
10. **Tests: later.** To cover: the commands in `steps.toml` match the
    validated ones in `pipeline.sh`; `_run-all` on the simulated data
    (`data-prep/tests/sim/`) finishes and produces every step's outputs;
    `results-for` each step in a fresh directory, and `show-cmd` then picks
    the right input folders; the state file (highlight, default = next
    step).

### The AWS machine

One large machine shared by all participants, each with their own user
account; data, software, databases and precomputed results in shared
read-only paths (e.g., `/opt/metag-ws/{data,precomputed,db}`), each user's
work in their home directory.

1. **Size**: the 24.8 min was measured with 16 threads / 64 GB for one run
   (peak RAM per step ≤ 8.8 GB). With many participants running at once,
   choose CPUs and the per-user thread count (`METAG_WS_THREADS`) together:
   e.g., 30 participants × 8 threads ≈ 240 vCPUs if all run the same step at
   the same time (they will not all do so, and `results-for` lets slow
   participants skip ahead). Time a few simultaneous runs on the chosen
   instance type and update data-prep/TIMING.md.
2. **Databases** on fast local disk (≈ 77 GB: eggNOG 51 GB, GUNC 13.5 GB,
   SingleM 9.7 GB, CheckM2 3.1 GB; more with CheckM2 DB v3). On a shared
   machine they stay in the page cache once the first user has read them, if
   there is enough RAM: plan RAM for the databases (≈ 36 GB of DIAMOND/SingleM
   files actually read) plus the users' jobs. Make the database paths in
   `pixi.toml` configurable instead of the aqua paths, and add a setup script
   that downloads them (`singlem data`, `checkm2 database --download`,
   `gunc download_db`, `download_eggnog_data.py`); this is machine setup, not
   part of the workshop.
3. **Software**: one shared `pixi install --frozen --all` (the `eggnog`
   environment too), and `metag-ws` and the tools on every user's `PATH`
   (e.g., activation in `/etc/profile.d/`).
4. **Users**: one account per participant (created from a list); home
   directories need ≈ 5 GB each for a full own run (nothing extra for
   `results-for`, which only creates symlinks).
5. Build it once as an AMI (e.g., with a provisioning script in
   `data-prep/scripts/aws/`), so it can be relaunched for each workshop.

### Open questions

* Number of participants (sets the instance size and the threads per user).
* Is `explain-cmd` also the place for interpreting the results (what to look
  for in the QC report, CheckM2 thresholds), or only the arguments?
