"""Draw how SingleM profiles a sample, in three steps.

Redrawn from media/SingleM-marker-gene-profiling.svg, in the style of the
CheckM1 cartoon (checkm1.py): reads are dark lines, the part of a read in a
marker gene's 20 amino-acid window a coloured box. (1) Screen the reads: keep
the few that cover the window of one of the 59 marker genes; (2) align them to
the marker's HMM, cut out the window, and group reads with the same window
sequence into OTUs; (3) give each OTU a taxonomy by comparing it with GTDB
genomes: the species if one is close enough, else a higher rank. The outputs
are the OTU table and the taxonomic profile. The deck adds one column at a
time; the handout figure has all three. A figure script whose output name
picks the figure:

    python media/singlem.py build/media/singlem.pdf          # the handout figure
    python media/singlem.py build/media/singlem_screen.svg   # one step of the deck

The steps (singlem_screen, _otus, _taxonomy) are listed in ../Makefile.
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import BAD, FAINT, GREY, TEXT, text

W, H = 1080, 470
LIGHT = '#888888'
READ = '#333333'
HIT = '#3c78d8'                       # a marker gene, as in checkm1.py
SEQ = ['#1b9e77', '#d95f02']          # two window sequences: two OTUs
STEPS = ['screen', 'otus', 'taxonomy']


def svg(width, height, body, name):
    return checkm1.svg(width, height, body, name,
                       about='how SingleM works, redrawn from '
                             'SingleM-marker-gene-profiling.svg')


def line(x0, x1, y, colour, width, dash=''):
    return (f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{colour};'
            f'stroke-width:{width};stroke-linecap:round{dash}" />')


def box(x0, x1, y, colour, h=16):
    return f'<rect x="{x0}" y="{y - h / 2}" width="{x1 - x0}" height="{h}" rx="3" style="fill:{colour}" />'


def arrow(x, y, length=22):
    return [f'<path d="M {x},{y} H {x + length}" style="fill:none;stroke:{GREY};stroke-width:3" />',
            f'<path d="M {x + length},{y - 8} L {x + length + 14},{y} L {x + length},{y + 8} Z" '
            f'style="fill:{GREY}" />']


def heading(x, title, sub):
    out = [text(x, 40, title, size=26, weight='bold')]
    for i, s in enumerate(sub):
        out.append(text(x, 72 + 24 * i, s, size=19, colour=LIGHT))
    return out


def screen():
    """Most reads miss the marker windows: only the hits go on."""
    out = heading(20, '1. Screen', ['DIAMOND: reads vs a 20 aa', 'window in each of 59',
                                    'marker genes'])
    reads = [  # (x, y, start of the window part, or None)
        (30, 160, None), (180, 160, 210),
        (50, 195, None), (200, 195, None),
        (30, 230, 70), (180, 230, None),
        (60, 265, None), (190, 265, None),
        (30, 300, None), (170, 300, 175),
    ]
    for x, y, hit in reads:
        if hit is None:
            out.append(line(x, x + 100, y, FAINT, 5, ';stroke-dasharray:4,10'))
        else:
            out.append(line(x, x + 100, y, READ, 7))
            out.append(box(hit, hit + 50, y, HIT))
    # A marker gene, and its window.
    out.append(f'<rect x="30" y="336" width="280" height="28" rx="4" '
               f'style="fill:#ffffff;stroke:{GREY};stroke-width:3" />')
    out.append(f'<rect x="145" y="336" width="50" height="28" '
               f'style="fill:{HIT};stroke:{GREY};stroke-width:3" />')
    out.append(text(30, 392, 'a marker gene, its window', size=19, colour=LIGHT))
    out.append(text(20, 444, 'most reads miss every window', size=19, colour=LIGHT))
    return out


WX0, WX1 = 480, 560     # the window, on the HMM and on the reads


def otus():
    """Align the hits to the marker's HMM; group them by their window sequence."""
    out = heading(370, '2. Group into OTUs', ['align to the HMM; same', 'window sequence: one OTU'])
    for x in (WX0, WX1):
        out.append(f'<path d="M {x},{125} V {350}" style="fill:none;stroke:{GREY};'
                   'stroke-width:2;stroke-dasharray:6,5" />')
    # A read that ends before the window: no window sequence, dropped.
    out.append(line(380, 460, 145, READ, 7))
    out.append(text(WX0 + (WX1 - WX0) / 2, 155, '✗', size=30, anchor='middle', weight='bold',
                    colour=BAD))
    for x0, x1, y, seq in [(420, 600, 195, 0), (450, 640, 240, 0), (470, 660, 285, 1)]:
        out.append(line(x0, x1, y, READ, 7))
        out.append(box(WX0, WX1, y, SEQ[seq]))
    out.append(f'<rect x="380" y="320" width="300" height="28" rx="4" '
               f'style="fill:#ffffff;stroke:{GREY};stroke-width:3" />')
    out.append(f'<rect x="{WX0}" y="320" width="{WX1 - WX0}" height="28" '
               f'style="fill:{HIT};stroke:{GREY};stroke-width:3" />')
    out.append(text(380, 378, 'marker gene (HMM)', size=19, colour=LIGHT))
    out.append(text(380, 420, 'reads missing the', size=19, colour=LIGHT))
    out.append(text(380, 444, 'window are dropped', size=19, colour=LIGHT))

    # Brackets: OTU 1 (two reads), OTU 2 (one).
    for y0, y1, label in [(185, 250, 'OTU 1'), (275, 295, 'OTU 2')]:
        out.append(f'<path d="M 680,{y0} H 692 V {y1} H 680" style="fill:none;'
                   f'stroke:{TEXT};stroke-width:2.5" />')
        out.append(text(702, (y0 + y1) / 2 + 7, label, size=20))
    out += arrow(345, 240, 10)
    return out


def taxonomy():
    """Give each OTU a taxonomy, as precise as the reference genomes allow."""
    out = heading(800, '3. Taxonomy', ['compare the windows', 'with GTDB genomes'])
    rows = [(SEQ[0], 'OTU 1', '×2', 'E. coli', 'close match: species'),
            (SEQ[1], 'OTU 2', '×1', 'Yersinia', 'no close match: genus')]
    for i, (colour, name, n, taxon, why) in enumerate(rows):
        y = 160 + 90 * i
        out.append(box(800, 850, y, colour, h=22))
        out.append(text(862, y + 8, f'{name} {n}', size=20))
        out.append(text(820, y + 42, f'→ <tspan font-style="italic">{taxon}</tspan>', size=22))
        out.append(text(840, y + 66, why, size=17, colour=LIGHT))
    out.append(text(800, 384, 'Output', size=22, weight='bold'))
    out.append(text(800, 416, 'OTU table (per marker)', size=19))
    out.append(text(800, 444, 'taxonomic profile', size=19))
    out += arrow(760, 240, 10)
    return out


def figure(upto):
    body = []
    for step, draw in zip(STEPS, [screen, otus, taxonomy]):
        body += draw()
        if step == upto:
            break
    return body


def main(out):
    out = Path(out)
    name = out.stem
    if name == 'singlem':
        doc = svg(W, H, figure('taxonomy'), name)
    else:
        step = name.removeprefix('singlem_')
        if step not in STEPS:
            sys.exit(f'singlem.py: unknown figure {name!r} (steps: {", ".join(STEPS)})')
        doc = svg(W, H, figure(step), name)
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'singlem.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
