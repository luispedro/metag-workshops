#!/usr/bin/env python
"""Choose the names of the reads that go into the workshop dataset.

A read (or read pair: decisions are made on the name, so both mates follow)
is kept if
  * it aligns to a contig of a selected bin, and survives the per-bin
    downsampling (fraction = min(1, max_depth / bin_depth)), or
  * it does not align to a selected bin and is drawn as background
    (fraction --background).
Sampling uses a salted hash of the read name, so it is deterministic.

Inputs
  --contigs    TSV: contig, bin, length (selected bins only)
  --alignments `samtools view` (SAM, no header) or minimap2 PAF, restricted
               to alignments of interest; '-' for stdin
  --names      all read names of the raw reads (one per line, e.g.
               `seqkit seq -n -i R1.fq.gz`), used to draw the background
Outputs
  --out        read names to keep
  --report     per-bin read counts, depth, and downsampling fraction
"""
import argparse
import collections
import hashlib
import sys


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--format', choices=['sam', 'paf'], required=True)
    p.add_argument('--contigs', required=True)
    p.add_argument('--alignments', required=True)
    p.add_argument('--names', required=True)
    p.add_argument('--max-depth', type=float, default=float('inf'),
                   help='downsample bins above this depth (default: no downsampling)')
    p.add_argument('--depth', help='TSV: bin, depth (default: estimate from alignments)')
    p.add_argument('--background', type=float, default=0.01)
    p.add_argument('--seed', default='workshop')
    p.add_argument('--out', required=True)
    p.add_argument('--report', required=True)
    return p.parse_args()


def normalise(name):
    # bwa strips /1 and /2 from read names; FASTQ IDs may still have them
    if name.endswith(('/1', '/2')):
        return name[:-2]
    return name


def uniform(name, salt):
    h = hashlib.blake2b((salt + name).encode(), digest_size=8).digest()
    return int.from_bytes(h, 'little') / 2**64


def open_input(path):
    return sys.stdin if path == '-' else open(path)


def main():
    args = parse_args()
    contig2bin = {}
    bin_size = collections.Counter()
    with open(args.contigs) as f:
        for line in f:
            contig, b, length = line.rstrip('\n').split('\t')
            contig2bin[contig] = b
            bin_size[b] += int(length)

    # first bin hit per read; aligned bases per bin (for depth estimates)
    read_bin = {}
    aligned = collections.Counter()
    with open_input(args.alignments) as f:
        for line in f:
            t = line.split('\t', 11)
            if args.format == 'sam':
                name, contig, alen = t[0], t[2], len(t[9])
            else:
                name, contig = t[0], t[5]
                if contig == '*':
                    continue
                alen = int(t[8]) - int(t[7])
            b = contig2bin.get(contig)
            if b is None:
                continue
            aligned[b] += alen
            read_bin.setdefault(normalise(name), b)

    depth = {}
    if args.depth:
        with open(args.depth) as f:
            for line in f:
                b, d = line.split('\t')[:2]
                if b in bin_size:
                    depth[b] = float(d)
    for b in bin_size:
        depth.setdefault(b, aligned[b] / bin_size[b])
    fraction = {b: min(1.0, args.max_depth / depth[b]) if depth[b] else 1.0
                for b in bin_size}

    n_bin = collections.Counter()
    n_kept = collections.Counter()
    n_background = 0
    n_total = 0
    with open(args.out, 'w') as out:
        for name, b in read_bin.items():
            n_bin[b] += 1
            if uniform(name, args.seed + ':bin') < fraction[b]:
                n_kept[b] += 1
                out.write(name + '\n')
        with open(args.names) as f:
            seen = set()
            for line in f:
                name = normalise(line.split()[0])
                n_total += 1
                if name in read_bin or name in seen:
                    continue
                if uniform(name, args.seed + ':background') < args.background:
                    seen.add(name)
                    n_background += 1
                    out.write(name + '\n')

    with open(args.report, 'w') as rep:
        rep.write('bin\tsize\tdepth\tfraction_kept\treads_aligned\treads_kept\n')
        for b in sorted(bin_size):
            rep.write(f'{b}\t{bin_size[b]}\t{depth[b]:.2f}\t{fraction[b]:.4f}\t'
                      f'{n_bin[b]}\t{n_kept[b]}\n')
        rep.write(f'background\t\t\t{args.background}\t{n_total - len(read_bin)}\t{n_background}\n')


if __name__ == '__main__':
    main()
