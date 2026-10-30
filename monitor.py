import argparse
import csv
import socket
import statistics
import time
from datetime import datetime, timezone


def probe(host, port, timeout=2.0):
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.perf_counter() - start) * 1000, 2), None
    except OSError as exc:
        return None, str(exc)


def summarize(samples):
    successful = [row["latency_ms"] for row in samples if row["latency_ms"] is not None]
    return {"total": len(samples), "successful": len(successful), "success_rate": round(100 * len(successful) / len(samples), 1) if samples else 0.0,
            "min_ms": min(successful) if successful else None, "avg_ms": round(statistics.mean(successful), 2) if successful else None,
            "max_ms": max(successful) if successful else None}


def main():
    parser = argparse.ArgumentParser(description="TCP service latency sampler")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--csv", default=None)
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0 or args.timeout <= 0 or not 1 <= args.port <= 65535:
        parser.error("invalid count, interval, timeout, or port")
    rows = []
    for i in range(args.count):
        latency, error = probe(args.host, args.port, args.timeout)
        row = {"timestamp": datetime.now(timezone.utc).isoformat(), "host": args.host, "port": args.port, "latency_ms": latency, "error": error or ""}
        rows.append(row)
        print(f"[{i+1}/{args.count}] {latency} ms" if error is None else f"[{i+1}/{args.count}] failed: {error}")
        if i + 1 < args.count:
            time.sleep(args.interval)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(summarize(rows))


if __name__ == "__main__":
    main()
