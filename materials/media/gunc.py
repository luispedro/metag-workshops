"""Draw the GUNC cartoon: do the taxa follow the contigs?

Redrawn from the MAG QC deck (slides 2 and 3, after the GUNC blog post,
https://www.big-data-biology.org/blog/2021/02/12/gunc/). Each gene of a bin is
classified to a taxon, A or B. Both bins have the same genes: 19 classified to
A and 8 to B. In one, the B genes are spread over all the contigs: the
classifier makes mistakes, but nothing says the bin mixes genomes. In the
other, the B genes sit together, on their own contigs: those contigs are
likely from another genome, binned with the first (a chimera).

The taxa take the colours of the binning cartoons: the green genome of the
green bin, and the yellow one that contaminated it (media/binning_errors.svg).
The rest of the style is that of the CheckM1 cartoon (checkm1.py), and, like
it, this is a figure script whose output name picks the figure:

    python media/gunc.py build/media/gunc.pdf           # the handout figure
    python media/gunc.py build/media/gunc_spread.svg    # one step of the deck

The steps (gunc_spread, gunc_chimeric) are listed in ../Makefile.
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import W, H, GREY, TEXT, BAD, text

TAXA = {'A': '#66a61e', 'B': '#e6ab02'}
GW, GH, STEP = 32, 26, 40   # gene boxes, and the distance between them
MARGIN = 35   # contig beyond its first and last genes
CX = 315      # the centre of the bin

# Contigs: (y, shift from the centre of the bin, taxa of its genes); the genes
# are STEP apart, with gaps where a '.' is. Same genes in both bins; only which
# contigs the B genes are on changes.
CASES = {
    'spread': [
        (100, -30, 'BA.A.'),
        (160, 20, 'BAA.BAA'),
        (220, 0, 'AAB.AAA.AAB'),
        (280, -20, 'AA.AB.BA'),
        (340, 25, 'A.AB'),
    ],
    'chimeric': [
        (100, -30, 'AA.A.'),
        (160, 20, 'AAA.AAA'),
        (220, 0, 'AAA.AAA.AAA'),
        (280, -20, 'BB.BA.BB'),
        (340, 25, 'B.BB'),
    ],
}
# The contigs of the other genome, circled as in media/binning_errors.svg.
CIRCLED = {'spread': [], 'chimeric': [280, 340]}
TITLES = {
    'spread': 'Errors spread over the contigs',
    'chimeric': 'Errors that follow the contigs',
}
RESULT = {
    'spread': [('mixed', TEXT), ('low', TEXT), ('Classifier noise: fine', TEXT)],
    'chimeric': [('separated', BAD), ('high', BAD), ('A chimera', BAD)],
}


def svg(width, height, body, name):
    return checkm1.svg(width, height, body, name,
                       about='GUNC cartoon, redrawn from the MAG QC deck (slides 2-3)')


def gene(taxon, x, y):
    return [f'<rect x="{x}" y="{y - GH / 2}" width="{GW}" height="{GH}" rx="3" '
            f'style="fill:{TAXA[taxon]}" />',
            text(x + GW / 2, y + 7, taxon, size=19, anchor='middle', weight='bold',
                 colour='#ffffff')]


def contig(shift, layout):
    """Where a contig starts and ends, and the x and taxon of each of its genes."""
    out = []
    x = 0
    for c in layout:
        if c != '.':
            out.append((x, c))
            x += STEP
        else:
            x += STEP / 2
    width = x - (STEP - GW) + 2 * MARGIN
    x0 = CX + shift - width / 2
    return x0, x0 + width, [(x0 + MARGIN + x, c) for x, c in out]


def panel(case):
    out = ['<ellipse cx="315" cy="220" rx="300" ry="185" style="fill:none;stroke:#666666;'
           'stroke-width:5;stroke-dasharray:16,10" />']
    counts = {t: 0 for t in TAXA}
    for y, shift, layout in CASES[case]:
        x0, x1, gs = contig(shift, layout)
        if y in CIRCLED[case]:
            out.append(f'<rect x="{x0 - 25}" y="{y - 24}" width="{x1 - x0 + 50}" height="48" '
                       f'rx="24" style="fill:none;stroke:{BAD};stroke-width:4" />')
        out.append(f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{GREY};'
                   f'stroke-width:10;stroke-linecap:round" />')
        for x, t in gs:
            out += gene(t, x, y)
            counts[t] += 1

    # The tally (the same in both bins), then where the B genes are.
    lx = 670
    out.append(text(lx, 52, 'Genes classified as', size=24, weight='bold'))
    for i, t in enumerate(TAXA):
        y = 90 + 45 * i
        out += gene(t, lx, y)
        out.append(text(lx + 50, y + 9, f'taxon {t}', size=24))
        out.append(text(lx + 200, y + 9, f'×{counts[t]}', size=24))
    (along, ac), (css, cc), (verdict, vc) = RESULT[case]
    bold = lambda c: 'bold' if c == BAD else 'normal'
    out.append(text(lx, 210, 'Along the contigs', size=24, weight='bold'))
    out.append(text(lx, 245, f'taxa {along}', size=24, weight=bold(ac), colour=ac))
    out.append(text(lx, 295, 'Clade separation', size=24, weight='bold'))
    out.append(text(lx, 330, css, size=24, weight=bold(cc), colour=cc))
    out.append(text(lx, 395, verdict, size=26, weight=bold(vc), colour=vc))
    return out


def combined():
    """The handout figure: the two bins, one above the other."""
    body = []
    th = H + 50
    for i, case in enumerate(CASES):
        body.append(f'<g transform="translate(0,{i * th})">')
        body.append(text(20, 32, TITLES[case], size=30, weight='bold'))
        body.append('<g transform="translate(0,45)">')
        body += ['  ' + line for line in panel(case)]
        body.append('</g>')
        body.append('</g>')
    return svg(W, th * len(CASES), body, 'gunc')


def main(out):
    out = Path(out)
    name = out.stem
    if name == 'gunc':
        doc = combined()
    else:
        case = name.removeprefix('gunc_')
        if case not in CASES:
            sys.exit(f'gunc.py: unknown figure {name!r} (cases: {", ".join(CASES)})')
        doc = svg(W, H, panel(case), name)
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        # Same conversion as the static SVG figures get in common/workshop.mk.
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'gunc.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
