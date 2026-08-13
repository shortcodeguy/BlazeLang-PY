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
import hmac
import binascii
from typing import Dict, Any, Optional, Callable, Union, List, Tuple, Pattern, BinaryIO

# ==================================================
# Configuration and Constants
# ==================================================

DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
DEFAULT_SESSION_COOKIE_NAME = "blaze_session"
DEFAULT_SESSION_EXPIRY = 86400  # 24 hours
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds

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

def generate_request_id() -> str:
    """Generate a unique request ID for tracing/logging purposes."""
    return uuid.uuid4().hex

def parse_basic_auth(auth_header: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Parse an 'Authorization: Basic <base64>' header.
    Returns (username, password) tuple, or None if not present/invalid.
    """
    if not auth_header:
        return None
    if not auth_header.startswith('Basic '):
        return None
    encoded = auth_header[len('Basic '):].strip()
    try:
        decoded = base64.b64decode(encoded).decode('utf-8')
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if ':' not in decoded:
        return None
    username, password = decoded.split(':', 1)
    return username, password

def parse_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """
    Parse an 'Authorization: Bearer <token>' header.
    Returns the token string, or None if not present/invalid.
    """
    if not auth_header:
        return None
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[len('Bearer '):].strip()
    return token or None

def _b64url_encode(data: bytes) -> str:
    """Base64url-encode without padding, per JWT spec."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def _b64url_decode(data: str) -> bytes:
    """Base64url-decode, restoring padding as needed."""
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def jwt_encode(payload: Dict[str, Any], secret: str, algorithm: str = 'HS256',
               headers: Optional[Dict[str, Any]] = None) -> str:
    """
    Encode a JWT using only the standard library.
    Supports HS256, HS384, HS512.
    """
    hash_map = {'HS256': hashlib.sha256, 'HS384': hashlib.sha384, 'HS512': hashlib.sha512}
    if algorithm not in hash_map:
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")

    header = {'alg': algorithm, 'typ': 'JWT'}
    if headers:
        header.update(headers)

    header_b64 = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}".encode('ascii')

    signature = hmac.new(secret.encode('utf-8'), signing_input, hash_map[algorithm]).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def jwt_decode(token: str, secret: str, algorithms: Optional[List[str]] = None,
               verify_exp: bool = True) -> Dict[str, Any]:
    """
    Decode and verify a JWT using only the standard library.
    Raises ValueError on invalid token, bad signature, or expiration.
    """
    hash_map = {'HS256': hashlib.sha256, 'HS384': hashlib.sha384, 'HS512': hashlib.sha512}
    allowed_algorithms = algorithms or list(hash_map.keys())

    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header_b64, payload_b64, signature_b64 = parts

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise ValueError("Invalid JWT encoding")

    algorithm = header.get('alg')
    if algorithm not in allowed_algorithms or algorithm not in hash_map:
        raise ValueError(f"Unacceptable JWT algorithm: {algorithm}")

    signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
    expected_signature = hmac.new(secret.encode('utf-8'), signing_input, hash_map[algorithm]).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid JWT signature")

    if verify_exp and 'exp' in payload:
        if time.time() > float(payload['exp']):
            raise ValueError("JWT has expired")

    return payload

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

class UnauthorizedError(HttpError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(401, message)

class ForbiddenError(HttpError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(403, message)

class InternalServerErrorException(HttpError):
    def __init__(self, message: str = "Internal Server Error"):
        super().__init__(500, message)

class RateLimitExceededError(HttpError):
    def __init__(self, message: str = "Too Many Requests"):
        super().__init__(429, message)

# ==================================================
# HTTP Status Response Helpers
# (return Response objects with consistent JSON error bodies)
# ==================================================

def _error_body(status: int, message: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a consistent JSON error response body."""
    body = {
        'success': False,
        'error': {
            'status': status,
            'message': message
        }
    }
    if request_id:
        body['error']['requestId'] = request_id
    return body

def BadRequest(message: str = "Bad Request", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(400, message, request_id), status=400)

def Unauthorized(message: str = "Unauthorized", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(401, message, request_id), status=401)

def Forbidden(message: str = "Forbidden", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(403, message, request_id), status=403)

def NotFound(message: str = "Not Found", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(404, message, request_id), status=404)

def MethodNotAllowed(message: str = "Method Not Allowed", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(405, message, request_id), status=405)

def InternalServerError(message: str = "Internal Server Error", request_id: Optional[str] = None) -> 'Response':
    return JSON(_error_body(500, message, request_id), status=500)

# ==================================================
# Request and Response Classes
# ==================================================

class Request:
    """Encapsulates an HTTP request with parsed data."""

    def __init__(self, handler: http.server.BaseHTTPRequestHandler):
        self.handler = handler
        self.request_id = generate_request_id()
        self.method = handler.command
        self.path = handler.path
        self.url = handler.path
        # NOTE: handler.headers is an email.message.Message, which is
        # case-insensitive on lookup (per RFC 7230, header field names are
        # case-insensitive). Converting it to a plain dict() loses that
        # case-insensitivity, so all *internal* lookups below use
        # handler.headers.get(...) directly rather than self.headers.get(...).
        # self.headers itself is still exposed to BlazeLang/user code as a
        # plain dict for convenience.
        self.headers = dict(handler.headers)
        # Prefer a forwarded client IP if present (e.g. behind a proxy), else socket address
        forwarded_for = handler.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            self.client_ip = forwarded_for.split(',')[0].strip()
        else:
            self.client_ip = handler.client_address[0]
        self.protocol = handler.request_version
        self.host = handler.headers.get('Host', '')
        self.user_agent = handler.headers.get('User-Agent', '')
        self.timestamp = datetime.datetime.utcnow().isoformat() + 'Z'

        # Parse URL. The path portion is percent-decoded so that routes and
        # static files with spaces/unicode/reserved characters (e.g. "%20")
        # resolve correctly, and so that path-traversal checks downstream see
        # the real characters rather than an encoded payload.
        parsed = urllib.parse.urlparse(handler.path)
        self.path = urllib.parse.unquote(parsed.path)
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
        # Use the original (case-insensitive) headers object here, not the
        # plain self.headers dict -- see note in __init__.
        try:
            content_length = int(self.handler.headers.get('Content-Length', 0) or 0)
        except ValueError:
            content_length = 0
        if content_length <= 0:
            return

        # Read body
        raw_body = self.handler.rfile.read(content_length)
        self.body = raw_body

        content_type = self.handler.headers.get('Content-Type', '') or ''

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

    def get_basic_auth(self) -> Optional[Tuple[str, str]]:
        """Parse Basic Auth credentials from the Authorization header, if present."""
        return parse_basic_auth(self.handler.headers.get('Authorization'))

    def get_bearer_token(self) -> Optional[str]:
        """Parse a Bearer token from the Authorization header, if present."""
        return parse_bearer_token(self.handler.headers.get('Authorization'))

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for BlazeLang callback."""
        return {
            'requestId': self.request_id,
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

        # Set cookies. Per RFC 6265, multiple Set-Cookie headers must be sent
        # as separate header lines -- unlike most headers, Set-Cookie values
        # cannot be safely comma-joined (commas are legal inside e.g. the
        # Expires attribute, so a combined value is ambiguous/invalid and
        # many clients will fail to parse it). We store the list here and
        # _send_response() sends one "Set-Cookie" header per entry.
        cookie_headers = []
        for name, (value, kwargs) in self.cookies.items():
            cookie_headers.append(serialize_cookie(name, value, **kwargs))
        if cookie_headers:
            headers['Set-Cookie'] = cookie_headers

        # Normalize ContentType to Content-Type
        if 'ContentType' in headers:
            headers['Content-Type'] = headers.pop('ContentType')

        return status, headers, body

# ==================================================
# Response Helper Functions
# ==================================================

def JSON(data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Response:
    """Build a JSON response."""
    response = Response()
    response.status = status
    response.headers['Content-Type'] = 'application/json'
    if headers:
        response.set_headers(headers)
    response.body = data
    return response

def Text(text: str, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Response:
    """Build a plain text response."""
    response = Response()
    response.status = status
    response.headers['Content-Type'] = 'text/plain'
    if headers:
        response.set_headers(headers)
    response.body = text
    return response

def Redirect(location: str, status: int = 302, headers: Optional[Dict[str, str]] = None) -> Response:
    """Build a redirect response."""
    response = Response()
    response.status = status
    response.headers['Location'] = location
    if headers:
        response.set_headers(headers)
    response.body = ''
    return response

def File(file_path: str, content_type: Optional[str] = None,
         headers: Optional[Dict[str, str]] = None, as_attachment: bool = False,
         filename: Optional[str] = None) -> Response:
    """Build a response that serves a file's contents from disk."""
    response = Response()
    if not os.path.isfile(file_path):
        response.status = 404
        response.headers['Content-Type'] = 'application/json'
        response.body = {'success': False, 'error': {'status': 404, 'message': 'File not found'}}
        return response
    with open(file_path, 'rb') as f:
        data = f.read()
    response.status = 200
    response.headers['Content-Type'] = content_type or get_mime_type(file_path)
    if as_attachment:
        disp_name = filename or os.path.basename(file_path)
        response.headers['Content-Disposition'] = f'attachment; filename="{disp_name}"'
    if headers:
        response.set_headers(headers)
    response.body = data
    return response

def Status(status: int, body: Any = None, headers: Optional[Dict[str, str]] = None) -> Response:
    """Build a response with a custom status code and optional body."""
    response = Response()
    response.status = status
    if headers:
        response.set_headers(headers)
    response.body = body
    return response

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
# Rate Limiting (disabled unless configured)
# ==================================================

class RateLimiter:
    """Simple in-memory per-IP sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check whether a request from client_ip is allowed, recording the hit if so."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._hits.get(client_ip, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                self._hits[client_ip] = timestamps
                return False
            timestamps.append(now)
            self._hits[client_ip] = timestamps
            return True

class RouteGroup:
    """
    Context manager representing a route group/prefix.
    Nesting is supported; prefixes concatenate.
    """
    def __init__(self, server: 'BlazeHttpServer', prefix: str):
        self.server = server
        # Normalize: no trailing slash on the prefix itself
        self.prefix = prefix[:-1] if prefix.endswith('/') and prefix != '/' else prefix

    def __enter__(self):
        self.server._route_prefix_stack.append(self.prefix)
        return self.server

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.server._route_prefix_stack.pop()
        return False

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
            # Rate limiting is disabled by default; set 'rate_limit_max' (>0) to enable.
            'rate_limit_max': None,
            'rate_limit_window': DEFAULT_RATE_LIMIT_WINDOW,
        }
        self.session_store = SessionStore()
        self._server_instance = None
        self._stop_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._rate_limiter: Optional[RateLimiter] = None
        self._route_prefix_stack: List[str] = []

    def route(self, path: str, methods: List[str] = None) -> Callable:
        """Decorator to register a route handler."""
        full_path = self._current_prefix() + path
        def decorator(handler):
            if methods is None:
                route_methods = ['GET']
            elif isinstance(methods, str):
                route_methods = [methods]
            else:
                route_methods = methods
            for method in route_methods:
                self.routes.append((method.upper(), full_path, handler))
            return handler
        return decorator

    def _current_prefix(self) -> str:
        """Compose the currently active route-group prefix, if any."""
        return ''.join(self._route_prefix_stack)

    def group(self, prefix: str) -> 'RouteGroup':
        """
        Create a route group/prefix. Can be used as a context manager:

            with server.group('/api/v1'):
                @server.route('/users')
                def handler(req): ...

        Registers routes under '/api/v1/users'.
        """
        return RouteGroup(self, prefix)

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
        # (Re)build the rate limiter if rate limiting configuration changed.
        max_requests = self.config.get('rate_limit_max')
        if max_requests:
            self._rate_limiter = RateLimiter(
                int(max_requests),
                int(self.config.get('rate_limit_window') or DEFAULT_RATE_LIMIT_WINDOW)
            )
        else:
            self._rate_limiter = None

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
            next_fn = lambda: chain(index + 1)
            # Mirror the route-handler dispatch below: a BlazeLang function
            # value must be invoked as callback(interpreter, [args...]),
            # while a plain Python callable is invoked directly. Previously
            # middleware was always called the Python way, so BlazeLang
            # middleware registered via use() would receive the wrong
            # arguments (or crash) instead of (req, res, next).
            if hasattr(middleware, "__call__") and hasattr(middleware, "parameters"):
                result = middleware(self.interpreter, [request.to_dict(), response, next_fn])
            else:
                result = middleware(request, response, next_fn)
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
        start_time = time.time()
        request = None
        response = None
        try:
            # Create request object
            request = Request(handler)
            response = Response()

            # Optional per-IP rate limiting (disabled unless configured)
            if self._rate_limiter is not None:
                if not self._rate_limiter.is_allowed(request.client_ip):
                    self._send_error(handler, 429, "Too Many Requests", request.request_id)
                    self._log_request(request, 429, start_time)
                    return

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
                self._log_request(request, response.status, start_time)
                return

            # Find route handler
            route_handler, route_params = self._find_route_handler(request.method, request.path)
            if route_handler:
                request.params = route_params
                callback = route_handler
            else:
                # Check static files. HEAD must be served the same way as
                # GET (same headers/ETag/Content-Length), just without a
                # body -- that suppression happens later in
                # _send_response(), not here.
                if self.static_directory and request.method in ('GET', 'HEAD'):
                    served = self._serve_static(handler, request, response)
                    if served:
                        self._log_request(request, response.status, start_time)
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
            if isinstance(result, Response):
                response = result
            elif isinstance(result, dict):
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
            self._log_request(request, response.status, start_time)

        except HttpError as e:
            req_id = request.request_id if request else None
            self._send_error(handler, e.status, e.message, req_id)
            self._log_request(request, e.status, start_time)
        except Exception as e:
            # Internal server error
            req_id = request.request_id if request else None
            self._send_error(handler, 500, f"Internal Server Error: {str(e)}", req_id)
            self._log_request(request, 500, start_time)

    def _log_request(self, request: Optional[Request], status: int, start_time: float) -> None:
        """Log a completed request with method, path, status, request ID, and response time."""
        elapsed_ms = (time.time() - start_time) * 1000
        if request is not None:
            print(
                f"[{request.request_id}] {request.method} {request.path} "
                f"-> {status} ({elapsed_ms:.2f}ms)"
            )
        else:
            print(f"[unknown] -> {status} ({elapsed_ms:.2f}ms)")

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

        # Send. Content-Length/ETag/etc. above are always computed from the
        # real (would-be) body so a HEAD response reports accurate headers;
        # per RFC 7231 sec 4.3.2 a HEAD response must NOT include a body.
        handler.send_response(status)
        for key, value in headers.items():
            if key == 'Set-Cookie' and isinstance(value, list):
                for cookie_value in value:
                    handler.send_header(key, str(cookie_value))
            else:
                handler.send_header(key, str(value))
        handler.end_headers()
        if handler.command != 'HEAD':
            handler.wfile.write(body)

    def _send_error(self, handler: http.server.BaseHTTPRequestHandler, status: int, message: str,
                     request_id: Optional[str] = None) -> None:
        """Send error response as JSON with a consistent structure."""
        response = Response()
        response.status = status
        response.headers['Content-Type'] = 'application/json'
        response.body = _error_body(status, message, request_id)
        self._send_response(handler, response)

    def _serve_static(self, handler: http.server.BaseHTTPRequestHandler, request: Request, response: Response) -> bool:
        """Serve static file if exists and matches request."""
        # Get relative path. request.path is already percent-decoded (see
        # Request.__init__), so this check runs against the real characters
        # instead of an encoded traversal payload like "%2e%2e%2f".
        path = request.path
        # Remove leading slash and any query
        if path.startswith('/'):
            path = path[1:]
        # Reject absolute paths, backslashes, NUL bytes, and any literal ".."
        # segment up front. An empty path (the site root, e.g. requesting
        # "/") is valid and resolves to the static directory itself, which
        # is handled by the is-a-directory branch below (serves index.html).
        if '..' in path or path.startswith('/') or path.startswith('\\') or '\x00' in path:
            return False
        full_path = os.path.normpath(os.path.join(self.static_directory, path))
        # Defense in depth: even after the checks above, resolve symlinks and
        # confirm the final real path is still contained within the static
        # root before touching the filesystem. Prevents traversal via
        # symlinks or platform-specific path quirks that a string check on
        # 'path' alone wouldn't catch.
        real_root = os.path.realpath(self.static_directory)
        real_path = os.path.realpath(full_path)
        if real_path != real_root and not real_path.startswith(real_root + os.sep):
            return False
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
                # If the application explicitly registered an OPTIONS route,
                # honor it like any other method instead of always
                # short-circuiting with a generic CORS preflight response.
                path_only = urllib.parse.urlparse(self.path).path
                route_handler, _ = server_ref._find_route_handler('OPTIONS', urllib.parse.unquote(path_only))
                if route_handler is not None:
                    server_ref.handle_request(self)
                    return
                # Default: CORS preflight response.
                response = Response()
                response.status = 200
                if server_ref.config['enable_cors']:
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
        """
        Gracefully stop the server.

        This can race with listen()'s own `finally: self.stop()` (e.g. an
        external caller invokes stop() while serve_forever() is returning
        after its own shutdown()). Take the instance under a lock and clear
        it immediately so a concurrent/duplicate call is a no-op instead of
        calling shutdown()/server_close() on a None or already-closed
        server.
        """
        with self._stop_lock:
            server = self._server_instance
            self._server_instance = None
        if server is None:
            return
        try:
            server.shutdown()
        finally:
            server.server_close()
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

    def route(path: str, methods: List[str] = None, handler: Callable = None) -> Callable:
        """
        Register a route.

        Supports both calling conventions:
          - Decorator style:   route(path, methods)(handler)
          - Direct call style: route(path, methods, handler)
        """
        if handler is not None:
            return server.route(path, methods)(handler)
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

    def group(prefix: str):
        """Create a route group/prefix (usable as a context manager)."""
        return server.group(prefix)

    return {
        'listen': listen,
        'stop': stop,
        'route': route,
        'static': static,
        'use': use,
        'configure': configure,
        'group': group,

        # Response helpers
        'json_response': JSON,
        'text_response': Text,
        'redirect': Redirect,
        'file_response': File,
        'status_response': Status,

        # HTTP status helpers
        'bad_request': BadRequest,
        'unauthorized': Unauthorized,
        'forbidden': Forbidden,
        'not_found': NotFound,
        'method_not_allowed': MethodNotAllowed,
        'internal_server_error': InternalServerError,

        # Auth utilities
        'parse_basic_auth': parse_basic_auth,
        'parse_bearer_token': parse_bearer_token,

        # JWT utilities
        'jwt_encode': jwt_encode,
        'jwt_decode': jwt_decode,

        # Request ID utility
        'generate_request_id': generate_request_id,
    }