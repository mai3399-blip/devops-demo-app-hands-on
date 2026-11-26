#!/usr/bin/env python3
"""probe: knocks on the shop RATE times a second and prints one line per second.

    python3 probe.py http://localhost:8080
    python3 probe.py http://localhost:8081 --csv k8s.csv

Each line: the time, how many requests in that second succeeded and failed,
which versions answered, how many different containers answered, and why
requests failed. Ctrl-C prints a summary: requests sent, failed, and the
longest stretch in which every request failed. Standard library only.
"""
import argparse
import csv
import http.client
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import Counter


def reason(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP{e.code}"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(e, urllib.error.URLError):
        r = e.reason
        if isinstance(r, (socket.timeout, TimeoutError)):
            return "timeout"
        if isinstance(r, ConnectionRefusedError):
            return "refused"
        return type(r).__name__
    if isinstance(e, (http.client.RemoteDisconnected, ConnectionResetError)):
        return "reset"
    return type(e).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--rate", type=float, default=10, help="requests per second (10)")
    ap.add_argument("--timeout", type=float, default=1.0, help="seconds per request (1)")
    ap.add_argument("--csv", help="write every request to this file")
    a = ap.parse_args()

    rows = []
    lock = threading.Lock()

    def knock(t):
        try:
            with urllib.request.urlopen(a.url, timeout=a.timeout) as r:
                d = json.loads(r.read())
            row = (t, 1, str(d.get("version", "")), str(d.get("host", "")), "")
        except Exception as e:  # every failure is a result
            row = (t, 0, "", "", reason(e))
        with lock:
            rows.append(row)

    def line(sec):
        with lock:
            got = [r for r in rows if int(r[0]) == sec]
        ok = [r for r in got if r[1]]
        bad = [r for r in got if not r[1]]
        parts = [time.strftime("%H:%M:%S", time.localtime(sec)), f"ok {len(ok):2d}", f"fail {len(bad):2d}"]
        if ok:
            v = Counter(r[2] for r in ok)
            parts.append(" ".join(f"v{k}:{n}" for k, n in sorted(v.items())))
            parts.append(f"hosts {len({r[3] for r in ok})}")
        if bad:
            parts.append(" ".join(f"{k}:{n}" for k, n in Counter(r[4] for r in bad).most_common()))
        print("  ".join(parts), flush=True)

    start = time.time()
    first = int(start) + 1
    printed = first
    nxt = float(first)
    try:
        while True:
            now = time.time()
            if now < nxt:
                time.sleep(min(nxt - now, 0.05))
                continue
            threading.Thread(target=knock, args=(nxt,), daemon=True).start()
            nxt += 1.0 / a.rate
            while printed + 1 + a.timeout + 0.2 <= time.time():
                line(printed)
                printed += 1
    except KeyboardInterrupt:
        pass

    time.sleep(a.timeout + 0.2)
    last = int(nxt - 1.0 / a.rate)
    while printed <= last:
        line(printed)
        printed += 1

    with lock:
        done = sorted(rows)
    failed = [r for r in done if not r[1]]
    longest, best_start, run_start = 0.0, None, None
    for t, ok, *_ in done:
        if ok:
            run_start = None
            continue
        if run_start is None:
            run_start = t
        if t - run_start >= longest:
            longest, best_start = t - run_start, run_start
    pct = 100.0 * len(failed) / len(done) if done else 0.0
    print(f"\nsent {len(done)}, failed {len(failed)} ({pct:.1f}%)", flush=True)
    if best_start is not None:
        when = time.strftime("%H:%M:%S", time.localtime(best_start))
        print(f"longest stretch of failures: {longest + 1.0 / a.rate:.1f} s, from {when}", flush=True)

    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "ok", "version", "host", "error"])
            w.writerows((f"{r[0]:.3f}", r[1], r[2], r[3], r[4]) for r in done)


if __name__ == "__main__":
    main()
