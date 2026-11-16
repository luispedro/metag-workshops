"""Draw the functional annotation cartoon, in three steps.

Redrawn from the MAG functional annotation deck (slide 3): (1) predict the
genes (ORFs) on a contig, (2) annotate them by comparing them to a database,
(3) filter the hits, using informed human judgement. Each step is a row, its
label on the left and the cartoon on the right; the steps of the deck add one
row at a time, and the handout figure has all three.

The genes are arrows, pointing along their strand, in ColorBrewer's Dark2
colours (as are the genomes of the binning cartoons and the taxa of gunc.py).
The rest of the style is that of the CheckM1 cartoon (checkm1.py); a gene the
filter drops is drawn as a missing marker gene is there (dashed outline).
Like checkm1.py, this is a figure script whose output name picks the figure:

    python media/annotation.py build/media/annotation.pdf          # the handout figure
    python media/annotation.py build/media/annotation_genes.svg    # one step of the deck

The steps (annotation_genes, _database, _judgement) are listed in ../Makefile.
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import GREY, TEXT, text

W, H = 1080, 560
LIGHT = '#888888'
DARK2 = ['#1b9e77', '#d95f02', '#7570b3']
STEPS = ['genes', 'database', 'judgement']

# The cartoon, on the right: the contig and its genes, (x0, x1, strand,
# colour, kept by the filter), then the database.
CX0, CX1 = 520, 1060
GENES = [
    (555, 715, +1, DARK2[0], True),
    (755, 880, -1, DARK2[1], True),
    (920, 1030, +1, DARK2[2], False),
]
GH = 28                         # the height of a gene arrow
TIP = 18                        # the length of its point
Y_CONTIG = 75
DB = (540, 185, 1045, 310)      # x0, y0, x1, y1
Y_OUT = 470

# The labels, on the left, one row per step: (y, title, details).
LABELS = [
    (Y_CONTIG + 9, '1. Predict genes', ['Prodigal, Pyrodigal']),
    (232, '2. Annotate the genes', ['eggNOG-mapper (generic)',
                                     'RGI (antibiotic resistance)', '…']),
    (Y_OUT - 40, '3. Use informed', ['human judgement!']),
]


def gene(x0, x1, strand, colour, y, faint=False):
    """A gene, as an arrow pointing along its strand."""
    t, b = y - GH / 2, y + GH / 2
    if strand > 0:
        d = f'M {x0},{t} H {x1 - TIP} L {x1},{y} L {x1 - TIP},{b} H {x0} Z'
    else:
        d = f'M {x1},{t} H {x0 + TIP} L {x0},{y} L {x0 + TIP},{b} H {x1} Z'
    style = (f'fill:none;stroke:{colour};stroke-width:3;stroke-dasharray:6,4' if faint
             else f'fill:{colour}')
    return f'<path d="{d}" style="{style};stroke-linejoin:round" />'


def contig():
    """The contig and its genes, with the start and stop codons of the first."""
    out = [f'<path d="M {CX0},{Y_CONTIG} H {CX1}" style="fill:none;stroke:{GREY};'
           f'stroke-width:10;stroke-linecap:round" />']
    out += [gene(x0, x1, s, c, Y_CONTIG) for x0, x1, s, c, _ in GENES]
    x0, x1 = GENES[0][:2]
    y = Y_CONTIG - GH / 2 - 10
    out.append(text(x0, y, 'ATG', size=18, colour=LIGHT))
    out.append(text(x1, y, 'TAA', size=18, anchor='end', colour=LIGHT))
    return out


def centre(g):
    return (g[0] + g[1]) / 2


def arrow(x, y0, y1):
    """A thin arrow, pointing down from y0 to y1."""
    return [f'<path d="M {x},{y0} V {y1 - 14}" style="fill:none;stroke:{GREY};stroke-width:3" />',
            f'<path d="M {x - 9},{y1 - 16} L {x},{y1} L {x + 9},{y1 - 16} Z" style="fill:{GREY}" />']


def label(step):
    y, title, details = LABELS[step]
    if step == 2:
        # The original's emphasis: the third step is the one people skip.
        return [text(20, y, title, size=32, weight='bold'),
                text(20, y + 40, details[0], size=32, weight='bold')]
    out = [text(20, y, title, size=32)]
    for i, d in enumerate(details):
        out.append(text(52, y + 38 + 32 * i, d, size=24, colour=LIGHT))
    return out


def panel(case):
    n = STEPS.index(case) + 1
    out = label(0) + contig()
    if n >= 2:
        out += label(1)
        x0, y0, x1, y1 = DB
        for g in GENES:
            out += arrow(centre(g), Y_CONTIG + GH / 2 + 4, y0 - 4)
        out.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="8" '
                   f'style="fill:#f3f3f3;stroke:{GREY};stroke-width:3" />')
        out.append(text((x0 + x1) / 2, (y0 + y1) / 2 + 11, 'Database', size=30,
                        anchor='middle', colour=TEXT))
    if n >= 3:
        out += label(2)
        y1 = DB[3]
        for g in GENES:
            out += arrow(centre(g), y1 + 4, Y_OUT - GH / 2 - 4)
        mid = (centre(GENES[0]) + centre(GENES[1])) / 2
        out.append(f'<text x="{mid}" y="{(y1 + Y_OUT) / 2 + 10}" style="{checkm1.FONT};'
                   f'font-size:30px;font-weight:bold;font-style:italic;fill:{TEXT};'
                   f'text-anchor:middle">Filter</text>')
        out += [gene(x0, x1, s, c, Y_OUT, faint=not kept) for x0, x1, s, c, kept in GENES]
    return out


def svg(body, name):
    return checkm1.svg(W, H, body, name,
                       about='functional annotation cartoon, redrawn from the MAG '
                             'functional annotation deck (slide 3)')


def main(out):
    out = Path(out)
    name = out.stem
    if name == 'annotation':
        # The handout figure: all three steps.
        doc = svg(panel(STEPS[-1]), name)
    else:
        case = name.removeprefix('annotation_')
        if case not in STEPS:
            sys.exit(f'annotation.py: unknown figure {name!r} (steps: {", ".join(STEPS)})')
        doc = svg(panel(case), name)
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        # Same conversion as the static SVG figures get in common/workshop.mk.
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'annotation.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
