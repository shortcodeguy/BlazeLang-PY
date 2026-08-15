# Changelog

## 1.3.0

- Added `BLZ1011`: unrecognized/typo'd declaration keyword detection (e.g. `Fucntion foo() {` -> "Did you mean 'Function'?"), scoped to the `Word Name(`/`Word Name {` shape so ordinary calls and expressions are never flagged.
- Added `BLZ1012`: unrecognized `Import ... from "module"` module name, with a "did you mean" suggestion for near-miss casing and a warning for anything else that isn't a known standard module or a local `.blz` path.
- Added an editor-title "▶ Run BlazeLang" button (visible only for `.blz` files) plus a Run dropdown (Run File / Run File with Arguments / Run Project).
- Added `BlazeLang: Run File`, `Run File with Arguments`, `Run Project`, and `Stop` commands; the CLI is always invoked as `blz run "<file>"` (never via Python), and a friendly error is shown if the `blz` CLI can't be found.
- Added `blazelang.cliPath`, `blazelang.enableCompletion`, `blazelang.enableFormatting`, and `blazelang.run.autoSave` settings (`blazelang.interpreterPath` still works as a fallback).
- Terminal output like `main.blz:12:5` is now clickable and jumps straight to that line/column.
- Added custom-attribute support: syntax highlighting, hover (`Name` / `Arguments` / description), completion for known attributes, and diagnostics for malformed attributes (e.g. `@role(` with no closing paren) without flagging unknown attributes as errors.
- Added `Struct` and `Enum` declarations to diagnostics, symbols/outline, hover, completion, and syntax highlighting.
- Added recognition of Meta hooks (`OnCall`, `Before`, `OnReturn`, `After`, `OnError`) and `bind` variables/properties (`.value`, `.previous`, `.history`, `.changes`) in completion, hover, and highlighting.
- Added snippets for `struct`, `enum`, `meta`, `import`, `export`, `attr`, and `bind`.
- Verified scope-aware duplicate-declaration diagnostics correctly allow same-named `var`s across separate functions/classes/scopes.

## 1.1.0

- Fixed: `&&` and `||` (logical AND/OR) and `&` / `|` (bitwise AND/OR) are now correctly recognized and syntax-highlighted by the TextMate grammar; previously these operators had no highlighting rule at all.
- Fixed: the duplicate-declaration diagnostic (BLZ1004) is now scope-aware. Reusing a variable name across separate `Meta` functions, `Function`s, classes, or sibling blocks (`if`/`while`) no longer produces a false-positive duplicate-declaration warning. Genuine duplicates within the same scope are still correctly reported.

## 1.0.0

- Initial production-ready BlazeLang language extension.
- Added syntax/semantic highlighting, diagnostics, IntelliSense, navigation, formatting, snippets, commands, and icons.