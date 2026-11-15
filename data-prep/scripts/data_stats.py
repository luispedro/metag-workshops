#!/usr/bin/env python
"""Read and assembly statistics of a pipeline run (by default, the full data).

Writes, to OUTDIR (default: RUN/stats):

  read_lengths.png/.pdf   post-QC read length histograms (short and long reads)
  reads.tsv, reads.md     reads, mean length and total length, before and after QC
  assemblies.tsv, .md     contigs, mean length (and total, N50, longest) of each
                          assembly found in RUN:
                            assembly/polished.fa     long-read (myloasm + polypolish)
                            assembly_sr/contigs.fa   short-read only (MEGAHIT; the
                                                     `assemble_sr` step of pipeline.sh)
                          an assembly that is not there yet is skipped: rerun this
                          script once it is

Read numbers come from the fastp/fastplong JSON reports; the long-read length
histogram too (fastplong bins lengths on a log scale). fastp has no length
histogram, so the short-read lengths are counted from qc/sr_R*.fq.gz: on the
full data, this reads ~20 GB, so run the script on the queue, e.g.

    mqsub --no-email -t 4 -m 8 --hours 4 -- pixi run python scripts/data_stats.py runs/full

The counts are kept in OUTDIR/sr_read_lengths.tsv, so later runs (e.g. once the
short-read assembly is done) skip that part.

Usage: python scripts/data_stats.py [RUN] [-o OUTDIR] [-t THREADS]
"""
import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault('MPLCONFIGDIR', os.path.join(os.environ.get('TMPDIR', '/tmp'), 'mpl'))
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)
import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ASSEMBLIES = [
    ('long reads (myloasm + polypolish)', 'assembly/polished.fa'),
    ('short reads only (MEGAHIT)', 'assembly_sr/contigs.fa'),
]

# colours (dataviz reference palette): one per read type, used in every panel
SR_COLOUR = '#2a78d6'
LR_COLOUR = '#eb6834'
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'


# --- reads ----------------------------------------------------------------------

def read_table(run):
    fastp = json.load(open(os.path.join(run, 'qc/fastp.json')))['summary']
    fastplong = json.load(open(os.path.join(run, 'qc/fastplong.json')))['summary']
    rows = []
    for tech, summary in (('short reads (R1 + R2)', fastp), ('long reads', fastplong)):
        for stage, key in (('raw', 'before_filtering'), ('after QC', 'after_filtering')):
            s = summary[key]
            rows.append({'reads': tech, 'stage': stage,
                         'n_reads': s['total_reads'],
                         'mean_length_bp': s['total_bases'] / s['total_reads'],
                         'total_length_bp': s['total_bases']})
    return pd.DataFrame(rows)


def count_lengths(fq):
    """{read length: number of reads} of a (gzipped) FASTQ file"""
    cmd = (f"zcat '{fq}' | mawk 'NR % 4 == 2 {{ c[length($0)]++ }} "
           "END { for (l in c) print l \"\\t\" c[l] }'")
    out = subprocess.run(['bash', '-o', 'pipefail', '-c', cmd],
                         check=True, capture_output=True, text=True).stdout
    return pd.Series({int(l): int(c) for l, c in (x.split('\t') for x in out.splitlines())})


def sr_lengths(run, outdir):
    cache = os.path.join(outdir, 'sr_read_lengths.tsv')
    if os.path.exists(cache):
        return pd.read_table(cache, index_col=0)
    print('Counting short-read lengths (qc/sr_R1.fq.gz, qc/sr_R2.fq.gz)...', flush=True)
    with ThreadPoolExecutor(2) as ex:
        r1, r2 = ex.map(count_lengths, [os.path.join(run, f'qc/sr_{r}.fq.gz') for r in ('R1', 'R2')])
    counts = pd.DataFrame({'R1': r1, 'R2': r2}).fillna(0).astype(int).sort_index()
    counts.index.name = 'length'
    counts.to_csv(cache + '.tmp', sep='\t')
    os.replace(cache + '.tmp', cache)
    return counts


def lr_lengths(run):
    """fastplong's (log-binned) read length histogram, after QC"""
    d = json.load(open(os.path.join(run, 'qc/fastplong.json')))
    h = d['read_after_filtering']['long_read_qc']['read_length_distribution']
    return pd.DataFrame({'start': h['start'], 'end': h['end'], 'reads': h['read_count']})


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def thousands(x, _pos=None):
    return f'{x:,.0f}'


def mark_mean(ax, mean, y_frac=0.92, ha='left'):
    ax.axvline(mean, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(mean, y_frac, f' mean {mean:,.1f} bp ', transform=ax.get_xaxis_transform(),
            color=INK, fontsize=9, ha=ha, va='top')


def plot_read_lengths(sr, lr, reads, outdir):
    qc = reads[reads.stage == 'after QC'].set_index('reads')
    fig, (ax_sr, ax_lr) = plt.subplots(1, 2, figsize=(11, 4), facecolor=SURFACE)

    total = sr.sum(axis=1)
    ax_sr.bar(total.index, total.values, width=0.8, color=SR_COLOUR, linewidth=0)
    ax_sr.set_yscale('log')
    ax_sr.set_xlim(0, total.index.max() + 2)
    ax_sr.set_xlabel('read length (bp)')
    ax_sr.set_ylabel('reads (log scale)')
    ax_sr.set_title(f'Short reads after QC: {total.sum():,} (R1 + R2)',
                    loc='left', fontsize=11, color=INK)
    style(ax_sr)
    mark_mean(ax_sr, qc.loc['short reads (R1 + R2)', 'mean_length_bp'], y_frac=0.75, ha='right')
    ax_sr.text(total.idxmax(), total.max(), f'{total.max() / total.sum():.1%} at {total.idxmax()} bp ',
               color=INK, fontsize=9, ha='right', va='center')

    lr = lr[lr.reads > 0]
    ax_lr.bar(lr.start, lr.reads, width=(lr.end - lr.start + 1) * 0.9, align='edge',
              color=LR_COLOUR, linewidth=0)
    ax_lr.set_xscale('log')
    ax_lr.xaxis.set_major_formatter(plt.FuncFormatter(thousands))
    ax_lr.yaxis.set_major_formatter(plt.FuncFormatter(thousands))
    ax_lr.set_xlabel('read length (bp, log scale)')
    ax_lr.set_ylabel('reads per bin (log-spaced bins)')
    ax_lr.set_title(f'Long reads after QC: {int(lr.reads.sum()):,}',
                    loc='left', fontsize=11, color=INK)
    style(ax_lr)
    ax_lr.set_ylim(0, lr.reads.max() * 1.15)   # room for the label
    mark_mean(ax_lr, qc.loc['long reads', 'mean_length_bp'], y_frac=0.99)

    fig.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(outdir, f'read_lengths.{ext}'), dpi=200, facecolor=SURFACE)
    plt.close(fig)


# --- assemblies -----------------------------------------------------------------

def contig_lengths(fasta, threads):
    out = subprocess.run(['seqkit', 'fx2tab', '--name', '--only-id', '--length',
                          '-j', str(threads), fasta],
                         check=True, capture_output=True, text=True).stdout
    return pd.Series([int(line.rsplit('\t', 1)[1]) for line in out.splitlines()])


def n50(lengths):
    s = lengths.sort_values(ascending=False)
    return int(s[s.cumsum() >= s.sum() / 2].iloc[0])


def assembly_table(run, threads):
    rows = []
    for name, path in ASSEMBLIES:
        fasta = os.path.join(run, path)
        if not os.path.exists(fasta):
            print(f'{path}: not found, skipping', flush=True)
            continue
        print(f'Reading {path}...', flush=True)
        lengths = contig_lengths(fasta, threads)
        rows.append({'assembly': name, 'file': path,
                     'n_contigs': len(lengths),
                     'mean_length_bp': lengths.mean(),
                     'total_length_bp': int(lengths.sum()),
                     'N50_bp': n50(lengths),
                     'longest_bp': int(lengths.max()),
                     'n_contigs_1kbp': int((lengths >= 1000).sum()),
                     'total_length_1kbp_bp': int(lengths[lengths >= 1000].sum())})
    return pd.DataFrame(rows)


# --- output ---------------------------------------------------------------------

def write_table(df, base, title):
    df.to_csv(base + '.tsv', sep='\t', index=False, float_format='%.1f')
    md = df.copy()
    for c in md.columns:
        if pd.api.types.is_numeric_dtype(md[c]):
            fmt = '{:,.1f}' if c.startswith('mean') else '{:,.0f}'
            md[c] = md[c].map(fmt.format)
    cols = list(md.columns)
    numeric = [pd.api.types.is_numeric_dtype(df[c]) for c in cols]
    lines = [f'## {title}', '',
             '| ' + ' | '.join(c.replace('_', ' ') for c in cols) + ' |',
             '|' + '|'.join('---:' if n else '---' for n in numeric) + '|']
    lines += ['| ' + ' | '.join(row) + ' |' for row in md.astype(str).values]
    text = '\n'.join(lines) + '\n'
    with open(base + '.md', 'w') as f:
        f.write(text)
    print(text)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('run', nargs='?', default='runs/full')
    p.add_argument('-o', '--outdir')
    p.add_argument('-t', '--threads', type=int,
                   default=int(os.environ.get('NCPUS') or 4))
    args = p.parse_args()
    outdir = args.outdir or os.path.join(args.run, 'stats')
    os.makedirs(outdir, exist_ok=True)

    reads = read_table(args.run)
    write_table(reads, os.path.join(outdir, 'reads'), 'Reads')
    plot_read_lengths(sr_lengths(args.run, outdir), lr_lengths(args.run), reads, outdir)
    print(f'Wrote {outdir}/read_lengths.png')
    write_table(assembly_table(args.run, args.threads),
                os.path.join(outdir, 'assemblies'), 'Assemblies')


if __name__ == '__main__':
    main()
