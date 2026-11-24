#!/usr/bin/env python3
"""Log analysis with unsupervised anomaly detection (bonus feature).

Reads the app's structured JSON logs - from a file / stdin, or straight from Elasticsearch -
and reports:

  1. Error-rate anomalies: per-minute error counts scored with a robust z-score
     (median / MAD), so a spike stands out even when the baseline is noisy.
  2. Log-template clustering: messages are reduced to templates by masking variable
     tokens (numbers, ids, hex, emails, paths), a lightweight version of the Drain
     algorithm, so thousands of lines collapse into a few recurring patterns.
  3. Suspicious behaviour: brute-force login attempts per user and slow endpoints.

Usage:
  kubectl -n taskmanager logs deploy/taskmanager-blue | python scripts/log_analyzer.py -
  python scripts/log_analyzer.py app.log
  python scripts/log_analyzer.py --es http://localhost:9200 --index 'taskmanager-*' --minutes 60
"""
import argparse
import json
import re
import statistics
import sys
import urllib.request
from collections import Counter, defaultdict

MASKS = [
    (re.compile(r"[0-9a-f]{16,}", re.I), "<HEX>"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "<EMAIL>"),
    (re.compile(r"(/[\w.-]+)+/?"), "<PATH>"),
    (re.compile(r"\b\d+(\.\d+)?\b"), "<NUM>"),
]


def template(message):
    for pattern, token in MASKS:
        message = pattern.sub(token, message)
    return message


def robust_z(values):
    """Median/MAD z-scores; resistant to the outliers we are trying to find."""
    if len(values) < 3:
        return [0.0] * len(values)
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values) or 1.0
    return [0.6745 * (v - med) / mad for v in values]


def load_lines(source):
    stream = sys.stdin if source == "-" else open(source, encoding="utf-8")
    with stream:
        for line in stream:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_es(url, index, minutes, size=10000):
    query = {"size": size, "sort": [{"@timestamp": "asc"}],
             "query": {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}}}
    req = urllib.request.Request(f"{url.rstrip('/')}/{index}/_search", data=json.dumps(query).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - operator-supplied URL
        for hit in json.load(resp)["hits"]["hits"]:
            yield hit["_source"]


def analyse(records, z_threshold=3.5, slow_ms=500, brute_force=5):
    per_minute = defaultdict(lambda: {"total": 0, "errors": 0})
    templates = Counter()
    failed_logins = Counter()
    slow = Counter()
    levels = Counter()

    for r in records:
        ts = str(r.get("timestamp") or r.get("@timestamp") or "")[:16]  # YYYY-MM-DDTHH:MM
        level = r.get("level", "INFO")
        levels[level] += 1
        status = int(r.get("status") or 0)
        is_error = level in ("ERROR", "CRITICAL") or status >= 500
        per_minute[ts]["total"] += 1
        per_minute[ts]["errors"] += int(is_error)
        if level in ("WARNING", "ERROR", "CRITICAL"):
            templates[(level, template(str(r.get("message", ""))))] += 1
        if r.get("message") == "failed login":
            failed_logins[str(r.get("user"))] += 1
        if float(r.get("duration_ms") or 0) > slow_ms:
            slow[f"{r.get('method')} {r.get('path')}"] += 1

    minutes = sorted(per_minute)
    errors = [per_minute[m]["errors"] for m in minutes]
    anomalies = [
        {"minute": m, "errors": per_minute[m]["errors"], "total": per_minute[m]["total"], "z": round(z, 2)}
        for m, z in zip(minutes, robust_z(errors)) if z >= z_threshold and per_minute[m]["errors"] > 0
    ]
    return {
        "records": sum(levels.values()),
        "levels": dict(levels),
        "error_spikes": anomalies,
        "top_patterns": [{"level": lv, "pattern": p, "count": c} for (lv, p), c in templates.most_common(10)],
        "possible_brute_force": {u: c for u, c in failed_logins.items() if c >= brute_force},
        "slow_endpoints": dict(slow.most_common(5)),
    }


def print_report(report):
    print(f"Analysed {report['records']} log records  levels={report['levels']}")
    print("\nError-rate anomalies (robust z-score):")
    for a in report["error_spikes"] or [{"minute": "-", "errors": 0, "total": 0, "z": 0}]:
        if a["minute"] == "-":
            print("  none detected")
        else:
            print(f"  {a['minute']}  errors={a['errors']}/{a['total']}  z={a['z']}")
    print("\nMost frequent warning/error patterns:")
    for p in report["top_patterns"] or []:
        print(f"  {p['count']:>5}  {p['level']:<8} {p['pattern']}")
    if not report["top_patterns"]:
        print("  none")
    print("\nPossible brute-force login attempts:", report["possible_brute_force"] or "none")
    print("Slow endpoints (>500 ms):", report["slow_endpoints"] or "none")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", default="-", help="log file or '-' for stdin")
    ap.add_argument("--es", help="Elasticsearch URL, e.g. http://localhost:9200")
    ap.add_argument("--index", default="taskmanager-*")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)

    records = load_es(args.es, args.index, args.minutes) if args.es else load_lines(args.source)
    report = analyse(records)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 1 if report["error_spikes"] else 0


if __name__ == "__main__":
    sys.exit(main())
