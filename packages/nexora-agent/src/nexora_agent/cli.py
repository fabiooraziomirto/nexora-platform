"""nexora-agent CLI entrypoint.

Commands:
  nexora-agent pair    [--server URL] [--gateway URL] [--name NAME] [--type TYPE]
  nexora-agent start   [--server URL] [--gateway URL]
  nexora-agent status
  nexora-agent reset
  nexora-agent logs    (tail systemd journal)
  nexora-agent version
"""
import argparse
import asyncio
import json
import logging
import sys

from nexora_agent import config, credentials


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nexora-agent",
        description="Nexora IoT edge agent for Linux ARM/x86 devices",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # pair
    p_pair = sub.add_parser("pair", help="Pair this device with Nexora")
    p_pair.add_argument("--server", default=config.SERVER_URL, help="device-service URL")
    p_pair.add_argument("--gateway", default=config.GATEWAY_URL, help="nexora-edge gateway URL")
    p_pair.add_argument("--name", default=None, help="Device friendly name")
    p_pair.add_argument("--type", default="linux-agent", dest="device_type")

    # start
    p_start = sub.add_parser("start", help="Start the agent tunnel (foreground)")
    p_start.add_argument("--server", default=None)
    p_start.add_argument("--gateway", default=None)

    # status
    sub.add_parser("status", help="Show pairing status and device info")

    # reset
    sub.add_parser("reset", help="Clear credentials and unpair this device")

    # logs
    sub.add_parser("logs", help="Tail the systemd journal for nexora-agent")

    # version
    sub.add_parser("version", help="Print agent version")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.command == "pair":
        _cmd_pair(args)
    elif args.command == "start":
        _cmd_start(args)
    elif args.command == "status":
        _cmd_status()
    elif args.command == "reset":
        _cmd_reset()
    elif args.command == "logs":
        _cmd_logs()
    elif args.command == "version":
        _cmd_version()


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_pair(args) -> None:
    import socket
    name = args.name or socket.gethostname()
    print(f"Starting pairing for '{name}'...")
    print(f"  Server:  {args.server}")
    print(f"  Gateway: {args.gateway}")

    from nexora_agent import pairing
    try:
        creds = asyncio.run(pairing.run_pairing(
            server_url=args.server,
            gateway_url=args.gateway,
            device_name=name,
            device_type=args.device_type,
        ))
        print(f"\nPairing complete!")
        print(f"  Device ID: {creds['device_id']}")
        print(f"\nRun 'nexora-agent start' to connect.")
    except pairing.PairingExpired:
        print("Pairing timed out — the code was not entered in time.", file=sys.stderr)
        sys.exit(1)
    except pairing.PairingDenied:
        print("Pairing was denied by the owner.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Pairing failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _cmd_start(args) -> None:
    creds = credentials.load()
    if not creds:
        print("Device is not paired. Run 'nexora-agent pair' first.", file=sys.stderr)
        sys.exit(1)

    # Allow CLI overrides
    if args.server:
        creds["server_url"] = args.server
    if args.gateway:
        creds["gateway_url"] = args.gateway

    print(f"Starting nexora-agent — device_id={creds['device_id']}")
    print(f"  Server:  {creds['server_url']}")
    print(f"  Gateway: {creds['gateway_url']}")

    from nexora_agent import tunnel
    try:
        asyncio.run(tunnel.run(creds))
    except KeyboardInterrupt:
        print("\nAgent stopped.")


def _cmd_status() -> None:
    creds = credentials.load()
    if not creds:
        print("Status: NOT PAIRED")
        print("Run 'nexora-agent pair' to set up this device.")
        return

    print("Status: PAIRED")
    print(f"  Device ID:   {creds.get('device_id', 'unknown')}")
    print(f"  Name:        {creds.get('device_name', 'unknown')}")
    print(f"  Server:      {creds.get('server_url', 'unknown')}")
    print(f"  Gateway:     {creds.get('gateway_url', 'unknown')}")
    print(f"  Paired at:   {creds.get('paired_at', creds.get('saved_at', 'unknown'))}")

    # Offline queue depth
    from nexora_agent import offline_queue
    depth = offline_queue.depth()
    if depth:
        print(f"  Offline queue: {depth} items pending")

    # Credential storage backend
    from nexora_agent.credentials import _tpm_available
    backend = "TPM 2.0" if _tpm_available() else "file (/etc/nexora-agent/credentials.json)"
    print(f"  Credential store: {backend}")


def _cmd_reset() -> None:
    creds = credentials.load()
    if not creds:
        print("Device is not paired — nothing to reset.")
        return
    answer = input(f"Reset device '{creds.get('device_name', creds.get('device_id'))}' and clear credentials? [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return
    credentials.clear()
    print("Credentials cleared. Run 'nexora-agent pair' to re-pair.")


def _cmd_logs() -> None:
    import os
    os.execvp("journalctl", ["journalctl", "-u", "nexora-agent", "-f", "--no-pager"])


def _cmd_version() -> None:
    try:
        from importlib.metadata import version
        print(f"nexora-agent {version('nexora-agent')}")
    except Exception:
        print("nexora-agent (version unknown)")


if __name__ == "__main__":
    main()
