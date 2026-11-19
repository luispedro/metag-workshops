"""Draw the three ways to profile a community from its reads.

One row per strategy, its name and tools on the left, a cartoon on the right
(as in annotation.py):

1. marker genes: only the reads from a few genes (the coloured boxes of the
   CheckM1 cartoon) are used, the others ignored (faint);
2. k-mers: each read is cut into k-mers, looked up in a database of the k-mers
   of reference genomes, and the read goes to the taxon most k-mers point to;
3. mapping: reads are aligned to whole reference genomes.

Reads are dark lines; genomes take the colours of the binning cartoons. The
rest of the style is that of checkm1.py. A figure script:

    python media/profiling.py build/media/profiling.pdf
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import FAINT, GREY, MARKERS, TEXT, text

W, H = 1080, 540
LIGHT = '#888888'
READ = '#333333'
TAXA = {'A': '#66a61e', 'B': '#7570b3'}
RL = 70
CX0, CX1 = 420, 1040   # the cartoons

ROWS = [
    (60, '1. Marker genes', ['SingleM, MetaPhlAn,', 'mOTUs, Kaiju']),
    (240, '2. k-mers', ['Kraken, Sylph']),
    (410, '3. Mapping', ['CoverM, minimap2']),
]


def svg(width, height, body, name):
    return checkm1.svg(width, height, body, name,
                       about='three ways to profile a community from its reads')


def line(x0, x1, y, colour, width, dash=''):
    return (f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{colour};'
            f'stroke-width:{width};stroke-linecap:round{dash}" />')


def arrow(x, y, length=40):
    return [f'<path d="M {x},{y} H {x + length}" style="fill:none;stroke:{GREY};stroke-width:3" />',
            f'<path d="M {x + length},{y - 8} L {x + length + 14},{y} L {x + length},{y + 8} Z" '
            f'style="fill:{GREY}" />']


def markers(y):
    """A genome with three marker genes; only the reads on them count."""
    out = [line(CX0, CX1, y + 45, GREY, 10)]
    genes = [(480, 0), (700, 1), (900, 2)]
    for x, m in genes:
        out.append(f'<rect x="{x}" y="{y + 34}" width="70" height="22" rx="3" '
                   f'style="fill:{MARKERS[m]}" />')
    lanes = [(y + 15, [430, 590, 690, 820, 960]), (y - 5, [470, 760, 880])]
    for yy, starts in lanes:
        for s in starts:
            on = any(min(s + RL, x + 70) - max(s, x) >= 35 for x, _ in genes)
            out.append(line(s, s + RL, yy, READ, 7) if on else
                       line(s, s + RL, yy, FAINT, 5, ';stroke-dasharray:4,10'))
    out.append(text(CX0, y + 95, 'only the reads from a few genes are used',
                    size=20, colour=LIGHT))
    return out


def kmers(y):
    """A read, cut into k-mers, each looked up in a database of reference k-mers."""
    x0, x1 = CX0, CX0 + 200
    out = [line(x0, x1, y, READ, 7)]
    k, step = 60, 35
    for i, t in enumerate('AABA.'):
        a, yy = x0 + i * step, y + 20 + 11 * i
        out.append(line(a, a + k, yy, TAXA[t], 6) if t != '.' else
                   line(a, a + k, yy, FAINT, 4, ';stroke-dasharray:4,8'))
    out += arrow(x1 + 30, y + 35)
    out.append(f'<rect x="{x1 + 95}" y="{y + 9}" width="180" height="52" rx="6" '
               f'style="fill:#f2f2f2;stroke:{GREY};stroke-width:3" />')
    out.append(text(x1 + 185, y + 42, 'k-mer database', size=20, anchor='middle'))
    out += arrow(x1 + 290, y + 35)
    out.append(f'<rect x="{x1 + 360}" y="{y + 22}" width="26" height="26" rx="3" '
               f'style="fill:{TAXA["A"]}" />')
    out.append(text(x1 + 373, y + 41, 'A', size=19, anchor='middle', weight='bold',
                    colour='#ffffff'))
    out.append(text(CX0, y + 95, 'cut each read into k-mers; look them up',
                    size=20, colour=LIGHT))
    return out


def mapping(y):
    """Reads aligned to whole reference genomes."""
    out = []
    genomes = [(y + 20, 'A', 900), (y + 55, 'B', 820)]
    for yy, t, end in genomes:
        out.append(line(CX0, end, yy, TAXA[t], 10))
        out.append(text(end + 20, yy + 8, f'genome {t}', size=20, colour=LIGHT))
    for s, snp in [(470, None), (610, 640), (780, None)]:
        out.append(line(s, s + RL, y - 5, READ, 7))
        if snp:
            out.append(f'<rect x="{snp - 3}" y="{y - 13}" width="6" height="16" '
                       f'style="fill:#d62728" />')
    out.append(text(CX0, y + 105, 'align each read to whole genomes',
                    size=20, colour=LIGHT))
    return out


def main(out):
    out = Path(out)
    body = []
    for (y, title, tools), draw in zip(ROWS, [markers, kmers, mapping]):
        body.append(text(20, y + 25, title, size=28, weight='bold'))
        for i, t in enumerate(tools):
            body.append(text(45, y + 60 + 28 * i, t, size=22, colour=LIGHT))
        body += draw(y + 15)
    doc = svg(W, H, body, out.stem)
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'profiling.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
