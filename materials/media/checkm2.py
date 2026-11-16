"""Draw the CheckM2 cartoon: genes come in groups.

The intuition behind CheckM2 (from the MAG QC deck, slide 8): genes form
groups (pathways, complexes, operons), so seeing some genes of a group means
the others should be there too. A bin with B1 and B3 but not B2 is missing
something; a bin with no gene of group C is just a genome without that
pathway; a bin with group A twice has more than one genome.

CheckM2 can also learn what CheckM1 is told: the single-copy marker genes
(the unlabelled boxes, coloured as in checkm1.py) are in every genome, once.
In the cartoon, both kinds of evidence agree: the contig an incomplete bin
lost carries a marker, and the contig a contaminated bin gained, too.

Drawn in the style of the CheckM1 cartoon (checkm1.py), and, like it, a figure
script whose output name picks the figure:

    python media/checkm2.py build/media/checkm2.pdf            # the handout figure
    python media/checkm2.py build/media/checkm2_complete.svg   # one step of the deck

The steps (checkm2_complete, _incomplete, _contaminated) are listed in
../Makefile.
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import W, H, GREY, FAINT, TEXT, BAD, MARKERS, text

# Group A must not take the blue of the markers.
GROUPS = {'A': '#1b9e77', 'B': '#e69138', 'C': '#6aa84f'}
GW, GH = 50, 26   # gene boxes

# Contigs: (y, x0, x1, [(gene, x)]). Genes M0-M3 are the single-copy markers.
# The genes of group A sit together (an operon); those of group B are spread
# over three contigs.
GOOD = [
    (110, 90, 520, [('A1', 170), ('A2', 225), ('A3', 280), ('M0', 400)]),
    (165, 110, 500, [('M1', 170), ('B1', 330)]),
    (220, 80, 440, [('B3', 140), ('M2', 300)]),
    (275, 120, 540, [('M3', 200), ('B2', 380)]),
]
CONTAMINANT = (330, 130, 520, [('M2', 165), ('A1', 260), ('A2', 315), ('A3', 370)])

CASES = {
    'complete':     dict(contigs=GOOD, missing=[]),
    'incomplete':   dict(contigs=GOOD[:3], missing=[GOOD[3]]),
    'contaminated': dict(contigs=GOOD + [CONTAMINANT], missing=[]),
}
TITLES = {
    'complete': 'A good bin',
    'incomplete': 'An incomplete bin',
    'contaminated': 'A contaminated bin',
}
VERDICT = {
    'complete': ('Complete and clean', TEXT),
    'incomplete': ('Incomplete', BAD),
    'contaminated': ('Contaminated', BAD),
}


def svg(width, height, body, name):
    return checkm1.svg(width, height, body, name,
                       about='CheckM2 cartoon, after the MAG QC deck (slide 8)')


def gene(name, x, y, state='found'):
    """A gene box: found (filled), expected but missing, or absent (faint).

    Marker genes (M0-M3) are drawn as in checkm1.py: no label."""
    if name[0] == 'M':
        colour = MARKERS[int(name[1:])]
    else:
        colour = GROUPS[name[0]]
    if state == 'found':
        box = f'fill:{colour}'
        label = '#ffffff'
    elif state == 'missing':
        box = f'fill:none;stroke:{BAD};stroke-width:3;stroke-dasharray:6,4'
        label = BAD
    else:
        box = f'fill:none;stroke:{FAINT};stroke-width:2'
        label = FAINT
    out = [f'<rect x="{x}" y="{y - GH / 2}" width="{GW}" height="{GH}" rx="3" style="{box}" />']
    if name[0] != 'M':
        out.append(text(x + GW / 2, y + 7, name, size=19, anchor='middle', weight='bold',
                        colour=label))
    return out


def contig(y, x0, x1, genes, faint=False):
    colour = FAINT if faint else GREY
    dash = ';stroke-dasharray:4,10' if faint else ''
    out = [f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{colour};'
           f'stroke-width:10;stroke-linecap:round{dash}" />']
    for name, x in genes:
        out += gene(name, x, y, 'missing' if faint else 'found')
    return out


def panel(case):
    c = CASES[case]
    out = ['<ellipse cx="315" cy="220" rx="300" ry="185" style="fill:none;stroke:#666666;'
           'stroke-width:5;stroke-dasharray:16,10" />']
    for args in c['missing']:
        out += contig(*args, faint=True)
    for args in c['contigs']:
        out += contig(*args)

    counts = {}
    for *_, genes in c['contigs']:
        for name, _ in genes:
            counts[name] = counts.get(name, 0) + 1

    lx = 670
    sx = lx + 232   # the status column

    def status(y, seen, names, absent_ok):
        if not any(seen) and absent_ok:
            return text(sx, y + 9, 'none: fine', size=24)
        if not all(seen):
            if names is None:
                return text(sx, y + 9, '1 missing', size=24, weight='bold', colour=BAD)
            gone = ', '.join(n for n, s in zip(names, seen) if not s)
            return text(sx, y + 9, f'no {gone}?', size=24, weight='bold', colour=BAD)
        if max(seen) > 1:
            what = '1 twice' if names is None else f'×{max(seen)}'
            return text(sx, y + 9, what, size=24, weight='bold', colour=BAD)
        return text(sx, y + 9, '✓', size=26)

    # The single-copy markers, as in CheckM1: all there, once.
    out.append(text(lx, 52, 'Single-copy markers', size=24, weight='bold'))
    names = [f'M{k}' for k in range(len(MARKERS))]
    seen = [counts.get(n, 0) for n in names]
    for k, (n, s) in enumerate(zip(names, seen)):
        out += gene(n, lx + 55 * k, 85, 'found' if s else 'missing')
    out.append(status(85, seen, None, absent_ok=False))

    # The groups: which of their genes the bin has.
    out.append(text(lx, 152, 'Gene groups', size=24, weight='bold'))
    for i, g in enumerate(GROUPS):
        y = 185 + 50 * i
        names = [f'{g}{k}' for k in (1, 2, 3)]
        seen = [counts.get(n, 0) for n in names]
        for k, (n, s) in enumerate(zip(names, seen)):
            state = 'found' if s else ('missing' if any(seen) else 'absent')
            out += gene(n, lx + 55 * k, y, state)
        out.append(status(y, seen, names, absent_ok=True))
    verdict, colour = VERDICT[case]
    out.append(text(lx, 375, verdict, size=26, weight='bold' if colour == BAD else 'normal',
                    colour=colour))
    return out


def combined():
    """The handout figure: the three bins, one above the other."""
    body = []
    th = H + 50
    for i, case in enumerate(CASES):
        body.append(f'<g transform="translate(0,{i * th})">')
        body.append(text(20, 32, TITLES[case], size=30, weight='bold'))
        body.append('<g transform="translate(0,45)">')
        body += ['  ' + line for line in panel(case)]
        body.append('</g>')
        body.append('</g>')
    return svg(W, th * len(CASES), body, 'checkm2')


def main(out):
    out = Path(out)
    name = out.stem
    if name == 'checkm2':
        doc = combined()
    else:
        case = name.removeprefix('checkm2_')
        if case not in CASES:
            sys.exit(f'checkm2.py: unknown figure {name!r} (cases: {", ".join(CASES)})')
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
        sys.exit(f'checkm2.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
