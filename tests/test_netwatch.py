import asyncio
import json
from pathlib import Path
import pytest
from netwatch.monitor import Target, Result, percentile, summarize, probe, run, group_summaries
from netwatch.cli import main


def test_percentiles():
    assert percentile([], 95) is None
    assert percentile([10, 20, 30, 40, 50], 50) == 30
    assert percentile([10, 20, 30, 40, 50], 95) == 48


def test_empty_summary():
    assert summarize([])["total"] == 0


def test_metrics():
    samples = [Result("", "db", "tcp", "localhost", 80, True, x) for x in (10, 20, 30)]
    samples += [Result("", "db", "tcp", "localhost", 80, False, None, error="timeout")]
    summary = summarize(samples)
    assert summary["availability_pct"] == 75
    assert summary["avg_ms"] == 20
    assert summary["jitter_ms"] == 10


def test_target_validation():
    with pytest.raises(ValueError):
        Target("x", "example.com", port=0)
    with pytest.raises(ValueError):
        Target("x", "example.com", protocol="icmp")


def test_successful_tcp_probe():
    async def scenario():
        async def handler(reader, writer):
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            result = await probe(Target("local", "127.0.0.1", port))
            assert result.ok and result.latency_ms is not None
    asyncio.run(scenario())


def test_http_failure_status():
    async def scenario():
        async def handler(reader, writer):
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            result = await probe(Target("local", "127.0.0.1", port, "http"))
            assert not result.ok and result.status_code == 503
    asyncio.run(scenario())


def test_invalid_cli_config(tmp_path):
    file = tmp_path / "bad.json"
    file.write_text('{"targets":[]}')
    with pytest.raises(SystemExit):
        main(["--config", str(file)])
