#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay events from exported topic/DLQ files")
    parser.add_argument("--input", required=True, help="Input JSONL file")
    parser.add_argument("--from-ts", type=float, default=0, help="Start timestamp")
    parser.add_argument("--to-ts", type=float, default=10**20, help="End timestamp")
    parser.add_argument("--tenant", default=None, help="Tenant filter")
    parser.add_argument("--correlation-id", default=None, help="Correlation id filter")
    args = parser.parse_args()

    replayed = 0
    with open(args.input, "r", encoding="utf-8") as fh:
        for line in fh:
            evt = json.loads(line)
            ts = float(evt.get("occurred_at", 0))
            if ts < args.from_ts or ts > args.to_ts:
                continue
            if args.tenant and evt.get("tenant_id") != args.tenant:
                continue
            if args.correlation_id and evt.get("correlation_id") != args.correlation_id:
                continue
            print(json.dumps(evt))
            replayed += 1
    print(f"replayed_events={replayed}")


if __name__ == "__main__":
    main()
