# BlazeLang Standard Library

All built-in modules use `Import Name from "module"` or `Import * as Name from "module"`. They require no installation and use PascalCase members. Invalid arguments produce a BlazeLang runtime diagnostic (`BLZ2001`); module-specific errors remain `BLZ4001` for HTTP, `BLZ5001` for File, and `BLZ6001` for JSON.

| Module | Reference and example | Returns / notes |
| --- | --- | --- |
| Math | `Abs(x)`, `Sqrt(x)`, `Pow(base, exp)`, `Sin(x)`, `Cos(x)`, `Tan(x)`, `Log(x)`, `Log10(x)`, `Exp(x)`, `Floor(x)`, `Ceil(x)`, `Round(x, digits)`, `Min(...)`, `Max(...)`, `Clamp(x,min,max)`, constants `PI`, `E`. Example: `Math.Clamp(Math.Sqrt(81), 0, 5)`. | Numbers. Trigonometric functions use radians; square roots and logarithms reject invalid domains. |
| Random | `Int(min,max)`, `Float()`, `Bool()`, `Choice(array)`, `Shuffle(array)`, `String(length)`. Example: `Random.String(12)`. | `Int` is inclusive; `Shuffle` returns a shuffled copy; `Choice` requires a non-empty array. |
| Date | `Today()`, `Year()`, `Month()`, `Day()`, `Weekday()`, `Format(pattern)`. Example: `Date.Format("dd/MM/yyyy")`. | Local date; `Today` is ISO-8601; format supports `yyyy`, `MM`, `dd`. |
| Time | `Now()`, `Hour()`, `Minute()`, `Second()`, `Sleep(milliseconds)`. Example: `Time.Sleep(1000)`. | Local clock; `Now` uses `HH:MM:SS`; sleep rejects negative durations. |
| Path | `Join(...)`, `Normalize(path)`, `FileName(path)`, `Directory(path)`, `Extension(path)`, `Parent(path)`. Example: `Path.Join("src", "main.blz")`. | Uses the host platform's path separator and never touches the file system. |
| System | `Platform()`, `Version()`, `Exit(code)`, `CurrentDirectory()`, `SetCurrentDirectory(path)`, `Arguments()`, `Clear()`, `Beep()`. Example: `System.Platform()`. | Process and terminal helpers. `SetCurrentDirectory` can affect relative paths later in the program. |
| Env | `Get(name, default)`, `Set(name,value)`, `Exists(name)`, `Remove(name)`. Example: `Env.Get("PATH")`. | Process-local environment; avoid putting secrets in program output. |
| File | See [FILE.md](FILE.md). | UTF-8, source-file-relative file operations; `BLZ5001`. |
| Http | See [HTTP.md](HTTP.md). | HTTP responses and uploads/downloads; `BLZ4001`. |
| Json | See [JSON.md](JSON.md). | Parse, stringify, pretty-print, validate; `BLZ6001`. |

Best practices: validate external input, use `Path.Join` rather than manually inserting separators, create directories before `File.Write` or `Http.Download`, and avoid calling `System.Exit` from reusable functions.
