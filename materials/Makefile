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

# media/checkm1.py, checkm2.py, gunc.py and annotation.py also draw the steps
# the deck goes through, one figure per step, picked by the output name (their
# handout figures, checkm1, checkm2, gunc and annotation, are built by the
# usual figure-script rules).
CHECKM1_STEPS := $(foreach s,markers complete incomplete contaminated,$(BUILD)/media/checkm1_$(s).svg)
CHECKM2_STEPS := $(foreach s,complete incomplete contaminated,$(BUILD)/media/checkm2_$(s).svg)
GUNC_STEPS    := $(foreach s,spread chimeric,$(BUILD)/media/gunc_$(s).svg)
ANNOT_STEPS   := $(foreach s,genes database judgement,$(BUILD)/media/annotation_$(s).svg)
$(CHECKM1_STEPS): $(BUILD)/media/%.svg: media/checkm1.py
	@mkdir -p $(dir $@)
	$(PYTHON) $< $@
$(CHECKM2_STEPS): $(BUILD)/media/%.svg: media/checkm2.py
	@mkdir -p $(dir $@)
	$(PYTHON) $< $@
$(GUNC_STEPS): $(BUILD)/media/%.svg: media/gunc.py
	@mkdir -p $(dir $@)
	$(PYTHON) $< $@
$(ANNOT_STEPS): $(BUILD)/media/%.svg: media/annotation.py
	@mkdir -p $(dir $@)
	$(PYTHON) $< $@
$(BUILD)/$(STEM)__slides.html: $(CHECKM1_STEPS) $(CHECKM2_STEPS) $(GUNC_STEPS) $(ANNOT_STEPS)
# checkm2.py, gunc.py, annotation.py and binning_modes.py take their style
# from checkm1.py.
$(CHECKM2_STEPS) $(foreach f,svg pdf png,$(BUILD)/media/checkm2.$(f)): media/checkm1.py
$(GUNC_STEPS) $(foreach f,svg pdf png,$(BUILD)/media/gunc.$(f)): media/checkm1.py
$(ANNOT_STEPS) $(foreach f,svg pdf png,$(BUILD)/media/annotation.$(f)): media/checkm1.py
$(foreach f,svg pdf png,$(BUILD)/media/binning_modes.$(f)): media/checkm1.py
