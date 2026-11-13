"""Check that the commands in the workshop notes match metag-ws.

Every command that `metag-ws show-cmd` prints for a participant who has run all
the steps themselves (no `results-for`), with 8 threads, must appear verbatim
as a ```bash block in metagenomics-workshop.md. Run in the default pixi
environment (it imports metag_ws):

    pixi run check-commands
"""
import re
import sys
from pathlib import Path

from metag_ws.cli import Context, Renderer, Steps

NOTES = Path(__file__).with_name('metagenomics-workshop.md')
THREADS = 8   # what the notes say (Conventions slide)


def main():
    blocks = {b.strip('\n') for b in re.findall(r'^```bash\n(.*?)^```', NOTES.read_text(), re.S | re.M)}
    ctx = Context(workdir=Path('/nonexistent'), data='/opt/metag-ws/data',
                  precomputed=Path('/nonexistent'), threads=THREADS, upto=None)
    r = Renderer(Steps(), ctx)
    missing = [(st.id, c) for st in r.steps.leaves for c in r.commands(st) if c not in blocks]
    for sid, c in missing:
        print(f'step {sid}: not in {NOTES.name}:\n{c}\n')
    if missing:
        sys.exit(f'FAIL: {len(missing)} command(s) differ from metag-ws (metag_ws/steps.toml)')
    print(f'OK: every metag-ws command is in {NOTES.name}')


if __name__ == '__main__':
    main()
