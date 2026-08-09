"""BlazeLang's synchronous HTTP standard-library module.

The public dictionary returned by :func:`create_http_module` is intentionally
plain Python/BlazeLang data: response fields are accessible as
``response.status`` and ``response.body`` from BlazeLang code.
"""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen


class HttpClient:
    """Small, dependency-free HTTP client used by the BlazeLang runtime."""

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path.cwd()).resolve()

    def get(self, url, options=None):
        return self._request("GET", url, options=options)

    def post(self, url, data=None, options=None):
        return self._request("POST", url, data=data, options=options)

    def put(self, url, data=None, options=None):
        return self._request("PUT", url, data=data, options=options)

    def patch(self, url, data=None, options=None):
        return self._request("PATCH", url, data=data, options=options)

    def delete(self, url, options=None):
        return self._request("DELETE", url, options=options)

    def head(self, url, options=None):
        return self._request("HEAD", url, options=options)

    def options(self, url, options=None):
        return self._request("OPTIONS", url, options=options)

    def download(self, url, path, options=None):
        response, raw = self._request("GET", url, options=options, include_raw=True)
        if response["ok"]:
            try:
                destination = self._path(path)
                # Downloads commonly target a new folder, so create its
                # parent tree before writing the response body.
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
                response["path"] = str(destination)
            except OSError as error:
                message = f"File write error: {error}"
                response.update({"ok": False, "statusText": message, "error": message, "path": str(path)})
        return response

    def upload(self, url, path, options=None):
        """Upload a file as an octet stream; multipart support can be added later."""
        try:
            content = self._path(path).read_bytes()
        except OSError as error:
            return self._error_response("POST", url, f"File read error: {error}")
        upload_options = dict(options or {})
        headers = dict(upload_options.get("headers") or {})
        headers.setdefault("Content-Type", "application/octet-stream")
        headers.setdefault("X-Filename", os.path.basename(path))
        upload_options["headers"] = headers
        return self._request("POST", url, data=content, options=upload_options)

    def _request(self, method, url, data=None, options=None, include_raw=False):
        options = options or {}
        if not isinstance(url, str) or not url:
            result = self._error_response(method, str(url), "Invalid URL")
            return (result, b"") if include_raw else result
        try:
            final_url = self._with_query(url, options.get("query"))
            headers = {str(key): str(value) for key, value in (options.get("headers") or {}).items()}
            payload = self._encode_body(data, headers)
            timeout_ms = options.get("timeout", 30000)
            timeout = max(0, float(timeout_ms)) / 1000
            request = Request(final_url, data=payload, headers=headers, method=method)
            with urlopen(request, timeout=timeout) as remote:
                raw = remote.read()
                result = self._response(method, remote.geturl(), remote.status, remote.reason, remote.headers, raw)
        except HTTPError as error:
            raw = error.read()
            result = self._response(method, error.geturl(), error.code, error.reason, error.headers, raw)
        except (URLError, ValueError, OSError) as error:
            raw = b""
            result = self._error_response(method, url, self._friendly_error(error))
        return (result, raw) if include_raw else result

    def _path(self, path):
        candidate = Path(str(path).replace("\\", os.sep).replace("/", os.sep))
        return (candidate if candidate.is_absolute() else self.base_dir / candidate).resolve()

    @staticmethod
    def _with_query(url, query):
        if not query:
            return url
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("Unsupported or invalid URL")
        values = parse_qsl(parts.query, keep_blank_values=True)
        values.extend(query.items())
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(values, doseq=True), parts.fragment))

    @staticmethod
    def _encode_body(data, headers):
        if data is None:
            return None
        if isinstance(data, (dict, list)):
            headers.setdefault("Content-Type", "application/json")
            return json.dumps(data).encode("utf-8")
        if isinstance(data, bytes):
            return data
        return str(data).encode("utf-8")

    @staticmethod
    def _response(method, url, status, status_text, headers, raw):
        header_map = dict(headers.items()) if headers else {}
        content_type = header_map.get("Content-Type", "").lower()
        charset = headers.get_content_charset() if headers and hasattr(headers, "get_content_charset") else "utf-8"
        text = raw.decode(charset or "utf-8", errors="replace")
        body = text
        if "json" in content_type:
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                pass
        ok = 200 <= status < 300
        return {"status": status, "statusText": str(status_text), "ok": ok,
                "body": body, "headers": header_map, "url": url, "method": method,
                "error": None if ok else str(status_text)}

    @staticmethod
    def _friendly_error(error):
        reason = getattr(error, "reason", error)
        return f"HTTP request failed: {reason}"

    @staticmethod
    def _error_response(method, url, message):
        return {"status": 0, "statusText": message, "ok": False, "body": "", "headers": {},
                "url": url, "method": method, "error": message}


def create_http_module(base_dir=None):
    """Return the public BlazeLang ``Http`` namespace."""
    client = HttpClient(base_dir)
    return {"Get": client.get, "Post": client.post, "Put": client.put, "Patch": client.patch,
            "Delete": client.delete, "Head": client.head, "Options": client.options,
            "Download": client.download, "Upload": client.upload}
