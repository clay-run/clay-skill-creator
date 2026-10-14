#!/usr/bin/env python3
"""Send a CSV to a Clay webhook source, one JSON object per POST.

Why one row per POST: a webhook-fed Clay table resolves {{Webhook}}.<key> per row, so a CSV
import leaves those formulas blank and a posted JSON array is not split into rows.

Key mapping: --keymap points at a JSON file {"csv_header": "payload_key", ...,
"__drop__": ["header", ...]}. Headers not in the map are sent unchanged.

Resilience: one persistent connection per worker; 408/429/5xx retried with exponential backoff
times a random factor in [0.5, 1.5) (jitter), capped at 10 s; any other non-200 is written to the
failures file once and not retried. Worker count is capped at 12: measured throughput plateaus
around 8-9 rows/s and more workers only add rate-limit responses and permanent losses.

Python 3.9+. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import threading
import time
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from urllib.parse import urlparse

RETRYABLE = {408, 429, 500, 502, 503, 504}
NULL_TOKENS = {"nan", "none", "null"}
MAX_WORKERS = 12


def read_rows(path: Path, keymap: dict) -> list[dict]:
    drops = set(keymap.get("__drop__", []))
    renames = {k: v for k, v in keymap.items() if k != "__drop__"}
    delim = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, delimiter=delim)
        headers = reader.fieldnames or []
        if any(h is None or h.strip() == "" for h in headers):
            sys.exit("ABORT: the CSV has an empty header; every column needs a name")
        if len(set(headers)) != len(headers):
            sys.exit("ABORT: duplicated header in the CSV; two columns cannot share one payload key")
        rows = []
        for raw in reader:
            row = {}
            for k, v in raw.items():
                if k in drops:
                    continue
                val = "" if v is None or v.strip().lower() in NULL_TOKENS else v
                row[renames.get(k, k)] = val
            rows.append(row)
    return rows


def read_failures(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line)["row"])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="CSV or TSV to send")
    ap.add_argument("--from-failures", help="resend the rows in a failures JSONL written by a previous run")
    ap.add_argument("--keymap", help="JSON file: {csv_header: payload_key, '__drop__': [...]}")
    ap.add_argument("--webhook", help="the Clay webhook URL (required unless --dry-run)")
    ap.add_argument("--skip", type=int, default=0, help="rows already sent (resume offset)")
    ap.add_argument("--limit", type=int, default=None, help="send only the first N rows after --skip (the test send)")
    ap.add_argument("--workers", type=int, default=8, help="parallel connections; capped at %d" % MAX_WORKERS)
    ap.add_argument("--retries", type=int, default=8, help="attempts per row on retryable statuses")
    ap.add_argument("--progress", help="progress file, rewritten every 2 s")
    ap.add_argument("--failures", help="JSONL of rows that did not land, for targeted resend")
    ap.add_argument("--dry-run", action="store_true", help="print the first mapped payload and the key list; send nothing")
    args = ap.parse_args()

    if not args.file and not args.from_failures:
        ap.error("one of --file or --from-failures is required")
    keymap = json.loads(Path(args.keymap).read_text(encoding="utf-8")) if args.keymap else {}
    if args.from_failures:
        rows = read_failures(Path(args.from_failures))
    else:
        rows = read_rows(Path(args.file), keymap)
    rows = rows[args.skip:]
    if args.limit is not None:
        rows = rows[: args.limit]
    total = len(rows)

    if args.dry_run:
        print(f"rows to send: {total}")
        if rows:
            print("payload keys:", ", ".join(rows[0].keys()))
            print("first payload:", json.dumps(rows[0], ensure_ascii=False, indent=1))
        print("dry run: nothing sent")
        return

    if not args.webhook:
        ap.error("--webhook is required to send")
    if not args.progress:
        ap.error("--progress is required to send")
    if args.workers > MAX_WORKERS:
        sys.exit(f"ABORT: {args.workers} workers requested; capped at {MAX_WORKERS}. "
                 "Measured: more workers add 429s and permanent losses without adding throughput.")
    if total == 0:
        print("nothing to send")
        return

    u = urlparse(args.webhook)
    conn_cls = HTTPSConnection if u.scheme == "https" else HTTPConnection
    host, path = u.netloc, (u.path or "/") + (("?" + u.query) if u.query else "")

    lock = threading.Lock()
    st = {"done": 0, "ok": 0, "fail": 0}
    tally: dict[int, int] = {}
    failed: list[dict] = []
    t0 = time.time()

    def worker(slice_rows: list[dict]) -> None:
        conn = conn_cls(host, timeout=20)
        for row in slice_rows:
            body = json.dumps(row, ensure_ascii=False).encode("utf-8")
            ok = False
            last_status = None
            for attempt in range(args.retries):
                try:
                    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
                    resp = conn.getresponse()
                    resp.read()
                    last_status = resp.status
                    with lock:
                        tally[resp.status] = tally.get(resp.status, 0) + 1
                    if resp.status == 200:
                        ok = True
                        break
                    if resp.status not in RETRYABLE:
                        break
                except Exception:
                    last_status = "conn"
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = conn_cls(host, timeout=20)
                time.sleep(min(2 ** attempt, 10) * (0.5 + random.random()))
            with lock:
                st["done"] += 1
                if ok:
                    st["ok"] += 1
                else:
                    st["fail"] += 1
                    failed.append({"status": last_status, "row": row})

    def write_progress(final: bool = False) -> None:
        elapsed = max(time.time() - t0, 1e-6)
        rate = st["done"] / elapsed
        tally_s = " · ".join(f"{k}: {v}" for k, v in sorted(tally.items(), key=lambda kv: str(kv[0])))
        text = (f"done {st['done']} / {total} · ok {st['ok']} · failed {st['fail']} · "
                f"{rate:.1f} rows/s · elapsed {int(elapsed)}s · status tally: {tally_s or '-'}"
                + (" · FINISHED" if final else ""))
        Path(args.progress).write_text(text + "\n", encoding="utf-8")

    slices = [rows[i::args.workers] for i in range(args.workers)]
    threads = [threading.Thread(target=worker, args=(s,), daemon=True) for s in slices if s]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        write_progress()
        time.sleep(2)
    write_progress(final=True)

    if args.failures and failed:
        with Path(args.failures).open("a", encoding="utf-8") as fh:
            for f in failed:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(Path(args.progress).read_text(encoding="utf-8").strip())
    if failed:
        print(f"{len(failed)} rows did not land" + (f"; written to {args.failures}" if args.failures else ""))


if __name__ == "__main__":
    main()
