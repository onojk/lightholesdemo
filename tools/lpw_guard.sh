#!/usr/bin/env bash
# Yield the CPU to lumens-per-watt wall-clock TIMED runs.
#
#   tools/lpw_guard.sh --check      exit 1 if a timed run is in progress now
#   tools/lpw_guard.sh --run CMD... wait until no timed run, then run CMD
#                                   in its own process group under the watch
#                                   (one-off stills, previews, test renders)
#   tools/lpw_guard.sh --classify CWD ARGV...
#                                   which rule (R2/R3) a python command line
#                                   would match, without running it (tests)
#   tools/lpw_guard.sh PGID         watch: SIGSTOP process group PGID while a
#                                   timed run is in progress, SIGCONT after;
#                                   exits when PGID is gone
#
# Author: no TTS or render while a lumens-per-watt TIMED run is in progress,
# since this pipeline's load would skew its wall-clock results. Op-count
# work (parity.py, *_accept.py, plain analysis) is deterministic: load cannot
# change it, so it is NOT waited for. A process is a timed run if it matches
# one of three rules (logged by number on every pause):
#
#   R1 sealed_run   it is tools/sealed_run.sh of ~/lumens-per-watt, or is
#                   descended from it (a sealed experiment: any command)
#   R2 time-name    a python script under ~/lumens-per-watt whose file name
#                   matches *time*.py (div64_time.py, aprimefix_time.py,
#                   i032time.py, phasetime.py)
#   R3 timing.py    a python script under ~/lumens-per-watt that is
#                   evolve/timing.py or itself imports it (baseline_yafu.py,
#                   shiftrun.py). Not transitively: the *_accept.py scripts
#                   reach it only through baseline_msieve.py and time nothing
#
# LPW_ROOT overrides ~/lumens-per-watt (tests only). Must run in its OWN
# process group (verify_set.sh runs with job control, so it does), or it
# would stop itself.
set -u
LPW="${LPW_ROOT:-$HOME/lumens-per-watt}"

timed_runs() {      # one line per match: "PID RULE CMDLINE"
    LPW="$LPW" python3 -I - "$@" <<'PY'
import os, re, sys

LPW = os.path.realpath(os.environ["LPW"])
SEALED = os.path.join(LPW, "tools", "sealed_run.sh")
IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", re.M)


def under(p):
    return p == LPW or p.startswith(LPW + os.sep)


def proc(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
        with open(f"/proc/{pid}/stat") as f:
            ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except (OSError, ValueError, IndexError):
        return None
    return argv, ppid, cwd


def script_of(argv, cwd):
    """The .py file a python process runs, resolved; None if not python."""
    if not argv or not re.match(r"python[\d.]*$", os.path.basename(argv[0])):
        return None
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" and i + 1 < len(args):
            rel = args[i + 1].replace(".", os.sep) + ".py"
            return os.path.realpath(os.path.join(cwd, rel))
        if a in ("-c", "-"):
            return None
        if a.startswith("-"):
            i += 1
            continue
        return os.path.realpath(os.path.join(cwd, a)) if a.endswith(".py") else None
    return None


_seen = {}


def uses_timing(path):
    """True if `path` is evolve/timing.py or itself imports `timing`.
    Direct imports only: the *_accept.py scripts import baseline_msieve,
    which imports timing at module level, but they time nothing."""
    if os.path.basename(path) == "timing.py":
        return True
    key = path
    if key in _seen:
        return _seen[key]
    _seen[key] = False
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    names = set()
    for m in IMPORT.finditer(src):
        if m.group(1):
            names.add(m.group(1))
        else:
            names.update(n.strip().split(" ")[0] for n in m.group(2).split(","))
    hit = False
    for n in names:
        last = n.split(".")[-1]
        if last == "timing":
            hit = True
            break
    _seen[key] = hit
    return hit


def file_rule(argv, cwd):
    s = script_of(argv, cwd)
    if s and under(s):
        if re.fullmatch(r".*time.*\.py", os.path.basename(s)):
            return "R2 time-name"
        if uses_timing(s):
            return "R3 timing.py"
    return None


if len(sys.argv) > 1:               # --classify CWD ARGV...
    print(file_rule(sys.argv[2:], os.path.realpath(sys.argv[1])) or "none")
    sys.exit(0)

procs = {}
for d in os.listdir("/proc"):
    if d.isdigit():
        r = proc(d)
        if r:
            procs[int(d)] = r

sealed = {pid for pid, (argv, _, _) in procs.items()
          if any(os.path.realpath(os.path.join(procs[pid][2], a)) == SEALED
                 for a in argv[:3] if a.endswith("sealed_run.sh"))}
me = os.getpid()
for pid, (argv, ppid, cwd) in sorted(procs.items()):
    if pid == me:
        continue
    rule = None
    p, hops = pid, 0
    while p in procs and hops < 64:
        if p in sealed:
            rule = "R1 sealed_run"
            break
        p, hops = procs[p][1], hops + 1
    if rule is None:
        rule = file_rule(argv, cwd)
    if rule:
        print(f"{pid} [{rule}] {' '.join(argv)[:100]}")
PY
}

if [ "${1:-}" = "--classify" ]; then
    shift
    timed_runs "$@"
    exit 0
fi

if [ "${1:-}" = "--check" ]; then
    r=$(timed_runs)
    if [ -n "$r" ]; then echo "lumens-per-watt timed run in progress:"; echo "$r"; exit 1; fi
    echo "no lumens-per-watt timed run"; exit 0
fi

if [ "${1:-}" = "--run" ]; then
    shift
    until "$0" --check > /dev/null; do sleep 30; done
    set -m
    "$@" &
    pid=$!
    "$0" "$pid" >&2 &
    # `wait` also returns when the guard pauses CMD; wait until it is gone.
    while :; do
        wait "$pid"
        rc=$?
        kill -0 "$pid" 2>/dev/null || exit "$rc"
        sleep 5
    done
fi

PGID=$1
paused=0
while kill -0 -- "-$PGID" 2>/dev/null; do
    r=$(timed_runs)
    if [ -n "$r" ] && [ "$paused" -eq 0 ]; then
        kill -STOP -- "-$PGID" 2>/dev/null
        paused=1
        echo "[$(date -Is)] PAUSED pgid $PGID for: $(paste -sd';' <<< "$r" | sed 's/;/; /g')"
    elif [ -z "$r" ] && [ "$paused" -eq 1 ]; then
        kill -CONT -- "-$PGID" 2>/dev/null
        paused=0
        echo "[$(date -Is)] RESUMED pgid $PGID"
    fi
    sleep 5
done
[ "$paused" -eq 1 ] && kill -CONT -- "-$PGID" 2>/dev/null
echo "[$(date -Is)] pgid $PGID gone; guard exits"
