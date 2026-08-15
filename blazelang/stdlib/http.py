"""BlazeLang synchronous HTTP standard-library module.

Supported:

    Http.Get(url)
    Http.Get(url, options)

    Http.Post(url, data)
    Http.Post(url, data, options)

    Http.Put(url, data, options)
    Http.Patch(url, data, options)
    Http.Delete(url, options)

Options:

    {
        authorization: "Bearer ...",
        ContentType: "application/json",
        query: {...},
        timeout: 30000
    }

The module also supports:

    headers: {
        Authorization: "...",
        ContentType: "application/json"
    }

But direct authorization is recommended for simple API calls.
"""

import json
import os

from pathlib import Path

from urllib.error import (
    HTTPError,
    URLError
)

from urllib.parse import (
    urlencode,
    urlsplit,
    urlunsplit,
    parse_qsl
)

from urllib.request import (
    Request,
    urlopen
)


class HttpClient:
    """Small dependency-free HTTP client."""

    def __init__(self, base_dir=None):

        self.base_dir = Path(
            base_dir or Path.cwd()
        ).resolve()


    # ============================================================
    # BASIC METHODS
    # ============================================================

    def get(self, url, options=None):

        return self._request(
            "GET",
            url,
            options=options
        )


    def post(
        self,
        url,
        data=None,
        options=None
    ):

        return self._request(
            "POST",
            url,
            data=data,
            options=options
        )


    def put(
        self,
        url,
        data=None,
        options=None
    ):

        return self._request(
            "PUT",
            url,
            data=data,
            options=options
        )


    def patch(
        self,
        url,
        data=None,
        options=None
    ):

        return self._request(
            "PATCH",
            url,
            data=data,
            options=options
        )


    def delete(
        self,
        url,
        options=None
    ):

        return self._request(
            "DELETE",
            url,
            options=options
        )


    def head(
        self,
        url,
        options=None
    ):

        return self._request(
            "HEAD",
            url,
            options=options
        )


    def options(
        self,
        url,
        options=None
    ):

        return self._request(
            "OPTIONS",
            url,
            options=options
        )


    # ============================================================
    # DOWNLOAD
    # ============================================================

    def download(
        self,
        url,
        path,
        options=None
    ):

        response, raw = self._request(
            "GET",
            url,
            options=options,
            include_raw=True
        )

        if response["ok"]:

            try:

                destination = self._path(
                    path
                )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                destination.write_bytes(
                    raw
                )

                response["path"] = str(
                    destination
                )

            except OSError as error:

                message = (
                    f"File write error: {error}"
                )

                response.update({
                    "ok": False,
                    "statusText": message,
                    "error": message,
                    "path": str(path)
                })

        return response


    # ============================================================
    # UPLOAD
    # ============================================================

    def upload(
        self,
        url,
        path,
        options=None
    ):

        try:

            content = self._path(
                path
            ).read_bytes()

        except OSError as error:

            return self._error_response(
                "POST",
                url,
                f"File read error: {error}"
            )


        upload_options = dict(
            options or {}
        )


        headers = dict(
            upload_options.get(
                "headers"
            ) or {}
        )


        headers.setdefault(
            "Content-Type",
            "application/octet-stream"
        )


        headers.setdefault(
            "X-Filename",
            os.path.basename(path)
        )


        upload_options["headers"] = headers


        return self._request(
            "POST",
            url,
            data=content,
            options=upload_options
        )


    # ============================================================
    # MAIN REQUEST
    # ============================================================

    def _request(
        self,
        method,
        url,
        data=None,
        options=None,
        include_raw=False
    ):

        options = options or {}


        if not isinstance(
            url,
            str
        ) or not url:

            result = self._error_response(
                method,
                str(url),
                "Invalid URL"
            )

            if include_raw:
                return result, b""

            return result


        try:

            # ----------------------------------------------------
            # QUERY
            # ----------------------------------------------------

            final_url = self._with_query(
                url,
                options.get("query")
            )


            # ----------------------------------------------------
            # HEADERS
            # ----------------------------------------------------

            headers = {}


            # Existing headers object
            raw_headers = options.get(
                "headers"
            ) or {}


            if isinstance(
                raw_headers,
                dict
            ):

                for key, value in raw_headers.items():

                    header_name = str(key)

                    header_name = (
                        self._normalize_header_name(
                            header_name
                        )
                    )

                    headers[
                        header_name
                    ] = str(value)


            # ----------------------------------------------------
            # DIRECT AUTHORIZATION
            # ----------------------------------------------------

            authorization = options.get(
                "authorization"
            )


            if authorization is not None:

                headers[
                    "Authorization"
                ] = str(
                    authorization
                )


            # ----------------------------------------------------
            # API KEY SHORTCUT
            # ----------------------------------------------------

            api_key = options.get(
                "apiKey"
            )


            if api_key is not None:

                headers[
                    "Authorization"
                ] = (
                    "Bearer " +
                    str(api_key)
                )


            # ----------------------------------------------------
            # CONTENT TYPE
            # ----------------------------------------------------

            content_type = options.get(
                "contentType"
            )


            if content_type is not None:

                headers[
                    "Content-Type"
                ] = str(
                    content_type
                )


            # ----------------------------------------------------
            # ACCEPT
            # ----------------------------------------------------

            accept = options.get(
                "accept"
            )


            if accept is not None:

                headers[
                    "Accept"
                ] = str(
                    accept
                )


            # ----------------------------------------------------
            # USER AGENT
            # ----------------------------------------------------

            user_agent = options.get(
                "userAgent"
            )


            if user_agent is not None:

                headers[
                    "User-Agent"
                ] = str(
                    user_agent
                )


            # ----------------------------------------------------
            # BODY
            # ----------------------------------------------------

            payload = self._encode_body(
                data,
                headers
            )


            # ----------------------------------------------------
            # TIMEOUT
            # ----------------------------------------------------

            timeout_ms = options.get(
                "timeout",
                30000
            )


            timeout = (
                max(
                    0,
                    float(timeout_ms)
                ) / 1000
            )


            # ----------------------------------------------------
            # REQUEST
            # ----------------------------------------------------

            request = Request(
                final_url,
                data=payload,
                headers=headers,
                method=method
            )


            # ----------------------------------------------------
            # DEBUGGING
            # ----------------------------------------------------

            # Uncomment temporarily if needed:
            #
            # print("[BlazeLang HTTP] Method:", method)
            # print("[BlazeLang HTTP] URL:", final_url)
            # print("[BlazeLang HTTP] Headers:", headers)


            with urlopen(
                request,
                timeout=timeout
            ) as remote:

                raw = remote.read()


                result = self._response(
                    method,
                    remote.geturl(),
                    remote.status,
                    remote.reason,
                    remote.headers,
                    raw
                )


        except HTTPError as error:

            raw = error.read()


            result = self._response(
                method,
                error.geturl(),
                error.code,
                error.reason,
                error.headers,
                raw
            )


        except (
            URLError,
            ValueError,
            OSError
        ) as error:

            raw = b""


            result = self._error_response(
                method,
                url,
                self._friendly_error(
                    error
                )
            )


        if include_raw:

            return result, raw

        return result


    # ============================================================
    # HEADER NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_header_name(
        name
    ):

        aliases = {

            "ContentType":
                "Content-Type",

            "contentType":
                "Content-Type",

            "AcceptType":
                "Accept",

            "acceptType":
                "Accept",

            "UserAgent":
                "User-Agent",

            "userAgent":
                "User-Agent",

            "ApiKey":
                "Authorization",

            "apiKey":
                "Authorization"
        }


        return aliases.get(
            name,
            name
        )


    # ============================================================
    # BODY ENCODING
    # ============================================================

    @staticmethod
    def _encode_body(
        data,
        headers
    ):

        if data is None:

            return None


        if isinstance(
            data,
            (dict, list)
        ):

            headers.setdefault(
                "Content-Type",
                "application/json"
            )


            return json.dumps(
                data
            ).encode(
                "utf-8"
            )


        if isinstance(
            data,
            bytes
        ):

            return data


        return str(
            data
        ).encode(
            "utf-8"
        )


    # ============================================================
    # QUERY
    # ============================================================

    @staticmethod
    def _with_query(
        url,
        query
    ):

        if not query:

            return url


        parts = urlsplit(
            url
        )


        if (
            parts.scheme
            not in ("http", "https")
            or not parts.netloc
        ):

            raise ValueError(
                "Unsupported or invalid URL"
            )


        values = parse_qsl(
            parts.query,
            keep_blank_values=True
        )


        if isinstance(
            query,
            dict
        ):

            values.extend(
                query.items()
            )


        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(
                    values,
                    doseq=True
                ),
                parts.fragment
            )
        )


    # ============================================================
    # RESPONSE
    # ============================================================

    @staticmethod
    def _response(
        method,
        url,
        status,
        status_text,
        headers,
        raw
    ):

        header_map = (
            dict(headers.items())
            if headers
            else {}
        )


        content_type = header_map.get(
            "Content-Type",
            ""
        ).lower()


        charset = (
            headers.get_content_charset()
            if headers
            and hasattr(
                headers,
                "get_content_charset"
            )
            else "utf-8"
        )


        text = raw.decode(
            charset or "utf-8",
            errors="replace"
        )


        body = text


        if "json" in content_type:

            try:

                body = json.loads(
                    text
                )

            except json.JSONDecodeError:

                body = text


        ok = (
            200 <= status < 300
        )


        return {
            "status": status,
            "statusText": str(
                status_text
            ),
            "ok": ok,
            "body": body,
            "headers": header_map,
            "url": url,
            "method": method,
            "error": (
                None
                if ok
                else str(status_text)
            )
        }


    # ============================================================
    # PATH
    # ============================================================

    def _path(
        self,
        path
    ):

        candidate = Path(
            str(path)
            .replace(
                "\\",
                os.sep
            )
            .replace(
                "/",
                os.sep
            )
        )


        return (
            candidate
            if candidate.is_absolute()
            else self.base_dir / candidate
        ).resolve()


    # ============================================================
    # ERROR
    # ============================================================

    @staticmethod
    def _friendly_error(
        error
    ):

        reason = getattr(
            error,
            "reason",
            error
        )


        return (
            f"HTTP request failed: {reason}"
        )


    @staticmethod
    def _error_response(
        method,
        url,
        message
    ):

        return {
            "status": 0,
            "statusText": message,
            "ok": False,
            "body": "",
            "headers": {},
            "url": url,
            "method": method,
            "error": message
        }


# ================================================================
# PUBLIC BLAZELANG MODULE
# ================================================================

def create_http_module(
    base_dir=None
):

    client = HttpClient(
        base_dir
    )


    return {
        "Get": client.get,
        "Post": client.post,
        "Put": client.put,
        "Patch": client.patch,
        "Delete": client.delete,
        "Head": client.head,
        "Options": client.options,
        "Download": client.download,
        "Upload": client.upload
    }