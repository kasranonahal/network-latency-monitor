"""Command-line entry point, config loading, reporting and CI exit codes."""
import argparse
import asyncio
import csv
import json
from dataclasses import asdict
from pathlib import Path
from .monitor import Target, group_summaries, run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Concurrent TCP/HTTP(S) network health monitor")
    parser.add_argument("--config", help="JSON config with a targets array")
    parser.add_argument("--host", help="Single target host")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--protocol", choices=["tcp", "http", "https"], default="tcp")
    parser.add_argument("--path", default="/")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--csv", help="Write per-probe samples to CSV")
    parser.add_argument("--json", dest="json_path", help="Write summary and samples to JSON")
    parser.add_argument("--min-availability", type=float, default=0, help="Fail if any target availability falls below this percent")
    parser.add_argument("--max-p95", type=float, help="Fail if any target p95 latency exceeds milliseconds")
    args = parser.parse_args(argv)
    if args.count < 1 or args.interval < 0 or not 0 <= args.min_availability <= 100 or (args.max_p95 is not None and args.max_p95 < 0):
        parser.error("invalid count, interval or threshold")
    if bool(args.config) == bool(args.host):
        parser.error("provide exactly one of --config or --host")
    try:
        if args.config:
            data = json.loads(Path(args.config).read_text(encoding="utf-8"))
            targets = [Target(**item) for item in data["targets"]]
        else:
            targets = [Target(name=args.host, host=args.host, port=args.port, protocol=args.protocol, path=args.path, timeout=args.timeout)]
        if not targets or len({t.name for t in targets}) != len(targets):
            raise ValueError("targets must have unique names and cannot be empty")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(f"invalid targets: {exc}")
    samples = asyncio.run(run(targets, args.count, args.interval))
    summaries = group_summaries(samples)
    for name, stats in summaries.items():
        p95 = str(stats["p95_ms"]) if stats["p95_ms"] is not None else "N/A"
        print(f"{name}: availability={stats['availability_pct']}% p95={p95}ms jitter={stats['jitter_ms']}ms successful={stats['successful']}/{stats['total']}")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(samples[0])))
            writer.writeheader()
            writer.writerows(asdict(s) for s in samples)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps({"summary": summaries, "samples": [asdict(s) for s in samples]}, indent=2) + "\n", encoding="utf-8")
    failed = any(s["availability_pct"] < args.min_availability or (args.max_p95 is not None and (s["p95_ms"] is None or s["p95_ms"] > args.max_p95)) for s in summaries.values())
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
