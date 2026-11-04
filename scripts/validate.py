#!/usr/bin/env python
"""Validate a pipeline run on the workshop dataset against the full-data run.

Checks (GOALS.md, Part 2, step 5):
  1. each selected full-data bin is recovered (skani ANI >= 99%, aligned
     fraction >= 50%), with similar CheckM2/GUNC quality and the same taxonomy
  2. the SingleM read profiles (short and long reads) contain the genus of
     each selected bin
  3. every step produced its expected outputs
  4. total wall-clock time: fails above --max-minutes (hard limit, 30),
     warns above --target-minutes (15)

Usage: python scripts/validate.py FULL_RUN SELECTION WORKSHOP_RUN [-o report.md]
"""
import argparse
import os
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from select_bins import bin_taxonomy, rank  # noqa: E402

EXPECTED = [
    'qc/fastp.html', 'qc/fastplong.html', 'qc/sr_R1.fq.gz', 'qc/lr.fq.gz',
    'profile/sr.profile.tsv', 'profile/lr.profile.tsv',
    'assembly/draft.fa', 'assembly/polished.fa',
    'mapping/sr.sorted.bam', 'binning/contig_bins.tsv',
    'binqc/checkm2/quality_report.tsv', 'binqc/bins.profile.tsv',
    'binqc/appraise_sr.txt', 'binqc/appraise_lr.txt',
    'annotation/all_bins.faa', 'annotation/eggnog/all_bins.emapper.annotations',
]


def quality(run):
    q = pd.read_table(os.path.join(run, 'binqc/checkm2/quality_report.tsv'))
    q = q.set_index('Name')[['Completeness', 'Contamination']]
    gdir = os.path.join(run, 'binqc/gunc')
    [g] = [f for f in os.listdir(gdir) if f.endswith('maxCSS_level.tsv')]
    g = pd.read_table(os.path.join(gdir, g)).set_index('genome')['pass.GUNC']
    g = g.astype(str).str.lower() == 'true'
    return q.join(g)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('full')
    p.add_argument('selection')
    p.add_argument('workshop')
    p.add_argument('-o', '--out', default=None)
    p.add_argument('--target-minutes', type=float, default=15)
    p.add_argument('--max-minutes', type=float, default=30,
                   help='hard limit: above this the workshop becomes difficult')
    args = p.parse_args()
    out = args.out or os.path.join(args.workshop, 'validation.md')
    ok = True
    lines = ['# Validation of the workshop dataset', '']

    with open(os.path.join(args.selection, 'selected_bins.txt')) as f:
        selected = [b.strip() for b in f if b.strip()]
    full_bins = [os.path.join(args.full, 'binning/output_bins', b + '.fa') for b in selected]
    ws_dir = os.path.join(args.workshop, 'binning/output_bins')
    ws_bins = sorted(os.path.join(ws_dir, f) for f in os.listdir(ws_dir) if f.endswith('.fa'))

    skani_out = os.path.join(args.workshop, 'skani_vs_full.tsv')
    subprocess.run(['skani', 'dist', '-q', *ws_bins, '-r', *full_bins, '-o', skani_out],
                   check=True)
    sk = pd.read_table(skani_out)
    sk['ref'] = sk['Ref_file'].map(lambda f: os.path.basename(f)[:-3])
    sk['query'] = sk['Query_file'].map(lambda f: os.path.basename(f)[:-3])
    sk = sk[(sk['ANI'] >= 99) & (sk['Align_fraction_ref'] >= 50)]
    best = sk.sort_values('Align_fraction_ref', ascending=False).drop_duplicates('ref')
    best = best.set_index('ref')

    qf, qw = quality(args.full), quality(args.workshop)
    tf = bin_taxonomy(os.path.join(args.full, 'binqc/bins.profile.tsv'))
    tw = bin_taxonomy(os.path.join(args.workshop, 'binqc/bins.profile.tsv'))

    lines += ['## 1. Selected bins', '',
              '| full bin | workshop bin | ANI | AF ref | compl. full/ws | contam. full/ws '
              '| GUNC full/ws | same taxonomy | status |',
              '|' + '---|' * 9]
    for b in selected:
        if b not in best.index:
            lines.append(f'| {b} | - | | | | | | | **NOT RECOVERED** |')
            ok = False
            continue
        m = best.loc[b]
        w = m['query']
        same_tax = tf.get(b) == tw.get(w)
        good = (abs(qf.loc[b, 'Completeness'] - qw.loc[w, 'Completeness']) <= 5
                and qw.loc[w, 'Contamination'] <= qf.loc[b, 'Contamination'] + 2
                and qw.loc[w, 'pass.GUNC'] and same_tax)
        ok &= good
        lines.append(
            f"| {b} | {w} | {m['ANI']:.2f} | {m['Align_fraction_ref']:.1f} "
            f"| {qf.loc[b, 'Completeness']:.1f}/{qw.loc[w, 'Completeness']:.1f} "
            f"| {qf.loc[b, 'Contamination']:.1f}/{qw.loc[w, 'Contamination']:.1f} "
            f"| {qf.loc[b, 'pass.GUNC']}/{qw.loc[w, 'pass.GUNC']} | {same_tax} "
            f"| {'ok' if good else '**CHECK**'} |")
    lines += ['', f'Workshop run has {len(ws_bins)} bins in total.', '']

    lines += ['## 2. SingleM read profiles contain the selected bins', '']
    for tech in ['sr', 'lr']:
        prof = pd.read_table(os.path.join(args.workshop, f'profile/{tech}.profile.tsv'))
        taxa = ' '.join(prof['taxonomy'])
        for b in selected:
            genus = rank(tf.get(b), 'g__')
            found = genus != 'unknown' and genus in taxa
            ok &= found
            lines.append(f'- {tech}: {b} ({genus}): {"found" if found else "**MISSING**"}')
    lines.append('')

    lines += ['## 3. Expected outputs', '']
    missing = [f for f in EXPECTED
               if not os.path.exists(os.path.join(args.workshop, f))
               or os.path.getsize(os.path.join(args.workshop, f)) == 0]
    ok &= not missing
    lines.append('All present.' if not missing else
                 'Missing or empty: ' + ', '.join(missing))
    lines.append('')

    lines += ['## 4. Runtime', '']
    t = pd.read_table(os.path.join(args.workshop, 'timings.tsv'))
    total = t['seconds'].sum() / 60
    ok &= total <= args.max_minutes
    lines += ['```', t.to_string(index=False), '```']
    verdict = ('ok' if total <= args.target_minutes else
               '**above target, below hard limit**' if total <= args.max_minutes else
               '**ABOVE HARD LIMIT**')
    lines += ['', f'Total: {total:.1f} min (target {args.target_minutes:g} min, '
              f'hard limit {args.max_minutes:g} min): {verdict}', '']

    lines.insert(1, f'**Overall: {"PASS" if ok else "FAIL"}**\n')
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
