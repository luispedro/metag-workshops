"""Check the metag-ws menu by driving it in a pseudo-terminal.

    pixi run test-menu                        # run the checks
    pixi run test-menu --show ROWS COLS KEY...  # print the screen after KEYs

KEYs are Python string literals, e.g. "'\\x1b[B'" (Down) or "'5.2\\n'".

The screen is reconstructed by a minimal terminal emulator that knows only
what the menu writes (\\r, \\n, cursor up, clear to end of screen, clear
screen; colours are ignored). Real terminals (VS Code, Jupyter, PuTTY, tmux)
and resizing still need checking by hand.
"""
import ast
import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

DOWN, UP, END, PGDOWN, ESC, CTRL_C = '\x1b[B', '\x1b[A', '\x1b[F', '\x1b[6~', '\x1b', '\x03'


def emulate(data, rows, cols):
    """The screen (list of lines) after writing `data` to a ROWSxCOLS terminal."""
    screen = [[' '] * cols for _ in range(rows)]
    y = x = 0
    for m in re.finditer(r'\x1b\[([?0-9;]*)([A-Za-z])|\x1b.|(.)', data, re.DOTALL):
        c = m.group(3)
        if c is not None:
            if c == '\r':
                x = 0
            elif c == '\n':
                y += 1
                if y >= rows:
                    screen.pop(0)
                    screen.append([' '] * cols)
                    y = rows - 1
            elif c >= ' ':
                if x < cols:
                    screen[y][x] = c
                x += 1
            continue
        arg, cmd = m.group(1), m.group(2)
        if cmd == 'A':
            y = max(0, y - (int(arg) if arg.isdigit() else 1))
        elif cmd == 'H':
            y = x = 0
        elif cmd == 'J':
            if arg == '2':
                screen = [[' '] * cols for _ in range(rows)]
            else:
                screen[y][x:] = [' '] * (cols - x)
                for yy in range(y + 1, rows):
                    screen[yy] = [' '] * cols
    return [''.join(line).rstrip() for line in screen]


def run(keys, rows=30, cols=100, state=None, env=None):
    """Run `metag-ws show-cmd` in a pty, type `keys`, and return
    (screen, exit code or None if still running)."""
    state = state or tempfile.mkdtemp(prefix='metag-ws-test-')
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(XDG_STATE_HOME=state, METAG_WS_DIR=state, METAG_WS_BACKGROUND='dark',
                          TERM='xterm-256color', **(env or {}))
        os.environ.pop('LINES', None)
        os.environ.pop('COLUMNS', None)
        os.execvp('metag-ws', ['metag-ws', 'show-cmd'])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
    buf = b''

    def drain(t):
        nonlocal buf
        end = time.time() + t
        while time.time() < end:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    d = os.read(fd, 65536)
                except OSError:   # the child exited
                    return False
                if not d:
                    return False
                buf += d
        return True

    alive = drain(1.5)
    for k in keys:
        if not alive:
            break
        os.write(fd, k.encode())
        alive = drain(0.4)
    drain(0.3)
    wp, status = os.waitpid(pid, os.WNOHANG)
    if not wp:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
    os.close(fd)
    return emulate(buf.decode(errors='replace'), rows, cols), (os.waitstatus_to_exitcode(status) if wp else None)


def cursor_line(screen):
    [line] = [s for s in screen if s.startswith('>')]
    return line


def contains(screen, text):
    return any(text in s for s in screen)


CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


@check
def starts_on_first_step_and_moves():
    screen, code = run([DOWN, DOWN, UP])
    assert code is None
    assert screen[0].startswith('Workshop steps (show the commands)')
    assert cursor_line(screen).split()[1] == '2'


@check
def scrolls_in_a_short_terminal():
    screen, _ = run([END], rows=12, cols=80)
    assert screen[0].startswith('Workshop steps')
    assert '(15 more above)' in screen[1]
    assert cursor_line(screen).split()[1] == '15'
    screen, _ = run([PGDOWN, PGDOWN], rows=12, cols=80)
    assert contains(screen, 'more above') and contains(screen, 'more below')


@check
def typing_moves_the_cursor():
    screen, _ = run(['1', '2'], rows=12, cols=80)
    assert cursor_line(screen).split()[1] == '12'
    assert screen[-1] == 'Step: 12'


@check
def unknown_step():
    screen, code = run(['9', '9', '\r'])
    assert code is None
    assert contains(screen, 'No step 99')


@check
def typed_step_and_enter_then_menu_is_erased():
    screen, code = run(['5.2\n'])
    assert code == 0
    assert not contains(screen, 'Workshop steps')
    assert contains(screen, 'Step 5.2: Polishing with short reads: Polish (polypolish)')


@check
def enter_chooses_the_cursor_step():
    screen, code = run([DOWN, '\r'], rows=50)
    assert code == 0
    assert contains(screen, 'Step 2.1: Read quality control: Short reads (fastp)')


@check
def quit_esc_and_ctrl_c_erase_the_menu():
    for key, expected in [('q', 0), (ESC, 0), (CTRL_C, 130)]:
        screen, code = run([key])
        assert code == expected, (repr(key), code)
        assert not any(screen), repr(key)


@check
def remembers_the_last_step():
    state = tempfile.mkdtemp(prefix='metag-ws-test-')
    run(['5.2\n'], state=state)
    screen, _ = run([], state=state)
    assert cursor_line(screen).split()[1] == '6'
    assert [s for s in screen if ' 5.2 ' in s][0].endswith('last used')


@check
def narrow_terminal_cuts_only_long_rows():
    screen, _ = run([], rows=30, cols=50)
    get_data = [s for s in screen if 'Get data' in s][0]
    assert not get_data.endswith('…')
    assert all(len(s) < 50 for s in screen)


@check
def plain_menu_when_asked():
    screen, code = run(['\r'], env={'METAG_WS_MENU': 'plain'})
    assert code == 0
    assert contains(screen, 'Step [1] (q to quit):')
    assert contains(screen, 'Step 1: Get data')


@check
def plain_menu_without_a_terminal():
    state = tempfile.mkdtemp(prefix='metag-ws-test-')
    env = dict(os.environ, XDG_STATE_HOME=state, METAG_WS_DIR=state, METAG_WS_BACKGROUND='dark')
    p = subprocess.run(['metag-ws', 'show-cmd'], input='5.2\n', capture_output=True, text=True, env=env)
    assert p.returncode == 0
    assert 'Step [1] (q to quit):' in p.stdout
    assert '# Step 5.2:' in p.stdout


def main(argv):
    if argv and argv[0] == '--show':
        screen, code = run([ast.literal_eval(k) for k in argv[3:]], rows=int(argv[1]), cols=int(argv[2]))
        for i, line in enumerate(screen):
            print(f'{i:2}|{line}')
        print('exit code:', 'still running' if code is None else code)
        return 0
    failed = 0
    for fn in CHECKS:
        try:
            fn()
            print(f'PASS {fn.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL {fn.__name__} {e}')
    print(f'{len(CHECKS) - failed}/{len(CHECKS)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
