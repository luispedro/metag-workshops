#!/usr/bin/env bash
# Workshop pipeline: the commands participants run, in order.
#
# The same script is used (a) on the full data, to choose the bins for the
# workshop dataset, and (b) on the workshop dataset, to validate and time it.
#
# Usage:
#   pixi run bash scripts/pipeline.sh -1 R1.fq.gz -2 R2.fq.gz -l ont.fq.gz -o OUTDIR \
#       [-t THREADS] [--until STEP | --only STEP] [--cleanup]
#       [--precomputed RUN --fake STEP,...]
#
# Steps (in order):
#   qc_sr qc_lr profile_sr profile_lr assemble polish_aln_r1 polish_aln_r2
#   polish map bin checkm2 gunc appraise genes eggnog
# --only runs a single step (used to split the full-data run into queue jobs,
# see jugfile.py); the steps it needs must already be done.
# Each finished step is recorded in OUTDIR/.done/STEP; rerunning skips it,
# so a killed job can simply be resubmitted. Per-step wall-clock time and peak
# memory go to OUTDIR/timings.tsv.
#
# --fake: for steps too slow for the workshop, print the commands and copy that
# step's outputs from a previous run (--precomputed) instead of running them.
# Only safe if the earlier steps reproduce the precomputed run (same bins).
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
STEPS=(qc_sr qc_lr profile_sr profile_lr assemble polish_aln_r1 polish_aln_r2
       polish map bin checkm2 gunc appraise genes eggnog)
THREADS=8
UNTIL=eggnog
CLEANUP=0
FAKE=
PRECOMPUTED=
ONLY=

usage() { sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -1) SR1=$(realpath "$2"); shift 2 ;;
        -2) SR2=$(realpath "$2"); shift 2 ;;
        -l) LR=$(realpath "$2"); shift 2 ;;
        -o) OUT=$2; shift 2 ;;
        -t) THREADS=$2; shift 2 ;;
        --until) UNTIL=$2; shift 2 ;;
        --only) ONLY=$2; shift 2 ;;
        --cleanup) CLEANUP=1; shift ;;
        --fake) FAKE=,$2,; shift 2 ;;
        --precomputed) PRECOMPUTED=$(realpath "$2"); shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage ;;
    esac
done
[[ -n "${SR1:-}" && -n "${SR2:-}" && -n "${LR:-}" && -n "${OUT:-}" ]] || usage
[[ " ${STEPS[*]} " == *" $UNTIL "* ]] || { echo "Unknown step: $UNTIL" >&2; exit 1; }
[[ -z "$ONLY" || " ${STEPS[*]} " == *" $ONLY "* ]] || { echo "Unknown step: $ONLY" >&2; exit 1; }
if [[ -n "$FAKE" ]]; then
    [[ -d "$PRECOMPUTED" ]] || { echo "--fake needs --precomputed RUN" >&2; exit 1; }
    for s in ${FAKE//,/ }; do
        [[ " ${STEPS[*]} " == *" $s "* ]] || { echo "Unknown step: $s" >&2; exit 1; }
    done
fi
for v in SINGLEM_METAPACKAGE_PATH CHECKM2DB GUNC_DB EGGNOG_DATA_DIR; do
    [[ -n "${!v:-}" ]] || { echo "$v is not set: run this script with 'pixi run'" >&2; exit 1; }
done

mkdir -p "$OUT/.done" "$OUT/tmp"
cd "$OUT"
# large temporary files go here; TMPDIR itself is left alone because a deep
# path breaks Python multiprocessing sockets (AF_UNIX path too long)
TMP=$PWD/tmp
[[ -f timings.tsv ]] || printf 'step\tseconds\tmax_rss_gb\tmode\n' > timings.tsv


# 1. Read quality control
step_qc_sr() {
    mkdir -p qc
    fastp \
        -i "$SR1" -I "$SR2" \
        -o qc/sr_R1.fq.gz -O qc/sr_R2.fq.gz \
        -h qc/fastp.html -j qc/fastp.json \
        -w "$(( THREADS < 16 ? THREADS : 16 ))"
}

step_qc_lr() {
    mkdir -p qc
    fastplong \
        -i "$LR" -o qc/lr.fq.gz \
        -l 1000 \
        -h qc/fastplong.html -j qc/fastplong.json \
        -w "$THREADS"
}

# 2. Read-based taxonomic profiling
step_profile_sr() {
    mkdir -p profile
    singlem pipe \
        -1 qc/sr_R1.fq.gz -2 qc/sr_R2.fq.gz \
        --otu-table profile/sr.otu.tsv \
        -p profile/sr.profile.tsv \
        --taxonomic-profile-krona profile/sr.profile.html \
        --threads "$THREADS"
}

step_profile_lr() {
    mkdir -p profile
    singlem pipe \
        -1 qc/lr.fq.gz \
        --otu-table profile/lr.otu.tsv \
        -p profile/lr.profile.tsv \
        --taxonomic-profile-krona profile/lr.profile.html \
        --threads "$THREADS"
}

# 3a. Long-read assembly (indexed here for the polishing alignments, which
# are two independent steps)
step_assemble() {
    myloasm qc/lr.fq.gz -o assembly/myloasm -t "$THREADS"
    [[ -s assembly/myloasm/assembly_primary.fa ]] || {
        echo "myloasm did not produce assembly_primary.fa" >&2; return 1; }
    ln -sf myloasm/assembly_primary.fa assembly/draft.fa
    bwa index assembly/draft.fa
}

# 3b. Short-read polishing: each read end mapped separately, all alignments
# (the two alignment steps can run at the same time), then polypolish
step_polish_aln_r1() {
    mkdir -p polish
    bwa mem -t "$THREADS" -a assembly/draft.fa qc/sr_R1.fq.gz > polish/aln_R1.sam
}

step_polish_aln_r2() {
    mkdir -p polish
    bwa mem -t "$THREADS" -a assembly/draft.fa qc/sr_R2.fq.gz > polish/aln_R2.sam
}

step_polish() {
    polypolish filter \
        --in1 polish/aln_R1.sam --in2 polish/aln_R2.sam \
        --out1 polish/filtered_R1.sam --out2 polish/filtered_R2.sam
    polypolish polish assembly/draft.fa \
        polish/filtered_R1.sam polish/filtered_R2.sam > assembly/polished.fa
    if [[ $CLEANUP == 1 ]]; then rm -f polish/*.sam; fi
}

# 3c. Map reads back to the polished assembly (paired-end) for coverage
step_map() {
    mkdir -p mapping
    bwa index assembly/polished.fa
    bwa mem -t "$THREADS" assembly/polished.fa qc/sr_R1.fq.gz qc/sr_R2.fq.gz \
        | samtools sort -@ "$THREADS" -o mapping/sr.sorted.bam
    samtools index mapping/sr.sorted.bam
}

# 3d. Binning with the pretrained soil model
step_bin() {
    SemiBin2 single_easy_bin \
        -i assembly/polished.fa \
        -b mapping/sr.sorted.bam \
        --environment soil \
        --sequencing-type long_read \
        --compression none \
        -o binning \
        -t "$THREADS"
}

# 4. Bin quality
step_checkm2() {
    checkm2 predict \
        -i binning/output_bins -x fa \
        -o binqc/checkm2 \
        --database_path "$CHECKM2DB" \
        -t "$THREADS" --force
}

step_gunc() {
    mkdir -p binqc/gunc
    gunc run \
        -d binning/output_bins -e .fa \
        -r "$GUNC_DB" \
        -o binqc/gunc --temp_dir "$TMP" \
        -t "$THREADS"
}

step_appraise() {
    singlem pipe \
        --genome-fasta-files binning/output_bins/*.fa \
        --otu-table binqc/bins.otu.tsv \
        -p binqc/bins.profile.tsv \
        --threads "$THREADS"
    for tech in sr lr; do
        singlem appraise \
            --metagenome-otu-tables profile/$tech.otu.tsv \
            --genome-otu-tables binqc/bins.otu.tsv \
            --output-unaccounted-for-otu-table binqc/appraise_$tech.unaccounted.tsv \
            > binqc/appraise_$tech.txt
    done
}

# 5. Gene prediction (per bin) and functional annotation
step_genes() {
    mkdir -p annotation/genes
    : > annotation/all_bins.faa
    for fa in binning/output_bins/*.fa; do
        b=$(basename "$fa" .fa)
        pyrodigal -i "$fa" \
            -a annotation/genes/$b.faa \
            -d annotation/genes/$b.fna \
            -o annotation/genes/$b.gff
        # prefix protein names with the bin name, so hits can be traced to bins
        sed "s/^>/>${b}__/" annotation/genes/$b.faa >> annotation/all_bins.faa
    done
}

step_eggnog() {
    mkdir -p annotation/eggnog
    pixi run --frozen --manifest-path "$REPO/pixi.toml" -e eggnog emapper.py \
        -i annotation/all_bins.faa --itype proteins \
        -m diamond \
        --data_dir "$EGGNOG_DATA_DIR" \
        -o all_bins --output_dir annotation/eggnog \
        --temp_dir "$TMP" \
        --cpu "$THREADS" --override
}


# Outputs of each step (relative to OUTDIR), copied when the step is faked
outputs_of() {
    case "$1" in
        qc_sr) echo qc/sr_* qc/fastp.* ;;
        qc_lr) echo qc/lr.* qc/fastplong.* ;;
        profile_sr) echo profile/sr.* ;;
        profile_lr) echo profile/lr.* ;;
        assemble) echo assembly/myloasm assembly/draft.fa assembly/draft.fa.* ;;
        polish_aln_r1) echo polish/aln_R1.sam ;;
        polish_aln_r2) echo polish/aln_R2.sam ;;
        polish) echo polish assembly/polished.fa ;;
        map) echo mapping assembly/polished.fa.* ;;
        bin) echo binning ;;
        checkm2) echo binqc/checkm2 ;;
        gunc) echo binqc/gunc ;;
        appraise) echo binqc/bins.* binqc/appraise_* ;;
        genes) echo annotation/genes annotation/all_bins.faa ;;
        eggnog) echo annotation/eggnog ;;
    esac
}

fake_step() {
    local s=$1 p
    echo "== $s: using precomputed results from $PRECOMPUTED. Commands:"
    declare -f step_$s | sed '1,2d;$d'
    for p in $(cd "$PRECOMPUTED" && outputs_of "$s"); do
        mkdir -p "$(dirname "$p")"
        cp -a "$PRECOMPUTED/$p" "$(dirname "$p")/"
    done
}

run_step() {
    local s=$1 mode=run
    if [[ -e .done/$s ]]; then
        echo "== $s: already done, skipping"
        return
    fi
    echo "== $s: starting $(date -Is)"
    local t0=$(date +%s)
    if [[ $FAKE == *,$s,* ]]; then
        mode=precomputed
        fake_step "$s"
        echo 0 > .done/$s.rss
    else
        # /usr/bin/time reports peak memory (of the largest process) for the step
        /usr/bin/time -f '%M' -o .done/$s.rss bash -c "$(declare -f step_$s); $(declare -p REPO SR1 SR2 LR THREADS CLEANUP TMP); set -euo pipefail; step_$s"
    fi
    local secs=$(( $(date +%s) - t0 ))
    printf '%s\t%d\t%.1f\t%s\n' "$s" "$secs" "$(awk '{print $1/1048576}' .done/$s.rss)" "$mode" >> timings.tsv
    touch .done/$s
    echo "== $s: done in ${secs}s"
}

if [[ -n "$ONLY" ]]; then
    run_step "$ONLY"
else
    for s in "${STEPS[@]}"; do
        run_step "$s"
        [[ $s == "$UNTIL" ]] && break
    done
fi
echo "Finished. Timings:"
column -t timings.tsv
