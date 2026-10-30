"""Backward-compatible entry point for the network observability CLI.

Usage: python monitor.py --host example.com --port 443
"""
from netwatch.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
