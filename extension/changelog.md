# Changelog

## 1.1.0

- Fixed: `&&` and `||` (logical AND/OR) and `&` / `|` (bitwise AND/OR) are now correctly recognized and syntax-highlighted by the TextMate grammar; previously these operators had no highlighting rule at all.
- Fixed: the duplicate-declaration diagnostic (BLZ1004) is now scope-aware. Reusing a variable name across separate `Meta` functions, `Function`s, classes, or sibling blocks (`if`/`while`) no longer produces a false-positive duplicate-declaration warning. Genuine duplicates within the same scope are still correctly reported.

## 1.0.0

- Initial production-ready BlazeLang language extension.
- Added syntax/semantic highlighting, diagnostics, IntelliSense, navigation, formatting, snippets, commands, and icons.