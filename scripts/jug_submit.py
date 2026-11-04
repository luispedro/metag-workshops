#!/usr/bin/env python
"""Provisioner: submit a right-sized queue job for every Jug task that is ready.

    pixi run python scripts/jug_submit.py            # one pass
    pixi run python scripts/jug_submit.py --watch    # repeat every 5 min until done
    pixi run python scripts/jug_submit.py --dry-run  # show what would be submitted
    pixi run python scripts/jug_submit.py --test --watch  # end-to-end test on
                                    # the simulated data (tests/smoke_test.sh)

Jug (jugfile.py) owns the dependencies; this script only starts workers. Each
worker is an mqsub/qsub job running

    jug execute --name <task function>

with the CPUs/RAM/walltime from RESOURCES below (aqua limit: 48 h). Workers
exit once their task is done; the next pass submits whatever became ready.

Submitted jobs are recorded in logs/jug_workers.json, so a task is not
submitted twice while its job is queued or running. Worker logs go to
logs/jug/.

Failures are not retried automatically. A task that raised an error, or whose
worker was killed (e.g. at the walltime limit; the file_keepalive store marks
it failed), is reported as FAILED. Check its log, fix the cause, then run
`pixi run jug cleanup --failed-only` and run this script again.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# task function -> (cpus, mem_gb, hours)
RESOURCES = {
    'full_qc_sr':      (16,  32, 24),
    'full_qc_lr':      (16,  32, 48),
    'full_profile_sr': (32,  64, 48),
    'full_profile_lr': (32,  64, 48),
    'full_assemble':   (64, 500, 48),
    'full_polish':     (64, 128, 48),
    'full_map':        (64, 128, 48),
    'full_bin':        (32, 128, 48),
    'full_checkm2':    (32, 128, 24),
    'full_gunc':       (32, 128, 24),
    'full_appraise':   (32,  64, 24),
    'full_map_lr':     (32,  64, 48),
    'select_bins':     (1,    8,  1),
    'make_subset':     (16,  64, 24),
    'workshop_run':    (None, 64, 4),   # CPUs = jugfile.WORKSHOP_THREADS
    'validate':        (4,   16,  1),
}
JUGDIR = 'file_keepalive:jugfile.jugdata'
STATE = os.path.join(REPO, 'logs', 'jug_workers.json')
TEST = False
ALIVE = set('QRHWTBSE')  # PBS states of a job that has not finished


def pixi_cache():
    # Inside the mqyolo sandbox the default pixi cache (/pkg/...) is read-only
    # but writable through /mnt/weka; jobs start from a fresh login shell.
    cache = os.environ.get('PIXI_CACHE_DIR', '')
    if cache and not os.access(cache, os.W_OK) and os.access('/mnt/weka' + cache, os.W_OK):
        cache = '/mnt/weka' + cache
    return cache


def job_alive(job_id):
    r = subprocess.run(['qstat', '-f', job_id], capture_output=True, text=True)
    m = re.search(r'job_state = (\w)', r.stdout)
    return r.returncode == 0 and m is not None and m.group(1) in ALIVE


def load_tasks():
    os.chdir(REPO)
    from jug import jug, task
    jug.init('jugfile.py', JUGDIR, on_error='propagate')
    jugfile = sys.modules['jugfile']
    return task.alltasks, jugfile


def task_state(t):
    if t.can_load():
        return 'done'
    if t.is_failed():
        return 'FAILED'
    if t.is_locked():
        return 'running'
    if t.can_run():
        return 'ready'
    return 'waiting'


def submit(fname, jugfile, dry_run):
    cpus, mem, hours = RESOURCES[fname]
    if cpus is None:
        cpus = jugfile.WORKSHOP_THREADS
    if TEST:
        cpus, mem, hours = min(cpus, 16), min(mem, 64), min(hours, 4)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    log = f'logs/jug/{fname}-{stamp}.log'
    cache = pixi_cache()
    inner = (f'jug execute jugfile.py --jugdir {JUGDIR} --name {fname} '
             f'--nr-wait-cycles 1 > {log} 2>&1')
    cmd = ['mqsub', '--no-email', '--bg', '-t', str(cpus), '-m', str(mem),
           '--hours', str(hours), '--name', f'wsj_{fname}', '--',
           'env', f'WS_THREADS={cpus}', *(['WS_TEST=1'] if TEST else []), *([f'PIXI_CACHE_DIR={cache}'] if cache else []),
           'pixi', 'run', '--frozen', 'bash', '-c', inner]
    if dry_run:
        print(f'  would submit {fname}: {cpus} CPUs, {mem} GB, {hours} h')
        return None
    os.makedirs(os.path.join(REPO, 'logs', 'jug'), exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    m = re.search(r'qsub stdout: *(\S+)', r.stdout + r.stderr)
    if r.returncode != 0 or not m:
        print(f'  submission of {fname} FAILED:\n{r.stdout}{r.stderr}', file=sys.stderr)
        return None
    print(f'  submitted {fname}: job {m.group(1)} ({cpus} CPUs, {mem} GB, {hours} h), log {log}')
    return m.group(1)


def one_pass(dry_run):
    """Returns (all tasks done, anything still in progress)."""
    tasks, jugfile = load_tasks()
    workers = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            workers = json.load(f)
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'jug tasks:')
    in_progress = False
    all_done = True
    for t in tasks:
        fname = t.name.split('.')[-1]
        if fname not in RESOURCES:
            continue  # e.g. jug.utils.timed_path helpers
        state = task_state(t)
        all_done &= state == 'done'
        key = t.hash().decode() if isinstance(t.hash(), bytes) else t.hash()
        job = workers.get(key)
        alive = job is not None and job_alive(job)
        if state == 'ready' and not alive:
            job = submit(fname, jugfile, dry_run)
            if job:
                workers[key] = job
                alive = True
                save_state(workers)  # at once: never submit the same task twice
        if state in ('ready', 'running') or alive:
            in_progress = True
        extra = f' (job {job})' if alive else ''
        print(f'  {state:8} {fname}{extra}')
    if not dry_run:
        save_state(workers)
    return all_done, in_progress


def save_state(workers):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + '.tmp', 'w') as f:
        json.dump(workers, f, indent=1)
    os.replace(STATE + '.tmp', STATE)


def main():
    sys.stdout.reconfigure(line_buffering=True)  # useful log when redirected
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--watch', action='store_true')
    p.add_argument('--interval', type=float, default=5, help='minutes between passes')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--test', action='store_true',
                   help='run the graph on the simulated data (tests/jugrun/)')
    args = p.parse_args()
    if args.test:
        global JUGDIR, STATE, TEST
        TEST = True
        os.environ['WS_TEST'] = '1'
        JUGDIR = 'file_keepalive:tests/jugfile.jugdata'
        STATE = os.path.join(REPO, 'logs', 'jug_workers_test.json')
    while True:
        all_done, in_progress = one_pass(args.dry_run)
        if all_done:
            print('All tasks are done.')
            return
        if not args.watch or args.dry_run:
            return
        if not in_progress:
            print('Nothing running and nothing ready: check FAILED tasks (see --help).')
            sys.exit(1)
        time.sleep(args.interval * 60)
        # a fresh process per pass: the jugfile may have been edited
        os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == '__main__':
    main()
