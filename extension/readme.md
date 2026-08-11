# BlazeLang for Visual Studio Code

Professional editing support for BlazeLang (`.blz`) source files. This extension is self-contained: it does not install BlazeLang or ship a compiler/interpreter.

## Features

- BlazeLang language registration, file icon, comments, folding, matching brackets, auto-closing pairs, indentation, and region folding.
- TextMate and semantic highlighting for the language implemented by BlazeLang: declarations, classes, functions, modules, values, strings, comments, properties, built-ins, and operators.
- Fast editor-side diagnostics, hover, completions, document/workspace symbols, definitions, references, rename, formatting, and quick fixes.
- Snippets for control flow, functions, classes, error handling, and I/O.
- Commands: **Run Current File**, **Format Document**, **Restart Language Server**, **New BlazeLang File**, and **Show Version**.

## Setup

1. Install this extension from a `.vsix` package or the Marketplace.
2. Open a folder containing `.blz` files. BlazeLang activates automatically.
3. If `blz` is not on `PATH`, set `blazelang.interpreterPath` to the full path of `blz.exe`.

Run the current editor with **BlazeLang: Run Current File**. The command issued is `blz run <file>` (or the configured interpreter path).

## Formatting and diagnostics

The formatter uses four spaces by default; set `blazelang.format.indentSize` to change it. Editor diagnostics are intentionally lightweight and incremental, so they remain responsive in large workspaces. The BlazeLang runtime remains the authority for execution-time diagnostics.

## Language compatibility

This extension follows the current BlazeLang lexer/parser: blocks use braces, `Function`, `Meta`, `Class`, and `Constructor` are capitalized, `Break`/`Continue` are capitalized, and statements do **not** use semicolons. Both `//` and `/* ... */` comments are supported by the lexer. `async`, `await`, `protected`, and `override` are reserved but not implemented by BlazeLang, so the extension does not suggest them.

Press `F5` in VS Code to launch an Extension Development Host.

## License

MIT. See [LICENSE](https://github.com/blazelang/vscode-blazelang/blob/HEAD/LICENSE).