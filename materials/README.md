# Workshop materials

One markdown source, [`metagenomics-workshop.md`](metagenomics-workshop.md),
from which pandoc builds

- a **reveal.js slide deck** (self-contained HTML; press `s` for speaker notes),
- a **student handout** (PDF and HTML, with a copy button on every command), and
- an **instructor handout** (PDF and HTML), with the teaching notes.

From the repository root:

```bash
pixi run -e docs materials           # everything, into materials/build/
pixi run -e docs check-materials     # fail if instructor notes leaked into the student handout
pixi run check-commands              # every metag-ws command is in the notes, verbatim
pixi run -e docs site                # the GitHub Pages site (site.sh), in materials/build/site/
```

The site (an index page, the deck and the handouts) is published to
<https://luispedro.github.io/metag-workshops/> on every push to `main`
(`../.github/workflows/pages.yml`).

or, for a single target, `pixi run -e docs make -C materials slides`
(`handouts`, `html`, `slides-pdf`, `docx`, `clean`). The first build needs
network: tectonic fetches LaTeX packages and the deck fetches reveal.js.

The build machinery (`common/`: make rules, pandoc filters, styles) is copied
from [vibe-workshops](https://github.com/luispedro/vibe-workshops), which
documents it in full (its `CLAUDE.md`). In short:

- `#` starts a part (a section slide), `##` is exactly one slide.
- Unmarked content goes everywhere; `::: handout` only in the handouts;
  `::: instructor` in the instructor handout and as speaker notes (never in the
  student handout: `check-materials`); `::: slides` only on the slides.
- ```` ```bash ```` blocks are shown as *type this in the shell*, with a copy
  button; output blocks opt out with ```` ```{.no-cue} ````.
- `::: remember`, `::: aside`, `::: reference` boxes.
- Diagrams as ```` ```dot ```` blocks (Graphviz), not ASCII.

The commands in the notes are those that `metag-ws show-cmd` prints (8
threads, no precomputed results). They are defined in
`../metag-ws/metag_ws/steps.toml`: change them there, then in the notes, and
run `pixi run check-commands`.
