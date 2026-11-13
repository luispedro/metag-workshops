#!/usr/bin/env bash
# Assemble the GitHub Pages site in materials/build/site/: the deck, the
# handouts (via `make site`) and an index page linking to them. Adapted from
# vibe-workshops (common/site.sh), which has several workshops; here there is
# one, so its files are at the top of the site.
#
#   pixi run -e docs site        # from the repo root
#
# .github/workflows/pages.yml runs this on every push to main.

set -euo pipefail

cd "$(dirname "$0")"
SITE=build/site
REPO=https://github.com/luispedro/metag-workshops

rm -rf "$SITE"
mkdir -p "$SITE"
make -s site SITE="$PWD/$SITE"

print_var() { make -s --eval='print-%: ; @echo $($*)' "print-$1"; }
src=$(print_var SRC)
stem=$(print_var STEM)

# Title and subtitle come from the source's YAML header.
tpl=$(mktemp)
trap 'rm -f "$tpl"' EXIT
echo '$title$' > "$tpl"
title=$(pandoc -t plain --template="$tpl" "$src")
echo '$subtitle$' > "$tpl"
subtitle=$(pandoc -t plain --template="$tpl" "$src")

{
  printf -- '---\ntitle: "%s"\nsubtitle: "%s. A hands-on workshop by [Luis Pedro Coelho](https://luispedro.org) and Ben Woodcroft"\n---\n\n' "$title" "$subtitle"
  printf 'Metagenomic data processing with long (Oxford Nanopore) and short (Illumina) reads: read QC, taxonomic profiling, hybrid assembly, binning, bin quality, gene prediction and functional annotation.\n\n'
  printf 'Source, and how to build it yourself: <%s>\n\n' "$REPO"

  printf '## Materials\n\n'
  if [ -f pre-workshop-checklist.md ]; then
    printf -- '- **Before the workshop:** [pre-workshop checklist](pre-workshop-checklist.html)\n'
  fi
  printf -- '- **Notes, with copy buttons:** [web](%s__student.html) · [PDF](%s__student.pdf)\n' "$stem" "$stem"
  printf -- '- **Slides:** [deck](%s__slides.html) (press `s` for speaker notes)\n' "$stem"
  printf -- '- **Instructor notes:** [web](%s__instructor.html) · [PDF](%s__instructor.pdf)\n\n' "$stem" "$stem"

  printf '## The data\n\n'
  printf 'A reduced version of one urban soil sample from\n\n'
  printf '> Duan Y, Cuscó A, Zhang Y, Inda-Díaz JS, Zhu C, Areias Castro A, Yang X, Yu J, Jiang G, Zhao X-M, Coelho LP. *Long-read metagenomic sequencing reveals novel lineages and functional diversity in urban soil microbiome.* (2026) doi:[10.64898/2026.03.20.713087](https://doi.org/10.64898/2026.03.20.713087)\n\n'

  printf '## Feedback\n\nFor feedback, please open an issue at <%s/issues> or [email Luis](mailto:luis@luispedro.org).\n' "$REPO"
} | pandoc -s -t html5 --embed-resources \
      --css=common/style/handout.css \
      --metadata pagetitle="$title" \
      -o "$SITE/index.html"

echo "Site assembled in materials/$SITE/"
