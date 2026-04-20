"""
start_tracker
~~~~~~~~~~~~~~~~~

Entry point for the centralized Tracker server (Task 2.3).

Usage:
    python start_tracker.py --server-ip 0.0.0.0 --server-port 5000
"""

import argparse
from apps.tracker import create_tracker

TRACKER_PORT = 5000

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Tracker",
        description="CO3094 – Hybrid Chat Tracker Server",
        epilog="Tracker daemon"
    )
    parser.add_argument("--server-ip",   default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=TRACKER_PORT)

    args = parser.parse_args()
    print("[Tracker] Starting on {}:{}".format(args.server_ip, args.server_port))
    create_tracker(args.server_ip, args.server_port)
