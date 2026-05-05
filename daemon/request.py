#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from .dictionary import CaseInsensitiveDict

class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = None
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = None
        #: request body to send to the server.
        self.body = None
        # The raw header
        self._raw_headers = None
        #: The raw body
        self._raw_body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None

    def extract_request_line(self, request):
        try:
            lines = request.splitlines()
            first_line = lines[0]
            method, path, version = first_line.split()

            if path == '/':
                path = '/index.html'
        except Exception:
            return None, None

        return method, path, version
             
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        lines = request.split('\r\n')
        headers = {}
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.lower()] = val
        return headers

    def fetch_headers_body(self, request):
        """Prepares the given HTTP headers."""
        # Split request into header section and body section
        parts = request.split("\r\n\r\n", 1)  # split once at blank line

        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # Prepare the request line from the request header
        print("[Request] prepare request missg {}".format(request))
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        #
        # @bksysnet Preapring the webapp hook with AsynapRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        #
        if self.path == "/login" and self.method == "POST":
            self.hook = True
        
        self._raw_headers, self._raw_body = self.fetch_headers_body(request)
        self.headers = self.prepare_headers(self._raw_headers)
        self.body = self._raw_body
        self.url = self.path
        self.cookies = CaseInsensitiveDict()
        self.form = {}
        self.authenticated = False
        self.login_success = False
        self.username = ""
        self._users = {}

        for db_path in ("db/users.txt", "./db/users.txt"):
            try:
                with open(db_path, "r") as db_file:
                    for line in db_file:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if ":" in line:
                            username, password = line.split(":", 1)
                        elif "," in line:
                            username, password = line.split(",", 1)
                        else:
                            parts = line.split()
                            if len(parts) != 2:
                                continue
                            username, password = parts
                        self._users[username.strip()] = password.strip()
                break
            except Exception:
                pass
            
        if not routes == {}:
            self.routes = routes
            print("[Request] Routing METHOD {} path {}".format(self.method, self.path))
            self.hook = routes.get((self.method, self.path))
            print("[Request] Hook has request {}".format(request))
            #
            # self.hook manipulation goes here
            # ...
            #

        self._raw_heaers = ""
        self._raw_body =  ""
        cookies = self.headers.get('cookie', '')
            #
            #  TODO: implement the cookie function here
            #        by parsing the header            #
        if cookies:
            for pair in cookies.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    self.cookies[key.strip()] = value.strip()

        session_id = self.cookies.get("sessionid", "")
        if session_id.endswith("-session"):
            username = session_id[:-len("-session")]
            if username in self._users:
                self.authenticated = True
                self.username = username

        auth_header = self.headers.get('authorization', '').strip()
        if auth_header.startswith('Basic '):
            try:
                decoder = __import__('base64')
                token = auth_header.split(None, 1)[1]
                decoded = decoder.b64decode(token).decode('utf-8')
                username, password = decoded.split(':', 1)
                if self._users.get(username) == password:
                    self.authenticated = True
                    self.username = username
            except Exception:
                pass

        if self.body:
            for pair in self.body.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    key = key.replace("+", " ")
                    value = value.replace("+", " ")
                    value = value.replace("%40", "@")
                    value = value.replace("%20", " ")
                    self.form[key] = value

        if self.path == "/login" and self.method == "POST":
            username = self.form.get("username", "")
            password = self.form.get("password", "")
            if self._users.get(username) == password:
                self.login_success = True
                self.authenticated = True
                self.username = username
        return

    def prepare_body(self, data, files, json=None):
        self.prepare_content_length(self.body)
        self.body = body
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return


    def prepare_content_length(self, body):
        self.headers["Content-Length"] = "0"
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return


    def prepare_auth(self, auth, url=""):
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return

    def prepare_cookies(self, cookies):
            self.headers["Cookie"] = cookies
