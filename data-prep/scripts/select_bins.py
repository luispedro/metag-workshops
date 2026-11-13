#!/usr/bin/env python
"""Summarise the bins of the full-data run and propose bins for the workshop.

Writes
  OUT/bins_summary.tsv   one row per bin: quality, depth, taxonomy, pass/fail
  OUT/selected_bins.txt  proposed selection, one bin per line (edit by hand
                         if needed: make_subset.sh reads this file)

Selection: bins passing the quality thresholds and GUNC are split into
N strata by log short-read depth (so the selection spans moderately to highly
abundant); within each stratum, prefer the bin from the least-represented
phylum (then class) among bins already chosen, then the best quality.
"""
import argparse
import glob
import math
import os
import subprocess

import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('run', help='output directory of pipeline.sh on the full data')
    p.add_argument('-o', '--out', default='selection')
    p.add_argument('-n', '--n-bins', type=int, default=5)
    p.add_argument('--min-completeness', type=float, default=90)
    p.add_argument('--max-contamination', type=float, default=5)
    return p.parse_args()


def contig_to_bin(bins_dir):
    rows = []
    for fa in sorted(glob.glob(os.path.join(bins_dir, '*.fa'))):
        b = os.path.basename(fa)[:-len('.fa')]
        with open(fa) as f:
            for line in f:
                if line.startswith('>'):
                    rows.append((line[1:].split()[0], b))
    return pd.DataFrame(rows, columns=['contig', 'bin'])


def contig_depth(bam):
    out = subprocess.run(['samtools', 'coverage', bam],
                         check=True, capture_output=True, text=True).stdout
    from io import StringIO
    cov = pd.read_table(StringIO(out))
    cov = cov.rename(columns={'#rname': 'contig', 'meandepth': 'depth'})
    cov['length'] = cov['endpos'] - cov['startpos'] + 1
    return cov[['contig', 'length', 'depth']]


def bin_taxonomy(profile_file):
    """Most-covered lineage for each genome in a `singlem pipe -f` profile."""
    prof = pd.read_table(profile_file)
    best = prof.sort_values('coverage', ascending=False).drop_duplicates('sample')
    return best.set_index('sample')['taxonomy'].str.replace('Root; ', '', regex=False)


def rank(tax, prefix):
    for t in str(tax).split('; '):
        if t.startswith(prefix):
            return t
    return 'unknown'


def main():
    args = parse_args()
    run = args.run
    os.makedirs(args.out, exist_ok=True)

    c2b = contig_to_bin(os.path.join(run, 'binning', 'output_bins'))
    cov = contig_depth(os.path.join(run, 'mapping', 'sr.sorted.bam'))
    c2b = c2b.merge(cov, on='contig', how='left')
    c2b['bases'] = c2b['length'] * c2b['depth']
    per_bin = c2b.groupby('bin').agg(n_contigs=('contig', 'size'),
                                     size=('length', 'sum'),
                                     bases=('bases', 'sum'))
    per_bin['sr_depth'] = per_bin['bases'] / per_bin['size']
    per_bin = per_bin.drop(columns='bases')

    checkm2 = pd.read_table(os.path.join(run, 'binqc', 'checkm2', 'quality_report.tsv'))
    checkm2 = checkm2.set_index('Name')[['Completeness', 'Contamination']]
    checkm2.columns = ['completeness', 'contamination']

    [gunc_file] = glob.glob(os.path.join(run, 'binqc', 'gunc', 'GUNC.*.maxCSS_level.tsv'))
    gunc = pd.read_table(gunc_file).set_index('genome')
    gunc = gunc[['clade_separation_score', 'pass.GUNC']]
    gunc.columns = ['gunc_css', 'gunc_pass']

    tax = bin_taxonomy(os.path.join(run, 'binqc', 'bins.profile.tsv')).rename('taxonomy')

    summary = per_bin.join(checkm2).join(gunc).join(tax)
    summary['phylum'] = summary['taxonomy'].map(lambda t: rank(t, 'p__'))
    summary['class'] = summary['taxonomy'].map(lambda t: rank(t, 'c__'))
    summary['gunc_pass'] = summary['gunc_pass'].astype(str).str.lower() == 'true'
    summary['passes'] = ((summary['completeness'] >= args.min_completeness)
                         & (summary['contamination'] <= args.max_contamination)
                         & summary['gunc_pass'])

    cands = summary[summary['passes']].sort_values('sr_depth', ascending=False)
    selected = []
    if len(cands) <= args.n_bins:
        selected = list(cands.index)
    else:
        logd = cands['sr_depth'].map(math.log)
        edges = [logd.min() + (logd.max() - logd.min()) * i / args.n_bins
                 for i in range(args.n_bins + 1)]
        strata = [cands[(logd >= lo) & (logd <= hi)] for lo, hi in zip(edges, edges[1:])]
        # if some strata are empty, the remaining picks come from the fullest ones
        picks_left = args.n_bins
        while picks_left and any(len(s) for s in strata):
            for s in sorted(strata, key=len, reverse=True):
                s = s.drop(index=selected, errors='ignore')
                if not len(s) or not picks_left:
                    continue
                chosen = summary.loc[selected]
                s = s.assign(
                    n_phylum=s['phylum'].map(chosen['phylum'].value_counts()).fillna(0),
                    n_class=s['class'].map(chosen['class'].value_counts()).fillna(0),
                    quality=s['completeness'] - 5 * s['contamination'])
                best = s.sort_values(['n_phylum', 'n_class', 'quality'],
                                     ascending=[True, True, False]).index[0]
                selected.append(best)
                picks_left -= 1
    summary['selected'] = summary.index.isin(selected)

    summary.sort_values('sr_depth', ascending=False).to_csv(
        os.path.join(args.out, 'bins_summary.tsv'), sep='\t', index_label='bin')
    with open(os.path.join(args.out, 'selected_bins.txt'), 'w') as f:
        for b in selected:
            f.write(b + '\n')

    with pd.option_context('display.width', 200, 'display.max_colwidth', 60):
        print(f'{len(summary)} bins, {len(cands)} pass the thresholds, {len(selected)} selected:')
        print(summary.loc[selected, ['size', 'sr_depth', 'completeness',
                                     'contamination', 'phylum', 'class']])


if __name__ == '__main__':
    main()
