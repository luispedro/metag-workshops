# The workshop materials: one markdown source, built by pandoc into a
# reveal.js deck and student/instructor handouts (PDF and HTML). The build
# rules are in common/workshop.mk. From the repository root:
#   pixi run -e docs materials
SRC         := metagenomics-workshop.md
STEM        := metag-workshop
WORKSHOP    := Metagenomics
STUDENT_SUB := Hands-on workshop — notes
INSTR_SUB   := Hands-on workshop — instructor notes
# GitHub Pages (site.sh): one workshop, so its files go at the top of the site
SITE        ?= build/site
SITE_DIR    ?= $(SITE)

include common/workshop.mk
