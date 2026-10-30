"""Asynchronous TCP and HTTP probes with monotonic latency measurement."""
from __future__ import annotations

import asyncio
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Target:
    name: str
    host: str
    port: int = 443
    protocol: str = "tcp"
    path: str = "/"
    timeout: float = 3.0

    def __post_init__(self):
        if not self.name or not self.host:
            raise ValueError("target name and host are required")
        if not 1 <= self.port <= 65535 or self.timeout <= 0:
            raise ValueError("port must be 1..65535 and timeout positive")
        if self.protocol not in {"tcp", "http", "https"}:
            raise ValueError("protocol must be tcp, http or https")
        if not self.path.startswith("/"):
            raise ValueError("HTTP path must start with /")


@dataclass
class Result:
    timestamp: str
    name: str
    protocol: str
    host: str
    port: int
    ok: bool
    latency_ms: float | None
    status_code: int | None = None
    error: str | None = None


async def probe(target: Target) -> Result:
    """Latency is TCP connect for tcp; connect+request+response headers for HTTP(S)."""
    started = time.perf_counter()
    writer = None
    result = Result(datetime.now(timezone.utc).isoformat(), target.name, target.protocol, target.host, target.port, False, None)
    try:
        async def request():
            nonlocal writer
            reader, writer = await asyncio.open_connection(target.host, target.port, ssl=True if target.protocol == "https" else None, server_hostname=target.host if target.protocol == "https" else None)
            if target.protocol == "tcp":
                return None
            request_bytes = (f"HEAD {target.path} HTTP/1.1\r\nHost: {target.host}\r\nConnection: close\r\nUser-Agent: netwatch/1.0\r\n\r\n").encode("ascii")
            writer.write(request_bytes)
            await writer.drain()
            line = await reader.readline()
            parts = line.decode("latin-1").split()
            if len(parts) < 2 or not parts[0].startswith("HTTP/"):
                raise ValueError("invalid HTTP status line")
            return int(parts[1])
        code = await asyncio.wait_for(request(), timeout=target.timeout)
        result.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        result.status_code = code
        result.ok = code is None or 200 <= code < 400
        if not result.ok:
            result.error = f"HTTP {code}"
    except (OSError, ValueError, asyncio.TimeoutError, UnicodeError) as exc:
        result.error = "timeout" if isinstance(exc, asyncio.TimeoutError) else f"{type(exc).__name__}: {exc}"
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
    return result


async def run(targets: list[Target], count: int = 5, interval: float = 1.0) -> list[Result]:
    if count < 1 or interval < 0:
        raise ValueError("count must be positive and interval nonnegative")
    results = []
    for i in range(count):
        results.extend(await asyncio.gather(*(probe(t) for t in targets)))
        if i + 1 < count:
            await asyncio.sleep(interval)
    return results


def percentile(data: list[float], p: int) -> float | None:
    if not data:
        return None
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * p / 100
    lo, hi = math.floor(index), math.ceil(index)
    return round(sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (index - lo), 2)


def summarize(results: list[Result]) -> dict:
    if not results:
        return {"total": 0, "successful": 0, "availability_pct": 0.0, "avg_ms": None, "min_ms": None, "max_ms": None, "p50_ms": None, "p95_ms": None, "p99_ms": None, "jitter_ms": None}
    good = [r.latency_ms for r in results if r.ok and r.latency_ms is not None]
    return {"total": len(results), "successful": len(good), "availability_pct": round(100 * len(good) / len(results), 2),
            "avg_ms": round(statistics.mean(good), 2) if good else None,
            "min_ms": min(good) if good else None, "max_ms": max(good) if good else None,
            "p50_ms": percentile(good, 50), "p95_ms": percentile(good, 95),
            "p99_ms": percentile(good, 99),
            "jitter_ms": round(statistics.mean(abs(b-a) for a,b in zip(good, good[1:])), 2) if len(good)>1 else None}


def group_summaries(results: list[Result]) -> dict[str, dict]:
    return {name: summarize([r for r in results if r.name == name]) for name in sorted({r.name for r in results})}
