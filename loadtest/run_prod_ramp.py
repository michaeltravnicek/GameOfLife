"""Stepped media ramp against production, recorded so two runs can be compared.

The point is the before/after around moving media to Cloudflare R2. That only
means something if both runs are measured the same way, so the ramp lives in a
script rather than in a shell history: same steps, same duration, same endpoints,
results written to results/<label>/.

What it measures, and why that is the interesting thing: media is served by
Django itself, so a worker is busy for the whole file transfer. The number that
decides the R2 question is not image throughput — it is what image traffic does
to the API next to it. Every step therefore runs one polite API probe user
alongside the media users, and the report keeps the two apart.

Safety, because this points at a live site:

* every step stops on its own after --duration seconds;
* the ramp aborts as soon as a step produces a 5xx, rather than climbing on;
* --max-mb caps the total transfer, because Render bills egress and the average
  image here is about 930 kB.

Usage:

    /usr/bin/python3 run_prod_ramp.py --label before-r2
    # ... move media to R2, deploy ...
    /usr/bin/python3 run_prod_ramp.py --label after-r2
    /usr/bin/python3 run_prod_ramp.py --compare before-r2 after-r2
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results"
HOST = "https://www.gameofyolo.com"

# Two different questions, two different ramps.
#
# media: how does serving files hurt the API next to them (the R2 question).
#        Users are few because each one moves ~900 kB and Render bills egress.
# api:   how many API requests does the service actually take. Users are many
#        because a JSON response is tiny — but this run is meaningless unless
#        ANON_THROTTLE_RATE is raised on Render first, or every step past the
#        first just measures the throttle. See R2_BASELINE.md.
MODES = {
    "media": {"tags": "media", "steps": [3, 6, 12, 24]},
    "api": {"tags": "api", "steps": [10, 25, 50, 100, 200]},
}
STEPS = MODES["media"]["steps"]
LOCUST = [sys.executable, "-m", "locust"]


def run_step(users: int, duration: int, label: str, host: str, tags: str) -> dict:
    """One locust run at a fixed user count. Returns the parsed summary."""
    outdir = RESULTS / label
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = outdir / f"step-{users:03d}"

    cmd = LOCUST + [
        "-f", str(HERE / "locustfile_prod.py"),
        "--host", host,
        "--tags", tags,
        "--headless",
        "--users", str(users + 1),   # +1 is the fixed_count API probe user
        "--spawn-rate", str(max(users // 2, 1)),
        "--run-time", f"{duration}s",
        "--csv", str(prefix),
        "--only-summary",
    ]
    print(f"\n=== {users} users ({tags}), {duration}s ===", flush=True)
    subprocess.run(cmd, cwd=HERE, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return parse_stats(prefix.with_name(prefix.name + "_stats.csv"), users)


def parse_stats(path: pathlib.Path, users: int) -> dict:
    """Pull the rows we care about out of locust's _stats.csv."""
    rows = {}
    if not path.exists():
        return {"users": users, "error": f"no stats file at {path}"}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["Name"]] = row

    def num(row, key, default=0.0):
        try:
            return float(row.get(key) or default)
        except ValueError:
            return default

    out = {"users": users, "endpoints": {}}
    for name, row in rows.items():
        if name == "Aggregated":
            continue
        out["endpoints"][name] = {
            "requests": int(num(row, "Request Count")),
            "failures": int(num(row, "Failure Count")),
            "rps": round(num(row, "Requests/s"), 2),
            "p50_ms": round(num(row, "50%")),
            "p95_ms": round(num(row, "95%")),
            "max_ms": round(num(row, "Max Response Time")),
            "avg_size_b": round(num(row, "Average Content Size")),
        }
    agg = rows.get("Aggregated", {})
    out["total_requests"] = int(num(agg, "Request Count"))
    out["total_failures"] = int(num(agg, "Failure Count"))

    # Why the failures live in a second file: _stats.csv only counts failures,
    # it never says what they were. "429 throttled" and "503 server error" are
    # the same number there and opposite meanings here — one is the rate limiter
    # doing its job, the other is the site breaking under us.
    out["errors"] = {}
    failures_path = path.with_name(path.name.replace("_stats.csv", "_failures.csv"))
    if failures_path.exists():
        with open(failures_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                msg = (row.get("Error") or "").strip()
                out["errors"][msg] = out["errors"].get(msg, 0) + int(
                    float(row.get("Occurrences") or 0)
                )
    out["mb_transferred"] = round(sum(
        e["requests"] * e["avg_size_b"] for e in out["endpoints"].values()
    ) / 1e6, 1)
    return out


def summarise(step: dict, mode: str = "media") -> str:
    """One console line per step. The two modes have nothing in common to print."""
    ends = step["endpoints"]
    fails = step["total_failures"]
    total = step["total_requests"] or 1

    if mode == "api":
        rps = sum(v["rps"] for v in ends.values())
        p95 = max((v["p95_ms"] for v in ends.values()), default=0)
        # In api mode a failure is almost always a 429, and the share of them is
        # the thing to look at: 100 % means the run measured the rate limiter.
        return (f"  API {rps:6.1f} rps  p95 {p95:6.0f} ms   |   "
                f"{step['total_requests']:5} req   fails {fails} ({100*fails/total:.0f} %)")

    media = {k: v for k, v in ends.items() if k.startswith("MEDIA")}
    probe = {k: v for k, v in ends.items() if k.startswith("PROBE")}
    m_rps = sum(v["rps"] for v in media.values())
    m_p95 = max((v["p95_ms"] for v in media.values()), default=0)
    p_p95 = max((v["p95_ms"] for v in probe.values()), default=0)
    return (f"  media {m_rps:5.1f} rps  p95 {m_p95:6.0f} ms   |   "
            f"API probe p95 {p_p95:6.0f} ms   |   "
            f"{step['mb_transferred']:6.1f} MB   fails {fails}")


def ramp(label: str, duration: int, max_mb: float, host: str, mode: str) -> None:
    RESULTS.mkdir(exist_ok=True)
    cfg = MODES[mode]
    run = {"label": label, "mode": mode, "host": host,
           "started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "duration_per_step_s": duration, "steps": []}
    transferred = 0.0

    for users in cfg["steps"]:
        step = run_step(users, duration, label, host, cfg["tags"])
        if "error" in step:
            print(f"  !! {step['error']}")
            break
        run["steps"].append(step)
        print(summarise(step, mode), flush=True)

        transferred += step["mb_transferred"]

        server_errors = sum(n for msg, n in step["errors"].items()
                            if "server error" in msg)
        if server_errors:
            print(f"  !! {server_errors} server errors — stopping the ramp here")
            break

        throttled = sum(n for msg, n in step["errors"].items() if "429" in msg)
        if mode == "api" and throttled:
            # Almost certainly 429s: the run is measuring the rate limiter, not
            # the server. Climbing further would only produce more of them.
            share = 100 * throttled / (step["total_requests"] or 1)
            print(f"  !! {throttled} requests throttled ({share:.0f} %) — this step "
                  "measured the rate limiter. Is ANON_THROTTLE_RATE raised on Render?")
        if transferred >= max_mb:
            print(f"  !! transfer cap reached ({transferred:.0f} MB) — stopping")
            break

    run["total_mb"] = round(transferred, 1)
    out = RESULTS / label / "summary.json"
    out.write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(f"\nWrote {out}  ({run['total_mb']} MB transferred in total)")


def compare(before: str, after: str) -> None:
    """Print a markdown table of two labelled runs, step by step."""
    def load(label):
        path = RESULTS / label / "summary.json"
        if not path.exists():
            sys.exit(f"no results for {label!r} — run the ramp with --label {label} first")
        return json.loads(path.read_text(encoding="utf-8"))

    a, b = load(before), load(after)
    print(f"\n| Media users | {before} media p95 | {after} media p95 | "
          f"{before} API p95 | {after} API p95 |")
    print("|---|---|---|---|---|")
    for sa, sb in zip(a["steps"], b["steps"]):
        def p95(step, prefix):
            vals = [v["p95_ms"] for k, v in step["endpoints"].items() if k.startswith(prefix)]
            return max(vals) if vals else 0
        print(f"| {sa['users']} | {p95(sa,'MEDIA')} ms | {p95(sb,'MEDIA')} ms | "
              f"{p95(sa,'PROBE')} ms | {p95(sb,'PROBE')} ms |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", help="name for this run, e.g. before-r2")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--duration", type=int, default=20, help="seconds per step")
    ap.add_argument("--max-mb", type=float, default=400.0,
                    help="stop once this much has been transferred (Render bills egress)")
    ap.add_argument("--mode", choices=sorted(MODES), default="media",
                    help="media = the R2 question (default); api = raw API capacity")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args()

    if args.compare:
        compare(*args.compare)
    elif args.label:
        ramp(args.label, args.duration, args.max_mb, args.host, args.mode)
    else:
        ap.error("give either --label or --compare")


if __name__ == "__main__":
    main()
