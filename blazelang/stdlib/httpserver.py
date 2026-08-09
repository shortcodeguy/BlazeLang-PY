"""
BlazeLang HTTP Server Module
Production-ready HTTP server for BlazeLang using only Python standard library.
"""

import http.server
import socketserver
import threading
import urllib.parse
import json
import os
import time
import datetime
import hashlib
import mimetypes
import gzip
import io
import email.parser
import email.policy
import re
import uuid
import base64
import socket
import ssl
from typing import Dict, Any, Optional, Callable, Union, List, Tuple, Pattern, BinaryIO

# ==================================================
# Configuration and Constants
# ==================================================

DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
DEFAULT_SESSION_COOKIE_NAME = "blaze_session"
DEFAULT_SESSION_EXPIRY = 86400  # 24 hours

# ==================================================
# Utility Functions
# ==================================================

def parse_cookie_string(cookie_header: str) -> Dict[str, str]:
    """Parse Cookie header string into dictionary."""
    cookies = {}
    if cookie_header:
        for item in cookie_header.split(';'):
            item = item.strip()
            if '=' in item:
                key, val = item.split('=', 1)
                cookies[key.strip()] = val.strip()
    return cookies

def serialize_cookie(
    name: str,
    value: str,
    max_age: Optional[int] = None,
    path: str = "/",
    domain: Optional[str] = None,
    secure: bool = False,
    http_only: bool = False
) -> str:
    """Serialize cookie attributes to Set-Cookie header value."""
    parts = [f"{name}={value}"]
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    parts.append(f"Path={path}")
    if domain:
        parts.append(f"Domain={domain}")
    if secure:
        parts.append("Secure")
    if http_only:
        parts.append("HttpOnly")
    return "; ".join(parts)

def generate_etag(data: bytes) -> str:
    """Generate ETag from data."""
    return f'"{hashlib.md5(data).hexdigest()}"'

def get_mime_type(filename: str) -> str:
    """Get MIME type from filename."""
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

def is_compressible(content_type: str) -> bool:
    """Check if content type is compressible."""
    compressible_types = [
        "text/", "application/json", "application/javascript",
        "application/xml", "application/rss+xml", "image/svg+xml"
    ]
    return any(content_type.startswith(t) for t in compressible_types)

def parse_multipart_form_data(
    data: bytes,
    boundary: str,
    max_size: int
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Parse multipart/form-data body.
    Returns (fields, files) where files is dict of filename -> {name, filename, content_type, data}.
    """
    fields = {}
    files = {}
    # Add boundary markers
    boundary_bytes = boundary.encode('ascii')
    parts = data.split(b'--' + boundary_bytes)
    for part in parts:
        if not part or part == b'--\r\n' or part == b'--':
            continue
        # Split headers and body
        if b'\r\n\r\n' not in part:
            continue
        header_section, body = part.split(b'\r\n\r\n', 1)
        # Remove trailing \r\n
        if body.endswith(b'\r\n'):
            body = body[:-2]
        # Parse headers
        headers = email.parser.BytesParser(policy=email.policy.default).parsebytes(header_section)
        content_disposition = headers.get('Content-Disposition', '')
        if not content_disposition:
            continue
        # Parse content-disposition
        disposition_parts = content_disposition.split(';')
        name = None
        filename = None
        for part_item in disposition_parts:
            part_item = part_item.strip()
            if part_item.startswith('name='):
                name = part_item[5:].strip('"')
            elif part_item.startswith('filename='):
                filename = part_item[9:].strip('"')
        if not name:
            continue
        if filename:
            # It's a file
            content_type = headers.get('Content-Type', 'application/octet-stream')
            if len(body) > max_size:
                raise ValueError(f"File {filename} exceeds maximum upload size")
            files[name] = {
                'name': name,
                'filename': filename,
                'content_type': content_type,
                'data': body
            }
        else:
            # It's a field
            try:
                value = body.decode('utf-8')
            except UnicodeDecodeError:
                value = body.decode('latin-1')
            fields[name] = value
    return fields, files

# ==================================================
# Exceptions
# ==================================================

class HttpError(Exception):
    """Base HTTP error."""
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)

class NotFoundError(HttpError):
    def __init__(self, path: str):
        super().__init__(404, f"Not Found: {path}")

class MethodNotAllowedError(HttpError):
    def __init__(self, method: str):
        super().__init__(405, f"Method {method} not allowed")

class BadRequestError(HttpError):
    def __init__(self, message: str = "Bad Request"):
        super().__init__(400, message)

# ==================================================
# Request and Response Classes
# ==================================================

class Request:
    """Encapsulates an HTTP request with parsed data."""

    def __init__(self, handler: http.server.BaseHTTPRequestHandler):
        self.handler = handler
        self.method = handler.command
        self.path = handler.path
        self.url = handler.path
        self.headers = dict(handler.headers)
        self.client_ip = handler.client_address[0]
        self.protocol = handler.request_version
        self.host = handler.headers.get('Host', '')
        self.user_agent = handler.headers.get('User-Agent', '')
        self.timestamp = datetime.datetime.utcnow().isoformat() + 'Z'

        # Parse URL
        parsed = urllib.parse.urlparse(handler.path)
        self.path = parsed.path
        self.query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        # Flatten query values (take first)
        self.query = {k: v[0] if v else '' for k, v in self.query.items()}

        # Params (path parameters, filled later by router)
        self.params = {}

        # Cookies
        cookie_header = handler.headers.get('Cookie', '')
        self.cookies = parse_cookie_string(cookie_header)

        # Body and derived fields
        self.body = ''
        self.json = None
        self.form = {}
        self.files = {}
        self._parse_body()

        # Session (placeholder, will be filled by middleware)
        self.session = {}

    def _parse_body(self) -> None:
        """Parse request body based on Content-Type."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            return

        # Read body
        raw_body = self.handler.rfile.read(content_length)
        self.body = raw_body

        content_type = self.headers.get('Content-Type', '')

        # JSON
        if 'application/json' in content_type:
            try:
                self.json = json.loads(raw_body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise BadRequestError("Invalid JSON body")
            return

        # URL-encoded form
        if 'application/x-www-form-urlencoded' in content_type:
            try:
                decoded = raw_body.decode('utf-8')
                self.form = urllib.parse.parse_qs(decoded, keep_blank_values=True)
                self.form = {k: v[0] if v else '' for k, v in self.form.items()}
            except UnicodeDecodeError:
                raise BadRequestError("Invalid form encoding")
            return

        # Multipart form
        if 'multipart/form-data' in content_type:
            # Extract boundary
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:]
                    if boundary.startswith('"') and boundary.endswith('"'):
                        boundary = boundary[1:-1]
                    break
            if not boundary:
                raise BadRequestError("Missing boundary in multipart/form-data")
            # Parse multipart
            try:
                self.form, self.files = parse_multipart_form_data(
                    raw_body,
                    boundary,
                    DEFAULT_MAX_UPLOAD_SIZE
                )
            except ValueError as e:
                raise BadRequestError(str(e))
            return

        # Plain text or other
        try:
            self.body = raw_body.decode('utf-8')
        except UnicodeDecodeError:
            self.body = raw_body

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for BlazeLang callback."""
        return {
            'method': self.method,
            'path': self.path,
            'url': self.url,
            'query': self.query,
            'params': self.params,
            'headers': self.headers,
            'cookies': self.cookies,
            'body': self.body,
            'json': self.json,
            'form': self.form,
            'files': self.files,
            'client_ip': self.client_ip,
            'host': self.host,
            'protocol': self.protocol,
            'userAgent': self.user_agent,
            'timestamp': self.timestamp,
            'session': self.session
        }


class Response:
    """Builds an HTTP response."""

    def __init__(self):
        self.status = 200
        self.headers = {}
        self.cookies = {}
        self.body = None
        self._sent = False

    def set_status(self, code: int) -> None:
        self.status = code

    def set_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def set_headers(self, headers: Dict[str, str]) -> None:
        for k, v in headers.items():
            self.set_header(k, v)

    def set_cookie(self, name: str, value: str, **kwargs) -> None:
        self.cookies[name] = (value, kwargs)

    def set_body(self, body: Any) -> None:
        self.body = body

    def to_http_response(self) -> Tuple[int, Dict[str, str], Union[str, bytes]]:
        """Convert to (status, headers, body) for sending."""
        status = self.status
        headers = dict(self.headers)

        # Process body
        if isinstance(self.body, (dict, list)):
            headers['Content-Type'] = 'application/json'
            body_str = json.dumps(self.body)
            body = body_str.encode('utf-8')
        elif isinstance(self.body, bytes):
            body = self.body
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/octet-stream'
        elif isinstance(self.body, str):
            body = self.body.encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'text/plain'
        elif self.body is None:
            body = b''
        else:
            # Convert to string
            body = str(self.body).encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'text/plain'

        # Set Content-Length
        headers['Content-Length'] = str(len(body))

        # Set cookies
        cookie_headers = []
        for name, (value, kwargs) in self.cookies.items():
            cookie_headers.append(serialize_cookie(name, value, **kwargs))
        if cookie_headers:
            headers['Set-Cookie'] = ', '.join(cookie_headers)

        # Normalize ContentType to Content-Type
        if 'ContentType' in headers:
            headers['Content-Type'] = headers.pop('ContentType')

        return status, headers, body

# ==================================================
# Route Pattern Matching
# ==================================================

def compile_route_pattern(pattern: str) -> Tuple[Pattern, List[str]]:
    """
    Convert route pattern like '/users/{id}' to regex and parameter names.
    Returns (regex, param_names).
    """
    # Escape regex special characters
    # Replace {param} with named capture group
    param_names = []
    # We'll replace {param} with (?P<param>[^/]+)
    # But we need to escape other regex characters
    # First, escape everything
    escaped = re.escape(pattern)
    # Now replace escaped braces: \\{ -> {
    # But we need to handle {param} specifically
    # We'll manually parse
    # Better: use a placeholder approach
    # We'll find all occurrences of {identifier}
    param_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    def repl(match):
        param_names.append(match.group(1))
        return r'([^/]+)'
    regex_str = param_pattern.sub(repl, pattern)
    # Ensure full match
    regex_str = '^' + regex_str + '$'
    return re.compile(regex_str), param_names


def match_route(route_pattern: str, path: str) -> Optional[Dict[str, str]]:
    """Match path against route pattern, return params if match."""
    regex, param_names = compile_route_pattern(route_pattern)
    match = regex.match(path)
    if not match:
        return None
    params = {}
    for i, name in enumerate(param_names):
        params[name] = match.group(i+1)
    return params

# ==================================================
# Session Management
# ==================================================

class SessionStore:
    """In-memory session store."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self, session_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._sessions[session_id] = {
                'data': data,
                'created': time.time(),
                'expires': time.time() + DEFAULT_SESSION_EXPIRY
            }

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session['expires'] > time.time():
                return session['data']
            if session:
                del self._sessions[session_id]
            return None

    def set(self, session_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]['data'] = data
                self._sessions[session_id]['expires'] = time.time() + DEFAULT_SESSION_EXPIRY

    def delete(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

# ==================================================
# Main HTTPServer Class
# ==================================================

class BlazeHttpServer:
    """Main server class holding configuration and request handling."""

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.routes = []  # List of (method, pattern, handler)
        self.middleware = []  # List of callables
        self.static_directory = None
        self.default_callback = None
        self.config = {
            'max_upload_size': DEFAULT_MAX_UPLOAD_SIZE,
            'request_timeout': DEFAULT_REQUEST_TIMEOUT,
            'enable_cors': True,
            'enable_compression': True,
            'enable_sessions': True,
            'session_cookie_name': DEFAULT_SESSION_COOKIE_NAME,
            'ssl_cert': None,
            'ssl_key': None,
            'enable_https': False,
            'keep_alive': True,
        }
        self.session_store = SessionStore()
        self._server_instance = None
        self._shutdown_event = threading.Event()

    def route(self, path: str, methods: List[str] = None) -> Callable:
        """Decorator to register a route handler."""
        def decorator(handler):
            if methods is None:
                methods = ['GET']
            for method in methods:
                self.routes.append((method.upper(), path, handler))
            return handler
        return decorator

    def static(self, directory: str) -> None:
        """Set static file serving directory."""
        self.static_directory = os.path.abspath(directory)

    def use(self, middleware_func: Callable) -> None:
        """Register middleware."""
        self.middleware.append(middleware_func)

    def configure(self, **kwargs) -> None:
        """Update configuration."""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value

    def _find_route_handler(self, method: str, path: str) -> Tuple[Optional[Callable], Dict[str, str]]:
        """Find matching route handler and params."""
        for route_method, route_path, handler in self.routes:
            if route_method != method and route_method != '*':
                continue
            params = match_route(route_path, path)
            if params is not None:
                return handler, params
        return None, {}

    def _apply_middleware(self, request: Request, response: Response) -> bool:
        """
        Apply middleware chain.
        Returns True if chain completed, False if response was sent early.
        """
        # We'll create a simple chain
        def chain(index):
            if index >= len(self.middleware):
                return True
            middleware = self.middleware[index]
            result = middleware(request, response, lambda: chain(index+1))
            if result is not None:
                # If middleware returns a response dict, use it
                if isinstance(result, dict):
                    response.status = result.get('status', 200)
                    response.headers = result.get('headers', {})
                    response.body = result.get('body', None)
                    # Cookies
                    if 'cookies' in result:
                        for k, v in result['cookies'].items():
                            response.set_cookie(k, v)
                    # Short-circuit
                    return False
            return True
        return chain(0)

    def handle_request(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        """Main request handler called by BlazeHTTPRequestHandler."""
        try:
            # Create request object
            request = Request(handler)
            response = Response()

            # Session handling
            session_cookie = self.config['session_cookie_name']
            session_id = request.cookies.get(session_cookie)
            if session_id and self.config['enable_sessions']:
                session_data = self.session_store.get(session_id)
                if session_data is not None:
                    request.session = session_data

            # Apply middleware
            chain_ok = self._apply_middleware(request, response)
            if not chain_ok:
                # Response already set by middleware, send it
                self._send_response(handler, response)
                return

            # Find route handler
            route_handler, route_params = self._find_route_handler(request.method, request.path)
            if route_handler:
                request.params = route_params
                callback = route_handler
            else:
                # Check static files
                if self.static_directory and request.method == 'GET':
                    served = self._serve_static(handler, request, response)
                    if served:
                        return
                # Fallback to default callback
                callback = self.default_callback

            if callback is None:
                # No handler found
                raise NotFoundError(request.path)

            # Execute callback
            # Check if BlazeLang function
            if hasattr(callback, "__call__") and hasattr(callback, "parameters"):
                # BlazeLang function: call with interpreter and [request]
                result = callback(self.interpreter, [request.to_dict()])
            else:
                # Normal Python callable
                result = callback(request.to_dict())

            # Build response from result
            if isinstance(result, dict):
                response.status = result.get('status', 200)
                response.headers = result.get('headers', {})
                response.body = result.get('body', None)
                # Cookies
                if 'cookies' in result:
                    for k, v in result['cookies'].items():
                        if isinstance(v, dict):
                            response.set_cookie(k, v.get('value', ''), **{kk: vv for kk, vv in v.items() if kk != 'value'})
                        else:
                            response.set_cookie(k, v)
            else:
                response.body = str(result)

            # Save session if modified
            if self.config['enable_sessions'] and request.session:
                if not session_id:
                    session_id = str(uuid.uuid4())
                    self.session_store.create(session_id, request.session)
                    response.set_cookie(session_cookie, session_id, max_age=DEFAULT_SESSION_EXPIRY, http_only=True)
                else:
                    self.session_store.set(session_id, request.session)

            self._send_response(handler, response)

        except HttpError as e:
            self._send_error(handler, e.status, e.message)
        except Exception as e:
            # Internal server error
            self._send_error(handler, 500, f"Internal Server Error: {str(e)}")

    def _send_response(self, handler: http.server.BaseHTTPRequestHandler, response: Response) -> None:
        """Send HTTP response."""
        status, headers, body = response.to_http_response()

        # CORS headers
        if self.config['enable_cors']:
            headers['Access-Control-Allow-Origin'] = '*'
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
            headers['Access-Control-Allow-Headers'] = '*'
            if 'Access-Control-Max-Age' not in headers:
                headers['Access-Control-Max-Age'] = '86400'

        # Compression
        if self.config['enable_compression'] and is_compressible(headers.get('Content-Type', '')):
            accept_encoding = handler.headers.get('Accept-Encoding', '')
            if 'gzip' in accept_encoding and len(body) > 1024:
                # Compress
                out = io.BytesIO()
                with gzip.GzipFile(fileobj=out, mode='wb') as gz:
                    gz.write(body)
                compressed = out.getvalue()
                if len(compressed) < len(body):
                    body = compressed
                    headers['Content-Encoding'] = 'gzip'
                    headers['Content-Length'] = str(len(body))

        # ETag (if not present and body not too large)
        if 'ETag' not in headers and len(body) < 1024*1024:
            headers['ETag'] = generate_etag(body)

        # Send
        handler.send_response(status)
        for key, value in headers.items():
            handler.send_header(key, str(value))
        handler.end_headers()
        handler.wfile.write(body)

    def _send_error(self, handler: http.server.BaseHTTPRequestHandler, status: int, message: str) -> None:
        """Send error response as JSON."""
        response = Response()
        response.status = status
        response.headers['Content-Type'] = 'application/json'
        response.body = {
            'success': False,
            'error': message
        }
        self._send_response(handler, response)

    def _serve_static(self, handler: http.server.BaseHTTPRequestHandler, request: Request, response: Response) -> bool:
        """Serve static file if exists and matches request."""
        # Get relative path
        path = request.path
        # Remove leading slash and any query
        if path.startswith('/'):
            path = path[1:]
        # Prevent directory traversal
        if '..' in path or path.startswith('/') or path.startswith('\\'):
            return False
        full_path = os.path.join(self.static_directory, path)
        if not os.path.exists(full_path):
            return False
        # Check if it's a directory
        if os.path.isdir(full_path):
            # Try index.html
            index_path = os.path.join(full_path, 'index.html')
            if os.path.exists(index_path):
                full_path = index_path
            else:
                # List directory? Not recommended; return 404
                return False
        # Check if file
        if not os.path.isfile(full_path):
            return False
        # Read file
        try:
            with open(full_path, 'rb') as f:
                file_data = f.read()
        except (IOError, OSError):
            return False
        # Check file size
        if len(file_data) > self.config['max_upload_size']:
            return False
        # Set response
        response.status = 200
        response.headers['Content-Type'] = get_mime_type(full_path)
        # Cache control
        response.headers['Cache-Control'] = 'public, max-age=3600'
        # ETag
        response.headers['ETag'] = generate_etag(file_data)
        # Check If-None-Match
        if 'If-None-Match' in handler.headers:
            if handler.headers['If-None-Match'] == response.headers['ETag']:
                response.status = 304
                response.body = None
                self._send_response(handler, response)
                return True
        response.body = file_data
        self._send_response(handler, response)
        return True

    def listen(self, port: int, callback: Callable) -> None:
        """Start the server."""
        self.default_callback = callback
        
        # Ensure port is integer
        port = int(port)

        # Create server
        handler_class = self._create_handler_class()

        # Configure socket
        server = socketserver.ThreadingTCPServer(
            ('', port),
            handler_class
        )
        server.allow_reuse_address = True

        if self.config['enable_https']:
            if not self.config['ssl_cert'] or not self.config['ssl_key']:
                raise RuntimeError("HTTPS enabled but SSL certificate/key not provided")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.config['ssl_cert'], self.config['ssl_key'])
            server.socket = context.wrap_socket(server.socket, server_side=True)

        # Set request timeout
        if self.config['request_timeout']:
            server.socket.settimeout(self.config['request_timeout'])

        self._server_instance = server
        self._shutdown_event.clear()

        print(f"BlazeLang HTTP Server running on http{'s' if self.config['enable_https'] else ''}://localhost:{port}")
        if self.static_directory:
            print(f"Serving static files from {self.static_directory}")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def _create_handler_class(self):
        """Create a request handler class bound to this server."""
        server_ref = self

        class BlazeHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
            """Internal request handler."""

            def setup(self):
                super().setup()
                self.timeout = server_ref.config.get('request_timeout', 30)

            def handle_one_request(self):
                # Override to handle keep-alive? We'll keep default.
                try:
                    super().handle_one_request()
                except socket.timeout:
                    # Ignore timeouts
                    pass

            def do_GET(self):
                server_ref.handle_request(self)

            def do_POST(self):
                server_ref.handle_request(self)

            def do_PUT(self):
                server_ref.handle_request(self)

            def do_DELETE(self):
                server_ref.handle_request(self)

            def do_PATCH(self):
                server_ref.handle_request(self)

            def do_HEAD(self):
                server_ref.handle_request(self)

            def do_OPTIONS(self):
                # Preflight CORS
                response = Response()
                response.status = 200
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = '*'
                response.headers['Access-Control-Max-Age'] = '86400'
                server_ref._send_response(self, response)

            def log_message(self, format, *args):
                # Custom logging
                print(f"{self.address_string()} - - [{self.log_date_time_string()}] {format % args}")

        return BlazeHTTPRequestHandler

    def stop(self) -> None:
        """Gracefully stop the server."""
        if self._server_instance:
            self._server_instance.shutdown()
            self._server_instance.server_close()
            self._server_instance = None
            print("Server stopped.")

# ==================================================
# Public Module API
# ==================================================

def create_httpserver_module(interpreter) -> Dict[str, Any]:
    """
    Create the BlazeLang HttpServer module.

    Args:
        interpreter: The BlazeLang interpreter instance.

    Returns:
        A dictionary with the server functions.
    """
    server = BlazeHttpServer(interpreter)

    def listen(port: int, callback: Callable) -> None:
        """Start the server on the given port with the default callback."""
        server.listen(int(port), callback)

    def stop() -> None:
        """Stop the server."""
        server.stop()

    def route(path: str, methods: List[str] = None) -> Callable:
        """Decorator to register a route."""
        return server.route(path, methods)

    def static(directory: str) -> None:
        """Set static files directory."""
        server.static(directory)

    def use(middleware_func: Callable) -> None:
        """Register middleware."""
        server.use(middleware_func)

    def configure(**kwargs) -> None:
        """Set server configuration."""
        server.configure(**kwargs)

    return {
        'listen': listen,
        'stop': stop,
        'route': route,
        'static': static,
        'use': use,
        'configure': configure
    }