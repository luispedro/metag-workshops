# Metagenomics workshop: goals

We want to design a hands-on workshop on metagenomic data processing using both
long-read (ONT) and short-read (Illumina) sequencing. This document has two
parts:

1. **Workshop content**: what participants do and learn.
2. **Dataset construction**: how we build a small, realistic dataset from real
   data so that the full workshop pipeline runs quickly.

The guiding principle: participants run *exactly* the commands they would run
on a real dataset, and see the files and results they would expect to see.


## Part 1: Workshop content

### 1. Read quality control

- `fastp` for short reads and `fastplong` (the long-read version of fastp) for
  long reads
- Participants should be able to read the QC reports and decide whether the
  data are fit for use.

### 2. Read-based taxonomic profiling

- SingleM (`singlem pipe`) on short reads and on long reads
- Participants should be able to interpret a taxonomic profile and compare the
  profiles from the two technologies.

### 3. Assembly and binning

The assembly is a **hybrid**: long reads are assembled and short reads are used
to polish the result.

- `myloasm` for long-read metagenome assembly
- `bwa mem -a` (each read end mapped separately) + `polypolish` for
  short-read polishing of the assembly
- `bwa mem` (paired-end) for mapping reads back to the polished assembly
  to compute coverage
- `SemiBin2` for binning contigs. Use the pretrained `soil` model
  (`--environment soil`) because training on a small dataset may be unstable.

### 4. Bin quality assessment

- `CheckM2` for completeness and contamination
- `GUNC` for chimerism (bins combining sequences from different organisms)
- `singlem appraise` to compare what the reads contain with what the bins
  recovered
- Participants should be able to say which bins are high quality, medium
  quality, or unusable, and why.

### 5. Gene prediction and functional annotation

- `pyrodigal` (single-genome mode, per bin) for gene prediction
- `eggNOG-mapper` for functional annotation
- Participants should be able to find a function of interest across bins.

### Computing environment

- All tools are installed through the `pixi` environment in this repository.
- All databases are downloaded and configured in advance: SingleM metapackage,
  CheckM2, GUNC, and eggNOG-mapper. Downloading them is *not* part of the
  workshop.


## Part 2: Dataset construction

### Source data

One urban soil sample (`full_data/`):

- Illumina paired-end reads: `1_350.fq1.gz`, `1_350.fq2.gz`
- ONT reads: `fq1_ont.fastq.gz`

The data come from the following study and are publicly available on ENA, so
the derived workshop dataset can be shared with participants (citing the
original study):

> Duan Y, Cuscó A, Zhang Y, Inda-Díaz JS, Zhu C, Areias Castro A, Yang X, Yu J,
> Jiang G, Zhao X-M, Coelho LP. *Long-read metagenomic sequencing reveals novel
> lineages and functional diversity in urban soil microbiome.* (2026)
> doi:[10.64898/2026.03.20.713087](https://doi.org/10.64898/2026.03.20.713087)

### Approach

We build **one** dataset that serves all exercises, so that the read-based
results and the assembly-based results describe the same organisms and can be
compared. We give up representativeness of the original sample in exchange
for a fast and coherent dataset. Random subsampling is not an option: it would
give mostly unassemblable fragments and no meaningful bins.

1. **Run the full pipeline on the full data**: QC, SingleM, myloasm, polishing,
   mapping, SemiBin2, CheckM2, GUNC.
2. **Select ~5 bins** that pass quality thresholds: CheckM2 completeness and
   contamination cutoffs to be defined, and passing GUNC. Bins should span the
   range of abundances *among good bins*. In a soil sample, truly rare
   organisms do not produce usable bins, so "range of abundances" means
   moderately abundant to highly abundant. The selection should ideally also
   span taxonomic diversity.
3. **Extract reads** that map to the selected bins:
   - short reads: keep a pair if either mate maps (`bwa`)
   - long reads: map with `minimap2`
   - if needed for runtime, downsample the reads of very abundant bins and
     record that this distorts the relative abundances
4. **Add background reads**: a small random fraction of reads that do not map
   to the selected bins. This keeps the dataset from being unrealistically
   clean: participants should see unbinned contigs, some fragmentation, and
   taxa in the SingleM profile that do not have bins.
5. **Validate**: run the workshop pipeline on the subset and check that
   - the ~5 selected bins are recovered with similar CheckM2 and GUNC quality
     and the same taxonomy as on the full data
   - the SingleM profile includes the taxa of the selected bins
   - every step produces the expected output files and none fails because the
     input is small (e.g., SemiBin2 training, polishing)
6. **Time it**: measure wall-clock time per step and adjust the number of bins,
   the coverage, and the background fraction until we meet the target below.

### Runtime target

Running all workshop commands from start to finish (QC → profiling → assembly
→ polishing → binning → quality checks → annotation) should take **under 15
minutes** of wall-clock time in the provided environment, and ideally less.
Database setup is excluded. The likely bottlenecks are eggNOG-mapper, GUNC, and
assembly. The number of bins (~5) is a starting point that should be adjusted
based on measured runtimes.
