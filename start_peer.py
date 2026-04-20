#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
start_peer
~~~~~~~~~~

Section 2.4 — Put It All Together

Entry point for launching a single P2P peer node.
Each peer connects to the tracker then talks directly to other peers.

Usage:
    python start_peer.py --username alice --password alice123 \\
                         --listen-port 4001 \\
                         --tracker-ip 127.0.0.1 --tracker-port 3000 \\
                         --channel general
"""

import argparse
from apps import create_peer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Peer',
        description='Start an AsynapRous Chat peer node',
        epilog='Section 2.3/2.4 — Hybrid P2P Chat'
    )
    parser.add_argument('--username',     default='alice')
    parser.add_argument('--password',     default='alice123')
    parser.add_argument('--listen-ip',    default='127.0.0.1')
    parser.add_argument('--listen-port',  type=int, default=4001)
    parser.add_argument('--tracker-ip',   default='127.0.0.1')
    parser.add_argument('--tracker-port', type=int, default=3000)
    parser.add_argument('--channel',      default='general')

    args = parser.parse_args()
    create_peer(
        args.username,
        args.password,
        args.listen_ip,
        args.listen_port,
        args.tracker_ip,
        args.tracker_port,
        args.channel,
    )
