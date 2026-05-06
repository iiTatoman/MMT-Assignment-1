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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import inspect

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        msg = conn.recv(4096).decode()
        req.prepare(msg, routes)
        print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

        response = resp.build_response(req)

        # Handle request hook
        if req.hook:
            #
            # TODO: handle for App hook here
            #
            if req.path == '/login' and req.method == 'POST':
                if getattr(req, 'login_success', False):
                    content = b"Login success"
                    sessionid = "{}-session".format(getattr(req, 'username', ''))
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Set-Cookie: sessionid={}; Path=/; HttpOnly\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).format(sessionid, len(content)).encode('utf-8') + content
                else:
                    content = b"Unauthorized"
                    response = (
                        "HTTP/1.1 401 Unauthorized\r\n"
                        "Content-Type: text/plain\r\n"
                        "WWW-Authenticate: Basic realm=\"AsynapRous\"\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).format(len(content)).encode('utf-8') + content
            elif req.path == '/login' or req.path == '/login.html':
                mime_type = resp.get_mime_type('/login.html')
                base_dir = resp.prepare_content_type(mime_type)
                length, content = resp.build_content('/login.html', base_dir)
                if length < 0:
                    response = resp.build_notfound()
                else:
                    resp._content = content
                    resp.status_code = 200
                    resp.reason = "OK"
                    resp._header = resp.build_response_header(req)
                    response = resp._header + resp._content
            elif not getattr(req, 'authenticated', False) and req.path not in ('/chat.html', '/favicon.ico'):
                content = b"Authentication required"
                response = (
                    "HTTP/1.1 401 Unauthorized\r\n"
                    "Content-Type: text/plain\r\n"
                    "WWW-Authenticate: Basic realm=\"AsynapRous\"\r\n"
                    "Content-Length: {}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ).format(len(content)).encode('utf-8') + content
            elif callable(req.hook):
                result = req.hook(headers=req.headers, body=req.body)
                if inspect.iscoroutine(result):
                    result = asyncio.run(result)

                content_type = 'application/json'
                if isinstance(result, tuple) and len(result) == 2:
                    content_type = result[0]
                    result = result[1]

                if isinstance(result, bytes):
                    content = result
                else:
                    content = str(result).encode('utf-8')

                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: {}\r\n"
                    "Content-Length: {}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ).format(content_type, len(content)).encode('utf-8') + content

        #print("[HttpAdapter] Response content {}".format(response))
        conn.sendall(response)
        conn.close()

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        addr = writer.get_extra_info("peername")
        print("[HttpAdapter] Invoke handle_client_coroutine connection {})".format(addr))

        # TODO Handle the request asynchronously
        msg = await reader.read(1024)


        req.prepare(msg.decode("utf-8"), routes=self.routes or {})

        # Handle request hook
        if req.hook:
            #
            # TODO: handle for App hook here
            #
            if callable(req.hook):
                result = req.hook(headers=req.headers, body=req.body)
                if inspect.iscoroutine(result):
                    result = await result
                content = str(result).encode('utf-8')
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    "Content-Length: {}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ).format(len(content)).encode('utf-8') + content
            elif req.path == '/login' and req.method == 'POST':
                if getattr(req, 'login_success', False):
                    content = b"Login success"
                    sessionid = "{}-session".format(getattr(req, 'username', ''))
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Set-Cookie: sessionid={}; Path=/\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).format(sessionid, len(content)).encode('utf-8') + content
                else:
                    content = b"Unauthorized"
                    response = (
                        "HTTP/1.1 401 Unauthorized\r\n"
                        "Content-Type: text/plain\r\n"
                        "WWW-Authenticate: Basic realm=\"AsynapRous\"\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).format(len(content)).encode('utf-8') + content
            elif req.path == '/login' or req.path == '/login.html':
                mime_type = resp.get_mime_type('/login.html')
                base_dir = resp.prepare_content_type(mime_type)
                length, content = resp.build_content('/login.html', base_dir)
                if length < 0:
                    response = resp.build_notfound()
                else:
                    resp._content = content
                    resp.status_code = 200
                    resp.reason = "OK"
                    resp._header = resp.build_response_header(req)
                    response = resp._header + resp._content
            elif not getattr(req, 'authenticated', False):
                content = b"Authentication required"
                response = (
                    "HTTP/1.1 401 Unauthorized\r\n"
                    "Content-Type: text/plain\r\n"
                    "WWW-Authenticate: Basic realm=\"AsynapRous\"\r\n"
                    "Content-Length: {}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ).format(len(content)).encode('utf-8') + content
            else:
                mime_type = resp.get_mime_type(req.path)
                base_dir = resp.prepare_content_type(mime_type)
                length, content = resp.build_content(req.path, base_dir)
                if length < 0:
                    response = resp.build_notfound()
                else:
                    resp._content = content
                    resp.status_code = 200
                    resp.reason = "OK"
                    resp._header = resp.build_response_header(req)
                    response = resp._header + resp._content
            resp.build_response = lambda prepared_request, envelop_content=None: response

        # Build response
        #print("[HttpAdapter] Start **ASYNC** build_response with type {}".format(type(req)))
        response = resp.build_response(req)

        # Send all the response asynchronously
        writer.write(response)
        await writer.drain()

    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        for header in headers:
            if header.startswith("Cookie:"):
                cookie_str = header.split(":", 1)[1].strip()
                for pair in cookie_str.split(";"):
                    key, value = pair.strip().split("=")
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = extract_cookies(req)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    def build_json_response(self, req, resp):
        """Builds a :class:`Response <Response>` object from JSON data

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response(req)

        # Set encoding.
        response.raw = resp

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response


    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("", "")

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

                        username = username.strip()
                        password = password.strip()
                        break

                if username and password:
                    break
            except Exception:
                pass

        if username and password:
            encoder = __import__('base64')
            token = "{}:{}".format(username, password).encode("utf-8")
            headers["Proxy-Authorization"] = "Basic {}".format(
                encoder.b64encode(token).decode("utf-8")
            )

        return headers