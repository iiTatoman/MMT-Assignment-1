"""
apps.chatapp
~~~~~~~~~~~~

Section 2.3 — Hybrid Chat Application
======================================

Implements the required chat application combining:
  - Client-server paradigm  (AsynapRous tracker server)
  - Peer-to-peer paradigm   (asyncio TCP direct peer connections)
  - Non-blocking communication (threading + asyncio coroutines)

API endpoints on tracker (client-server phase)
----------------------------------------------
  POST /login            Authenticate, create session token (RFC 6265)
  POST /submit-info      Register peer ip:port with tracker
  GET  /get-list         Return active peer list (peer discovery)
  POST /add-list         Join a channel
  POST /connect-peer     Notify tracker of a P2P link
  POST /broadcast-peer   Broadcast message stored in tracker
  POST /send-peer        Direct message via tracker (fallback)
  GET  /messages         Fetch message history for a channel

Peer-to-peer phase
------------------
  PeerNode.start_server()    — asyncio TCP listener for inbound P2P messages
  PeerNode.connect_to_peer() — asyncio TCP client to outbound peers
  PeerNode.broadcast()       — send message directly to all connected peers

Non-blocking model
------------------
  Tracker API  -> AsynapRous (threading backend)
  P2P server   -> asyncio.start_server  (coroutine)
  P2P client   -> asyncio.open_connection (coroutine)
"""

import json
import asyncio
import threading
import hashlib
import time
import base64
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daemon import AsynapRous
from daemon.response import USER_DB, SESSION_STORE


# Shared in-memory state (tracker database)

PEER_REGISTRY = {}           # { peer_id -> {ip, port, username, joined} }
PEER_LOCK     = threading.Lock()

CHANNELS = {"general": [], "random": [], "tech": []}
CHANNEL_LOCK = threading.Lock()

MESSAGES = {"general": [], "random": [], "tech": []}
MSG_LOCK = threading.Lock()


# Helpers

def _ts():
    return time.strftime("%H:%M:%S")

def _ok(data=None):
    payload = {"status": "ok"}
    if data is not None:
        payload["data"] = data
    return json.dumps(payload).encode("utf-8")

def _err(msg):
    return json.dumps({"status": "error", "message": msg}).encode("utf-8")

def _parse_body(body):
    try:
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return {}

def _auth_from_headers(headers):
    """Resolve authenticated username from session cookie or Basic-Auth header."""
    if not hasattr(headers, 'get'):
        return None
    # Session cookie (RFC 6265)
    cookie_str = headers.get("cookie", "")
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if pair.startswith('session_id='):
            token = pair.split('=', 1)[1]
            if token in SESSION_STORE:
                return SESSION_STORE[token]
    # Basic auth fallback (RFC 2617)
    auth_hdr = headers.get("authorization", "")
    if auth_hdr.lower().startswith("basic "):
        try:
            creds = base64.b64decode(auth_hdr.split(' ', 1)[1]).decode()
            user, pwd = creds.split(':', 1)
            if USER_DB.get(user) == pwd:
                return user
        except Exception:
            pass
    return None



# Client-server paradigm


tracker = AsynapRous()


@tracker.route('/login', methods=['POST'])
def chat_login(headers, body):
    """POST /login — authenticate and issue a session token."""
    data     = _parse_body(body)
    username = data.get('username') or data.get('user')
    password = data.get('password') or data.get('pass')

    if not username and hasattr(headers, 'get'):
        auth_hdr = headers.get('authorization', '')
        if auth_hdr.lower().startswith('basic '):
            try:
                creds = base64.b64decode(auth_hdr.split(' ', 1)[1]).decode()
                username, password = creds.split(':', 1)
            except Exception:
                pass

    if not username or USER_DB.get(username) != password:
        return _err("Invalid username or password")

    token = hashlib.sha256(
        "{}:{}:chat".format(username, time.time()).encode()
    ).hexdigest()
    SESSION_STORE[token] = username
    print("[ChatApp] Login: user={} token={}...".format(username, token[:8]))
    return _ok({"token": token, "username": username})


@tracker.route('/submit-info', methods=['POST'])
def submit_info(headers, body):
    """POST /submit-info — peer registration."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data      = _parse_body(body)
    peer_ip   = data.get('ip')
    peer_port = data.get('port')
    if not peer_ip or not peer_port:
        return _err("Missing ip or port")

    peer_id = "{}:{}".format(peer_ip, peer_port)
    with PEER_LOCK:
        PEER_REGISTRY[peer_id] = {
            "ip":       peer_ip,
            "port":     int(peer_port),
            "username": username,
            "joined":   _ts(),
        }
    print("[ChatApp] Registered peer {} ({})".format(peer_id, username))
    return _ok({"peer_id": peer_id})


@tracker.route('/get-list', methods=['GET'])
def get_list(headers, body):
    """GET /get-list — peer discovery, return active peers and channels."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    with PEER_LOCK:
        peers = dict(PEER_REGISTRY)
    with CHANNEL_LOCK:
        channels = {k: list(v) for k, v in CHANNELS.items()}

    return _ok({"peers": peers, "channels": channels})


@tracker.route('/add-list', methods=['POST'])
def add_list(headers, body):
    """POST /add-list — join a channel (channel listing)."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data    = _parse_body(body)
    channel = data.get('channel', 'general')
    peer_id = data.get('peer_id')
    if not peer_id:
        return _err("Missing peer_id")

    with CHANNEL_LOCK:
        if channel not in CHANNELS:
            CHANNELS[channel] = []
            MESSAGES[channel] = []
        if peer_id not in CHANNELS[channel]:
            CHANNELS[channel].append(peer_id)

    print("[ChatApp] {} joined channel={}".format(peer_id, channel))
    return _ok({"channel": channel, "members": CHANNELS[channel]})


@tracker.route('/connect-peer', methods=['POST'])
def connect_peer(headers, body):
    """POST /connect-peer — connection setup notification."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data      = _parse_body(body)
    from_peer = data.get('from')
    to_peer   = data.get('to')
    if not from_peer or not to_peer:
        return _err("Missing from or to")

    print("[ChatApp] P2P: {} <-> {}".format(from_peer, to_peer))
    return _ok({"connected": [from_peer, to_peer]})


@tracker.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers, body):
    """POST /broadcast-peer — store broadcast message in tracker history."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data    = _parse_body(body)
    channel = data.get('channel', 'general')
    text    = data.get('text', '')
    peer_id = data.get('peer_id', '')

    msg = {"from": username, "peer": peer_id, "text": text, "ts": _ts()}
    with MSG_LOCK:
        MESSAGES.setdefault(channel, []).append(msg)

    print("[ChatApp] Broadcast [{}] {}: {}".format(channel, username, text))
    return _ok({"message": msg})


@tracker.route('/send-peer', methods=['POST'])
def send_peer(headers, body):
    """POST /send-peer — direct message via tracker (fallback)."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data    = _parse_body(body)
    to_peer = data.get('to')
    text    = data.get('text', '')

    channel = "__dm__{}__{}".format(username, to_peer)
    msg     = {"from": username, "to": to_peer, "text": text, "ts": _ts()}
    with MSG_LOCK:
        MESSAGES.setdefault(channel, []).append(msg)

    print("[ChatApp] DM {} -> {}: {}".format(username, to_peer, text))
    return _ok({"message": msg})


@tracker.route('/messages', methods=['GET'])
def get_messages(headers, body):
    """GET /messages — fetch message history for a channel."""
    username = _auth_from_headers(headers)
    if not username:
        return _err("Unauthorized")

    data    = _parse_body(body)
    channel = data.get('channel', 'general') if isinstance(data, dict) else 'general'

    with MSG_LOCK:
        msgs = list(MESSAGES.get(channel, []))

    return _ok({"channel": channel, "messages": msgs})

# Peer-to-peer paradigm

class PeerNode:
    """Single chat peer combining inbound server + outbound client.

    Non-blocking model: asyncio coroutines (start_server / open_connection).
    """

    def __init__(self, username, listen_host, listen_port,
                 tracker_host, tracker_port):
        self.username     = username
        self.listen_host  = listen_host
        self.listen_port  = int(listen_port)
        self.tracker_host = tracker_host
        self.tracker_port = int(tracker_port)
        self.peer_id      = "{}:{}".format(listen_host, listen_port)
        self.token        = None
        self.connections  = {}        # {peer_id: asyncio.StreamWriter}
        self._conn_lock   = asyncio.Lock()
        self.inbox        = []

    # ---- Tracker REST calls (sync, run before event loop) ----

    def _tracker_request(self, method, path, body=None):
        import http.client, json as _j
        conn = http.client.HTTPConnection(
            self.tracker_host, self.tracker_port, timeout=5)
        hdrs = {"Content-Type": "application/json"}
        if self.token:
            hdrs["Cookie"] = "session_id={}".format(self.token)
        payload = _j.dumps(body).encode() if body else b""
        try:
            conn.request(method, path, payload, hdrs)
            resp = conn.getresponse()
            return _j.loads(resp.read().decode())
        except Exception as e:
            print("[Peer] tracker error: {}".format(e))
            return {}
        finally:
            conn.close()

    def login(self, password):
        data = self._tracker_request(
            'POST', '/login', {'username': self.username, 'password': password})
        if data.get('status') == 'ok':
            self.token = data['data']['token']
            print("[Peer] Logged in as {}".format(self.username))
            return True
        return False

    def register(self):
        return self._tracker_request(
            'POST', '/submit-info',
            {'ip': self.listen_host, 'port': self.listen_port})

    def fetch_peers(self):
        return self._tracker_request('GET', '/get-list')

    def join_channel(self, channel):
        return self._tracker_request(
            'POST', '/add-list',
            {'channel': channel, 'peer_id': self.peer_id})

    def notify_connect(self, to_peer_id):
        return self._tracker_request(
            'POST', '/connect-peer',
            {'from': self.peer_id, 'to': to_peer_id})

    # ---- Async P2P inbound server ----

    async def _handle_inbound(self, reader, writer):
        """Coroutine: receive P2P messages from a connected peer."""
        addr = writer.get_extra_info('peername')
        print("[Peer] Inbound P2P from {}".format(addr))
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                msg = json.loads(line.decode().strip())
                self.inbox.append(msg)
                # Message display — notification
                print("[Peer] <<< [{}] {}: {}".format(
                    msg.get('channel', '?'),
                    msg.get('from', '?'),
                    msg.get('text', '')))
        except Exception as e:
            print("[Peer] Inbound error: {}".format(e))
        finally:
            writer.close()

    async def start_server(self):
        """Start asyncio P2P listener (non-blocking coroutine)."""
        srv = await asyncio.start_server(
            self._handle_inbound, self.listen_host, self.listen_port)
        print("[Peer] P2P server on {}:{}".format(
            self.listen_host, self.listen_port))
        async with srv:
            await srv.serve_forever()

    # ---- Async P2P outbound client ----

    async def connect_to_peer(self, peer_id, peer_ip, peer_port):
        """Connection setup — open outbound P2P link."""
        async with self._conn_lock:
            if peer_id in self.connections:
                return
        try:
            reader, writer = await asyncio.open_connection(peer_ip, int(peer_port))
            async with self._conn_lock:
                self.connections[peer_id] = writer
            self.notify_connect(peer_id)
            print("[Peer] Connected to {}".format(peer_id))
        except Exception as e:
            print("[Peer] Cannot connect to {}: {}".format(peer_id, e))

    async def broadcast(self, channel, text):
        """Broadcast — direct peer communication, no tracker routing."""
        msg = json.dumps({
            "from": self.username, "channel": channel,
            "text": text, "ts": _ts(),
        }) + "\n"
        encoded = msg.encode('utf-8')
        async with self._conn_lock:
            peers = dict(self.connections)
        dead = []
        for pid, writer in peers.items():
            try:
                writer.write(encoded)
                await writer.drain()
            except Exception:
                dead.append(pid)
        async with self._conn_lock:
            for d in dead:
                self.connections.pop(d, None)

    async def discover_peers_forever(self):
        """Keep checking tracker for new peers and connect automatically."""
        while True:
            try:
                peer_data = await asyncio.to_thread(self.fetch_peers)
                peers = peer_data.get('data', {}).get('peers', {})

                for pid, info in peers.items():
                    if pid != self.peer_id:
                        await self.connect_to_peer(pid, info['ip'], info['port'])

            except Exception as e:
                print("[Peer] Discovery error: {}".format(e))

            await asyncio.sleep(3)


    async def input_loop(self, channel):
        """Read terminal input and broadcast to connected peers."""
        print("[Peer] You can now type messages in terminal.")
        print("[Peer] Commands: /peers")
        print("[Peer] Press Ctrl+C to quit.\n")

        while True:
            try:
                text = await asyncio.to_thread(input, "[{}] > ".format(self.username))
            except EOFError:
                continue

            text = text.strip()
            if not text:
                continue

            if text == "/peers":
                async with self._conn_lock:
                    print("[Peer] Connected peers: {}".format(list(self.connections.keys())))
                continue

            await self.broadcast(channel, text)
            print("[Peer] >>> [{}] {}: {}".format(channel, self.username, text))

    async def run(self, password, channel='general'):
        """Full peer lifecycle: login -> register -> auto-discover -> listen + chat."""
        if not self.login(password):
            print("[Peer] Login failed")
            return

        self.register()
        self.join_channel(channel)

        print("[Peer] Ready on {} in channel '{}'".format(self.peer_id, channel))

        await asyncio.gather(
            self.start_server(),
            self.discover_peers_forever(),
            self.input_loop(channel),
        )


# Put It All Together   

def create_chatapp(ip, port):
    """Start the tracker chat server (AsynapRous, threading backend)."""
    tracker.prepare_address(ip, port)
    tracker.run()


def create_peer(username, password, listen_host, listen_port,
                tracker_host, tracker_port, channel='general'):
    """Start a P2P peer node (asyncio event loop)."""
    peer = PeerNode(username, listen_host, listen_port,
                    tracker_host, tracker_port)
    asyncio.run(peer.run(password, channel))
