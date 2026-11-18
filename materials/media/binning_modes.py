"""Draw the four ways to bin several samples (redrawn from slide 9 of the MAG
QC deck, itself from Pan et al. 2022, Nature Communications, Fig. 1).

Each panel has three samples: their reads (purple documents) are mapped
(green arrows) to contigs (orange boxes holding contigs, drawn as grey lines,
as in the binning cartoons). The number of mappings, and of coverage values
per contig, is what differs between the four.

A figure script (see common/workshop.mk):

    python media/binning_modes.py build/media/binning_modes.svg
"""
import subprocess
import sys
from pathlib import Path

from checkm1 import GREY, TEXT, svg, text

PW, PH = 560, 365           # one panel
W, H = 2 * PW, 2 * PH
READ = ('#5e35b1', '#ede7f6')
CONTIG = ('#ef6c00', '#fff3e0')
MAP = '#2e7d32'
SUB = '#666666'
XS = [120, 280, 440]         # centres of the three samples
READ_Y, CONTIG_Y = 112, 250   # tops of the read and contig icons


def reads(cx, n):
    """A document with a folded corner, filled with short reads."""
    stroke, fill = READ
    x, y, w, h, f = cx - 38, READ_Y, 76, 88, 18
    out = [f'<path d="M {x},{y} H {x + w - f} L {x + w},{y + f} V {y + h} H {x} Z" '
           f'style="fill:{fill};stroke:{stroke};stroke-width:3;stroke-linejoin:round" />',
           f'<path d="M {x + w - f},{y} V {y + f} H {x + w}" '
           f'style="fill:none;stroke:{stroke};stroke-width:3;stroke-linejoin:round" />']
    # Short reads: rows of dashes, offset from row to row.
    for i, ry in enumerate(range(y + 16, y + h - 8, 12)):
        off = 6 * (i % 3)
        out.append(f'<path d="M {x + 10 + off},{ry} H {x + w - 10}" style="fill:none;'
                   f'stroke:{stroke};stroke-width:4;stroke-dasharray:12,5;opacity:0.55" />')
    out.append(text(cx, y - 8, n, size=17, anchor='middle', weight='bold', colour=stroke))
    return out


def contigs(cx, label, w=120, lines=((0.15, 0.85), (0.1, 0.65), (0.3, 0.9))):
    """A box of contigs (grey lines of varying length)."""
    stroke, fill = CONTIG
    x, y, h = cx - w / 2, CONTIG_Y, 74
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
           f'style="fill:{fill};stroke:{stroke};stroke-width:3" />']
    for i, (a, b) in enumerate(lines):
        ly = y + 34 + 13 * i
        out.append(f'<path d="M {x + a * w},{ly} H {x + b * w}" style="fill:none;'
                   f'stroke:{GREY};stroke-width:6;stroke-linecap:round" />')
    out.append(text(cx, y + 20, label, size=16, anchor='middle', weight='bold', colour=stroke))
    return out


def arrow(x0, x1, y1=CONTIG_Y - 4):
    y0 = READ_Y + 92
    return [f'<path d="M {x0},{y0} L {x1},{y1}" style="fill:none;stroke:{MAP};'
            f'stroke-width:3" marker-end="url(#map-arrow)" />']


def container(x0, x1, label):
    """The dashed box around contigs that are assembled or binned together."""
    y0, y1 = CONTIG_Y - 12, CONTIG_Y + 86
    return [f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" '
            f'style="fill:none;stroke:{CONTIG[0]};stroke-width:2.5;stroke-dasharray:9,6" />',
            text((x0 + x1) / 2, y1 + 21, label, size=16, anchor='middle', colour=CONTIG[0])]


def header(title, sub):
    return [text(24, 34, title, size=24, weight='bold'),
            text(24, 64, sub, size=18, colour=SUB)]


def single():
    out = header('Single-sample', '3 mappings · 1 coverage per contig')
    for i, x in enumerate(XS, 1):
        out += reads(x, f'Reads {i}') + contigs(x, f'Contigs {i}') + arrow(x, x)
    return out


def coassembly():
    out = header('Co-assembly', '3 mappings · 3 coverages per contig')
    out += container(50, 510, 'one assembly of all reads')
    out += contigs(280, 'Contigs', w=240,
                   lines=((0.08, 0.6), (0.3, 0.95), (0.12, 0.8)))
    for i, x in enumerate(XS, 1):
        out += reads(x, f'Reads {i}') + arrow(x, 280 + (x - 280) * 0.45)
    return out


def multi():
    out = header('Multi-sample', '9 mappings · 3 coverages per contig')
    for i, x in enumerate(XS, 1):
        out += reads(x, f'Reads {i}') + contigs(x, f'Contigs {i}')
    for x0 in XS:
        for x1 in XS:
            out += arrow(x0, x1 + (x0 - x1) * 0.2)
    return out


def concatenated():
    out = header('Concatenated', '3 mappings · 3 coverages per contig')
    out += container(50, 510, 'one file, binned together, then split by sample')
    for i, x in enumerate(XS, 1):
        out += reads(x, f'Reads {i}') + contigs(x, f'Contigs {i}') + arrow(x, x, CONTIG_Y - 16)
    return out


def figure():
    body = ['<defs>',
            f'  <marker id="map-arrow" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="4" markerHeight="4" orient="auto-start-reverse">',
            f'    <path d="M 0,0 L 10,5 L 0,10 z" style="fill:{MAP}" />',
            '  </marker>',
            '</defs>',
            f'<rect x="0" y="0" width="{W}" height="{H}" style="fill:#ffffff" />']
    panels = [single, coassembly, multi, concatenated]
    for i, panel in enumerate(panels):
        x, y = PW * (i % 2), PH * (i // 2)
        body.append(f'<g transform="translate({x},{y})">')
        body += ['  ' + line for line in panel()]
        body.append('</g>')
    # Separators between the panels.
    body.append(f'<path d="M {PW},16 V {H - 16} M 16,{PH} H {W - 16}" '
                f'style="fill:none;stroke:#cccccc;stroke-width:2" />')
    return svg(W, H, body, 'binning_modes',
               about='four ways to bin several samples, redrawn from the MAG QC deck (slide 9)')


def main(out):
    out = Path(out)
    doc = figure()
    fmt = out.suffix[1:]
    if fmt == 'svg':
        out.write_text(doc)
    elif fmt in ('pdf', 'png'):
        dpi = ['-d', '150', '-p', '150'] if fmt == 'png' else []
        subprocess.run(['rsvg-convert', '-f', fmt, *dpi, '-o', str(out)],
                       input=doc.encode(), check=True)
    else:
        sys.exit(f'binning_modes.py: cannot write {out.suffix!r} files')


if __name__ == '__main__':
    main(sys.argv[1])
