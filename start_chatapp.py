"""
start_chatapp
~~~~~~~~~~~~~

Section 2.4 — Put It All Together

Entry point for launching the Chat tracker server process.
Run this first, then launch peer nodes with start_peer.py.

Usage:
    python start_chatapp.py --server-ip 0.0.0.0 --server-port 3000
"""

import argparse
from apps import create_chatapp

PORT = 3000

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='ChatApp',
        description='Start the AsynapRous Chat tracker server',
        epilog='Section 2.3/2.4 — Hybrid Chat Application'
    )
    parser.add_argument('--server-ip',   default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)

    args = parser.parse_args()
    create_chatapp(args.server_ip, args.server_port)
