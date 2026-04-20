"""
start_peer
~~~~~~~~~~~~~~~~~

Entry point for a Peer process (Task 2.3).

Steps at startup:
  1. Register this peer with the Tracker via POST /submit-info.
  2. Fetch the full peer list via GET /get-list.
  3. Call POST /connect-peer on itself for each discovered peer.
  4. Launch the AsynapRous REST app (blocks here).

Usage:
    # Terminal 1 – tracker
    python start_tracker.py --server-port 5000

    # Terminal 2 – first peer
    python start_peer.py --username alice --server-port 6000 --p2p-port 6100

    # Terminal 3 – second peer
    python start_peer.py --username bob   --server-port 7000 --p2p-port 7100
"""

import argparse
import json
import socket
import time

from apps.peerapp import create_peerapp, peer_connections, state_lock, _send_to_peer

# -------------------------------------------------------------------
# Tracker connection config (override via env or extend CLI if needed)
# -------------------------------------------------------------------
TRACKER_IP   = "127.0.0.1"
TRACKER_PORT = 5000


# -------------------------------------------------------------------
# Minimal raw-HTTP helpers (no external libraries allowed)
# -------------------------------------------------------------------

def _raw_request(method, ip, port, path, payload=None):
    """Send a raw HTTP/1.1 request and return the response body as a string.

    :param method:  HTTP method string (e.g. 'POST', 'GET').
    :param ip:      Target IP.
    :param port:    Target port.
    :param path:    Request path (e.g. '/submit-info').
    :param payload: dict to JSON-encode as the request body (POST only).
    :return:        Response body string, or empty string on error.
    """
    try:
        body_bytes = json.dumps(payload).encode("utf-8") if payload else b""

        request = (
            "{method} {path} HTTP/1.1\r\n"
            "Host: {ip}:{port}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {clen}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(
            method=method, path=path, ip=ip, port=port, clen=len(body_bytes)
        ).encode("utf-8") + body_bytes

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ip, port))
        s.sendall(request)

        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        s.close()

        # Split off HTTP header and return body
        parts = response.split(b"\r\n\r\n", 1)
        return parts[1].decode("utf-8", errors="replace") if len(parts) > 1 else ""
    except Exception as e:
        print("[StartPeer] HTTP request error ({} {}:{}{}): {}".format(method, ip, port, path, e))
        return ""


def http_post(ip, port, path, payload):
    """POST JSON payload and return parsed response dict."""
    raw = _raw_request("POST", ip, port, path, payload)
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def http_get(ip, port, path):
    """GET and return parsed response dict."""
    raw = _raw_request("GET", ip, port, path)
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Peer",
        description="CO3094 – Hybrid Chat Peer",
        epilog="Peer daemon"
    )
    parser.add_argument("--username",    required=True,
                        help="Username for this peer (e.g. alice)")
    parser.add_argument("--password",    default="password123",
                        help="Password (default: password123)")
    parser.add_argument("--server-ip",   default="0.0.0.0",
                        help="IP to bind the REST app (default: 0.0.0.0)")
    parser.add_argument("--server-port", type=int, default=6000,
                        help="Port for the REST app (default: 6000)")
    parser.add_argument("--p2p-port",    type=int, default=6100,
                        help="Port for the P2P TCP listener (default: 6100)")
    parser.add_argument("--my-ip",       default="127.0.0.1",
                        help="Public/LAN IP advertised to tracker (default: 127.0.0.1)")
    parser.add_argument("--tracker-ip",  default=TRACKER_IP,
                        help="Tracker server IP (default: 127.0.0.1)")
    parser.add_argument("--tracker-port",type=int, default=TRACKER_PORT,
                        help="Tracker server port (default: 5000)")

    args = parser.parse_args()

    tracker_ip   = args.tracker_ip
    tracker_port = args.tracker_port
    my_ip        = args.my_ip
    username     = args.username

    # ------------------------------------------------------------------
    # Step 1 – Authenticate with the Tracker
    # ------------------------------------------------------------------
    print("[Peer:{}] Logging in to tracker {}:{}".format(
        username, tracker_ip, tracker_port))
    login_resp = http_post(tracker_ip, tracker_port, "/login", {
        "username": username,
        "password": args.password,
    })
    if "error" in login_resp:
        print("[Peer:{}] Login failed: {}. Proceeding anyway.".format(
            username, login_resp["error"]))
    else:
        print("[Peer:{}] Login OK, token={}".format(username, login_resp.get("token")))

    # ------------------------------------------------------------------
    # Step 2 – Register this peer's P2P address with the Tracker
    # ------------------------------------------------------------------
    print("[Peer:{}] Registering with tracker at {}:{} (P2P port {})".format(
        username, my_ip, args.p2p_port, args.p2p_port))
    reg_resp = http_post(tracker_ip, tracker_port, "/submit-info", {
        "username": username,
        "ip":       my_ip,
        "port":     args.p2p_port,
    })
    print("[Peer:{}] submit-info response: {}".format(username, reg_resp))

    # ------------------------------------------------------------------
    # Step 3 – Discover existing peers
    # ------------------------------------------------------------------
    list_resp = http_get(tracker_ip, tracker_port, "/get-list")
    existing_peers = list_resp.get("peers", [])
    print("[Peer:{}] Discovered peers: {}".format(username, existing_peers))

    # ------------------------------------------------------------------
    # Step 4 – Connect to each discovered peer (skip self)
    # ------------------------------------------------------------------
    # Store peer connections directly into module-level dict before app starts
    for peer in existing_peers:
        pname = peer.get("username")
        pip   = peer.get("ip")
        pport = peer.get("port")
        if pname == username:
            continue  # don't connect to ourselves
        print("[Peer:{}] Connecting to peer '{}' at {}:{}".format(
            username, pname, pip, pport))
        with state_lock:
            peer_connections[pname] = (pip, pport)

    # ------------------------------------------------------------------
    # Step 5 – Launch the AsynapRous REST app (blocks)
    # ------------------------------------------------------------------
    print("[Peer:{}] Starting REST app on {}:{} and P2P listener on port {}".format(
        username, args.server_ip, args.server_port, args.p2p_port))
    create_peerapp(args.server_ip, args.server_port, args.p2p_port)
