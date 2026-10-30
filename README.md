# Network Latency Monitor

A dependency-free Python CLI for measuring TCP connection latency and success rate for network services. Produces both human-readable summaries and machine-readable CSV samples.

## Quick start

```bash
python monitor.py --host example.com --port 443 --count 5 --interval 1 --csv samples.csv
```

The measurement times the TCP handshake, not ICMP ping or end-to-end HTTP latency. A failed connection is recorded as an error and excluded from the successful-latency average.

## Test

```bash
python -m unittest discover -s tests -v
```
