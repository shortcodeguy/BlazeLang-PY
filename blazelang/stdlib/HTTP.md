# BlazeLang HTTP Standard Library

Import the library with `Import Http from "http"` or `Import * as Http from "http"`.

| Method | Syntax | Result |
| --- | --- | --- |
| GET | `Http.Get(url, options)` | Response object |
| POST / PUT / PATCH | `Http.Post(url, data, options)` | Response object |
| DELETE / HEAD / OPTIONS | `Http.Delete(url, options)` | Response object |
| Download | `Http.Download(url, path, options)` | Response object with `path` |
| Upload | `Http.Upload(url, path, options)` | Response object |

`data` objects and arrays are JSON-encoded automatically. `options` can contain `headers`, `query`, and `timeout` (milliseconds). Every call returns `status`, `statusText`, `ok`, `body`, `headers`, `url`, `method`, and `error`; `error` is `null` for a successful response and contains the failure detail otherwise. `Http.Download` creates any missing destination directories automatically. Network errors return `ok: false` rather than terminating the program. JSON response bodies are decoded into BlazeLang objects/arrays when the server declares a JSON content type.
