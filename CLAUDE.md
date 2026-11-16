# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Material for a hands-on metagenomics workshop (ONT long reads + Illumina short
reads, one urban soil sample). Three parts that must stay consistent:

- `materials/metagenomics-workshop.md`: the single markdown source for the
  reveal.js deck and the student/instructor handouts (pandoc).
- `metag-ws/`: the `metag-ws` helper participants use on the workshop machine
  (`show-cmd`, `explain-cmd`, `results-for`, plus hidden `_run-all`).
- `data-prep/`: how the reduced dataset and the precomputed results were built
  (Jug task graph submitted with jug_hpc; not needed to run the workshop).

`GOALS.md` states what the workshop should cover; `PLAN.md` is the design and
current status (read it before changing `metag-ws` behaviour; update its
status when finishing work it lists).

## Commands

All software comes from pixi (`pixi install --all`). Environments: default
(bioinformatics tools + `metag-ws`, editable), `eggnog` and `gtdbtk` (each
separate because of dependency conflicts; used as `pixi run -e eggnog
emapper.py ...`), and `docs` (pandoc, tectonic, graphviz, matplotlib).

```bash
pixi run -e docs materials           # deck + handouts into materials/build/
pixi run -e docs make -C materials slides   # single target: slides, handouts, html, slides-pdf, docx, clean
pixi run -e docs check-materials     # fail if instructor notes leak into the student handout
pixi run check-commands              # every metag-ws command appears verbatim in the notes
pixi run -e docs site                # GitHub Pages site into materials/build/site/
pixi run metag-ws show-cmd 5.2       # print a step's command (no menu when a step is given)
```

First docs build needs network (tectonic fetches LaTeX packages, the deck
fetches reveal.js). CI (`.github/workflows/pages.yml`) runs `check-materials`
then `site` on every push to `main`, with only the `docs` environment.

There is no unit test suite. End-to-end tests run on the HPC queue
(`data-prep/tests/run_all_sim.sh`, `pixi run submit-test`); databases are at
`/work/microbiome/db/...` (paths in `pixi.toml` `[activation.env]`), so real
tool runs only work on that cluster.

## Architecture

### Commands live in one place: `metag-ws/metag_ws/steps.toml`

Each `[[step]]` has an id (`"5"` = step with its own folder, `"5.1"` = substep
sharing the parent's folder), commands (`[[step.cmd]]` with `run` and
per-argument `explain`), `outputs`, and `look_at`. Placeholders: `{2.1}` is the
folder holding step 2.1's outputs (own `02_QC` or `02_QC_precomputed` after
`results-for`), `{threads}`, `{threads_fastp}`, `{data}`. Shell variables are
written `$NAME`, not `${NAME}`. `results_only = true` marks steps shown but not
run (step 13, GTDB-Tk, ~130 GB RAM).

To change a command: edit `steps.toml`, then the matching ```` ```bash ````
block in the notes, then `pixi run check-commands`. `materials/check_commands.py`
renders every command with 8 threads and no precomputed inputs (via
`metag_ws.cli.Renderer`) and requires it verbatim as a ```` ```bash ```` (or
```` ```{.bash .no-cue} ```` for results-only) block.

Invariants the design relies on (reasons in PLAN.md, "`metag-ws`: design decisions"):
- Each step writes only into its own zero-padded folder (`01_DATA` …
  `13_GTDBTK`) and reads only from earlier ones; this is what makes
  `results-for` safe (it only creates `NN_STEP_precomputed` symlinks to the
  shared read-only copy, for all steps ≤ N, and records `precomputed_upto` in
  `$XDG_STATE_HOME/metag-ws/state.json`).
- Commands are exactly what participants type: concrete file names, database
  paths as env vars (`$CHECKM2DB`, ...), no wrappers.
- `_run-all` uses the same rendering path as `show-cmd`; it produces the
  precomputed results (`data-prep/scripts/run_precomputed.sh`) and the
  end-to-end test.

### Workshop notes (`materials/`)

Build machinery in `materials/common/` (make rules in `workshop.mk`, Lua
filters, styles) is copied from the vibe-workshops repo. Markup conventions:
- `#` starts a part (section slide); each `##` is exactly one slide.
- Unmarked content goes everywhere; `::: handout` handouts only;
  `::: instructor` instructor handout + speaker notes (never student handout);
  `::: slides` deck only. Boxes: `::: remember`, `::: aside`, `::: reference`.
- ```` ```bash ```` = "type this" with copy button; output blocks use
  ```` ```{.no-cue} ````.
- Slides are auto-badged hands-on/lecture; override with `{.handson}`,
  `{.lecture}`, or `{.no-tag}` on the `##` heading.
- Diagrams as ```` ```dot ```` blocks (Graphviz), never ASCII art.
- Figures: `media/NAME.py` scripts take the output path as argument and are
  built to `build/media/NAME.{svg,pdf,png}`; static `media/NAME.svg` are
  converted with rsvg-convert. Reference both as `![](media/NAME)` (no
  extension). Stepped deck figures (e.g. `checkm2_complete.svg`) are produced
  by the same script, picking the variant from the output filename; they need
  explicit rules in `materials/Makefile`. `checkm2.py`, `gunc.py`,
  `annotation.py` import their style from `checkm1.py`.

The untracked `2026-10-15__*.pptx` decks at the root are older lecture decks
used as sources when redrawing slides; they are not part of the build.

## Conventions

Commit messages start with `ENH`, `MIN` or `DOC` followed by a short summary
(e.g. `ENH Step 13: taxonomy of the bins with GTDB-Tk (results only)`), with
a body explaining the why for larger changes.
