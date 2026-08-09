# BlazeLang File Standard Library

Import the cross-platform, UTF-8 text file API with `Import File from "file"` or `Import * as File from "file"`. Relative paths are always resolved from the running `.blz` file. Failed operations raise `BlazeLang File Error [BLZ5001]` with the source location, a clear reason, and a recovery hint.

| Function | Purpose, parameters, return value, and example | Possible errors |
| --- | --- | --- |
| `Read(path)` | Reads UTF-8 text at `path`; returns a string. Example: `var text = File.Read("notes.txt")`. | Missing file, invalid path, permission denied, decode or I/O error. |
| `Write(path, text)` | Replaces or creates a UTF-8 file; returns `true`. Its parent directory must exist. Example: `File.Write("notes.txt", "Hello")`. | Missing parent directory, read-only file, disk full, invalid path. |
| `Append(path, text)` | Appends UTF-8 text, creating the file if its parent exists; returns `true`. Example: `File.Append("app.log", "Started\\n")`. | Missing parent directory, permission denied, disk full. |
| `Exists(path)` | Returns whether `path` is a regular file. Example: `if File.Exists("config.json") { Show("found") }`. | Does not throw for a missing path. |
| `Delete(path)` | Deletes a file; returns `true`. Example: `File.Delete("old.txt")`. | Missing file, read-only file, permission denied. |
| `Copy(source, destination)` | Copies file contents and metadata; returns `true`. Example: `File.Copy("config.json", "backup.json")`. | Missing source/parent directory, permission denied, disk full. |
| `Move(source, destination)` | Moves a file; returns `true`. Example: `File.Move("temp.txt", "archive/temp.txt")`. | Missing source/parent directory, destination conflict, permission denied. |
| `Rename(source, destination)` | Renames a file in its filesystem; returns `true`. Example: `File.Rename("old.txt", "new.txt")`. | Missing source/parent directory, destination conflict, permission denied. |
| `Size(path)` | Returns file size in bytes. Example: `Show(File.Size("video.mp4"))`. | Missing file, permission denied. |
| `Extension(path)` | Returns the final extension without the dot, or an empty string. Example: `Show(File.Extension("photo.png"))`. | None. |
| `CreateDirectory(path)` | Creates a directory and missing parents; returns `true`. Example: `File.CreateDirectory("downloads")`. | Invalid path, permission denied, conflicting file. |
| `DeleteDirectory(path, recursive)` | Deletes an empty directory; set optional `recursive` to `true` to delete contents too; returns `true`. Example: `File.DeleteDirectory("cache", true)`. | Missing directory, non-empty directory (without `true`), permission denied. |
| `ExistsDirectory(path)` | Returns whether `path` is a directory. Example: `if File.ExistsDirectory("downloads") { Show("ready") }`. | Does not throw for a missing path. |
| `ListFiles(path)` | Returns sorted immediate file names. `path` defaults to `"."`. Example: `for file in File.ListFiles(".") { Show(file) }`. | Missing directory, invalid path, permission denied. |
| `ListDirectories(path)` | Returns sorted immediate directory names. `path` defaults to `"."`. Example: `for dir in File.ListDirectories(".") { Show(dir) }`. | Missing directory, invalid path, permission denied. |

`Http.Download` and `Http.Upload` use the same source-file-relative path rules, so `Http.Download(url, "downloads/logo.png")` and `File.Exists("downloads/logo.png")` refer to the same item. Create the target directory before downloading.
