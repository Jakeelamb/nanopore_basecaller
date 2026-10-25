import ctypes
import os
from pathlib import Path
import signal
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def adopt_orphans():
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(36, 1, 0, 0, 0) == 0, "cannot become child subreaper")
    enabled = ctypes.c_int()
    require(libc.prctl(37, ctypes.byref(enabled), 0, 0, 0) == 0 and enabled.value == 1,
            "child subreaper not enabled")


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_group(process, pgid, grace=0.4):
    require(pgid == process.pid and pgid != os.getpgrp(), "invalid owned stage group")
    event = dict(pgid=pgid, leader_exited_before_cleanup=process.poll() is not None,
                 term_sent=False, kill_sent=False, reaped=[])
    for sig, field, duration in ((signal.SIGTERM, "term_sent", grace),
                                 (signal.SIGKILL, "kill_sent", 1.0)):
        if group_exists(pgid):
            try:
                os.killpg(pgid, sig)
                event[field] = True
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            # Popen owns its leader's wait status. Reap adopted children only afterward.
            if process.poll() is not None:
                while True:
                    try:
                        pid, status = os.waitpid(-pgid, os.WNOHANG)
                    except ChildProcessError:
                        break
                    if pid == 0:
                        break
                    event["reaped"].append(dict(pid=pid, status=status))
            if not group_exists(pgid):
                event["terminal"] = True
                return event
            time.sleep(0.02)
    require(not group_exists(pgid), "owned stage group remains after SIGKILL")
    event["terminal"] = True
    return event


def read_stat(pid):
    fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(") ", 1)[1].split()
    return dict(pid=pid, ppid=int(fields[1]), start=int(fields[19]),
                rss=int(fields[21]) * os.sysconf("SC_PAGE_SIZE"))


def pid_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def sample_processes(known, read=read_stat):
    controller = os.getpid()
    table = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        try:
            table[pid] = read(pid)
        except (FileNotFoundError, ProcessLookupError):
            require(not pid_exists(pid), "live process stat disappeared: " + str(pid))
    for pid in set(known) | {controller}:
        require(pid in table or not pid_exists(pid), "known live process absent from census: " + str(pid))
    require(controller in table, "controller absent from process census")
    owned = {controller}
    while True:
        expanded = owned | {pid for pid, row in table.items() if row["ppid"] in owned}
        if expanded == owned:
            return [table[pid] for pid in sorted(owned)]
        owned = expanded


def join_monitor(thread, done, timeout=1):
    done.set()
    thread.join(timeout=timeout)
    require(not thread.is_alive(), "resource monitor not terminal after bounded join")
