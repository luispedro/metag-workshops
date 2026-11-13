---
title: "Metagenomics with Long and Short Reads"
subtitle: "From reads to annotated draft genomes"
author:
  - "[Luis Pedro Coelho](https://luispedro.org)"
  - "[Ben Woodcroft](https://www.qut.edu.au/about/our-people/academic-profiles/b.woodcroft)"
date: "2026"
---

::: handout
These notes have every command of the workshop. The same commands, adapted
to where you are in the workshop, are also available on the workshop machine
through `metag-ws` (see [Your helper: `metag-ws`](#your-helper-metag-ws)).

Feedback, corrections and questions are very welcome: email
<luis@luispedro.org>.
:::

::: instructor
**Draft.** So far this source has the commands of every step and how to use
`metag-ws`. Background slides for each step (what the tool does, why, and how
to read its results) are still to be written: see the TODO notes.

The commands are what `metag-ws show-cmd` prints in a fresh `~/workshop`
with `METAG_WS_THREADS=8`. They come from `metag-ws/metag_ws/steps.toml`:
change them there first, then here.
:::

# Overview

## What we will do

```{.dot width=95%}
digraph pipeline {
  rankdir=LR;
  node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=11,
        fillcolor="#eceff1", color="#37474f"];
  edge [color="#37474f"];
  data   [label="1. Reads\nshort + long"];
  qc     [label="2. Read QC\nfastp / fastplong"];
  singlem[label="3. Profiling\nSingleM"];
  asm    [label="4. Assembly\nmyloasm"];
  polish [label="5. Polishing\nbwa + polypolish"];
  map    [label="6. Mapping\nbwa + samtools"];
  bin    [label="7. Binning\nSemiBin2"];
  checkm [label="8. CheckM2"];
  gunc   [label="9. GUNC"];
  appr   [label="10. SingleM\nappraise"];
  genes  [label="11. Genes\npyrodigal"];
  egg    [label="12. Annotation\neggNOG-mapper"];
  data -> qc -> singlem;
  qc -> asm -> polish -> map -> bin;
  bin -> checkm; bin -> gunc; bin -> appr; singlem -> appr;
  bin -> genes -> egg;
}
```

::: handout
The assembly is based on the long reads (Oxford Nanopore), and the short reads
(Illumina) are used to correct (polish) the assembly and to estimate the
coverage of each contig for binning.


:::

## Learning goals

At the end of the workshop, you should be able to

- read QC reports and decide whether the data are fit for use
- interpret a taxonomic profile, and compare short- and long-read profiles
- go from reads to bins (draft genomes): assembly, polishing, binning
- say which bins are high quality, medium quality or unusable, and why
- find a function of interest in an annotated genome

::: instructor
TODO: a slide or two of background on metagenomics, short vs. long reads,
and what a bin (MAG) is.
:::

## The data

One urban soil sample, sequenced with both Illumina (short reads) and Oxford
Nanopore (long reads):

> Duan Y, Cuscó A, Zhang Y, Inda-Díaz JS, Zhu C, Areias Castro A, Yang X, Yu J,
> Jiang G, Zhao X-M, Coelho LP. *Long-read metagenomic sequencing reveals novel
> lineages and functional diversity in urban soil microbiome.* (2026)
> doi:[10.64898/2026.03.20.713087](https://doi.org/10.64898/2026.03.20.713087)

::: handout
The full sample is ~20 GB of short reads and ~70 GB of long reads. Processing
it takes 38.5 hours (using multiple threads) and >512 GB of RAM.

We use a reduced version (1.2 GB) that keeps the reads of a few genomes that
assemble well, plus a small random fraction of the rest. The commands are
exactly those you would run on the full data, but they finish in minutes!

The price is that the dataset no longer represents the original sample: the
few selected genomes are much more abundant, relative to everything else, than
they were in the soil. **No conclusions about the soil microbiome can be drawn
from this dataset!**
:::

# Working on the workshop machine

## Getting started

Log in to the workshop machine, then make your workshop folder and go into it:

```bash
mkdir -p ~/workshop
cd ~/workshop
```

All the tools are already installed, as are the databases they need. Check
that it works:

```bash
metag-ws --help
```

::: instructor
TODO: how participants log in (machine name, user names, passwords or keys),
and how the environment is activated for them (PLAN.md, "The AWS machine").
:::

::: remember
Run all the commands in `~/workshop`. Every path in the commands is relative
to it.
:::

## Your folder

Each step has its own numbered folder:

```{.no-cue}
01_DATA     02_QC        03_SINGLEM   04_ASSEMBLY
05_POLISH   06_MAPPING   07_BINNING   08_CHECKM2
09_GUNC     10_APPRAISE  11_GENES     12_EGGNOG
```

::: handout
Each step writes only into its own folder and reads from the folders of
earlier steps. The numbers make `ls` list them in the order of the workshop.
Substeps (e.g., 2.1 and 2.2, the short- and long-read QC) share their step's
folder.
:::

## Your helper: `metag-ws`

```bash
metag-ws show-cmd
```

```bash
metag-ws explain-cmd
```

```bash
metag-ws results-for
```

::: handout
- `show-cmd` prints the commands of a step, ready to copy and paste.
- `explain-cmd` prints the same commands with every argument explained, and
  what to look at in the results.
- `results-for` brings in our precomputed results, up to the step you choose
  (see the next slide).

Without a step, each of them shows a menu of the steps: the step you used last
is highlighted, and pressing Enter selects the **next** one, so as you go
through the workshop you can mostly just press Enter. Steps you have finished
are marked `done`.

You can also give the step directly: a whole step (`metag-ws show-cmd 5`) or
a substep (`metag-ws show-cmd 5.2`).

The lines starting with `#` in the output of `show-cmd` are comments: they
are harmless if you paste them along with the commands.
:::

## Falling behind? `results-for`

```bash
metag-ws results-for 4
```

- Brings in our results of steps 1 to 4, as `01_DATA_precomputed`, …,
  `04_ASSEMBLY_precomputed`
- Your own folders are never changed
- From then on, `metag-ws show-cmd` uses them as inputs

::: handout
Use it when a step fails, or takes too long, or for any reason at all: you can
then continue from the next step with everyone else.

It always brings in all the steps up to the one you choose, not only that
step. Results from different runs do not mix well: contig names, bin names and
the number of bins differ between runs, so, e.g., our mapping of the reads
would not match your own assembly.

Our results may differ a little from yours, even when you ran exactly the same
commands, for the same reason.
:::

::: remember
After `results-for`, the commands in these notes (which use your own folders)
no longer match: take them from `metag-ws show-cmd` instead.
:::

## Conventions

- The commands use **8 threads** (`-t 8`, `--threads 8`, …): the machine is
  shared, so please do not raise it
- Long commands are split over several lines with `\`: paste the whole block
  at once
- Databases are given by environment variables, already set for you:
  `$CHECKM2DB`, `$GUNC_DB`, `$EGGNOG_DATA_DIR` (SingleM finds its own)

::: handout
The slowest steps take several minutes each: SingleM on the long reads (3.2),
assembly (4), GUNC (9) and eggNOG-mapper (12). While they run, read the
explanations (`metag-ws explain-cmd`) or look at the results of the previous
step in a second terminal. Altogether, the commands take about half an hour of
computer time.
:::

## Looking at HTML reports

Some tools write their reports as HTML pages (`fastp.html`, the SingleM Krona
charts). Copy them to your laptop and open them in a browser:

```bash
scp USER@WORKSHOP_MACHINE:workshop/02_QC/fastp.html .
```

::: handout
Run this on your laptop, not on the workshop machine, with your user name and
the name of the workshop machine.
:::

::: instructor
TODO: depends on how participants access the machine (SSH, Jupyter, VS Code
remote, ...): with Jupyter or VS Code, they can open the HTML files directly.
:::

# Step 1: Get data

## Copy the reads

```bash
mkdir -p 01_DATA
cp /opt/metag-ws/data/sample_*.fq.gz 01_DATA/
```

- Short reads (Illumina, paired-end): `sample_R1.fq.gz`, `sample_R2.fq.gz`
- Long reads (Oxford Nanopore): `sample_ont.fq.gz`

## Look at the reads

```bash
zcat 01_DATA/sample_R1.fq.gz | head -8
```

```bash
seqkit stats 01_DATA/*.fq.gz
```

::: instructor
TODO: FASTQ format; how many reads and bases of each kind; read lengths.
:::

# Step 2: Read quality control

## 2.1: Short reads (fastp)

```bash
mkdir -p 02_QC
fastp \
    -i 01_DATA/sample_R1.fq.gz -I 01_DATA/sample_R2.fq.gz \
    -o 02_QC/sr_R1.fq.gz -O 02_QC/sr_R2.fq.gz \
    -h 02_QC/fastp.html -j 02_QC/fastp.json \
    -w 8
```

Look at `02_QC/fastp.html`:

- How many reads and bases passed the filters?
- Quality per position (before and after filtering), adapter content,
  duplication rate, insert size

## 2.2: Long reads (fastplong)

```bash
mkdir -p 02_QC
fastplong \
    -i 01_DATA/sample_ont.fq.gz -o 02_QC/lr.fq.gz \
    -l 1000 \
    -h 02_QC/fastplong.html -j 02_QC/fastplong.json \
    -w 8
```

Look at `02_QC/fastplong.html`:

- Read length distribution (and N50), read quality
- How many reads and bases were removed?
- Compare the number of bases with the short reads

::: instructor
TODO: background on fastp/fastplong and how to decide whether the data are
fit for use.
:::

# Step 3: Read-based taxonomic profiling (SingleM)

## 3.1: Short reads

```bash
mkdir -p 03_SINGLEM
singlem pipe \
    -1 02_QC/sr_R1.fq.gz -2 02_QC/sr_R2.fq.gz \
    --otu-table 03_SINGLEM/sr.otu.tsv \
    -p 03_SINGLEM/sr.profile.tsv \
    --taxonomic-profile-krona 03_SINGLEM/sr.profile.html \
    --threads 8
```

Look at `03_SINGLEM/sr.profile.html` (Krona: click to zoom in):

- Which phyla and genera dominate?
- How much is classified only at a high level (e.g., phylum)?

::: handout
`03_SINGLEM/sr.profile.tsv` has the same profile as a table (coverage per
taxon).
:::

## 3.2: Long reads

```bash
mkdir -p 03_SINGLEM
singlem pipe \
    -1 02_QC/lr.fq.gz \
    --otu-table 03_SINGLEM/lr.otu.tsv \
    -p 03_SINGLEM/lr.profile.tsv \
    --taxonomic-profile-krona 03_SINGLEM/lr.profile.html \
    --threads 8
```

Compare the long-read profile, `03_SINGLEM/lr.profile.html`, with the
short-read one, `03_SINGLEM/sr.profile.html`:

- Do the two technologies see the same taxa, in similar proportions?
- Which differences could come from the technology, and which from the amount
  of data?

::: instructor
TODO: background on SingleM (marker genes, OTU tables, GTDB), and why a
read-based profile sees organisms that assembly misses.
:::

# Step 4: Long-read assembly (myloasm)

## Assemble the long reads

```bash
myloasm 02_QC/lr.fq.gz -o 04_ASSEMBLY -t 8
```

::: handout
`myloasm` creates the folder `04_ASSEMBLY` itself. Only the long reads are
used for assembly; the short reads come in at the next step.
:::

## Look at the assembly

The contigs are in `04_ASSEMBLY/assembly_primary.fa`. Their number and
lengths:

```bash
seqkit stats -a 04_ASSEMBLY/assembly_primary.fa
```

The contig names say whether a contig is circular (a complete chromosome or
plasmid?) and its depth:

```bash
grep -c circular-yes 04_ASSEMBLY/assembly_primary.fa
```

::: instructor
TODO: background on long-read metagenome assembly; N50; what circular
contigs mean.
:::

# Step 5: Polishing with short reads

## 5.1: Map the short reads to the draft

Index the draft assembly:

```bash
mkdir -p 05_POLISH
bwa index -p 05_POLISH/draft 04_ASSEMBLY/assembly_primary.fa
```

Map each read end separately, keeping all alignments (`-a`):

```bash
bwa mem -t 8 -a 05_POLISH/draft 02_QC/sr_R1.fq.gz > 05_POLISH/aln_R1.sam
bwa mem -t 8 -a 05_POLISH/draft 02_QC/sr_R2.fq.gz > 05_POLISH/aln_R2.sam
```

## Look at the alignments

SAM files are text:

```bash
grep -v '^@' 05_POLISH/aln_R1.sam | head
```

With `-a`, a read can have several alignments (flag 256 = secondary).

## 5.2: Polish (polypolish)

Filter the alignments, using the read pairs:

```bash
mkdir -p 05_POLISH
polypolish filter \
    --in1 05_POLISH/aln_R1.sam --in2 05_POLISH/aln_R2.sam \
    --out1 05_POLISH/filtered_R1.sam --out2 05_POLISH/filtered_R2.sam
```

Polish:

```bash
polypolish polish 04_ASSEMBLY/assembly_primary.fa \
    05_POLISH/filtered_R1.sam 05_POLISH/filtered_R2.sam > 05_POLISH/polished.fa
```

::: handout
polypolish reports (on the screen) how many positions it changed. Few changes
mean that the long-read assembly was already accurate. The polished assembly,
`05_POLISH/polished.fa`, has the same contigs, with corrected bases.

Generally, expect a relatively small number of changes, but they can have a
large effect on the predicted proteins especially if they fix frameshifts.
:::

::: instructor
TODO: why polish (error profile of Nanopore reads), and why polypolish needs
all alignments (repeats).
:::

# Step 6: Map reads to the polished assembly

## Map the short reads, as pairs

```bash
mkdir -p 06_MAPPING
bwa index -p 06_MAPPING/polished 05_POLISH/polished.fa
```

```bash
bwa mem -t 8 06_MAPPING/polished 02_QC/sr_R1.fq.gz 02_QC/sr_R2.fq.gz \
    | samtools sort -@ 8 -o 06_MAPPING/sr.sorted.bam
```

```bash
samtools index 06_MAPPING/sr.sorted.bam
```

## Look at the mapping

What fraction of the reads maps to the assembly?

```bash
samtools flagstat 06_MAPPING/sr.sorted.bam
```

Coverage per contig:

```bash
samtools coverage 06_MAPPING/sr.sorted.bam | head
```

::: handout
Reads that do not map come from organisms (or parts of genomes) that were not
assembled.
:::

# Step 7: Binning (SemiBin2)

## Bin the contigs

```bash
SemiBin2 single_easy_bin \
    -i 05_POLISH/polished.fa \
    -b 06_MAPPING/sr.sorted.bam \
    --environment soil \
    --sequencing-type long_read \
    --compression none \
    -o 07_BINNING \
    -t 8
```

::: handout
`--environment soil` uses a model pretrained on soil samples instead of
training one on this sample, which would be slower.
:::

## Look at the bins

Each bin is a FASTA file in `07_BINNING/output_bins/`.

- How many bins are there, and how large are they?
- `07_BINNING/bins_info.tsv`: size, number of contigs, N50

```bash
seqkit stats 07_BINNING/output_bins/*.fa
```

::: instructor
TODO: background on binning (composition + coverage); what SemiBin2 does.
:::

# Step 8: Completeness and contamination (CheckM2)

## Run CheckM2

```bash
checkm2 predict \
    -i 07_BINNING/output_bins -x fa \
    -o 08_CHECKM2 \
    --database_path $CHECKM2DB \
    -t 8 --force
```

## Look at the quality report

`08_CHECKM2/quality_report.tsv`: completeness and contamination of each bin.

```bash
sort -t$'\t' -k2,2gr 08_CHECKM2/quality_report.tsv | cut -f1-3 | column -t
```

Common thresholds (MIMAG):

- **high quality**: >90% complete, <5% contaminated
- **medium quality**: ≥50% complete, <10% contaminated

Which of your bins are high quality?

# Step 9: Chimerism (GUNC)

## Run GUNC

```bash
mkdir -p 09_GUNC
gunc run \
    -d 07_BINNING/output_bins -e .fa \
    -r $GUNC_DB \
    -o 09_GUNC --temp_dir 09_GUNC \
    -t 8
```

## Look at the GUNC results

```bash
cut -f1,2,8,9,13 09_GUNC/GUNC.progenomes_2.1.maxCSS_level.tsv | column -t
```

- `pass.GUNC`: whether the bin passes
- `clade_separation_score` (CSS) above 0.45: genes from different lineages
  were mixed (a chimera)

Do the bins that CheckM2 calls high quality pass GUNC?

::: instructor
TODO: what chimerism is, and why CheckM2 can miss it.
:::

# Step 10: What did the bins capture? (SingleM appraise)

## Marker genes in the bins

```bash
mkdir -p 10_APPRAISE
singlem pipe \
    --genome-fasta-files 07_BINNING/output_bins/*.fa \
    --otu-table 10_APPRAISE/bins.otu.tsv \
    -p 10_APPRAISE/bins.profile.tsv \
    --threads 8
```

## Compare reads and bins

```bash
singlem appraise \
    --metagenome-otu-tables 03_SINGLEM/sr.otu.tsv \
    --genome-otu-tables 10_APPRAISE/bins.otu.tsv \
    --output-unaccounted-for-otu-table 10_APPRAISE/appraise_sr.unaccounted.tsv \
    > 10_APPRAISE/appraise_sr.txt
singlem appraise \
    --metagenome-otu-tables 03_SINGLEM/lr.otu.tsv \
    --genome-otu-tables 10_APPRAISE/bins.otu.tsv \
    --output-unaccounted-for-otu-table 10_APPRAISE/appraise_lr.unaccounted.tsv \
    > 10_APPRAISE/appraise_lr.txt
```

## Look at the appraisal

- `10_APPRAISE/appraise_sr.txt`: `percent_binned` is the fraction of the
  marker-gene coverage in the reads that is in the bins
- `10_APPRAISE/appraise_sr.unaccounted.tsv`: what is in the reads but in no
  bin. Which taxa are missing, and why (abundance)?
- Compare with the long reads (`appraise_lr.*`)

# Step 11: Gene prediction (pyrodigal)

## Predict genes in each bin

```bash
mkdir -p 11_GENES
for fa in 07_BINNING/output_bins/*.fa; do
    b=$(basename $fa .fa)
    pyrodigal -i $fa -a 11_GENES/$b.faa -d 11_GENES/$b.fna -o 11_GENES/$b.gff
done
```

::: handout
A shell loop: the commands inside run once per bin. For each bin `BIN`, the
outputs are `11_GENES/BIN.faa` (proteins), `BIN.fna` (genes, DNA) and
`BIN.gff` (coordinates).
:::

## Look at the genes

How many genes per bin?

```bash
grep -c '>' 11_GENES/*.faa
```

Do larger bins have more genes? About how many genes per Mbp?

# Step 12: Functional annotation (eggNOG-mapper)

## Annotate one bin

Annotating all bins takes too long, so pick one: a bin with high completeness
and low contamination in `08_CHECKM2/quality_report.tsv`.

```bash
mkdir -p 12_EGGNOG
pixi run -e eggnog emapper.py \
    -i 11_GENES/BIN_NAME.faa --itype proteins \
    -m diamond \
    --data_dir $EGGNOG_DATA_DIR \
    -o BIN_NAME --output_dir 12_EGGNOG \
    --temp_dir 12_EGGNOG \
    --cpu 8 --override
```

Replace `BIN_NAME` (twice) with the name of your bin, e.g. `SemiBin_2`.

::: handout
`metag-ws show-cmd 12` fills in the best bin for you (by completeness − 5 ×
contamination).

eggNOG-mapper is installed in its own environment (`eggnog`), because it
needs a different version of one of its dependencies (DIAMOND) than GUNC.
`pixi run -e eggnog` runs a command in that environment.
:::

## Look at the annotations

`12_EGGNOG/BIN_NAME.emapper.annotations`: one line per protein, with its gene
name (`Preferred_name`), description, COG category, KEGG orthologs and
pathways, CAZy families, …

Look for a function:

```bash
grep -i nitrogenase 12_EGGNOG/BIN_NAME.emapper.annotations | cut -f1,8,9
```

- How many proteins have an annotation?
- Which COG categories are the most common?

::: instructor
TODO: background on orthology-based annotation, and an exercise looking for
a function across bins.
:::

# Wrap-up

## What we did

From short and long reads of one soil sample to quality-checked, annotated
draft genomes:

QC → profiling → assembly → polishing → mapping → binning → quality checks →
gene prediction → annotation

::: instructor
TODO: what changes on real (full-size) data: runtimes and resources, and
downloading the databases.
:::
