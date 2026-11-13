#!/usr/bin/env bash
# Smoke test: simulate a 3-genome community from GTDB r232 representatives and
# run the whole workshop pipeline on it. Checks flags, outputs, and gives a
# first idea of runtimes; it is NOT a substitute for validating real data.
#
# Run in the queue with
#   cd data-prep && mqsub --no-email -t 16 -m 64 --hours 4 -- pixi run --frozen bash tests/smoke_test.sh
set -euo pipefail
cd "$(dirname "$0")"
D=/work/microbiome/db/gtdb/gtdb_release232/genomic_files_reps/gtdb_genomes_reps_r232/database
THREADS=${THREADS:-16}
# genome  short-read depth  long-read depth
GENOMES=(
    "$D/GCF/000/011/365/GCF_000011365.1_genomic.fna.gz 40 25"   # Bradyrhizobium diazoefficiens
    "$D/GCF/900/460/065/GCF_900460065.1_genomic.fna.gz 20 15"   # Rhodococcus erythropolis
    "$D/GCF/000/698/785/GCF_000698785.1_genomic.fna.gz 10 10"   # Nitrososphaera viennensis
)
mkdir -p sim
if [[ ! -s sim/sample_ont.fq.gz ]]; then
    : > sim/r1.fq; : > sim/r2.fq; : > sim/ont.fq
    seed=1
    for g in "${GENOMES[@]}"; do
        read -r fa sr lr <<< "$g"
        size=$(zcat "$fa" | grep -v '>' | tr -d '\n' | wc -c)
        pairs=$(( size * sr / 300 ))
        zcat "$fa" > sim/genome.fa
        wgsim -N "$pairs" -1 150 -2 150 -e 0.002 -r 0.001 -R 0 -S $seed \
            sim/genome.fa sim/tmp1.fq sim/tmp2.fq > /dev/null
        cat sim/tmp1.fq >> sim/r1.fq; cat sim/tmp2.fq >> sim/r2.fq
        python sim_long.py "$fa" "$lr" $seed >> sim/ont.fq
        seed=$(( seed + 1 ))
    done
    rm sim/genome.fa sim/tmp?.fq
    # shuffle so reads are not ordered by genome
    seqkit shuffle -s 7 sim/ont.fq -o sim/sample_ont.fq.gz
    paste <(paste - - - - < sim/r1.fq) <(paste - - - - < sim/r2.fq) | shuf --random-source=<(yes) \
        | awk -F'\t' '{print $1"\n"$2"\n"$3"\n"$4 > "sim/s1.fq"; print $5"\n"$6"\n"$7"\n"$8 > "sim/s2.fq"}'
    gzip -c sim/s1.fq > sim/sample_R1.fq.gz; gzip -c sim/s2.fq > sim/sample_R2.fq.gz
    rm sim/r?.fq sim/s?.fq sim/ont.fq
fi
seqkit stats -T sim/sample_*.fq.gz
bash ../scripts/pipeline.sh -1 sim/sample_R1.fq.gz -2 sim/sample_R2.fq.gz -l sim/sample_ont.fq.gz \
    -o run -t "$THREADS"
column -t run/binqc/checkm2/quality_report.tsv | cut -c1-120
