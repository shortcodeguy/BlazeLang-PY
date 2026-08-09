# BlazeLang Diagnostics

BlazeLang emits structured diagnostics with a stable code, category, location, source preview, hint, and—when a user function is active—call stack. ANSI colour is used in interactive terminals; set `NO_COLOR=1` to force plain output.

| Code | Category | Typical cause | Fix |
| --- | --- | --- | --- |
| BLZ1001 | Syntax Error | Invalid character or unfinished string | Check the highlighted token. |
| BLZ1002 | Parser Error | Invalid BlazeLang grammar | Close brackets and use valid statement syntax. |
| BLZ2001 | Runtime Error | Invalid operation at runtime | Check the reported operation. |
| BLZ2002 | Undefined Variable | A name has not been declared | Declare it before use. |
| BLZ2003 | Division By Zero | A denominator evaluated to zero | Validate the denominator. |
| BLZ2004 | Type Error | Operator operands are incompatible | Convert or validate the values. |
| BLZ3001 | Import Error | Missing module/export or circular import | Check the path/export name. |
| BLZ3002 | Module Error | Invalid module state | Inspect the referenced module. |
| BLZ4001 | HTTP Error | Request could not be completed | Inspect `response.statusText`; HTTP requests are safe response objects. |
| BLZ5001 | File Error | File could not be read or written | Check path and permissions. |
| BLZ9001 | Internal Error | Interpreter implementation failure | Report the program and diagnostic. |

Try the intentionally failing programs in `blazelang/examples/v5/` with `python main.py run <file>`. `http_error.blz` completes safely and prints its error response, which lets programs handle network problems themselves.
