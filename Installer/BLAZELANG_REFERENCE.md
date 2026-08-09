# BlazeLang v1.6 Complete Syntax Reference

## Commands and installation

`blz.exe` is a standalone Windows executable: it bundles the BlazeLang interpreter and Python runtime, so people using BlazeLang do **not** need to install Python.

Put `blz.exe` in a permanent folder such as `C:\BlazeLang`, then add that folder to the Windows `PATH`. Open a new terminal and run:

```text
blz run program.blz
blz tokenize program.blz
blz parse program.blz
blz version
blz help
```

PowerShell, Command Prompt, and Windows Terminal use the same commands after the folder is in `PATH`:

```powershell
blz run .\examples\hello.blz
```

```cmd
blz run examples\hello.blz
```

Before adding it to `PATH`, run the executable from its folder with `./blz.exe run program.blz` in PowerShell or `blz.exe run program.blz` in Command Prompt.

## Lexical rules

Identifiers begin with a letter or `_` and may then contain letters, digits, and `_`. BlazeLang is case-sensitive: `Function`, `Meta`, `Class`, `Constructor`, `Break`, `Continue`, `Import`, `Export`, and `Default` must use the exact capitalization shown. Most other keywords are lowercase.

Strings may use double or single quotes. Supported escapes are `\n`, `\t`, `\\`, `\"`, `\'`, and `\{`. A string may span lines. Numbers may be integers (`42`) or decimals (`3.14`). Literals are `true`, `false`, and `null`.

BlazeLang currently has **no comment syntax** and **no semicolons**. Do not use `#`, `//`, `/* ... */`, or `;` in a `.blz` file.

## Variables, values, and access

```blz
var name = "BlazeLang"
constant version = "1.6"
var number = 42
var decimal = 3.14
var active = true
var missing = null
var names = ["Asha", "Ravi"]
var settings = { theme: "Dark", enabled: true }

names[0] = "Mira"
settings.theme = "Light"
```

Declarations are `var name` or `constant name`, optionally followed by `= expression`. A `constant` cannot be reassigned. Arrays use `[item, ...]`; object keys are identifiers followed by `:` and a value. Use `object.property` and `array[index]` to read or write values.

## Operators and expression order

| Group | Operators | Example |
| --- | --- | --- |
| Access and call | `.`, `[]`, `()` | `user.name`, `items[0]`, `Add(1, 2)` |
| Unary | `-`, `not` | `-total`, `not ready` |
| Power | `**` | `2 ** 8` |
| Multiply | `*`, `/`, `%` | `total / count` |
| Add | `+`, `-` | `first + last` |
| Compare | `==`, `!=`, `<`, `<=`, `>`, `>=` | `score >= 50` |
| Logical | `and`, `or` | `active and ready` |
| Assign | `=`, `+=`, `-=`, `*=`, `/=` | `count += 1` |

Parentheses group expressions: `(price + tax) * quantity`. `+` also joins strings. Assignment may target a variable, object property, or array element.

## Statements and control flow

```blz
if score >= 50 {
    Show("Passed")
}
else if score >= 40 {
    Show("Retake")
}
else {
    Show("Try again")
}

while count < 3 {
    count += 1
}

for item in ["one", "two"] {
    Show(item)
}

for index in range(0, 3) {
    if index == 1 {
        Continue
    }
    Show(index)
    if index == 2 {
        Break
    }
}
```

`if`, `else if`, `else`, `while`, and `for name in expression` use `{ ... }` blocks. `Break` and `Continue` are valid only inside a loop. There is no C-style `for (start; condition; step)` syntax.

## Functions and errors

```blz
Function Add(left, right) {
    return left + right
}

Meta Log(message) {
    Show(message)
}

try {
    throw "Unable to continue"
}
catch (error) {
    Show(error)
}
finally {
    Show("Cleanup finished")
}
```

Function syntax is `Function Name(parameter, ...) { ... }`. `return expression` ends a function; plain `return` returns `null`. `Meta` has the same declaration syntax but is intended for no-return routines. Error handling syntax is exactly `try { ... } catch (name) { ... } finally { ... }`; `finally` is optional, but `catch (name)` is required. Raise a runtime error with lowercase `throw expression`.

## Classes, instances, and inheritance

```blz
Class Person {
    Constructor(name) {
        this.name = name
    }

    Function Greeting() {
        return "Hello " + this.name
    }
}

Class Student: Person {
    Constructor(name) {
        this.name = name
    }
}

var person = Person("Asha")
Show(person.Greeting())
```

Use `Class Name { ... }` or `Class Child: Parent { ... }`. A class body may contain `Constructor(...)`, `Function ...`, `Meta ...`, `static Function ...`, `static Meta ...`, `public Function ...`, `public Meta ...`, `private Function ...`, and `private Meta ...`. Instance code uses `this`; `super` refers to the parent class where a parent exists.

## Imports, exports, and local modules

```blz
Import File from "file"
Import * as Json from "json"
Import { Parse as ParseJson, Pretty } from "json"
Import math as Math
Import "modules/config"

Export var appName = "BlazeLang"
Export constant release = "1.6"
Export Function Add(left, right) { return left + right }
Export Meta Log(text) { Show(text) }
Export Class App { }
Export Default var mainName = "default export"
```

Supported import forms are `Import Name from "module"`, `Import * as Name from "module"`, `Import { Export, Export as Local } from "module"`, the legacy `Import module as Name`, and `Import "module"`. Relative local module paths may omit `.blz`. Export forms are `Export` followed by `var`, `constant`, `Function`, `Meta`, or `Class`; prefix one declaration with `Default` to make it the default export.

Built-in module names are `math`, `random`, `date`, `time`, `path`, `system`, `env`, `file`, `http`, and `json`. See [blazelang/stdlib/STDLIB.md](blazelang/stdlib/STDLIB.md) for their functions.

## Built-in functions

| Built-in | Syntax / purpose |
| --- | --- |
| Output | `Show(value, ...)` prints with a newline; `Print(value, ...)` prints without one. |
| Input | `Input(prompt)` returns a string; terminal EOF returns an empty string. |
| Collections | `len(value)`, `range(stop)`, `range(start, stop)`, `range(start, stop, step)`. |
| Type conversion | `type(value)`, `Int(value)`, `Float(value)`, `String(value)`, `Bool(value)`. |
| Text | `Upper`, `Lower`, `Trim`, `Split`, `Join`, `Replace`, `Contains`, `StartsWith`, `EndsWith`, `Find`. |
| Other | `Reverse(value)`, `Random(min, max)`, `Sleep(seconds)`, `Exit(code)`. |

## Complete reserved-word list

| Active syntax word | Purpose |
| --- | --- |
| `var`, `constant` | Mutable and immutable declarations. |
| `if`, `else`, `while`, `for`, `in` | Branching and loops. |
| `Meta`, `Function`, `Class`, `Constructor`, `return` | Declarations, construction, and function return. |
| `Break`, `Continue` | Loop control. |
| `Import`, `Export`, `from`, `as`, `Default` | Module import/export syntax. |
| `try`, `catch`, `finally`, `throw` | Error handling. |
| `static`, `public`, `private` | Class-method modifiers. |
| `this`, `super` | Instance and parent-class references. |
| `and`, `or`, `not` | Boolean operators. |
| `true`, `false`, `null` | Boolean and null literals. |

`async`, `await`, `protected`, and `override` are reserved words in the lexer. They are not yet implemented as usable language syntax, so do not use them as identifiers or in programs until a future release adds their behavior.

## Diagnostics and error codes

Diagnostics include the error type, stable code, location, source preview, hint, and call stack where available.

| Code | Meaning | Common cause and fix |
| --- | --- | --- |
| `BLZ1001` | Syntax Error | Invalid character or unfinished string. Check the marked character. |
| `BLZ1002` | Parser Error | Unsupported or incomplete grammar. Check brackets, braces, and exact keyword spelling. |
| `BLZ2001` | Runtime Error | Invalid operation or invalid standard-library argument. Check values and control flow. |
| `BLZ2002` | Undefined Variable | The name has not been declared or imported. |
| `BLZ2003` | Division By Zero | The right side of `/` or `/=` became zero. |
| `BLZ2004` | Type Error | Operator values are incompatible. Convert values first. |
| `BLZ3001` | Import Error | Missing module/export, invalid module path, or circular import. |
| `BLZ3002` | Module Error | Invalid module loading state. |
| `BLZ4001` | HTTP Error | HTTP operation issue; inspect `response.ok`, `response.statusText`, and `response.error`. |
| `BLZ5001` | File Error | File-system issue; check path, parent directory, permissions, and disk space. |
| `BLZ6001` | JSON Error | Invalid JSON or a non-serializable JSON value. |
| `BLZ9001` | Internal Error | Unexpected interpreter failure; preserve the diagnostic and a minimal reproducer. |

`Http.Download(url, "downloads/logo.jpg")` creates missing destination directories automatically. `File.Write` and `File.Append` require their parent directory to exist; use `File.CreateDirectory` first.
