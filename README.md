# Metagenomics with long and short reads

Material for a hands-on workshop on metagenomic data processing, using both
long reads (Oxford Nanopore) and short reads (Illumina), by Luis Pedro Coelho
and Ben Woodcroft.

Starting from the reads of one urban soil sample, participants go through
read QC, read-based taxonomic profiling, hybrid assembly (long-read assembly,
polished with short reads), binning, bin quality checks, gene prediction and
functional annotation, running exactly the commands they would run on real
data. The dataset is a reduced version of the sample, so that every step
finishes in minutes.

| | |
|---|---|
| [`materials/`](materials/) | the workshop notes: one markdown file ([`metagenomics-workshop.md`](materials/metagenomics-workshop.md)) that builds the slides and the handouts |
| [`metag-ws/`](metag-ws/) | `metag-ws`, the helper available on the workshop machine: the commands of each step, what their arguments mean, and precomputed results to catch up |
| [`data-prep/`](data-prep/) | how the workshop dataset and the precomputed results were built (not needed for the workshop) |
| `pixi.toml` | the software: every tool used in the workshop, installed with [pixi](https://pixi.sh) |

## Attending?

The slides and notes, including a web version with a copy button on every
command, are at <https://luispedro.github.io/metag-workshops/>.

Everything (data, software, databases) is set up on the workshop machine:
you only need a laptop with an SSH client and a web browser, and to be
comfortable with the shell.

## The data

> Duan Y, Cuscó A, Zhang Y, Inda-Díaz JS, Zhu C, Areias Castro A, Yang X, Yu J,
> Jiang G, Zhao X-M, Coelho LP. *Long-read metagenomic sequencing reveals novel
> lineages and functional diversity in urban soil microbiome.* (2026)
> doi:[10.64898/2026.03.20.713087](https://doi.org/10.64898/2026.03.20.713087)

## Running it yourself

```bash
pixi install --all             # the tools (eggNOG-mapper is in its own environment)
pixi run metag-ws --help
```

The databases (SingleM metapackage, CheckM2, GUNC, eggNOG-mapper) are not part
of the installation; their paths are set in `pixi.toml` (`[activation.env]`).

## Building the notes

```bash
pixi run -e docs materials           # slides + student and instructor handouts
pixi run -e docs check-materials     # no instructor notes in the student handout
pixi run check-commands              # the notes match the commands of metag-ws
pixi run -e docs site                # the GitHub Pages site, in materials/build/site/
```

Outputs are in `materials/build/`. On every push to `main`,
`.github/workflows/pages.yml` publishes the site to
<https://luispedro.github.io/metag-workshops/>. See [`materials/README.md`](materials/README.md).
