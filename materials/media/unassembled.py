"""Draw why not all reads end up in a MAG.

Four genomes in the sample, one row each: the genome (a faint dashed line),
its reads above it, and what becomes of them on the right. The abundant
genome assembles; the rare one leaves gaps; two strains (or repeats) break the
assembly; a eukaryote has a genome too large to cover, and tools built for
prokaryotes.

Reads are short lines in the colours of the binning cartoons; the rest of the
style is that of the CheckM1 cartoon (checkm1.py). A figure script:

    python media/unassembled.py build/media/unassembled.pdf
"""
import subprocess
import sys
from pathlib import Path

import checkm1
from checkm1 import BAD, FAINT, GREY, TEXT, text

W, H = 1080, 500
LIGHT = '#888888'
X0, X1 = 310, 650        # the genome
RL = 70                  # read length
LANE = 20                # distance between lanes of reads

# (y, title, details, colour, reads as lanes of start positions (from X0),
#  outcome, colour of the outcome)
ROWS = [
    (60, 'Abundant genome', ['high coverage'], '#7570b3',
     [[0, 90, 180, 270], [40, 130, 220], [75, 165, 255]],
     ['Assembled:', 'a MAG'], TEXT),
    (185, 'Rare genome', ['coverage too low'], '#e7298a',
     [[0, 160]],
     ['Gaps: contigs', 'too short to bin'], BAD),
    (290, 'Strains, repeats', ['almost identical', 'sequences'], '#66a61e',
     [[0, 90, 180, 270], [45, 135, 225]],
     ['Assembly breaks', 'into pieces'], BAD),
    (415, 'Eukaryotes', ['often huge genomes'], '#a6761d',
     [[60, 250]],
     ['Often too big', 'to cover; tools', 'mostly for bacteria'], BAD),
]
SNPS = [80, 165, 200, 250]   # where the second strain differs (from X0)


def svg(width, height, body, name):
    return checkm1.svg(width, height, body, name,
                       about='why not all reads end up in a MAG')


def line(x0, x1, y, colour, width, dash=''):
    return (f'<path d="M {x0},{y} H {x1}" style="fill:none;stroke:{colour};'
            f'stroke-width:{width};stroke-linecap:round{dash}" />')


def row(y, title, details, colour, lanes, outcome, oc):
    out = [text(20, y + 6, title, size=26, weight='bold')]
    for i, d in enumerate(details):
        out.append(text(40, y + 36 + 26 * i, d, size=20, colour=LIGHT))

    euk = title == 'Eukaryotes'
    gy = y + LANE * len(lanes)
    end = X1 + 50 if euk else X1
    out.append(line(X0, end, gy, FAINT, 4, ';stroke-dasharray:4,10'))
    if euk:
        out.append(text(end + 12, gy + 6, '…', size=22, colour=LIGHT))
    for i, starts in enumerate(lanes):
        yy = y + LANE * i
        for s in starts:
            out.append(line(X0 + s, X0 + s + RL, yy, colour, 7))
            if title.startswith('Strains') and i == 1:
                # The second strain: the same sequence, but for a few SNPs.
                for x in SNPS:
                    if s + 6 < x < s + RL - 6:
                        out.append(f'<rect x="{X0 + x - 3}" y="{yy - 8}" width="6" '
                                   f'height="16" style="fill:{TEXT}" />')

    ay = y + LANE * (len(lanes) - 1) / 2
    ax = X1 + 85
    out.append(line(ax, ax + 40, ay, GREY, 3).replace(';stroke-linecap:round', ''))
    out.append(f'<path d="M {ax + 40},{ay - 8} L {ax + 54},{ay} L {ax + 40},{ay + 8} Z" '
               f'style="fill:{GREY}" />')
    weight = 'normal' if oc == TEXT else 'bold'
    for i, s in enumerate(outcome):
        out.append(text(ax + 70, ay + 7 + 28 * i, s, size=22, weight=weight, colour=oc))
    return out


def main(out):
    out = Path(out)
    body = []
    for r in ROWS:
        body += row(*r)
    doc = svg(W, H, body, out.stem)
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'unassembled.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
