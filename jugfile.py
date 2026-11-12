"""Building the workshop dataset (PLAN.md), as a Jug task graph.

    full-data pipeline (one task per step of scripts/pipeline.sh)
        -> bin selection -> read extraction -> timed workshop run -> validation

Do not run `jug execute` by hand on the login node: run jug_hpc, which submits
a queue job (sized as in jug_hpc.toml) for each task as soon as it is ready:

    pixi run submit             # e.g. in tmux; stops when everything is done

Check progress with `pixi run jug status`; results with `pixi run jug shell`.

Tuning the dataset (GOALS.md, step 6): edit SUBSET below. Every parameter
combination gets its own directory, subsets/<tag>/, so earlier attempts are
kept and the full-data tasks are not rerun. To choose the bins by hand, write
them (one per line) to selection_manual.txt; editing it changes the tag.

Test mode (WS_TEST=1, set by `pixi run submit-test` and tests/jug_hpc.toml):
the same graph on the simulated community from tests/smoke_test.sh, under
tests/jugrun/.

Tasks run the scripts in scripts/; Jug does not notice changes to those
scripts: after changing one, `jug invalidate --name <task>` the affected tasks.
"""
import hashlib
import json
import os
import shutil
import subprocess

from jug import TaskGenerator
from jug.utils import timed_path

REPO = os.path.dirname(os.path.abspath(__file__))

FULL_INPUTS = [
    timed_path('full_data/1_350.fq1.gz'),
    timed_path('full_data/1_350.fq2.gz'),
    timed_path('full_data/fq1_ont.fastq.gz'),
]
FULL_RUN = 'runs/full'
OUT = '.'

SUBSET = {
    'n_bins': 5,
    'min_completeness': 90,
    'max_contamination': 5,
    'max_depth_sr': 60,
    # 0.01 background gave 40 bins (73% of the proteins) and a 45 min run
    'max_depth_lr': 25,
    'background': 0.002,
    'seed': 'workshop',
}
MANUAL_SELECTION = 'selection_manual.txt'

# The workshop run is timed, so it gets a fixed number of threads matching the
# machines participants will use (its jug_hpc class has this many CPUs).
WORKSHOP_THREADS = 16

if os.environ.get('WS_TEST'):
    # absolute: in test mode, the jugfile is loaded from tests/ (jug_hpc's
    # project directory, tests/jug_hpc.toml)
    FULL_INPUTS = [timed_path(os.path.join(REPO, f'tests/sim/sample_{r}.fq.gz'))
                   for r in ('R1', 'R2', 'ont')]
    OUT = 'tests/jugrun'
    FULL_RUN = f'{OUT}/full'
    SUBSET = dict(SUBSET, n_bins=2, min_completeness=80, max_depth_sr=20, max_depth_lr=15,
                  background=0.05)
    MANUAL_SELECTION = 'tests/selection_manual.txt'


def threads():
    """CPUs of the queue job running this task (set by jug_hpc)."""
    return int(os.environ.get('JUG_HPC_CPUS') or os.environ.get('NCPUS') or 4)


def sh(*cmd):
    cmd = [str(c) for c in cmd]
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO)


def pipeline_step(step, inputs, *extra):
    run = FULL_RUN
    sr1, sr2, lr = (str(p) for p in inputs)
    done = os.path.join(REPO, run, '.done', step)
    if os.path.exists(done):
        # Jug decided this must run (e.g., after `jug invalidate`): redo it
        os.unlink(done)
    sh('bash', 'scripts/pipeline.sh', '-1', sr1, '-2', sr2, '-l', lr,
       '-o', run, '-t', threads(), '--only', step, *extra)
    return run


# --- 1. Full pipeline on the full data ----------------------------------------
# Arguments named `_after` only carry the dependency.

@TaskGenerator
def full_qc_sr(inputs):
    return pipeline_step('qc_sr', inputs)

@TaskGenerator
def full_qc_lr(inputs):
    return pipeline_step('qc_lr', inputs)

@TaskGenerator
def full_profile_sr(inputs, _after):
    return pipeline_step('profile_sr', inputs)

@TaskGenerator
def full_profile_lr(inputs, _after):
    return pipeline_step('profile_lr', inputs)

@TaskGenerator
def full_assemble(inputs, _after):
    return pipeline_step('assemble', inputs)

@TaskGenerator
def full_polish_aln(inputs, read, _after):
    """`bwa mem -a` of one read end (read: 'r1' or 'r2') vs. the draft"""
    return pipeline_step(f'polish_aln_{read}', inputs)

@TaskGenerator
def full_polish(inputs, _after):
    # --cleanup removes the (very large) `bwa mem -a` SAM files afterwards
    return pipeline_step('polish', inputs, '--cleanup')

@TaskGenerator
def full_map(inputs, _after):
    return pipeline_step('map', inputs)

@TaskGenerator
def full_bin(inputs, _after):
    return pipeline_step('bin', inputs)

@TaskGenerator
def full_checkm2(inputs, _after):
    return pipeline_step('checkm2', inputs)

@TaskGenerator
def full_gunc(inputs, _after):
    return pipeline_step('gunc', inputs)

@TaskGenerator
def full_appraise(inputs, _after):
    return pipeline_step('appraise', inputs)

@TaskGenerator
def full_map_lr(inputs, _after):
    """Raw ONT reads vs. the polished assembly (for extracting long reads)."""
    out = os.path.join(FULL_RUN, 'subset_work', 'lr_vs_assembly.paf.gz')
    os.makedirs(os.path.join(REPO, os.path.dirname(out)), exist_ok=True)
    tmp = os.path.join(REPO, out + '.tmp')
    t = threads()
    cmd = (f'minimap2 -x map-ont --secondary=no -t {t} '
           f'{FULL_RUN}/assembly/polished.fa {inputs[2]} | gzip > {tmp}')
    print('+', cmd, flush=True)
    subprocess.run(['bash', '-o', 'pipefail', '-c', cmd], check=True, cwd=REPO)
    os.replace(tmp, os.path.join(REPO, out))
    return out


# --- 2-6. Workshop dataset ----------------------------------------------------

@TaskGenerator
def select_bins(full_run, params, manual, outdir, _after):
    sh('python', 'scripts/select_bins.py', full_run, '-o', outdir,
       '-n', params['n_bins'],
       '--min-completeness', params['min_completeness'],
       '--max-contamination', params['max_contamination'])
    if manual is not None:
        with open(os.path.join(REPO, outdir, 'selected_bins.txt'), 'w') as f:
            f.write(manual)
    with open(os.path.join(REPO, outdir, 'selected_bins.txt')) as f:
        return {'selection': outdir, 'bins': f.read().split()}


@TaskGenerator
def make_subset(inputs, selection, paf, params, outdir):
    sr1, sr2, lr = (str(p) for p in inputs)
    sh('bash', 'scripts/make_subset.sh', '-r', FULL_RUN,
       '-s', selection['selection'], '-o', outdir,
       '-1', sr1, '-2', sr2, '-l', lr, '-p', paf, '-t', threads(),
       '--max-depth-sr', params['max_depth_sr'],
       '--max-depth-lr', params['max_depth_lr'],
       '--background', params['background'],
       '--seed', params['seed'])
    return outdir


@TaskGenerator
def workshop_run(data, outdir, nthreads):
    """The whole workshop pipeline on the toy data, timed (steps 5-6)."""
    if os.path.exists(os.path.join(REPO, outdir)):
        shutil.rmtree(os.path.join(REPO, outdir))  # timings must be from a clean run
    sh('bash', 'scripts/pipeline.sh',
       '-1', f'{data}/sample_R1.fq.gz', '-2', f'{data}/sample_R2.fq.gz',
       '-l', f'{data}/sample_ont.fq.gz', '-o', outdir, '-t', nthreads)
    return outdir


@TaskGenerator
def validate(full_run, selection, run):
    """Returns the validation report; a FAIL is a result, not a task error."""
    report = os.path.join(run, 'validation.md')
    r = subprocess.run(['python', 'scripts/validate.py', full_run,
                        selection['selection'], run, '-o', report], cwd=REPO)
    with open(os.path.join(REPO, report)) as f:
        return {'passed': r.returncode == 0, 'report': f.read()}


# --- graph ----------------------------------------------------------------------

qc_sr = full_qc_sr(FULL_INPUTS)
qc_lr = full_qc_lr(FULL_INPUTS)
profile_sr = full_profile_sr(FULL_INPUTS, qc_sr)
profile_lr = full_profile_lr(FULL_INPUTS, qc_lr)
assembled = full_assemble(FULL_INPUTS, qc_lr)
polish_aln = [full_polish_aln(FULL_INPUTS, read, [assembled, qc_sr]) for read in ('r1', 'r2')]
polished = full_polish(FULL_INPUTS, polish_aln)
mapped = full_map(FULL_INPUTS, polished)
binned = full_bin(FULL_INPUTS, mapped)
checkm2 = full_checkm2(FULL_INPUTS, binned)
gunc = full_gunc(FULL_INPUTS, binned)
appraise = full_appraise(FULL_INPUTS, [binned, profile_sr, profile_lr])
lr_paf = full_map_lr(FULL_INPUTS, polished)

manual = None
if os.path.exists(os.path.join(REPO, MANUAL_SELECTION)):
    with open(os.path.join(REPO, MANUAL_SELECTION)) as f:
        manual = f.read()
tag = hashlib.sha256(json.dumps([SUBSET, manual], sort_keys=True).encode()).hexdigest()[:8]
base = f'{OUT}/subsets/{tag}'

selection = select_bins(FULL_RUN, SUBSET, manual, f'{base}/selection',
                        [checkm2, gunc, appraise])
workshop_data = make_subset(FULL_INPUTS, selection, lr_paf, SUBSET, f'{base}/workshop_data')
run = workshop_run(workshop_data, f'{base}/run', WORKSHOP_THREADS)
validation = validate(FULL_RUN, selection, run)
