#!/usr/bin/env bash
# Build the workshop dataset from the full-data run and a bin selection.
#
# Usage:
#   pixi run bash scripts/make_subset.sh -r RUN -s selection -o workshop_data \
#       -1 R1.fq.gz -2 R2.fq.gz -l ont.fq.gz [-t THREADS] \
#       [-p LR_VS_ASSEMBLY.paf.gz] [--max-depth-sr X] [--max-depth-lr X]
#       [--background F] [--seed S]
#
#   RUN        output of pipeline.sh on the full data
#   selection  directory with selected_bins.txt and bins_summary.tsv
#              (from select_bins.py; selected_bins.txt may be edited by hand)
#
# Short reads: a pair is kept if either mate aligns (bwa, from the full run's
#   BAM) to a contig of a selected bin.
# Long reads: the raw ONT reads are mapped with minimap2 to the full polished
#   assembly (or -p gives that PAF, computed beforehand); a read is kept if its
#   primary alignment is to a selected bin.
# Bins above --max-depth-* are downsampled (recorded in selection/reads_*.tsv:
#   this distorts relative abundances). A fraction --background of the other
#   reads is added at random.
set -euo pipefail

THREADS=8
MAX_DEPTH_SR=inf
MAX_DEPTH_LR=inf
BACKGROUND=0.01
SEED=workshop
PAF=
while [[ $# -gt 0 ]]; do
    case "$1" in
        -r) RUN=$(realpath "$2"); shift 2 ;;
        -s) SEL=$(realpath "$2"); shift 2 ;;
        -o) OUT=$2; shift 2 ;;
        -1) SR1=$(realpath "$2"); shift 2 ;;
        -2) SR2=$(realpath "$2"); shift 2 ;;
        -l) LR=$(realpath "$2"); shift 2 ;;
        -t) THREADS=$2; shift 2 ;;
        --max-depth-sr) MAX_DEPTH_SR=$2; shift 2 ;;
        --max-depth-lr) MAX_DEPTH_LR=$2; shift 2 ;;
        --background) BACKGROUND=$2; shift 2 ;;
        --seed) SEED=$2; shift 2 ;;
        -p) PAF=$(realpath "$2"); shift 2 ;;
        *) echo "Unknown argument: $1" >&2; sed -n '2,20p' "$0"; exit 1 ;;
    esac
done
HERE=$(cd "$(dirname "$0")" && pwd)
W=$SEL/work
mkdir -p "$W" "$OUT"

# selected contigs: contig, bin, length
: > "$W/selected_contigs.tsv"
while read -r b; do
    [[ -n "$b" ]] || continue
    seqkit fx2tab -n -i -l "$RUN/binning/output_bins/$b.fa" \
        | awk -v b="$b" 'BEGIN{OFS="\t"} {print $1, b, $2}' >> "$W/selected_contigs.tsv"
done < "$SEL/selected_bins.txt"
awk 'BEGIN{OFS="\t"} {print $1, 0, $3}' "$W/selected_contigs.tsv" > "$W/selected_contigs.bed"
# bin, sr_depth (looked up by column name)
awk -F'\t' 'NR==1 {for (i=1; i<=NF; i++) if ($i=="sr_depth") c=i; next} {print $1"\t"$c}' \
    "$SEL/bins_summary.tsv" > "$W/sr_depth.tsv"

# --- short reads -----------------------------------------------------------
seqkit seq -n -i "$SR1" > "$W/sr_names.txt"
samtools view -F 0x904 -M -L "$W/selected_contigs.bed" "$RUN/mapping/sr.sorted.bam" \
    | python "$HERE/select_reads.py" --format sam \
        --contigs "$W/selected_contigs.tsv" --alignments - \
        --depth "$W/sr_depth.tsv" --max-depth "$MAX_DEPTH_SR" \
        --names "$W/sr_names.txt" --background "$BACKGROUND" --seed "$SEED" \
        --out "$W/sr_keep.txt" --report "$SEL/reads_sr.tsv"
# match IDs with or without a /1 or /2 suffix
for r in 1 2; do
    in=$SR1; [[ $r == 2 ]] && in=$SR2
    seqkit grep -j "$THREADS" --id-regexp '^(\S+?)(?:/[12])?(?:\s|$)' \
        -f "$W/sr_keep.txt" "$in" -o "$OUT/sample_R$r.fq.gz"
done

# --- long reads ------------------------------------------------------------
if [[ -z "$PAF" ]]; then
    PAF=$W/lr_vs_assembly.paf.gz
    if [[ ! -s "$PAF" ]]; then
        minimap2 -x map-ont --secondary=no -t "$THREADS" \
            "$RUN/assembly/polished.fa" "$LR" | gzip > "$PAF.tmp"
        mv "$PAF.tmp" "$PAF"
    fi
fi
seqkit seq -n -i "$LR" > "$W/lr_names.txt"
# tp:A:P = primary alignment
zcat "$PAF" | grep -P '\ttp:A:P\t' \
    | python "$HERE/select_reads.py" --format paf \
        --contigs "$W/selected_contigs.tsv" --alignments - \
        --max-depth "$MAX_DEPTH_LR" \
        --names "$W/lr_names.txt" --background "$BACKGROUND" --seed "$SEED" \
        --out "$W/lr_keep.txt" --report "$SEL/reads_lr.tsv"
seqkit grep -j "$THREADS" -f "$W/lr_keep.txt" "$LR" -o "$OUT/sample_ont.fq.gz"

seqkit stats -T -j "$THREADS" "$OUT"/sample_*.fq.gz > "$SEL/workshop_data_stats.tsv"
cp "$SEL/selected_bins.txt" "$SEL/reads_sr.tsv" "$SEL/reads_lr.tsv" "$OUT/"
echo "Workshop data in $OUT"
column -t "$SEL/reads_sr.tsv" "$SEL/reads_lr.tsv" "$SEL/workshop_data_stats.tsv"
