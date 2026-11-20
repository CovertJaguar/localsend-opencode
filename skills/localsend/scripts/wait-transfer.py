#!/usr/bin/env python3
"""Block until localsend-cli reports a finished transfer, then print a verdict.

Reads the JSON-lines event log written by:

    localsend-cli receive --event-log /path/to/events.jsonl

and exits as soon as the first `session_complete` record shows up. The record
is written by the receiver only after every file announced in the manifest has
landed, so this is exact regardless of how long the batch takes. Polling only —
no inotify, no ReadDirectoryChanges — so Windows, macOS and Linux behave the
same with nothing but the standard library.

    python3 wait-transfer.py --event-log ~/ls-events.jsonl --timeout 900

Exit codes: 0 every file verified, 2 a file is missing or its size disagrees
with the announced manifest, 124 nothing arrived before the timeout.
"""

import argparse
import json
import os
import sys
import time


def _show(text):
    """Keep output readable on consoles with narrow encodings."""
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, "replace").decode(enc, "replace")


def follow(path, timeout, from_start):
    """Yield event records as they are appended to the log."""
    deadline = time.monotonic() + timeout
    offset = None
    pending = b""

    while True:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if offset is None:
                offset = 0 if from_start else size
            if size < offset:          # log truncated or rotated
                offset = 0
                pending = b""
            if size > offset:
                with open(path, "rb") as f:
                    f.seek(offset)
                    pending += f.read()
                    offset = f.tell()
                *lines, pending = pending.split(b"\n")
                for raw in lines:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        yield json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                continue               # drain before sleeping
        if time.monotonic() > deadline:
            raise TimeoutError
        time.sleep(0.25)


def report(record):
    files = record.get("files") or []
    ok = bool(record.get("ok"))
    print(_show(
        f"TRANSFER COMPLETE: {record.get('count')} file(s) from "
        f"{record.get('sender')} ({record.get('address')}) "
        f"in {record.get('duration_s')}s"
    ))
    for f in files:
        flag = "ok  " if f.get("ok") else "FAIL"
        print(_show(
            f"  {flag} {f.get('bytes'):>10} bytes  {f.get('sha256')}  {f.get('path')}"
        ))
    print(_show(
        f"TOTAL: {record.get('bytes')} bytes saved, "
        f"{record.get('declared_bytes')} announced, "
        f"verdict: {'ALL GOOD' if ok else 'CHECK FAILED'}"
    ))
    return 0 if ok else 2


def main():
    parser = argparse.ArgumentParser(
        description="Wait for a localsend-cli transfer and report its outcome.",
    )
    parser.add_argument("--event-log", required=True, metavar="PATH",
                        help="event log written by localsend-cli receive --event-log")
    parser.add_argument("--timeout", type=float, default=3600.0,
                        help="seconds to wait before giving up (default: 3600)")
    parser.add_argument("--from-start", action="store_true",
                        help="also report transfers already recorded in the log")
    args = parser.parse_args()

    path = os.path.expanduser(args.event_log)
    try:
        for record in follow(path, args.timeout, args.from_start):
            if record.get("event") == "session_complete":
                sys.exit(report(record))
    except TimeoutError:
        print(f"TIMEOUT: no completed transfer in {args.timeout:g}s "
              f"(watched {path})", file=sys.stderr)
        sys.exit(124)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
