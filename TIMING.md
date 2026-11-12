# Timing report: workshop dataset

Run 2026-11-12 on aqua; written 2026-11-13. Times are wall-clock
(`timings.tsv` from `scripts/pipeline.sh`; the job times come from PBS).

## Summary

| subset | background | LR depth cap | eggNOG-mapper on | bins | total | validation |
|---|---|---|---|---|---|---|
| `6549321d` | 0.01 | 40× | all bins (79,008 proteins) | 40 | **45.0 min** | FAIL (above 30 min hard limit) |
| `9ca3c728` | 0.002 | 25× | best MAG only (SemiBin_2, 5,039 proteins) | 32 | **24.8 min** | PASS (above 15 min target, below 30 min limit) |

Both subsets: 5 selected bins, minimum completeness 90%, maximum contamination
5%, SR depth cap 60×. The workshop run uses 16 threads (`WORKSHOP_THREADS`),
in a 16-CPU / 64 GB job. `9ca3c728` is the current setting (commit `2ab49c8`).

## Workshop run, per step

| step | `6549321d` (s) | `9ca3c728` (s) | change (s) | share of `9ca3c728` | peak RAM `9ca3c728` (GB) |
|---|---:|---:|---:|---:|---:|
| qc_sr | 5 | 3 | −2 | 0.2% | 1.3 |
| qc_lr | 51 | 30 | −21 | 2.0% | 1.8 |
| profile_sr | 206 | 159 | −47 | 10.7% | 1.7 |
| profile_lr | 361 | 248 | −113 | 16.7% | 3.7 |
| assemble | 380 | 174 | −206 | 11.7% | 5.0 |
| polish_aln_r1 | 13 | 8 | −5 | 0.5% | 1.2 |
| polish_aln_r2 | 14 | 9 | −5 | 0.6% | 1.2 |
| polish | 32 | 26 | −6 | 1.7% | 3.6 |
| map | 58 | 31 | −27 | 2.1% | 1.6 |
| bin | 95 | 71 | −24 | 4.8% | 0.6 |
| checkm2 | 92 | 78 | −14 | 5.2% | 5.7 |
| gunc | 375 | 316 | −59 | 21.2% | 8.8 |
| appraise | 94 | 74 | −20 | 5.0% | 1.6 |
| genes | 36 | 24 | −12 | 1.6% | 0.3 |
| eggnog | 890 | 238 | −652 | 16.0% | 6.4 |
| **total** | **2,702 (45.0 min)** | **1,489 (24.8 min)** | **−1,213** | | max 8.8 |

By stage (`9ca3c728`): QC 0.6 min, read profiling 6.8 min, assembly and
polishing 3.6 min, mapping and binning 1.7 min, bin QC (CheckM2, GUNC,
SingleM appraise) 7.8 min, genes and annotation 4.4 min.

### Workshop input data

| | `6549321d` | `9ca3c728` |
|---|---:|---:|
| short reads (pairs, 2×150 bp) | 2,402,577 | 1,283,956 |
| of which background | 1,398,799 (58%) | 280,178 (22%) |
| long reads | 233,283 (1.76 Gbp) | 128,308 (1.00 Gbp) |
| of which background | 102,100 (44%) | 20,526 (16%) |
| polished assembly | 65.5 Mbp | 46.3 Mbp |
| binned | 60.6 Mbp, 40 bins | 41.1 Mbp, 32 bins (17 < 0.5 Mbp) |

## eggNOG-mapper on a single MAG

`tests/eggnog_single_mag/run.sh`: SemiBin_1 of `6549321d` (100% complete,
0.3% contamination, 5,043 proteins), 16 CPUs, DIAMOND mode:

| input | proteins | time | peak RAM |
|---|---:|---:|---:|
| all 40 bins (`6549321d` workshop run) | 79,008 | 890 s (14.8 min) | 8.1 GB |
| one MAG (test) | 5,043 | 250 s (4.2 min) | 6.7 GB |
| one MAG (`9ca3c728` workshop run, SemiBin_2) | 5,039 | 238 s (4.0 min) | 6.4 GB |

4,560 of the 5,043 test proteins (90%) were annotated. On 16× fewer proteins
it is only ~3.6× faster: most of the time is a fixed cost, likely reading
the 9.3 GB `eggnog_proteins.dmnd`.

## Remaining bottlenecks (`9ca3c728`)

- **gunc (5.3 min)** and **eggnog (4.0 min)**: mostly fixed cost. On the
  tiny simulated test data, gunc still took 270 s and eggnog 383 s (13,363
  proteins). Less data barely helps; to go lower, fake gunc (precomputed
  results, `--fake gunc`) or drop it.
- **profile_lr (4.1 min)**, **profile_sr (2.7 min)**, **assemble (2.9 min)**:
  scale with the reads; a smaller background or lower depth caps would save
  a few minutes at most.

## Building the subset (queue jobs)

| task | job | CPUs | wall time |
|---|---|---:|---:|
| select_bins | 28068592 | 4 | 12.9 min |
| make_subset | 28069902 | 16 | 45.5 min |
| workshop_run | 28074566 | 16 | 25.1 min |
| validate | 28076454 | 4 | 0.4 min |

## Full-data run (`runs/full`, run once, reused by both subsets)

| step | time (h) | CPUs | peak RAM (GB) |
|---|---:|---:|---:|
| qc_sr | 0.1 | 16 | 1.3 |
| qc_lr | 0.5 | 16 | 2.8 |
| profile_sr | 0.8 | 32 | 4.2 |
| profile_lr | 1.6 | 32 | 6.9 |
| assemble | 6.4 | 64 | 188.7 |
| polish_aln_r1 | 1.6 | 12 | 17.6 |
| polish_aln_r2 | 1.6 | 12 | 17.8 |
| polish | 1.6 | 12 | 646.4 |
| map | 8.1 | 12 | 17.5 |
| bin | 6.7 | 12 | 14.0 |
| checkm2 | 0.9 | 32 | 27.8 |
| gunc | 7.7 | 32 | 28.3 |
| appraise | 0.8 | 32 | 5.0 |
| **sum of steps** | **38.5** | | |

Several steps ran at the same time as separate jobs (QC and profiling;
the two polishing alignments; CheckM2, GUNC and appraise), so the sum is more
than the wall-clock time from start to finish. The full run produced 2,421
bins. The long-read-vs-assembly mapping (`full_map_lr`, for extracting long
reads) has no `timings.tsv` entry.
