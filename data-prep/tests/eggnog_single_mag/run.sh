#!/usr/bin/env bash
# Time eggnog-mapper on a single MAG (SemiBin_1 of subset 6549321d, 5043 proteins)
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/hpc/worker_setup.sh
out=tests/eggnog_single_mag
mkdir -p $out/tmp
/usr/bin/time -v pixi run --frozen -e eggnog emapper.py \
    -i subsets/6549321d/run/annotation/genes/SemiBin_1.faa --itype proteins \
    -m diamond --data_dir "$EGGNOG_DATA_DIR" \
    -o SemiBin_1 --output_dir $out --temp_dir $PWD/$out/tmp \
    --cpu 16 --override
