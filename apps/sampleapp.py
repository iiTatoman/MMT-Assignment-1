#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import sys
import os
import importlib.util
import json

from   daemon import AsynapRous

app = AsynapRous()

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print("[SampleApp] Logging in {} to {}".format(headers, body))
    data = {"message": "Welcome to the RESTful TCP WebApp"}

    # Convert to JSON string
    json_str = json.dumps(data)
    return (json_str.encode("utf-8"))

@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    print("[SampleApp] received body {}".format(body))

    try:
        message = json.loads(body)
        data = {"received": message }
        # Convert to JSON string
        json_str = json.dumps(data)
        return (json_str.encode("utf-8"))
    except json.JSONDecodeError:
        data = {"error": "Invalid JSON"}
        # Convert to JSON string
        json_str = json.dumps(data)
        return (json_str.encode("utf-8"))


@app.route('/hello', methods=['PUT'])
async def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] **ASYNC** Hello in {} to {}".format(headers, body))
    data =  {"id": 1, "name": "Alice", "email": "alice@example.com"}

    # Convert to JSON string
    json_str = json.dumps(data)
    return (json_str.encode("utf-8"))


# Chat application tracker routes

PEERS = {}
CHANNELS = {"general": {"members": [], "messages": []}}


def _json(data):
    return json.dumps(data)


def _decode_value(value):
    value = value.replace('+', ' ')
    value = value.replace('%20', ' ')
    value = value.replace('%21', '!')
    value = value.replace('%23', '#')
    value = value.replace('%24', '$')
    value = value.replace('%25', '%')
    value = value.replace('%26', '&')
    value = value.replace('%2B', '+').replace('%2b', '+')
    value = value.replace('%2F', '/').replace('%2f', '/')
    value = value.replace('%3A', ':').replace('%3a', ':')
    value = value.replace('%3D', '=').replace('%3d', '=')
    value = value.replace('%3F', '?').replace('%3f', '?')
    value = value.replace('%40', '@')
    return value


def _parse_body(body):
    if not body:
        return {}
    if isinstance(body, bytes):
        body = body.decode('utf-8')

    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    data = {}
    for pair in body.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            data[_decode_value(key)] = _decode_value(value)
    return data


def _ensure_channel(channel):
    if not channel:
        channel = 'general'
    if channel not in CHANNELS:
        CHANNELS[channel] = {"members": [], "messages": []}
    return channel


def _public_peers():
    data = {}
    for peer_id, peer in PEERS.items():
        data[peer_id] = {
            "username": peer.get("username", peer_id),
            "ip": peer.get("ip", "127.0.0.1"),
            "port": peer.get("port", ""),
            "channels": peer.get("channels", []),
        }
    return data


def _public_channels():
    data = {}
    for channel, info in CHANNELS.items():
        data[channel] = list(info.get("members", []))
    return data


@app.route('/chat.html', methods=['GET'])
def chat_page(headers="guest", body="anonymous"):
    filepath = os.path.join('www', 'chat.html')
    try:
        with open(filepath, 'rb') as html_file:
            return ('text/html; charset=utf-8', html_file.read())
    except Exception:
        return ('text/html; charset=utf-8', b'<h1>chat.html not found</h1>')


@app.route('/favicon.ico', methods=['GET'])
def favicon(headers="guest", body="anonymous"):
    return ('image/x-icon', b'')


@app.route('/submit-info', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    data = _parse_body(body)
    username = data.get('username', 'guest')
    ip = data.get('ip', '127.0.0.1')
    port = str(data.get('port', '0'))
    peer_id = data.get('peer_id', '{}:{}'.format(ip, port))

    PEERS[peer_id] = {
        "username": username,
        "ip": ip,
        "port": port,
        "channels": PEERS.get(peer_id, {}).get("channels", []),
    }

    if 'general' not in PEERS[peer_id]["channels"]:
        PEERS[peer_id]["channels"].append('general')
    if peer_id not in CHANNELS['general']["members"]:
        CHANNELS['general']["members"].append(peer_id)

    return _json({"status": "ok", "data": {"peer_id": peer_id}})


@app.route('/get-list', methods=['GET', 'POST'])
def get_list(headers="guest", body="anonymous"):
    return _json({
        "status": "ok",
        "data": {
            "peers": _public_peers(),
            "channels": _public_channels(),
        }
    })


@app.route('/add-list', methods=['POST'])
def add_list(headers="guest", body="anonymous"):
    data = _parse_body(body)
    channel = _ensure_channel(data.get('channel', 'general'))
    peer_id = data.get('peer_id', '')

    if peer_id:
        if peer_id not in CHANNELS[channel]["members"]:
            CHANNELS[channel]["members"].append(peer_id)
        if peer_id in PEERS and channel not in PEERS[peer_id]["channels"]:
            PEERS[peer_id]["channels"].append(channel)

    return _json({"status": "ok", "data": {"channel": channel}})


@app.route('/connect-peer', methods=['POST'])
def connect_peer(headers="guest", body="anonymous"):
    data = _parse_body(body)
    peer_id = data.get('peer_id', data.get('target', ''))
    peer = PEERS.get(peer_id)
    if not peer:
        return _json({"status": "error", "message": "peer not found"})
    return _json({"status": "ok", "data": {"peer_id": peer_id, "peer": peer}})


@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers="guest", body="anonymous"):
    data = _parse_body(body)
    channel = _ensure_channel(data.get('channel', 'general'))
    username = data.get('username', 'guest')
    peer_id = data.get('peer_id', '')
    text = data.get('text', data.get('message', ''))

    if peer_id and peer_id not in CHANNELS[channel]["members"]:
        CHANNELS[channel]["members"].append(peer_id)
    if peer_id in PEERS and channel not in PEERS[peer_id]["channels"]:
        PEERS[peer_id]["channels"].append(channel)

    msg_no = len(CHANNELS[channel]["messages"]) + 1
    message = {
        "from": username,
        "peer_id": peer_id,
        "text": text,
        "ts": "msg {}".format(msg_no),
    }
    CHANNELS[channel]["messages"].append(message)
    return _json({"status": "ok", "data": message})


@app.route('/send-peer', methods=['POST'])
def send_peer(headers="guest", body="anonymous"):
    data = _parse_body(body)
    target = data.get('target', data.get('to', ''))
    channel = _ensure_channel(data.get('channel', 'dm-' + target if target else 'general'))
    username = data.get('username', 'guest')
    text = data.get('text', data.get('message', ''))
    msg_no = len(CHANNELS[channel]["messages"]) + 1
    message = {"from": username, "to": target, "text": text, "ts": "msg {}".format(msg_no)}
    CHANNELS[channel]["messages"].append(message)
    return _json({"status": "ok", "data": message})


@app.route('/messages', methods=['POST'])
def messages(headers="guest", body="anonymous"):
    data = _parse_body(body)
    channel = _ensure_channel(data.get('channel', 'general'))
    return _json({
        "status": "ok",
        "data": {
            "channel": channel,
            "messages": CHANNELS[channel]["messages"],
        }
    })


@app.route('/ping', methods=['GET'])
def ping(headers="guest", body="anonymous"):
    return _json({"status": "ok", "message": "pong"})


def create_sampleapp(ip, port):
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
