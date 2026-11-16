"""Draw the CheckM1 cartoon (redrawn from slide 7 of the MAG QC deck).

A bin is a set of contigs (grey lines) in a dashed ellipse, as in the binning
cartoons; single-copy marker genes are coloured boxes on the contigs. On the
right, a tally of how often each marker is found, and the resulting
completeness and contamination.

A figure script (see common/workshop.mk), with one twist: the name of the
output picks the figure.

    python media/checkm1.py build/media/checkm1.pdf             # the handout figure
    python media/checkm1.py build/media/checkm1_complete.svg    # one step of the deck

The steps (checkm1_markers, _complete, _incomplete, _contaminated) are listed
in ../Makefile, and the deck refers to them as media/checkm1_STEP.svg, found
under build/ through --resource-path.
"""
import subprocess
import sys
from pathlib import Path

W, H = 1080, 440
GREY = '#666666'
FAINT = '#c8c8c8'
TEXT = '#333333'
BAD = '#d62728'
FONT = "font-family:'DejaVu Sans',sans-serif"
MARKERS = ['#f1c232', '#3c78d8', '#8e7cc3', '#990000']

# Contigs: (y, x0, x1, [(marker, x)]); marker boxes are 70 wide.
GOOD = [
    (110, 90, 520, [(0, 180)]),
    (165, 110, 500, [(1, 300)]),
    (220, 80, 440, [(2, 150)]),
    (275, 120, 540, [(3, 210)]),
]
CONTAMINANT = (330, 160, 460, [(2, 330)])

CASES = {
    'markers':      dict(contigs=[c[:3] + ([],) for c in GOOD], missing=[], counts=None),
    'complete':     dict(contigs=GOOD, missing=[]),
    'incomplete':   dict(contigs=GOOD[:3], missing=[GOOD[3]]),
    'contaminated': dict(contigs=GOOD + [CONTAMINANT], missing=[]),
}
TITLES = {
    'complete': 'A good bin',
    'incomplete': 'An incomplete bin',
    'contaminated': 'A contaminated bin',
}


def contig(y, x0, x1, genes, faint=False):
    colour = FAINT if faint else GREY
    dash = ';stroke-dasharray:4,10' if faint else ''
    out = [f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{colour};'
           f'stroke-width:10;stroke-linecap:round{dash}" />']
    for m, x in genes:
        style = (f'fill:none;stroke:{MARKERS[m]};stroke-width:3;stroke-dasharray:6,4'
                 if faint else f'fill:{MARKERS[m]}')
        out.append(f'<rect x="{x}" y="{y - 11}" width="70" height="22" rx="3" style="{style}" />')
    return out


def text(x, y, s, size=26, anchor='start', weight='normal', colour=TEXT):
    return (f'<text x="{x}" y="{y}" style="{FONT};font-size:{size}px;'
            f'font-weight:{weight};fill:{colour};text-anchor:{anchor}">{s}</text>')


def panel(case, title=None):
    c = CASES[case]
    out = []
    if title:
        out.append(text(20, 38, title, size=28, weight='bold'))
    out.append('<ellipse cx="315" cy="220" rx="300" ry="185" style="fill:none;stroke:#666666;'
               'stroke-width:5;stroke-dasharray:16,10" />')
    for y, x0, x1, genes in c['missing']:
        out += contig(y, x0, x1, genes, faint=True)
    for y, x0, x1, genes in c['contigs']:
        out += contig(y, x0, x1, genes)

    counts = [0] * len(MARKERS)
    for *_, genes in c['contigs']:
        for m, _ in genes:
            counts[m] += 1

    # The tally: each marker gene, and how many copies the bin has.
    lx = 670
    out.append(text(lx, 75, 'Marker genes', size=26, weight='bold'))
    for i, colour in enumerate(MARKERS):
        y = 110 + 55 * i
        out.append(f'<rect x="{lx}" y="{y - 11}" width="70" height="22" rx="3" style="fill:{colour}" />')
        if c.get('counts', True) is not None:
            n = counts[i]
            out.append(text(lx + 95, y + 9, f'×{n}', size=28,
                            weight='normal' if n == 1 else 'bold',
                            colour=TEXT if n == 1 else BAD))
    if case == 'markers':
        out.append(text(lx, 345, 'each expected', size=26))
        out.append(text(lx, 380, 'exactly once', size=26, weight='bold'))
    else:
        n = len(MARKERS)
        found = sum(1 for k in counts if k > 0)
        extra = sum(k - 1 for k in counts if k > 1)
        out.append(text(lx, 345, f'Completeness: {found}/{n} = {100 * found // n}%', size=26,
                        colour=TEXT if found == n else BAD, weight='normal' if found == n else 'bold'))
        out.append(text(lx, 385, f'Contamination: {extra}/{n} = {100 * extra // n}%', size=26,
                        colour=TEXT if extra == 0 else BAD, weight='normal' if extra == 0 else 'bold'))
    return out


def svg(width, height, body, name,
        about='CheckM1 cartoon, redrawn from the MAG QC deck (slide 7)'):
    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<!-- {name}: {about}. -->',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" id="svg-{name}">',
        *('  ' + line for line in body),
        '</svg>', ''])


def combined():
    """The handout figure: the three bins, one above the other."""
    body = []
    cases = ['complete', 'incomplete', 'contaminated']
    th = H + 50
    for i, case in enumerate(cases):
        body.append(f'<g transform="translate(0,{i * th})">')
        body.append(text(20, 32, TITLES[case], size=30, weight='bold'))
        body.append('<g transform="translate(0,45)">')
        body += ['  ' + line for line in panel(case)]
        body.append('</g>')
        body.append('</g>')
    return svg(W, th * len(cases), body, 'checkm1')


def main(out):
    out = Path(out)
    name = out.stem
    if name == 'checkm1':
        doc = combined()
    else:
        case = name.removeprefix('checkm1_')
        if case not in CASES:
            sys.exit(f'checkm1.py: unknown figure {name!r} (cases: {", ".join(CASES)})')
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
        sys.exit(f'checkm1.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
