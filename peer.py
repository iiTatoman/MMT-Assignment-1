"""
peer.py
~~~~~~~

Only the Python standard library is used.
"""

import argparse
import asyncio
import base64
import json
import sys
import time


class PeerNode:
    """A non-blocking peer node using asyncio."""

    def __init__(self, name, ip, port, tracker_host, tracker_port, auth=None):
        self.name = name
        self.ip = ip
        self.port = port
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.auth = auth
        self.channel = "general"
        self.peers = {}
        self.peer_id = "{}:{}".format(ip, port)

    def response_ok(self, response):
        """Accept both {'ok': true} and {'status': 'ok'} response styles."""
        return response.get("ok") is True or response.get("status") == "ok"

    def response_data(self, response):
        """Return nested data if the tracker wraps responses in a data object."""
        if isinstance(response.get("data"), dict):
            return response.get("data")
        return response

    async def http_request(self, method, path, payload=None):
        """Send a minimal HTTP request to the tracker."""
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        headers = [
            "{} {} HTTP/1.1".format(method, path),
            "Host: {}:{}".format(self.tracker_host, self.tracker_port),
            "Content-Type: application/json",
            "Content-Length: {}".format(len(body)),
            "Connection: close",
        ]

        if self.auth:
            token = "{}:{}".format(self.auth[0], self.auth[1]).encode("utf-8")
            encoded = base64.b64encode(token).decode("utf-8")
            headers.append("Authorization: Basic {}".format(encoded))

        raw_request = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body

        reader, writer = await asyncio.open_connection(
            self.tracker_host, self.tracker_port
        )
        writer.write(raw_request)
        await writer.drain()

        raw_response = await reader.read(-1)
        writer.close()
        await writer.wait_closed()

        text = raw_response.decode("utf-8", errors="ignore")
        response_body = text.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in text else text

        try:
            return json.loads(response_body)
        except Exception:
            return {"ok": False, "raw": response_body}

    async def register(self):
        """Register this peer with the tracker server."""
        response = await self.http_request(
            "POST",
            "/submit-info",
            {"username": self.name, "ip": self.ip, "port": self.port},
        )
        if self.response_ok(response):
            data = self.response_data(response)
            self.peer_id = data.get("peer_id", self.peer_id)
        print("[tracker]", response)
        return response

    async def refresh_peers(self):
        """Fetch peer list from the tracker."""
        response = await self.http_request("GET", "/get-list")
        if self.response_ok(response):
            data = self.response_data(response)
            peers = data.get("peers", {})

            self.peers = {}

            # Current sampleapp returns peers as a dictionary:
            # {"127.0.0.1:7004": {"username": "fox", ...}}
            if isinstance(peers, dict):
                for peer_id, peer in peers.items():
                    username = peer.get("username", peer_id)
                    if peer_id == self.peer_id or username == self.name:
                        continue

                    peer_data = dict(peer)
                    peer_data["peer_id"] = peer_id

                    # Allow both:
                    #   /send 127.0.0.1:7004 hello
                    # and:
                    #   /send fox hello
                    self.peers[peer_id] = peer_data
                    self.peers[username] = peer_data

            # Older format support: [{"username": "...", "ip": "..."}]
            elif isinstance(peers, list):
                for peer in peers:
                    username = peer.get("username", "")
                    peer_id = peer.get(
                        "peer_id",
                        "{}:{}".format(peer.get("ip", ""), peer.get("port", "")),
                    )
                    if peer_id == self.peer_id or username == self.name:
                        continue

                    peer_data = dict(peer)
                    peer_data["peer_id"] = peer_id
                    self.peers[peer_id] = peer_data
                    if username:
                        self.peers[username] = peer_data

        return response

    async def join_channel(self, channel):
        """Join/create a channel through the tracker."""
        self.channel = channel
        response = await self.http_request(
            "POST",
            "/add-list",
            {
                "username": self.name,
                "peer_id": self.peer_id,
                "channel": channel,
            },
        )
        print("[tracker]", response)

    async def resolve_peer(self, peer_name):
        """Resolve another peer by username or peer_id."""
        peer = self.peers.get(peer_name)
        if peer:
            return peer

        await self.refresh_peers()
        peer = self.peers.get(peer_name)
        if peer:
            return peer

        response = await self.http_request(
            "POST",
            "/connect-peer",
            {
                "username": self.name,
                "peer_id": peer_name,
                "target": peer_name,
            },
        )

        if self.response_ok(response):
            data = self.response_data(response)
            peer = data.get("peer", {})
            peer_id = data.get("peer_id", peer_name)
            peer["peer_id"] = peer_id
            self.peers[peer_name] = peer
            self.peers[peer_id] = peer
            if peer.get("username"):
                self.peers[peer.get("username")] = peer
            return peer

        print("[tracker]", response)
        return None

    async def send_direct(self, peer_name, text, channel=None):
        """Send a message directly to another peer over TCP."""
        peer = await self.resolve_peer(peer_name)
        if not peer:
            return

        message = {
            "type": "dm",
            "from": self.name,
            "to": peer.get("username", peer_name),
            "channel": channel or self.channel,
            "text": text,
            "time": int(time.time()),
        }

        try:
            reader, writer = await asyncio.open_connection(
                peer["ip"], int(peer["port"])
            )
            writer.write(json.dumps(message).encode("utf-8") + b"\n")
            await writer.drain()
            ack = await reader.readline()
            writer.close()
            await writer.wait_closed()
            print("[sent -> {}] {}".format(peer_name, text))
            if ack:
                print("[ack]", ack.decode("utf-8", errors="ignore").strip())
        except Exception as exc:
            print("[error] could not send to {}: {}".format(peer_name, exc))

    async def broadcast(self, text):
        """Broadcast a message directly to all peers in the current peer list."""
        await self.http_request(
            "POST",
            "/broadcast-peer",
            {
                "username": self.name,
                "peer_id": self.peer_id,
                "channel": self.channel,
                "message": text,
            },
        )
        await self.refresh_peers()

        tasks = []
        sent_peer_ids = set()

        for peer in self.peers.values():
            peer_id = peer.get("peer_id")
            if not peer_id or peer_id in sent_peer_ids:
                continue
            sent_peer_ids.add(peer_id)
            tasks.append(
                self.send_direct(peer_id, text, self.channel)
            )

        if tasks:
            await asyncio.gather(*tasks)
        else:
            print("[broadcast] no other peers are registered yet")

    async def handle_peer_connection(self, reader, writer):
        """Receive one direct message from another peer."""
        addr = writer.get_extra_info("peername")
        try:
            raw = await reader.readline()
            message = json.loads(raw.decode("utf-8"))
            print(
                "\n[{} @ #{}] {}".format(
                    message.get("from", addr),
                    message.get("channel", "general"),
                    message.get("text", ""),
                )
            )
            writer.write(b'{"ok": true}\n')
            await writer.drain()
        except Exception as exc:
            writer.write(
                json.dumps({"ok": False, "error": str(exc)}).encode("utf-8") + b"\n"
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def command_loop(self):
        """Read user commands without blocking the TCP listener."""
        print("\nCommands:")
        print("  /peers")
        print("  /channel CHANNEL")
        print("  /send PEER MESSAGE")
        print("  /broadcast MESSAGE")
        print("  /quit\n")

        while True:
            try:
                line = await asyncio.to_thread(input, "#{}> ".format(self.channel))
            except EOFError:
                return

            line = line.strip()
            if not line:
                continue

            if line == "/quit":
                print("bye")
                return

            if line == "/peers":
                response = await self.refresh_peers()
                print(json.dumps(response, indent=2))
                continue

            if line.startswith("/channel "):
                channel = line.split(" ", 1)[1].strip()
                if channel:
                    await self.join_channel(channel)
                continue

            if line.startswith("/send "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    print("usage: /send PEER MESSAGE")
                    continue
                await self.send_direct(parts[1], parts[2])
                continue

            if line.startswith("/broadcast "):
                text = line.split(" ", 1)[1].strip()
                await self.broadcast(text)
                continue

            print("unknown command")

    async def run(self):
        """Start listener, register with tracker, and run CLI loop."""
        server = await asyncio.start_server(
            self.handle_peer_connection, self.ip, self.port
        )
        print("[peer] listening on {}:{}".format(self.ip, self.port))

        await self.register()
        await self.join_channel("general")
        await self.refresh_peers()

        async with server:
            command_task = asyncio.create_task(self.command_loop())
            server_task = asyncio.create_task(server.serve_forever())

            done, pending = await asyncio.wait(
                [command_task, server_task], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()


def main():
    parser = argparse.ArgumentParser(description="AsynapRous section 2.3 peer node")
    parser.add_argument("--name", required=True)
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--tracker-host", default="127.0.0.1")
    parser.add_argument("--tracker-port", type=int, default=2026)
    parser.add_argument("--auth-user", default="")
    parser.add_argument("--auth-pass", default="")
    args = parser.parse_args()

    auth = None
    if args.auth_user or args.auth_pass:
        auth = (args.auth_user, args.auth_pass)

    peer = PeerNode(
        args.name,
        args.ip,
        args.port,
        args.tracker_host,
        args.tracker_port,
        auth=auth,
    )

    try:
        asyncio.run(peer.run())
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
