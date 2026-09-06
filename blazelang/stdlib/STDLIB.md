# BlazeLang Standard Library

All built-in modules use `Import Name from "module"` or `Import * as Name from "module"`. They require no installation and use PascalCase members. Invalid arguments produce a BlazeLang runtime diagnostic (`BLZ2001`); module-specific errors remain `BLZ4001` for HTTP, `BLZ5001` for File, and `BLZ6001` for JSON.

| Module | Reference and example | Returns / notes |
| --- | --- | --- |
| Math | `Abs(x)`, `Sqrt(x)`, `Pow(base, exp)`, `Sin(x)`, `Cos(x)`, `Tan(x)`, `Log(x)`, `Log10(x)`, `Exp(x)`, `Floor(x)`, `Ceil(x)`, `Round(x, digits)`, `Min(...)`, `Max(...)`, `Clamp(x,min,max)`, constants `PI`, `E`. Example: `Math.Clamp(Math.Sqrt(81), 0, 5)`. | Numbers. Trigonometric functions use radians; square roots and logarithms reject invalid domains. |
| Random | `Int(min,max)`, `Float()`, `Bool()`, `Choice(array)`, `Shuffle(array)`, `String(length)`. Example: `Round(x, digits)`, `Choice` requires a non-empty array. |
| Date | `Today()`, `Year()`, `Month()`, `Day()`, `Weekday()`, `Format(pattern)`. Example: `Date.Format("dd/MM/yyyy")`. | Local date; `Today` is ISO-8601; format supports `yyyy`, `MM`, `dd`. |
| Time | `Now()`, `Hour()`, `Minute()`, `Second()`, `Sleep(milliseconds)`. Example: `Time.Sleep(1000)`. | Local clock; `Now` uses `HH:MM:SS`; sleep rejects negative durations. |
| Path | `Join(...)`, `Normalize(path)`, `FileName(path)`, `Directory(path)`, `Extension(path)`, `Parent(path)`. Example: `Path.Join("src", "main.blz")`. | Uses the host platform's path separator and never touches the file system. |
| System | `Platform()`, `Version()`, `Exit(code)`, `CurrentDirectory()`, `SetCurrentDirectory(path)`, `Arguments()`, `Clear()`, `Beep()`. Example: `System.Platform()`. | Process and terminal helpers. `SetCurrentDirectory` can affect relative paths later in the program. |
| Env | `Get(name, default)`, `Set(name,value)`, `Exists(name)`, `Remove(name)`. Example: `Env.Get("PATH")`. | Process-local environment; avoid putting secrets in program output. |
| File | See [FILE.md](FILE.md). | UTF-8, source-file-relative file operations; `BLZ5001`. |
| Http | See [HTTP.md](HTTP.md). | HTTP responses and uploads/downloads; `BLZ4001`. |
| Json | See [JSON.md](JSON.md). | Parse, stringify, pretty-print, validate; `BLZ6001`. |
| Image | `Image.Create(width,height)`, `Image.Open(path)`, `Image.Load(path)`, `Image.LoadURL(url)`, then `Width()`, `Height()`, `Resize(w,h)`, `Crop(x,y,w,h)`, `Rotate(deg)`, `Flip("horizontal"|"vertical")`, `FlipHorizontal()`, `FlipVertical()`, `Grayscale`, `Invert`, `Blur`, `Sharpen`, pixel and drawing methods, and `Save(path)`. | PNG, JPG/JPEG, BMP, and WebP. Images are held as RGBA; PNG and WebP preserve alpha. `LoadURL` fetches images over HTTP/HTTPS. |
| Video | `Video.Load(path)` / `Video.Open(path)`, then `Width()`, `Height()`, `Duration()`, `Play()`, `Pause()`, `Stop()`, `Seek(seconds)`, `GetPosition()`, `IsPlaying()`. | Video loading, metadata, and basic playback controls backed by OpenCV. Supports common video formats (.mp4, .avi, .mov, .mkv, .webm). |
| Process | `Start(cmd, args)`, `Run(cmd, args)`, `Wait(handle, timeout)`, `Kill(handle)`, `IsRunning(handle)`, `PID(handle)`, `ExitCode(handle)`. Example: `Process.Run("cmd /c echo Hello")`. | Native process management helper. Supports synchronous execution (`Run`) and background process control (`Start`/`Wait`/`Kill`/`IsRunning`/`PID`/`ExitCode`). |
| CLI | `CLI.Create(name, description)`, `Command` (also available on a command for subcommands), `Argument`, `Option`, `Flag`, `Alias`, and `Run`. Context helpers: `Arguments`, `CurrentDirectory`, `ScriptPath`, `ExecutablePath`, `Exit(code)`. | Script arguments follow the `.blz` file: `blz run app.blz hello --name Rohit`. `--help`/`-h` and `--version`/`-V` are automatic; validation failures exit with code 1. See `examples/cli/cli.blz`. |

Best practices: validate external input, use `Path.Join` rather than manually inserting separators, create directories before `File.Write` or `Http.Download`, and avoid calling `System.Exit` from reusable functions.
