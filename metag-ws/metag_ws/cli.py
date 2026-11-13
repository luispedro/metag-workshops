"""metag-ws: the metagenomics workshop helper.

    metag-ws show-cmd [STEP]       print the command(s) of a step
    metag-ws explain-cmd [STEP]    the same, with every argument explained
    metag-ws results-for [STEP]    bring in the precomputed results up to STEP

Without STEP, a menu of the steps is shown. The steps, their commands and the
explanations are in steps.toml (next to this file).

Hidden, for testing and for building the precomputed results:

    metag-ws _run-all -o DIR [--data DIR] [-t THREADS] [--until STEP]

Configuration (environment variables; the defaults are for the workshop
machine):

    METAG_WS_DIR          participant's working directory (~/workshop)
    METAG_WS_DATA         shared directory with the reads (/opt/metag-ws/data)
    METAG_WS_PRECOMPUTED  shared precomputed results (/opt/metag-ws/precomputed)
    METAG_WS_THREADS      threads per participant (8)
"""
import argparse
import glob
import json
import os
import re
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

STEPS_FILE = Path(__file__).with_name('steps.toml')
PRECOMPUTED_SUFFIX = '_precomputed'
PLACEHOLDER = re.compile(r'\{(\d+(?:\.\d+)?|threads|threads_fastp|data)\}')
# databases that the commands use through environment variables (set by pixi)
DB_VARS = ['SINGLEM_METAPACKAGE_PATH', 'CHECKM2DB', 'GUNC_DB', 'EGGNOG_DATA_DIR']

out = Console(highlight=False)
err = Console(stderr=True, highlight=False, soft_wrap=True)


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
                      outputs=d.get('outputs', []), look_at=d.get('look_at', '').strip())
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

    def render(self, text, current):
        def sub(m):
            key = m.group(1)
            if key == 'threads':
                return str(self.ctx.threads)
            if key == 'threads_fastp':
                return str(min(self.ctx.threads, 16))
            if key == 'data':
                return self.ctx.data
            return folder_of(self.steps.by_id[key], current, self.ctx)
        return PLACEHOLDER.sub(sub, text)

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

def choose_step(steps, state, ctx, action):
    last = steps.by_id.get(state.get('last', ''))
    default = steps.next_after(last) if last else steps.tops[0]
    out.print(f'[bold]Workshop steps[/] ({action}):')
    for st in steps.order:
        sub = st.parent is not None
        label = f'{st.id:>{6 if sub else 4}}  {escape(st.title)}'
        tags = []
        if st.is_leaf and ctx.upto and step_key(st.id) <= step_key(ctx.upto):
            tags.append('[cyan]precomputed[/]')
        if st.is_leaf and done_outputs(st, ctx.workdir):
            tags.append('[green]done[/]')
        if st is last:
            tags.append('[yellow]last used[/]')
        mark = '[bold]>[/]' if st is default else ' '
        line = f'{mark} {label:<{58 if sub else 60}} {" ".join(tags)}'
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
            err.print(f'[red]{escape(str(e))}[/]')


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
        err.print(f'[yellow]Run the commands in your workshop folder, {escape(d)}: {escape(how)}[/]')


def warn_missing(r, st):
    missing = r.missing_inputs(st)
    if missing:
        last = missing[-1][0].id
        which = ', '.join(f'{ref.id} ({folder}/)' for ref, folder in missing)
        err.print(f'[yellow]Step {st.id} needs the outputs of step{"s" if len(missing) > 1 else ""} {which}, '
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
        warn_missing(r, leaf)
        print('\n'.join(r.header(leaf)))
        print('\n'.join(r.commands(leaf)))
        sys.stdout.flush()
        if leaf.look_at:
            err.print(f'[dim]What to look at:\n{escape(r.render(leaf.look_at, leaf))}[/]')


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
        warn_missing(r, leaf)
        for line in r.header(leaf)[1:]:
            out.print(f'[dim]{escape(line)}[/]', soft_wrap=True)
        for c in leaf.cmds:
            out.print(Syntax(r.render(c['run'], leaf).strip('\n'), 'bash', theme='ansi_dark',
                             background_color='default', word_wrap=True))
            table = Table(show_header=False, box=None, padding=(0, 2, 0, 2))
            table.add_column(style='bold cyan', no_wrap=True, max_width=36)
            table.add_column()
            for arg, text in c.get('explain', []):
                table.add_row(escape(r.render(arg, leaf)), escape(r.render(text, leaf)))
            out.print(table)
            out.print()
        if leaf.look_at:
            out.print('[bold]What to look at[/]')
            out.print(escape(r.render(leaf.look_at, leaf)), soft_wrap=True)
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
    state['precomputed_upto'] = upto
    save_state(state)
    nxt = steps.next_after(steps.by_id[upto]) if upto != steps.leaves[-1].id else None
    out.print(f'\nPrecomputed results of steps 1 to {upto} are in [bold]{escape(pretty(ctx.workdir))}[/], '
              f'in the *{PRECOMPUTED_SUFFIX} folders (your own folders are not changed).')
    out.print('[yellow]Note: these results may not be exactly the same as your own: for example, '
              'contig names and bin names and numbers can differ between runs.[/]')
    if nxt:
        out.print(f'From now on, the commands from [bold]metag-ws show-cmd[/] use them as inputs '
                  f'(e.g., for step {nxt.id}): use metag-ws show-cmd rather than a printed copy of the commands.')


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
        if done.exists():
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
        args = p.parse_args(argv)
        args.fn(steps, args)
    except UserError as e:
        err.print(f'[red]metag-ws: {escape(str(e))}[/]')
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    sys.exit(main())
