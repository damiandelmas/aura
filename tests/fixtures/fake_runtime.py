#!/usr/bin/env python3
"""Deterministic terminal runtime used by Aura E2E tests."""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="fake")
    parser.add_argument("--mode", choices=["echo", "slow", "stuck", "error"], default="echo")
    args = parser.parse_args()

    print(f"READY {args.name}", flush=True)

    if args.mode == "stuck":
        while True:
            time.sleep(60)

    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if line == "/exit":
            print(f"EXIT {args.name}", flush=True)
            return 0
        if args.mode == "error":
            print(f"ERROR {args.name}: simulated failure", flush=True)
            continue
        if args.mode == "slow":
            print(f"BUSY {args.name}", flush=True)
            time.sleep(1)
        if line.startswith("[AURA MESSAGE") or line.startswith("[/AURA MESSAGE]") or not line:
            print(f"SEEN {args.name} {line}", flush=True)
        else:
            print(f"ACK {args.name} {line}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
