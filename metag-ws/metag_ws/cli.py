"""metag-ws: the metagenomics workshop helper.

    metag-ws show-cmd [STEP]       print the command(s) of a step
    metag-ws explain-cmd [STEP]    the same, with every argument explained
    metag-ws results-for [STEP]    bring in the precomputed results up to STEP
    metag-ws get-data              step 1 in one go: copy the reads into 01_DATA/

Without STEP, a menu of the steps is shown. The steps, their commands and the
explanations are in steps.toml (next to this file). Results-only steps (too
large for the workshop machine) show their commands, but participants look at
the precomputed results instead.

Hidden, for testing and for building the precomputed results:

    metag-ws _run-all -o DIR [--data DIR] [-t THREADS] [--until STEP] [--skip-results-only]

Configuration (environment variables; the defaults are for the workshop
machine):

    METAG_WS_DIR          participant's working directory (~/workshop)
    METAG_WS_DATA         shared directory with the reads (/opt/metag-ws/data)
    METAG_WS_PRECOMPUTED  shared precomputed results (/opt/metag-ws/precomputed)
    METAG_WS_THREADS      threads per participant (8)
    METAG_WS_BACKGROUND   light or dark, to override the terminal's (detected)
    METAG_WS_MENU         plain: a typed menu instead of the arrow-key one
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

STEPS_FILE = Path(__file__).with_name('steps.toml')
PRECOMPUTED_SUFFIX = '_precomputed'
PLACEHOLDER = re.compile(r'\{(\d+(?:\.\d+)?|threads|threads_fastp|data)\}')
# databases that the commands use through environment variables (set by pixi)
DB_VARS = ['SINGLEM_METAPACKAGE_PATH', 'CHECKM2DB', 'GUNC_DB', 'EGGNOG_DATA_DIR', 'GTDBTK_DATA_PATH']

out = Console(highlight=False)
err = Console(stderr=True, highlight=False, soft_wrap=True)


# --- colours ------------------------------------------------------------------
# Plain ANSI yellow and cyan are hard to read on a light background, so the
# styles depend on the terminal's background (detected in setup_colours).

THEMES = {
    'dark': Theme({'warn': 'yellow', 'error': 'red', 'arg': 'bold cyan',
                   'tag.precomputed': 'cyan', 'tag.done': 'green', 'tag.last': 'yellow'}),
    'light': Theme({'warn': 'dark_orange3', 'error': 'red3', 'arg': 'bold blue',
                    'tag.precomputed': 'blue', 'tag.done': 'green4', 'tag.last': 'dark_orange3',
                    'rule.line': 'green4'}),
}
SYNTAX_THEME = {'dark': 'ansi_dark', 'light': 'ansi_light'}
BACKGROUND = 'dark'


def query_terminal_background(timeout=0.5):
    """Ask the terminal for its background colour (OSC 11); 'light', 'dark' or None.

    A device-attributes query (DA1), which practically all terminals answer, is
    sent right after, so terminals that ignore OSC 11 do not cost the timeout.
    """
    import select
    import termios
    try:
        fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return None
    try:
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ICANON | termios.ECHO)
        new[6][termios.VMIN] = 0
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new)
        try:
            os.write(fd, b'\033]11;?\033\\\033[c')
            buf = b''
            deadline = time.monotonic() + timeout
            while not re.search(rb'\033\[\?[\d;]*c', buf):
                left = deadline - time.monotonic()
                if left <= 0 or not select.select([fd], [], [], left)[0]:
                    break
                chunk = os.read(fd, 1024)
                if not chunk:
                    break
                buf += chunk
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, old)
    except (OSError, termios.error):
        return None
    finally:
        os.close(fd)
    m = re.search(rb'\]11;rgba?:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)', buf)
    if not m:
        return None
    r, g, b = (int(x, 16) / (16 ** len(x) - 1) for x in m.groups())
    return 'light' if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else 'dark'


def detect_background():
    """'light' or 'dark': METAG_WS_BACKGROUND, else ask the terminal, else COLORFGBG, else dark"""
    forced = os.environ.get('METAG_WS_BACKGROUND', '').lower()
    if forced in ('light', 'dark'):
        return forced
    if not (out.is_terminal and out.color_system) or os.environ.get('TERM') == 'dumb':
        return 'dark'
    bg = query_terminal_background()
    if bg:
        return bg
    # e.g. COLORFGBG=0;15 (black on white), set by rxvt, konsole and others
    fgbg = os.environ.get('COLORFGBG', '').split(';')[-1]
    if fgbg.isdigit():
        return 'light' if int(fgbg) in (7, 15) else 'dark'
    return 'dark'


def setup_colours():
    global BACKGROUND
    BACKGROUND = detect_background()
    for c in (out, err):
        c.push_theme(THEMES[BACKGROUND])


class UserError(Exception):
    pass


# --- steps --------------------------------------------------------------------

def step_key(sid):
    return tuple(int(x) for x in sid.split('.'))


@dataclass
class Step:
    id: str
    title: str
    folder: str
    parent: 'Step | None'
    children: list
    cmds: list
    outputs: list
    look_at: str
    results_only: str   # why the step is not run in the workshop ('' if it is)

    @property
    def is_leaf(self):
        return not self.children

    @property
    def top(self):
        return self.parent or self

    def full_title(self):
        if self.parent:
            return f'{self.parent.title}: {self.title}'
        return self.title

    def leaves(self):
        return self.children or [self]


class Steps:
    def __init__(self, path=STEPS_FILE):
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        self.by_id = {}
        self.order = []   # all steps, in menu order
        for d in data['step']:
            sid = d['id']
            parent = None
            if '.' in sid:
                parent = self.by_id[sid.split('.')[0]]
            st = Step(id=sid, title=d['title'],
                      folder=parent.folder if parent else d['folder'],
                      parent=parent, children=[], cmds=d.get('cmd', []),
                      outputs=d.get('outputs', []), look_at=d.get('look_at', '').strip(),
                      results_only=d.get('results_only', parent.results_only if parent else '').strip())
            if parent:
                parent.children.append(st)
            self.by_id[sid] = st
            self.order.append(st)
        self.tops = [s for s in self.order if s.parent is None]
        self.leaves = [s for s in self.order if s.is_leaf]
        for st in self.leaves:
            for c in st.cmds:
                for ref in PLACEHOLDER.findall(c['run']):
                    if ref[0].isdigit() and not self.by_id[ref].is_leaf:
                        raise ValueError(f'step {st.id}: {{{ref}}} must name a substep')

    def get(self, sid):
        """Step from user input ('5', '5.2', '05')."""
        try:
            norm = '.'.join(str(int(x)) for x in sid.strip().split('.'))
        except ValueError:
            norm = None
        if norm not in self.by_id:
            raise UserError(f'Unknown step: {sid} (steps are {self.tops[0].id} to {self.tops[-1].id}; '
                            'run without a step for the menu)')
        return self.by_id[norm]

    def next_after(self, st):
        """The default choice after `st`: the next step at the same level
        (after a whole step, the next whole step; after a substep, the next
        substep, or the next step if it has none)."""
        seq = self.tops if st.parent is None else self.leaves
        i = seq.index(st)
        return seq[i + 1] if i + 1 < len(seq) else st


# --- configuration and state ----------------------------------------------------

@dataclass
class Context:
    workdir: Path
    data: str
    precomputed: Path
    threads: int
    upto: str | None   # leaf id of the last precomputed step, or None


def config_from_env():
    threads = os.environ.get('METAG_WS_THREADS', '8')
    try:
        threads = int(threads)
    except ValueError:
        raise UserError(f'METAG_WS_THREADS must be a number (it is "{threads}")')
    return dict(
        workdir=Path(os.path.expanduser(os.environ.get('METAG_WS_DIR', '~/workshop'))),
        data=os.environ.get('METAG_WS_DATA', '/opt/metag-ws/data'),
        precomputed=Path(os.environ.get('METAG_WS_PRECOMPUTED', '/opt/metag-ws/precomputed')),
        threads=threads,
    )


def state_path():
    base = os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state')
    return Path(base) / 'metag-ws' / 'state.json'


def load_state():
    try:
        with open(state_path()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, p)


# --- rendering commands -----------------------------------------------------------

def is_precomputed(ref, current, ctx):
    """Whether the outputs of leaf `ref` come from the precomputed results
    when running step `current` (whose own outputs are always its own)."""
    return (ref.id != current.id and ctx.upto is not None
            and step_key(ref.id) <= step_key(ctx.upto))


def folder_of(ref, current, ctx):
    return ref.folder + (PRECOMPUTED_SUFFIX if is_precomputed(ref, current, ctx) else '')


class Renderer:
    def __init__(self, steps, ctx):
        self.steps = steps
        self.ctx = ctx

    def render(self, text, current, precomputed=False):
        """Fill in the placeholders of `text`, for step `current`. With
        `precomputed`, every step's folder is its precomputed one."""
        def sub(m):
            key = m.group(1)
            if key == 'threads':
                return str(self.ctx.threads)
            if key == 'threads_fastp':
                return str(min(self.ctx.threads, 16))
            if key == 'data':
                return self.ctx.data
            ref = self.steps.by_id[key]
            return ref.folder + PRECOMPUTED_SUFFIX if precomputed else folder_of(ref, current, self.ctx)
        return PLACEHOLDER.sub(sub, text)

    def look_at(self, st):
        """What to look at after `st`: in our results for a results-only step."""
        return self.render(st.look_at, st, precomputed=bool(st.results_only))

    def commands(self, st):
        return [self.render(c['run'], st).strip('\n') for c in st.cmds]

    def inputs(self, st):
        """Leaves whose outputs `st` reads, in order."""
        refs = set()
        for c in st.cmds:
            refs.update(r for r in PLACEHOLDER.findall(c['run']) if r[0].isdigit() and r != st.id)
        return sorted((self.steps.by_id[r] for r in refs), key=lambda s: step_key(s.id))

    def missing_inputs(self, st):
        """[(input step, folder)] for inputs whose outputs are not there."""
        missing = []
        for ref in self.inputs(st):
            folder = self.ctx.workdir / folder_of(ref, st, self.ctx)
            if not all(glob.glob(str(folder / o)) for o in ref.outputs):
                missing.append((ref, folder_of(ref, st, self.ctx)))
        return missing

    def header(self, st):
        """Comment lines above the commands of leaf `st`."""
        lines = [f'# Step {st.id}: {st.full_title()}']
        pre = sorted({folder_of(r, st, self.ctx) for r in self.inputs(st) if is_precomputed(r, st, self.ctx)})
        if pre:
            lines.append(f'# Using precomputed inputs: {", ".join(pre)} '
                         f'(metag-ws results-for {self.ctx.upto})')
        return lines


def done_outputs(st, workdir):
    return bool(st.outputs) and all(glob.glob(str(workdir / st.folder / o)) for o in st.outputs)


# --- the menu -------------------------------------------------------------------

def menu_label(st, ctx, last):
    """The menu line of `st` (markup), without the cursor mark."""
    sub = st.parent is not None
    label = f'{st.id:>{6 if sub else 4}}  {escape(st.title)}'
    tags = []
    if st.is_leaf and (ctx.upto and step_key(st.id) <= step_key(ctx.upto)
                       or st.results_only and (ctx.workdir / (st.folder + PRECOMPUTED_SUFFIX)).exists()):
        tags.append('[tag.precomputed]precomputed[/]')
    if st.is_leaf and done_outputs(st, ctx.workdir):
        tags.append('[tag.done]done[/]')
    if st is last:
        tags.append('[tag.last]last used[/]')
    return f'{label:<{58 if sub else 60}} {" ".join(tags)}'


def use_key_menu():
    return (os.environ.get('METAG_WS_MENU', '').lower() != 'plain'
            and sys.stdin.isatty() and out.is_terminal and os.environ.get('TERM') != 'dumb')


def choose_step(steps, state, ctx, action):
    """The step chosen in the menu, or None. The menu starts on the step
    after the last one used."""
    last = steps.by_id.get(state.get('last', ''))
    default = steps.next_after(last) if last else steps.tops[0]
    labels = [menu_label(st, ctx, last) for st in steps.order]
    if use_key_menu():
        import termios
        try:
            return KeyMenu(steps, labels, default, action).run()
        except termios.error:
            pass   # not a real terminal after all: the typed menu
    return choose_step_typed(steps, labels, last, default, action)


class KeyMenu:
    """Choose with the arrow keys (or j/k, PgUp/PgDn, Home/End) and Enter, or
    type a step number (the cursor follows) and Enter.

    Drawn inline (not full screen), at most as tall as the terminal (scrolling
    if needed), and erased when done, so the output that follows is the same
    as with the step on the command line.
    """
    KEYS = {'\x1b[A': 'up', '\x1bOA': 'up', 'k': 'up',
            '\x1b[B': 'down', '\x1bOB': 'down', 'j': 'down',
            '\x1b[5~': 'pgup', '\x1b[6~': 'pgdown',
            '\x1b[H': 'home', '\x1bOH': 'home', '\x1b[1~': 'home', '\x1b[7~': 'home',
            '\x1b[F': 'end', '\x1bOF': 'end', '\x1b[4~': 'end', '\x1b[8~': 'end',
            '\r': 'enter', '\n': 'enter', '\x7f': 'backspace', '\x08': 'backspace',
            'q': 'quit', 'Q': 'quit', '\x1b': 'quit', '\x04': 'quit', '\x03': 'interrupt'}
    KEY_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z~]|\x1bO[A-Za-z]|.', re.DOTALL)
    INCOMPLETE = re.compile(r'\x1b(\[[0-9;]*|O)?\Z')   # an escape sequence cut short
    HINT = '[dim]Up/Down to move, Enter to choose, or type a step number; q to quit[/]'

    def __init__(self, steps, labels, default, action):
        self.steps = steps
        self.rows = steps.order
        self.labels = labels
        self.action = action
        self.cursor = self.rows.index(default)
        self.top = 0          # first row shown, when they do not all fit
        self.typed = ''       # step number being typed
        self.message = ''
        self.drawn = 0        # lines on screen
        self.drawn_size = None
        self.result = None

    def write(self, s):
        sys.stdout.write(s)
        sys.stdout.flush()

    def size(self):
        try:
            return tuple(os.get_terminal_size(sys.stdout.fileno()))
        except OSError:
            return (80, 24)

    def run(self):
        import codecs
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        # no line editing or echo; Ctrl-C arrives as a key, so the terminal is
        # restored and the menu erased before stopping
        new[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new)
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.write('\033[?25l')   # hide the cursor
        try:
            self.draw()
            while True:
                for key in self.keys(fd):
                    if self.handle(key):
                        return self.result
                self.draw()
        finally:
            self.erase()
            self.write('\033[?25h')
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def keys(self, fd):
        """The next keys pressed ([] if the terminal was resized)."""
        import select
        while not select.select([fd], [], [], 0.25)[0]:
            if self.size() != self.drawn_size:
                return []
        chunk = os.read(fd, 1024)
        if not chunk:
            return ['\x04']
        data = self.decoder.decode(chunk)
        while self.INCOMPLETE.search(data) and select.select([fd], [], [], 0.05)[0]:
            data += self.decoder.decode(os.read(fd, 1024))
        return self.KEY_RE.findall(data)

    def handle(self, key):
        """Act on `key`; True when done (the choice in self.result)."""
        k = self.KEYS.get(key, key)
        self.message = ''
        if k == 'interrupt':
            raise KeyboardInterrupt
        if k == 'quit':
            return True
        if k == 'enter':
            if not self.typed:
                self.result = self.rows[self.cursor]
                return True
            try:
                self.result = self.steps.get(self.typed)
                return True
            except UserError:
                self.message = f'No step {self.typed}'
                self.typed = ''
                return False
        if k == 'backspace' or (len(k) == 1 and (k.isdigit() or k == '.')):
            self.typed = self.typed[:-1] if k == 'backspace' else self.typed + k
            try:
                self.cursor = self.rows.index(self.steps.get(self.typed))
            except UserError:
                pass
            return False
        page = max(self.size()[1] - 6, 1)
        moves = {'up': -1, 'down': 1, 'pgup': -page, 'pgdown': page,
                 'home': -len(self.rows), 'end': len(self.rows)}
        if k in moves:
            self.typed = ''
            self.cursor = max(0, min(len(self.rows) - 1, self.cursor + moves[k]))
        return False

    def go_to_top(self):
        return '\r' + (f'\033[{self.drawn - 1}A' if self.drawn > 1 else '')

    def erase(self):
        if self.drawn:
            self.write(self.go_to_top() + '\033[J')
            self.drawn = 0

    def draw(self):
        cols, lines = self.size()
        if self.drawn and (cols, lines) != self.drawn_size:
            # the terminal may have re-wrapped what was drawn: start afresh
            self.write('\033[H\033[2J')
            self.drawn = 0
        self.drawn_size = (cols, lines)
        n = len(self.rows)
        avail = max(lines - 2, 3)   # without the header and footer lines
        scroll = n > avail
        if scroll:
            shown = max(avail - 2, 1)   # without the "more" lines
            self.top = max(0, min(self.top, self.cursor, n - shown), self.cursor - shown + 1)
        else:
            self.top, shown = 0, n
        text = [f'[bold]Workshop steps[/] ({escape(self.action)}):']
        if scroll:
            text.append(f'[dim]     ({self.top} more above)[/]' if self.top else '')
        for i in range(self.top, self.top + shown):
            if i == self.cursor:
                text.append(f'[reverse][bold]>[/bold] {self.labels[i]}[/reverse]')
            else:
                text.append(f'  {self.labels[i]}')
        if scroll:
            below = n - self.top - shown
            text.append(f'[dim]     ({below} more below)[/]' if below else '')
        if self.message:
            text.append(f'[error]{escape(self.message)}[/]  {self.HINT}')
        elif self.typed:
            text.append(f'Step: [bold]{escape(self.typed)}[/]')
        else:
            text.append(self.HINT)
        rendered = []
        width = max(cols - 1, 20)
        for t in text:
            t = Text.from_markup(t)
            if t.cell_len > width:
                t.rstrip()   # the padding before the tags, so only real cuts show '…'
            with out.capture() as cap:
                out.print(t, no_wrap=True, overflow='ellipsis', width=width)
            rendered.append(cap.get().rstrip('\n'))
        self.write(self.go_to_top() + '\033[J' + '\n'.join(rendered))
        self.drawn = len(rendered)


def choose_step_typed(steps, labels, last, default, action):
    """The menu without cursor keys: type the step (Enter for the default)."""
    out.print(f'[bold]Workshop steps[/] ({action}):')
    for st, label in zip(steps.order, labels):
        mark = '[bold]>[/]' if st is default else ' '
        line = f'{mark} {label}'
        if st is last:
            line = f'[reverse]{line}[/]'
        elif st is default:
            line = f'[bold]{line}[/]'
        out.print(line)
    while True:
        try:
            ans = input(f'Step [{default.id}] (q to quit): ').strip()
        except EOFError:
            out.print()
            return None
        if ans.lower() in ('q', 'quit', 'exit'):
            return None
        if not ans:
            return default
        try:
            return steps.get(ans)
        except UserError as e:
            err.print(f'[error]{escape(str(e))}[/]')


def pick(steps, args, state, ctx, action):
    if args.step is not None:
        st = steps.get(args.step)
    else:
        st = choose_step(steps, state, ctx, action)
        if st is None:
            return None
    state['last'] = st.id
    save_state(state)
    return st


def context_from_state(state):
    return Context(**config_from_env(), upto=state.get('precomputed_upto'))


def pretty(path):
    home = os.path.expanduser('~')
    s = str(path)
    return '~' + s[len(home):] if home != '/' and (s == home or s.startswith(home + '/')) else s


def warn_cwd(ctx):
    try:
        same = Path.cwd().resolve() == ctx.workdir.resolve()
    except FileNotFoundError:
        same = False
    if not same:
        d = pretty(ctx.workdir)
        how = f'cd {d}' if ctx.workdir.is_dir() else f'mkdir -p {d} && cd {d}'
        err.print(f'[warn]Run the commands in your workshop folder, {escape(d)}: {escape(how)}[/]')


def warn_missing(r, st):
    missing = r.missing_inputs(st)
    if missing:
        last = missing[-1][0].id
        which = ', '.join(f'{ref.id} ({folder}/)' for ref, folder in missing)
        err.print(f'[warn]Step {st.id} needs the outputs of step{"s" if len(missing) > 1 else ""} {which}, '
                  f'which are not there yet. Run {"them" if len(missing) > 1 else "it"} first '
                  f'(metag-ws show-cmd {last}), or use the precomputed results (metag-ws results-for {last}).[/]')


# --- subcommands ------------------------------------------------------------------

def cmd_show(steps, args):
    state = load_state()
    ctx = context_from_state(state)
    st = pick(steps, args, state, ctx, 'show the commands')
    if st is None:
        return
    r = Renderer(steps, ctx)
    warn_cwd(ctx)
    for i, leaf in enumerate(st.leaves()):
        if i:
            print()
        if leaf.results_only:
            err.print(f'[warn][bold]Results only: do not run this step.[/bold]\n{escape(leaf.results_only)}[/]')
        else:
            warn_missing(r, leaf)
        print('\n'.join(r.header(leaf)))
        print('\n'.join(r.commands(leaf)))
        sys.stdout.flush()
        if leaf.look_at:
            err.print(f'[dim]What to look at:\n{escape(r.look_at(leaf))}[/]')


def cmd_explain(steps, args):
    state = load_state()
    ctx = context_from_state(state)
    st = pick(steps, args, state, ctx, 'explain the commands')
    if st is None:
        return
    r = Renderer(steps, ctx)
    warn_cwd(ctx)
    for leaf in st.leaves():
        out.rule(f'[bold]Step {leaf.id}: {escape(leaf.full_title())}')
        if leaf.results_only:
            out.print(f'[warn][bold]Results only: do not run this step.[/bold]\n{escape(leaf.results_only)}[/]',
                      soft_wrap=True)
        else:
            warn_missing(r, leaf)
        for line in r.header(leaf)[1:]:
            out.print(f'[dim]{escape(line)}[/]', soft_wrap=True)
        for c in leaf.cmds:
            out.print(Syntax(r.render(c['run'], leaf).strip('\n'), 'bash', theme=SYNTAX_THEME[BACKGROUND],
                             background_color='default', word_wrap=True))
            table = Table(show_header=False, box=None, padding=(0, 2, 0, 2))
            table.add_column(style='arg', no_wrap=True, max_width=36)
            table.add_column()
            for arg, text in c.get('explain', []):
                table.add_row(escape(r.render(arg, leaf)), escape(r.render(text, leaf)))
            out.print(table)
            out.print()
        if leaf.look_at:
            out.print('[bold]What to look at[/]')
            out.print(escape(r.look_at(leaf)), soft_wrap=True)
            out.print()


def cmd_results_for(steps, args):
    state = load_state()
    ctx = context_from_state(state)
    st = pick(steps, args, state, ctx, 'bring in precomputed results')
    if st is None:
        return
    if not ctx.precomputed.is_dir():
        raise UserError(f'The precomputed results are not available ({ctx.precomputed} does not exist)')
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    tops = [t for t in steps.tops if step_key(t.id) <= step_key(st.top.id)]
    missing = [t for t in tops if not (ctx.precomputed / t.folder).is_dir()]
    if missing:
        raise UserError('No precomputed results for step(s) ' + ', '.join(t.id for t in missing)
                        + f' in {ctx.precomputed}')
    for t in tops:
        link = ctx.workdir / (t.folder + PRECOMPUTED_SUFFIX)
        if os.path.lexists(link):
            out.print(f'  {link.name} (already there)')
        else:
            os.symlink(ctx.precomputed / t.folder, link)
            out.print(f'  {link.name}')
    upto = st.leaves()[-1].id
    if st.results_only:
        # Only there to look at: the other steps keep using the same inputs
        # (and the earlier results are there to compare with).
        out.print(f'\nPrecomputed results of steps 1 to {upto} are in [bold]{escape(pretty(ctx.workdir))}[/], '
                  f'in the *{PRECOMPUTED_SUFFIX} folders (your own folders are not changed). '
                  f'The commands of the other steps still use the same inputs as before.')
        out.print('[warn]Note: these results may not be exactly the same as your own: for example, '
                  'bin names and numbers can differ between runs.[/]')
        return
    state['precomputed_upto'] = upto
    save_state(state)
    nxt = steps.next_after(steps.by_id[upto]) if upto != steps.leaves[-1].id else None
    out.print(f'\nPrecomputed results of steps 1 to {upto} are in [bold]{escape(pretty(ctx.workdir))}[/], '
              f'in the *{PRECOMPUTED_SUFFIX} folders (your own folders are not changed).')
    out.print('[warn]Note: these results may not be exactly the same as your own: for example, '
              'contig names and bin names and numbers can differ between runs.[/]')
    if nxt:
        out.print(f'From now on, the commands from [bold]metag-ws show-cmd[/] use them as inputs '
                  f'(e.g., for step {nxt.id}): use metag-ws show-cmd rather than a printed copy of the commands.')


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif os.path.lexists(path):
        path.unlink()


def cmd_get_data(steps, args):
    """A shortcut for step 1: copy everything in the shared data directory
    into step 1's folder (in the current directory, like the commands).
    Files already there are left alone; each file is copied under a temporary
    name first, so that an interrupted copy is not taken for a complete one."""
    state = load_state()
    ctx = context_from_state(state)
    src = Path(ctx.data)
    if not src.is_dir():
        raise UserError(f'The workshop data is not available ({src} does not exist)')
    entries = sorted(src.iterdir())
    if not entries:
        raise UserError(f'The workshop data directory ({src}) is empty')
    step1 = steps.by_id['1']
    warn_cwd(ctx)
    dest = Path.cwd() / step1.folder
    dest.mkdir(parents=True, exist_ok=True)
    for e in entries:
        target = dest / e.name
        if os.path.lexists(target):
            out.print(f'  {step1.folder}/{e.name} (already there)')
            continue
        tmp = dest / f'.{e.name}.partial'
        remove(tmp)
        try:
            if e.is_dir():
                # copyfile: plain copies, not read-only like the shared files
                shutil.copytree(e, tmp, copy_function=shutil.copyfile)
            else:
                shutil.copyfile(e, tmp)
            os.replace(tmp, target)
        except BaseException:
            remove(tmp)
            raise
        out.print(f'  {step1.folder}/{e.name}')
    state['last'] = step1.id   # as after show-cmd 1: the menu starts on step 2
    save_state(state)
    out.print(f'\nStep {step1.id} ({step1.title.lower()}) is done: the workshop data is in '
              f'[bold]{escape(pretty(dest))}[/].')


# --- _run-all -------------------------------------------------------------------

def run_all(argv):
    steps = Steps()
    cfg = config_from_env()
    p = argparse.ArgumentParser(prog='metag-ws _run-all',
                                description='Run the commands of all steps (as printed by show-cmd) into DIR.')
    p.add_argument('-o', '--output', required=True, metavar='DIR', help='working directory for the run')
    p.add_argument('--data', default=cfg['data'], metavar='DIR',
                   help=f'directory with sample_R1/R2/ont.fq.gz (default: {cfg["data"]})')
    p.add_argument('-t', '--threads', type=int, default=cfg['threads'])
    p.add_argument('--until', metavar='STEP', help='stop after this step')
    p.add_argument('--skip-results-only', action='store_true',
                   help='do not run the results-only steps (step 10, GTDB-Tk, needs ~130 GB of RAM)')
    args = p.parse_args(argv)
    for v in DB_VARS:
        if not os.environ.get(v):
            raise UserError(f'{v} is not set: run in the pixi environment')
    workdir = Path(args.output).resolve()
    ctx = Context(workdir=workdir, data=str(Path(args.data).resolve()),
                  precomputed=cfg['precomputed'], threads=args.threads, upto=None)
    until = steps.get(args.until).leaves()[-1] if args.until else steps.leaves[-1]
    (workdir / '.done').mkdir(parents=True, exist_ok=True)
    timings = workdir / 'timings.tsv'
    if not timings.exists():
        timings.write_text('step\tseconds\tmax_rss_gb\n')
    for leaf in steps.leaves:
        done = workdir / '.done' / leaf.id
        if args.skip_results_only and leaf.results_only:
            print(f'== {leaf.id}: results only, skipping', flush=True)
        elif done.exists():
            print(f'== {leaf.id}: already done, skipping', flush=True)
        else:
            r = Renderer(steps, ctx)
            for ref, folder in r.missing_inputs(leaf):
                raise UserError(f'step {leaf.id}: outputs of step {ref.id} missing in {folder}/')
            script = '\n'.join(r.header(leaf) + r.commands(leaf))
            print(f'== {leaf.id}: starting {time.strftime("%Y-%m-%dT%H:%M:%S")}\n{script}', flush=True)
            t0 = time.time()
            proc = subprocess.Popen(['bash', '-euo', 'pipefail', '-c', script], cwd=workdir)
            # wait4 gives the peak RSS of the largest process in the step
            _, status, usage = os.wait4(proc.pid, 0)
            proc.returncode = os.waitstatus_to_exitcode(status)
            secs = time.time() - t0
            if proc.returncode != 0:
                raise UserError(f'step {leaf.id} failed (exit code {proc.returncode}) after {secs:.0f}s')
            with open(timings, 'a') as f:
                f.write(f'{leaf.id}\t{secs:.0f}\t{usage.ru_maxrss / 1048576:.1f}\n')
            done.touch()
            print(f'== {leaf.id}: done in {secs:.0f}s', flush=True)
        if leaf is until:
            break
    print(timings.read_text(), end='')


# --- main -----------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv and argv[0] == '_run-all':
            return run_all(argv[1:])
        steps = Steps()
        p = argparse.ArgumentParser(
            prog='metag-ws',
            description='Helper for the metagenomics workshop: the commands of each step, '
                        'what their arguments mean, and precomputed results to catch up.',
            epilog='Without STEP, a menu of the steps is shown. A STEP can be a step (5) or '
                   'a substep (5.2). Run the commands in your workshop folder '
                   f'({pretty(config_from_env()["workdir"])}).')
        sub = p.add_subparsers(dest='command', metavar='COMMAND', required=True)
        for name, fn, help_ in [
                ('show-cmd', cmd_show, 'print the command(s) of a step, ready to copy'),
                ('explain-cmd', cmd_explain, 'print the command(s) of a step, with every argument explained'),
                ('results-for', cmd_results_for,
                 'bring in the precomputed results of all steps up to STEP (into *_precomputed folders)')]:
            sp = sub.add_parser(name, help=help_, description=help_)
            sp.add_argument('step', nargs='?', metavar='STEP')
            sp.set_defaults(fn=fn)
        help_ = (f'step 1 in one go: copy the workshop data ({config_from_env()["data"]}) '
                 f'into {steps.by_id["1"].folder}/')
        sub.add_parser('get-data', help=help_, description=help_).set_defaults(fn=cmd_get_data)
        args = p.parse_args(argv)
        setup_colours()
        args.fn(steps, args)
    except UserError as e:
        err.print(f'[error]metag-ws: {escape(str(e))}[/]')
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    sys.exit(main())
