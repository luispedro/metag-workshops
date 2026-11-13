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

Each step names the tools it uses, with links to their papers. [Tools and
references](#tools-and-references), at the end, lists them all, together with
alternatives.
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

::: handout
Tool: [SeqKit](https://bioinf.shenwei.me/seqkit/)
([Shen et al., 2016](https://doi.org/10.1371/journal.pone.0163962);
[Shen et al., 2024](https://doi.org/10.1002/imt2.191)).
:::

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

::: handout
Tool: [fastp](https://github.com/OpenGene/fastp)
([Chen et al., 2018](https://doi.org/10.1093/bioinformatics/bty560);
[Chen, 2023](https://doi.org/10.1002/imt2.107)).
:::

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

::: handout
Tool: [fastplong](https://github.com/OpenGene/fastplong), the long-read
version of fastp. It has no paper of its own: its authors ask that you cite
fastp.
:::

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

Tool: [SingleM](https://wwood.github.io/singlem/)
([Woodcroft et al., 2025](https://doi.org/10.1038/s41587-025-02738-1)). The
taxonomy is that of [GTDB](https://gtdb.ecogenomic.org)
([Parks et al., 2025](https://doi.org/10.1093/nar/gkaf1040)), and the charts
are drawn with [Krona](https://github.com/marbl/Krona)
([Ondov et al., 2011](https://doi.org/10.1186/1471-2105-12-385)).
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

Tool: [myloasm](https://github.com/bluenote-1577/myloasm)
([Shaw et al., 2026](https://doi.org/10.1038/s41587-026-03053-z)).
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

::: handout
Tool: [BWA](https://github.com/lh3/bwa) (`bwa mem`;
[Li & Durbin, 2009](https://doi.org/10.1093/bioinformatics/btp324);
[Li, 2013](https://arxiv.org/abs/1303.3997)).
:::

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

Tool: [Polypolish](https://github.com/rrwick/Polypolish)
([Wick & Holt, 2022](https://doi.org/10.1371/journal.pcbi.1009802);
`polypolish filter`: [Bouras et al., 2024](https://doi.org/10.1099/mgen.0.001254)).
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

::: handout
Tools: [BWA](https://github.com/lh3/bwa) (as in step 5) and
[SAMtools](https://www.htslib.org)
([Danecek et al., 2021](https://doi.org/10.1093/gigascience/giab008)).
:::

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

Tool: [SemiBin2](https://github.com/BigDataBiology/SemiBin)
([Pan et al., 2023](https://doi.org/10.1093/bioinformatics/btad209)).
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

::: handout
Tool: [CheckM2](https://github.com/chklovski/CheckM2)
([Chklovski et al., 2023](https://doi.org/10.1038/s41592-023-01940-w)).
:::

## Look at the quality report

`08_CHECKM2/quality_report.tsv`: completeness and contamination of each bin.

```bash
sort -t$'\t' -k2,2gr 08_CHECKM2/quality_report.tsv | cut -f1-3 | column -t
```

Common thresholds (MIMAG):

- **high quality**: >90% complete, <5% contaminated
- **medium quality**: ≥50% complete, <10% contaminated

Which of your bins are high quality?

::: handout
MIMAG is a community standard for reporting MAGs
([Bowers et al., 2017](https://doi.org/10.1038/nbt.3893)).
:::

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

::: handout
Tool: [GUNC](https://grp-bork.embl-community.io/gunc/)
([Orakov et al., 2021](https://doi.org/10.1186/s13059-021-02393-0)), with its
database built from [proGenomes 2.1](https://progenomes.embl.de)
([Mende et al., 2020](https://doi.org/10.1093/nar/gkz1002)).
:::

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

::: handout
Tool: [SingleM](https://wwood.github.io/singlem/) again (`pipe` and
`appraise`; [Woodcroft et al., 2025](https://doi.org/10.1038/s41587-025-02738-1)).
:::

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

Tool: [Pyrodigal](https://github.com/althonos/pyrodigal)
([Larralde, 2022](https://doi.org/10.21105/joss.04296)), Python bindings to
[Prodigal](https://github.com/hyattpd/Prodigal)
([Hyatt et al., 2010](https://doi.org/10.1186/1471-2105-11-119)).
:::

## Look at the genes

How many genes per bin?

```bash
grep -c '>' 11_GENES/*.faa
```

Do larger bins have more genes? About how many genes per Mbp?

# Step 12: Functional annotation (eggNOG-mapper)

## Annotate one bin

Annotating all bins takes too long, so we annotate one: the first command
picks the best bin in `08_CHECKM2/quality_report.tsv` (highest completeness −
5 × contamination).

```bash
BIN_NAME=$(awk -F'\t' 'NR > 1 { print $2 - 5 * $3, $1 }' 08_CHECKM2/quality_report.tsv \
    | sort -gr | head -n 1 | cut -d' ' -f2)
echo $BIN_NAME
mkdir -p 12_EGGNOG
pixi run -e eggnog emapper.py \
    -i 11_GENES/$BIN_NAME.faa --itype proteins \
    -m diamond \
    --data_dir $EGGNOG_DATA_DIR \
    -o $BIN_NAME --output_dir 12_EGGNOG \
    --temp_dir 12_EGGNOG \
    --cpu 8 --override
```

To annotate another bin, set the variable yourself instead, e.g.
`BIN_NAME=SemiBin_2`.

::: handout
`BIN_NAME=...` sets a shell variable; `$BIN_NAME` uses it. `$(...)` runs a
command and uses its output: here, `awk` computes the score of each bin,
`sort -gr` puts the highest first, and `head`/`cut` keep the name of the top
one. Shell variables are lost when you close the terminal: if you open a new
one, set `BIN_NAME` again before looking at the annotations.

eggNOG-mapper is installed in its own environment (`eggnog`), because it
needs a different version of one of its dependencies (DIAMOND) than GUNC.
`pixi run -e eggnog` runs a command in that environment.

Tool: [eggNOG-mapper](https://github.com/eggnogdb/eggnog-mapper)
([Cantalapiedra et al., 2021](https://doi.org/10.1093/molbev/msab293)), with the
[eggNOG 5](http://eggnog5.embl.de) database
([Huerta-Cepas et al., 2019](https://doi.org/10.1093/nar/gky1085)) and
[DIAMOND](https://github.com/bbuchfink/diamond)
([Buchfink et al., 2021](https://doi.org/10.1038/s41592-021-01101-x)).
:::

## Look at the annotations

`12_EGGNOG/$BIN_NAME.emapper.annotations`: one line per protein, with its gene
name (`Preferred_name`), description, COG category, KEGG orthologs and
pathways, CAZy families, …

Look for a function:

```bash
grep -i nitrogenase 12_EGGNOG/$BIN_NAME.emapper.annotations | cut -f1,8,9
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

# References

## Tools and references

::: slides
Every tool we used, with its paper, and alternatives to it: see the end of the
handout.
:::

::: handout
For each step, the tools we used (**Used**) and some other tools that do the
same job (**Alternatives**). The alternatives are only a selection: they are
not ranked, and not all of them work with every kind of data.

### Data

- Duan Y, Cuscó A, Zhang Y, Inda-Díaz JS, Zhu C, Areias Castro A, Yang X, Yu
  J, Jiang G, Zhao X-M, Coelho LP (2026). Long-read metagenomic sequencing
  reveals novel lineages and functional diversity in urban soil microbiome.
  *bioRxiv*.
  <https://doi.org/10.64898/2026.03.20.713087>
  --- the sample used in this workshop.

### Looking at sequence files (steps 1, 4 and 7)

**Used:**

- [SeqKit](https://bioinf.shenwei.me/seqkit/): a toolkit for FASTA/FASTQ
  files (statistics, filtering, subsampling, ...).
  - Shen W, Le S, Li Y, Hu F (2016). SeqKit: a cross-platform and ultrafast
    toolkit for FASTA/Q file manipulation. *PLoS ONE*.
    <https://doi.org/10.1371/journal.pone.0163962>
  - Shen W, Sipos B, Zhao L (2024). SeqKit2: a Swiss army knife for sequence
    and alignment processing. *iMeta*.
    <https://doi.org/10.1002/imt2.191>

### Read quality control (step 2)

**Used:**

- [fastp](https://github.com/OpenGene/fastp): adapter trimming, quality
  filtering and an HTML report for short reads, in one pass.
  - Chen S, Zhou Y, Chen Y, Gu J (2018). fastp: an ultra-fast all-in-one FASTQ
    preprocessor. *Bioinformatics*.
    <https://doi.org/10.1093/bioinformatics/bty560>
  - Chen S (2023). Ultrafast one-pass FASTQ data preprocessing, quality
    control, and deduplication using fastp. *iMeta*.
    <https://doi.org/10.1002/imt2.107>
  - Chen S (2025). fastp 1.0: an ultra-fast all-round tool for FASTQ data
    quality control and preprocessing. *iMeta*.
    <https://doi.org/10.1002/imt2.70078>
- [fastplong](https://github.com/OpenGene/fastplong): the same, for long
  reads (Nanopore, PacBio). No paper of its own: cite fastp.

**Alternatives:**

- [Cutadapt](https://github.com/marcelm/cutadapt): adapter and quality
  trimming of short reads. Martin M (2011). Cutadapt removes adapter sequences
  from high-throughput sequencing reads. *EMBnet.journal*.
  <https://doi.org/10.14806/ej.17.1.200>
- [Trimmomatic](https://github.com/usadellab/Trimmomatic): adapter and
  quality trimming of Illumina reads. Bolger AM, Lohse M, Usadel B (2014).
  Trimmomatic: a flexible trimmer for Illumina sequence data.
  *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btu170>
- [Chopper](https://github.com/wdecoster/chopper) and
  [NanoPlot](https://github.com/wdecoster/NanoPlot): filtering and QC plots
  for long reads. De Coster W, Rademakers R (2023). NanoPack2:
  population-scale evaluation of long-read sequencing data. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btad311>
- [Filtlong](https://github.com/rrwick/Filtlong): keeps the best long reads,
  by length and quality. No paper.
- [MultiQC](https://github.com/MultiQC/MultiQC): combines the QC reports of
  many samples and tools into one. Ewels P, Magnusson M, Lundin S, Käller M
  (2016). MultiQC: summarize analysis results for multiple tools and samples
  in a single report. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btw354>

### Taxonomic profiling (steps 3 and 10)

**Used:**

- [SingleM](https://wwood.github.io/singlem/): profiles a community from
  the reads that cover a set of single-copy marker genes, so it also sees
  organisms with no reference genome; `appraise` compares the reads with the
  bins. Woodcroft BJ, et al. (2025). Comprehensive taxonomic identification of
  microbial species in metagenomic data using SingleM and Sandpiper. *Nature
  Biotechnology*.
  <https://doi.org/10.1038/s41587-025-02738-1>
- [GTDB](https://gtdb.ecogenomic.org): the genome-based taxonomy that
  SingleM (and GTDB-Tk, below) use. Parks DH, et al. (2025). GTDB release 10:
  a complete and systematic taxonomy for 715 230 bacterial and 17 245 archaeal
  genomes. *Nucleic Acids Research*.
  <https://doi.org/10.1093/nar/gkaf1040>
- [Krona](https://github.com/marbl/Krona): the interactive, zoomable charts
  of the profiles. Ondov BD, Bergman NH, Phillippy AM (2011). Interactive
  metagenomic visualization in a Web browser. *BMC Bioinformatics*.
  <https://doi.org/10.1186/1471-2105-12-385>

**Alternatives:**

- [mOTUs](https://motu-tool.org): marker-gene profiling, like SingleM, with
  species built from reference genomes and MAGs. Ruscheweyh H-J, et al.
  (2022). Cultivation-independent genomes greatly expand taxonomic-profiling
  capabilities of mOTUs across various environments. *Microbiome*.
  <https://doi.org/10.1186/s40168-022-01410-z>
- [MetaPhlAn](https://github.com/biobakery/MetaPhlAn): clade-specific marker
  genes; best for well-studied environments, such as the human gut.
  Blanco-Míguez A, et al. (2023). Extending and improving metagenomic
  taxonomic profiling with uncharacterized species using MetaPhlAn 4. *Nature
  Biotechnology*.
  <https://doi.org/10.1038/s41587-023-01688-w>
- [sylph](https://github.com/bluenote-1577/sylph): very fast, k-mer based
  profiling against a database of genomes. Shaw J, Yu YW (2024). Rapid
  species-level metagenome profiling and containment estimation with sylph.
  *Nature Biotechnology*.
  <https://doi.org/10.1038/s41587-024-02412-y>

### Assembly (step 4)

**Used:**

- [myloasm](https://github.com/bluenote-1577/myloasm): metagenome assembler
  for modern long reads (Nanopore R10.4, PacBio HiFi), which separates
  closely related strains. Shaw J, et al. (2026). High-resolution metagenome
  assembly for modern long reads with myloasm. *Nature Biotechnology*.
  <https://doi.org/10.1038/s41587-026-03053-z>

**Alternatives (long reads):**

- [metaFlye](https://github.com/mikolmogorov/Flye): the metagenome mode of
  the Flye assembler. Kolmogorov M, et al. (2020). metaFlye: scalable
  long-read metagenome assembly using repeat graphs. *Nature Methods*.
  <https://doi.org/10.1038/s41592-020-00971-x>
- [metaMDBG](https://github.com/GaetanBenoitDev/metaMDBG): fast and
  low-memory, first for HiFi reads and, with nanoMDBG, for Nanopore reads.
  - Benoit G, et al. (2024). High-quality metagenome assembly from long
    accurate reads with metaMDBG. *Nature Biotechnology*.
    <https://doi.org/10.1038/s41587-023-01983-6>
  - Benoit G, et al. (2026). High-quality metagenome assembly from nanopore
    reads with nanoMDBG. *Nature Communications*.
    <https://doi.org/10.1038/s41467-026-69760-y>
- [hifiasm-meta](https://github.com/xfengnefx/hifiasm-meta): for PacBio
  HiFi reads only. Feng X, Cheng H, Portik D, Li H (2022). Metagenome
  assembly of high-fidelity long reads with hifiasm-meta. *Nature Methods*.
  <https://doi.org/10.1038/s41592-022-01478-3>

**Alternatives (short reads only):**

- [MEGAHIT](https://github.com/voutcn/megahit): fast and low-memory. Li D,
  Liu C-M, Luo R, Sadakane K, Lam T-W (2015). MEGAHIT: an ultra-fast
  single-node solution for large and complex metagenomics assembly via
  succinct de Bruijn graph. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btv033>
- [metaSPAdes](https://github.com/ablab/spades): slower and more
  memory-hungry, often more contiguous. Nurk S, Meleshko D, Korobeynikov A,
  Pevzner PA (2017). metaSPAdes: a new versatile metagenomic assembler.
  *Genome Research*.
  <https://doi.org/10.1101/gr.213959.116>

### Polishing (step 5)

**Used:**

- [Polypolish](https://github.com/rrwick/Polypolish): short-read polishing
  that uses all the alignments of each read, so that it can also correct
  repeats.
  - Wick RR, Holt KE (2022). Polypolish: short-read polishing of long-read
    bacterial genome assemblies. *PLoS Computational Biology*.
    <https://doi.org/10.1371/journal.pcbi.1009802>
  - Bouras G, Judd LM, Edwards RA, Vreugde S, Stinear TP, Wick RR (2024). How
    low can you go? Short-read polishing of Oxford Nanopore bacterial genome
    assemblies. *Microbial Genomics*.
    <https://doi.org/10.1099/mgen.0.001254>
    --- introduces `polypolish filter` (and pypolca, below), and compares
    the short-read polishers.

**Alternatives (with short reads):**

- [pypolca](https://github.com/gbouras13/pypolca): a reimplementation of
  POLCA, often run after Polypolish (Bouras et al., 2024, above).
- [POLCA](https://github.com/alekseyzimin/masurca) (part of MaSuRCA). Zimin
  AV, Salzberg SL (2020). The genome polishing tool POLCA makes fast and
  accurate corrections in genome assemblies. *PLoS Computational Biology*.
  <https://doi.org/10.1371/journal.pcbi.1007981>
- [Pilon](https://github.com/broadinstitute/pilon). Walker BJ, et al.
  (2014). Pilon: an integrated tool for comprehensive microbial variant
  detection and genome assembly improvement. *PLoS ONE*.
  <https://doi.org/10.1371/journal.pone.0112963>

**Alternatives (with the long reads themselves):**

- [Medaka](https://github.com/nanoporetech/medaka): Oxford Nanopore's
  neural-network polisher. No paper.
- [Racon](https://github.com/lbcb-sci/racon). Vaser R, Sović I, Nagarajan N,
  Šikić M (2017). Fast and accurate de novo genome assembly from long
  uncorrected reads. *Genome Research*.
  <https://doi.org/10.1101/gr.214270.116>

### Read mapping (steps 5 and 6)

**Used:**

- [BWA](https://github.com/lh3/bwa) (`bwa mem`): maps short reads to a
  reference (here, the assembly).
  - Li H, Durbin R (2009). Fast and accurate short read alignment with
    Burrows-Wheeler transform. *Bioinformatics*.
    <https://doi.org/10.1093/bioinformatics/btp324>
  - Li H (2013). Aligning sequence reads, clone sequences and assembly contigs
    with BWA-MEM. *arXiv*.
    <https://arxiv.org/abs/1303.3997>
- [SAMtools](https://www.htslib.org): sorts, indexes and summarises the
  alignments (`sort`, `index`, `flagstat`, `coverage`). Danecek P, et al.
  (2021). Twelve years of SAMtools and BCFtools. *GigaScience*.
  <https://doi.org/10.1093/gigascience/giab008>

**Alternatives:**

- [bwa-mem2](https://github.com/bwa-mem2/bwa-mem2): the same results as
  `bwa mem`, faster. Vasimuddin M, Misra S, Li H, Aluru S (2019). Efficient
  architecture-aware acceleration of BWA-MEM for multicore systems. *IEEE
  IPDPS*.
  <https://doi.org/10.1109/IPDPS.2019.00041>
- [Bowtie 2](https://github.com/BenLangmead/bowtie2). Langmead B, Salzberg
  SL (2012). Fast gapped-read alignment with Bowtie 2. *Nature Methods*.
  <https://doi.org/10.1038/nmeth.1923>
- [strobealign](https://github.com/ksahlin/strobealign): very fast
  short-read mapper. Sahlin K (2022). Strobealign: flexible seed size enables
  ultra-fast and accurate read alignment. *Genome Biology*.
  <https://doi.org/10.1186/s13059-022-02831-7>
- [minimap2](https://github.com/lh3/minimap2): the standard mapper for long
  reads (it also maps short reads). Li H (2018). Minimap2: pairwise alignment
  for nucleotide sequences. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/bty191>
- [CoverM](https://github.com/wwood/CoverM): coverage of contigs and
  genomes from the alignments (and the fraction of reads that the bins
  explain, an alternative to `singlem appraise`). Aroney STN, et al. (2025).
  CoverM: read alignment statistics for metagenomics. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btaf147>

### Binning (step 7)

**Used:**

- [SemiBin2](https://github.com/BigDataBiology/SemiBin): deep learning on
  contig composition and coverage, with models pretrained for several
  environments, and support for long-read assemblies.
  - Pan S, Zhao X-M, Coelho LP (2023). SemiBin2: self-supervised contrastive
    learning leads to better MAGs for short- and long-read sequencing.
    *Bioinformatics*.
    <https://doi.org/10.1093/bioinformatics/btad209>
  - Pan S, Zhu C, Zhao X-M, Coelho LP (2022). A deep siamese neural network
    improves metagenome-assembled genomes in microbiome datasets across
    different environments. *Nature Communications*.
    <https://doi.org/10.1038/s41467-022-29843-y>

**Alternatives:**

- [MetaBAT 2](https://bitbucket.org/berkeleylab/metabat): fast and widely
  used. Kang DD, et al. (2019). MetaBAT 2: an adaptive binning algorithm for
  robust and efficient genome reconstruction from metagenome assemblies.
  *PeerJ*. <https://doi.org/10.7717/peerj.7359>
- [VAMB](https://github.com/RasmussenLab/vamb): variational autoencoders;
  best with many samples. Nissen JN, et al. (2021). Improved metagenome
  binning and assembly using deep variational autoencoders. *Nature
  Biotechnology*.
  <https://doi.org/10.1038/s41587-020-00777-4>
- [COMEBin](https://github.com/ziyewang/COMEBin): contrastive learning. Wang
  Z, et al. (2024). Effective binning of metagenomic contigs using
  contrastive multi-view representation learning. *Nature Communications*.
  <https://doi.org/10.1038/s41467-023-44290-z>
- LorBin: designed for long-read assemblies. Xue W, et al. (2025). LorBin:
  efficient binning of long-read metagenomes by multiscale adaptive
  clustering and evaluation. *Nature Communications*.
  <https://doi.org/10.1038/s41467-025-64916-8>
- MaxBin 2. Wu Y-W, Simmons BA, Singer SW (2016). MaxBin 2.0: an automated
  binning algorithm to recover genomes from multiple metagenomic datasets.
  *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btv638>
- [CONCOCT](https://github.com/BinPro/CONCOCT). Alneberg J, et al. (2014).
  Binning metagenomic contigs by coverage and composition. *Nature Methods*.
  <https://doi.org/10.1038/nmeth.3103>
- [DAS Tool](https://github.com/cmks/DAS_Tool): not a binner itself, it
  combines the bins of several binners into a better set. Sieber CMK, et al.
  (2018). Recovery of genomes from metagenomes via a dereplication,
  aggregation and scoring strategy. *Nature Microbiology*.
  <https://doi.org/10.1038/s41564-018-0171-1>

### Bin quality (steps 8 and 9)

**Used:**

- [CheckM2](https://github.com/chklovski/CheckM2): predicts completeness
  and contamination with machine learning on the genes of the bin, so it
  also works for lineages with few reference genomes. Chklovski A, Parks DH,
  Woodcroft BJ, Tyson GW (2023). CheckM2: a rapid, scalable and accurate tool
  for assessing microbial genome quality using machine learning. *Nature
  Methods*.
  <https://doi.org/10.1038/s41592-023-01940-w>
- MIMAG, the reporting standard that defines the quality tiers. Its
  high-quality tier also requires the 23S, 16S and 5S rRNA genes and at least
  18 tRNAs, which we did not check. Bowers RM, et al. (2017). Minimum
  information about a single amplified genome (MISAG) and a
  metagenome-assembled genome (MIMAG) of bacteria and archaea. *Nature
  Biotechnology*. <https://doi.org/10.1038/nbt.3893>
- [GUNC](https://grp-bork.embl-community.io/gunc/): detects chimeric bins
  (genes from different lineages), which completeness and contamination
  estimates can miss. Orakov A, et al. (2021). GUNC: detection of chimerism
  and contamination in prokaryotic genomes. *Genome Biology*.
  <https://doi.org/10.1186/s13059-021-02393-0>
- [proGenomes](https://progenomes.embl.de): the reference genomes from which
  the GUNC database is built. Mende DR, et al. (2020). proGenomes2: an
  improved database for accurate and consistent habitat, taxonomic and
  functional annotations of prokaryotic genomes. *Nucleic Acids Research*.
  <https://doi.org/10.1093/nar/gkz1002>

**Alternatives:**

- [CheckM](https://github.com/Ecogenomics/CheckM): the predecessor of
  CheckM2, based on lineage-specific marker genes. Parks DH, Imelfort M,
  Skennerton CT, Hugenholtz P, Tyson GW (2015). CheckM: assessing the quality
  of microbial genomes recovered from isolates, single cells, and
  metagenomes. *Genome Research*.
  <https://doi.org/10.1101/gr.186072.114>
- [BUSCO](https://busco.ezlab.org): completeness from universal single-copy
  orthologs (also for eukaryotes and viruses). Manni M, Berkeley MR, Seppey M,
  Simão FA, Zdobnov EM (2021). BUSCO update: novel and streamlined workflows
  along with broader and deeper phylogenetic coverage for scoring of
  eukaryotic, prokaryotic, and viral genomes. *Molecular Biology and
  Evolution*.
  <https://doi.org/10.1093/molbev/msab199>
- MDMcleaner: finds and removes contaminating contigs. Vollmers J, Wiegand S,
  Lenk F, Kaster A-K (2022). How clear is our current view on microbial dark
  matter? (Re-)assessing public MAG & SAG datasets with MDMcleaner. *Nucleic
  Acids Research*.
  <https://doi.org/10.1093/nar/gkac294>

### Gene prediction (step 11)

**Used:**

- [Pyrodigal](https://github.com/althonos/pyrodigal): Python bindings to
  Prodigal, with the same results, faster.
  - Larralde M (2022). Pyrodigal: Python bindings and interface to Prodigal,
    an efficient method for gene prediction in prokaryotes. *Journal of Open
    Source Software*.
    <https://doi.org/10.21105/joss.04296>
  - Hyatt D, et al. (2010). Prodigal: prokaryotic gene recognition and
    translation initiation site identification. *BMC Bioinformatics*.
    <https://doi.org/10.1186/1471-2105-11-119>

**Alternatives:**

- [Prodigal](https://github.com/hyattpd/Prodigal) itself (paper above).
- FragGeneScan: for short, error-prone sequences (e.g., unassembled reads).
  Rho M, Tang H, Ye Y (2010). FragGeneScan: predicting genes in short and
  error-prone reads. *Nucleic Acids Research*.
  <https://doi.org/10.1093/nar/gkq747>
- Genome annotation pipelines (next section) also predict the genes, and the
  RNA genes that MIMAG asks for.

### Functional annotation (step 12)

**Used:**

- [eggNOG-mapper](https://github.com/eggnogdb/eggnog-mapper): transfers
  annotations (gene names, COG, KEGG, CAZy, ...) from orthologs in the eggNOG
  database. Cantalapiedra CP, Hernández-Plaza A, Letunic I, Bork P,
  Huerta-Cepas J (2021). eggNOG-mapper v2: functional annotation, orthology
  assignments, and domain prediction at the metagenomic scale. *Molecular
  Biology and Evolution*.
  <https://doi.org/10.1093/molbev/msab293>
- [eggNOG 5](http://eggnog5.embl.de): the orthology database that
  eggNOG-mapper 2.1 uses. Huerta-Cepas J, et al. (2019). eggNOG 5.0: a
  hierarchical, functionally and phylogenetically annotated orthology
  resource based on 5090 organisms and 2502 viruses. *Nucleic Acids
  Research*. <https://doi.org/10.1093/nar/gky1085>
- [DIAMOND](https://github.com/bbuchfink/diamond): fast protein search,
  used by eggNOG-mapper (and by CheckM2 and GUNC). Buchfink B, Reuter K, Drost
  H-G (2021). Sensitive protein alignments at tree-of-life scale using
  DIAMOND. *Nature Methods*.
  <https://doi.org/10.1038/s41592-021-01101-x>

**Alternatives:**

- [Bakta](https://github.com/oschwengers/bakta): complete annotation of a
  bacterial genome (genes, RNAs, functions), with standard output formats.
  Schwengers O, et al. (2021). Bakta: rapid and standardized annotation of
  bacterial genomes via alignment-free sequence identification. *Microbial
  Genomics*. <https://doi.org/10.1099/mgen.0.000685>
- [Prokka](https://github.com/tseemann/prokka): the older, widely used
  equivalent of Bakta. Seemann T (2014). Prokka: rapid prokaryotic genome
  annotation. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btu153>
- [DRAM](https://github.com/WrightonLabCSU/DRAM): annotation of MAGs with a
  summary of their metabolism. Shaffer M, et al. (2020). DRAM for distilling
  microbial metabolism to automate the curation of microbiome function.
  *Nucleic Acids Research*.
  <https://doi.org/10.1093/nar/gkaa621>
- [KofamScan](https://www.genome.jp/tools/kofamkoala/): KEGG orthologs from
  profile HMMs. Aramaki T, et al. (2020). KofamKOALA: KEGG Ortholog
  assignment based on profile HMM and adaptive score threshold.
  *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btz859>
- [InterProScan](https://github.com/ebi-pf-team/interproscan): protein
  domains and families (Pfam and the other InterPro databases). Jones P, et
  al. (2014). InterProScan 5: genome-scale protein function classification.
  *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btu031>

### Beyond this workshop

Steps that a full analysis usually adds:

- [GTDB-Tk](https://github.com/Ecogenomics/GTDBTk): the taxonomy of each
  bin, in GTDB. Chaumeil P-A, Mussig AJ, Hugenholtz P, Parks DH (2022).
  GTDB-Tk v2: memory friendly classification with the genome taxonomy
  database. *Bioinformatics*.
  <https://doi.org/10.1093/bioinformatics/btac672>
- Dereplication, to keep one genome per species across samples:
  - [dRep](https://github.com/MrOlm/drep). Olm MR, Brown CT, Brooks B,
    Banfield JF (2017). dRep: a tool for fast and accurate genomic
    comparisons that enables improved genome recovery from metagenomes
    through de-replication. *The ISME Journal*.
    <https://doi.org/10.1038/ismej.2017.126>
  - [galah](https://github.com/wwood/galah). No paper.
  - [skani](https://github.com/bluenote-1577/skani): fast average
    nucleotide identity (ANI) between genomes, as used by dereplication.
    Shaw J, Yu YW (2023). Fast and robust metagenomic sequence comparison
    through sparse chaining with skani. *Nature Methods*.
    <https://doi.org/10.1038/s41592-023-02018-3>
- Pipelines that run the whole analysis, from reads to annotated bins:
  - [nf-core/mag](https://nf-co.re/mag). Krakau S, Straub D, Gourlé H,
    Gabernet G, Nahnsen S (2022). nf-core/mag: a best-practice pipeline for
    metagenome hybrid assembly and binning. *NAR Genomics and
    Bioinformatics*.
    <https://doi.org/10.1093/nargab/lqac007>
  - [Aviary](https://github.com/rhysnewell/aviary). No paper.
  - [NGLess](https://ngless.embl.de): a language for writing such
    pipelines. Coelho LP, et al. (2019). NG-meta-profiler: fast processing of
    metagenomes using NGLess, a domain-specific language. *Microbiome*.
    <https://doi.org/10.1186/s40168-019-0684-8>

### Software environment

- [pixi](https://pixi.sh): installs the tools and keeps their versions fixed
  (`pixi.toml`). No paper.
- [Bioconda](https://bioconda.github.io): where (almost) all the tools come
  from. Grüning B, et al. (2018). Bioconda: sustainable and comprehensive
  software distribution for the life sciences. *Nature Methods*.
  <https://doi.org/10.1038/s41592-018-0046-7>
:::
