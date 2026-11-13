#!/usr/bin/env python
"""Simulate ONT-like reads (log-normal lengths, ~1% errors) from a genome.

Usage: sim_long.py GENOME.fna[.gz] DEPTH SEED > reads.fq
Only for smoke-testing the pipeline: the error model is crude.
"""
import gzip
import math
import random
import sys

genome, depth, seed = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
rng = random.Random(seed)
opener = gzip.open if genome.endswith('.gz') else open
seqs, cur = [], []
with opener(genome, 'rt') as f:
    for line in f:
        if line.startswith('>'):
            if cur:
                seqs.append(''.join(cur))
            cur = []
        else:
            cur.append(line.strip().upper())
seqs.append(''.join(cur))
total = sum(len(s) for s in seqs)
comp = str.maketrans('ACGT', 'TGCA')
prefix = genome.split('/')[-1].split('_genomic')[0]
out, n, bases = sys.stdout, 0, 0
while bases < depth * total:
    L = int(rng.lognormvariate(math.log(8000), 0.6))
    s = rng.choices(seqs, weights=[len(x) for x in seqs])[0]
    if len(s) < L:
        continue
    start = rng.randrange(len(s) - L + 1)
    frag = s[start:start + L]
    if rng.random() < .5:
        frag = frag.translate(comp)[::-1]
    read = []
    for c in frag:
        r = rng.random()
        if r < .004:
            read.append(rng.choice('ACGT'))      # substitution
        elif r < .007:
            read.append(c + rng.choice('ACGT'))  # insertion
        elif r < .010:
            pass                                 # deletion
        else:
            read.append(c)
    read = ''.join(read)
    n += 1
    bases += L
    out.write(f'@{prefix}_{n} start={start}\n{read}\n+\n{"5" * len(read)}\n')
