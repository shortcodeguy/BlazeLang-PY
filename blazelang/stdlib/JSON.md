# BlazeLang JSON Standard Library

Import with `Import Json from "json"` or `Import * as Json from "json"`.

| Method | Parameters | Returns |
| --- | --- | --- |
| `Json.Parse(text)` | JSON string (or an already-decoded HTTP value) | Object, array, primitive, or `null` |
| `Json.Stringify(value)` | BlazeLang value | Compact JSON string |
| `Json.Pretty(value)` | BlazeLang value or JSON string | Four-space-indented JSON string |
| `Json.Validate(text)` | JSON string | `true` or `false` |

`Parse` reports malformed input as `BlazeLang JSON Error [BLZ6001]` with the JSON line and column. `Validate` is the non-throwing alternative. JSON response bodies returned by the HTTP library may already be objects; `Json.Parse(response.body)` accepts them unchanged.
