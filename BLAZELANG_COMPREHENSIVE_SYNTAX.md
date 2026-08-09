# BlazeLang Comprehensive Syntax Example

This guide is derived from the current lexer, parser, and interpreter in this
repository. The snippets below collectively exercise every implemented
language form. `async`, `await`, `protected`, and `override` are tokenized as
reserved words, but the parser does not implement them; they are deliberately
not shown as usable syntax.

## Main program (`syntax_showcase.blz`)

```blz
// Single-line comments are accepted by the lexer.
/* Multi-line comments are accepted too. */

// All supported import forms.
Import DefaultThing from "modules/syntax_module"
Import * as Syntax from "modules/syntax_module"
Import { namedValue, add as AddFromModule } from "modules/syntax_module"
Import "modules/side_effect"
Import math as LegacyMath

Import Math from "math"
Import RandomModule from "random"
Import Date from "date"
Import Time from "time"
Import Path from "path"
Import System from "system"
Import Env from "env"
Import Json from "json"
Import File from "file"
Import Http from "http"

// Declarations, literals, escapes, arrays, objects, and access.
var declaredLater
var integer = 42
var decimal = 3.14
var negative = -integer
var quoted = 'single-quoted string'
var escaped = "line one\nline two\t\\ \" \' \{"
var active = true
var inactive = false
var nothing = null
constant release = "1.6"
var values = [1, 2, 3,]
var profile = { name: "Asha", enabled: active, tags: ["blaze", "lang"], }
var firstValue = values[0]
var profileName = profile.name
values[0] = 10
values[1] += 2
values[2] -= 1
profile.name = "Mira"
profile.count = 1
profile.count *= 2
profile.count /= 2

// Calls, grouping, all arithmetic/comparison/logical/unary operators.
var arithmetic = (integer + decimal - 2) * 3 / 2 % 5 ** 2
var comparisons = integer == 42 and integer != 0 and integer > 1 and integer >= 42 and integer < 100 and integer <= 42
var logic = not inactive or active
var combined = "Hello, " + profile.name
Show(combined, arithmetic, comparisons, logic)
Print("Print does not add a newline; ")
Show("Show does.")

// Built-in helpers and conversion syntax.
var words = Split(Trim("  red,blue  "), ",")
var text = Join(words, " + ")
var transformed = Replace(Upper(text), "RED", Lower("GREEN"))
var textFacts = [Contains(transformed, "green"), StartsWith(transformed, "GREEN"), EndsWith(transformed, "blue"), Find(transformed, "blue")]
var reversed = Reverse(words)
var builtins = [len(words), range(3), range(1, 4), range(5, 0, -2), type(profile), Int("7"), Float("2.5"), String(42), Bool(1), Random(1, 2)]
Show(reversed, textFacts, builtins)

// if / else if / else, while, for-in, Break, and Continue.
if integer < 0 {
    Show("negative")
}
else if integer == 42 {
    Show("answer")
}
else {
    Show("another value")
}

var counter = 0
while counter < 3 {
    counter += 1
}

for index in range(0, 5) {
    if index == 1 {
        Continue
    }
    if index == 4 {
        Break
    }
    Show(index)
}

for word in words {
    Show(word)
}

// Function, Meta, return with a value, and bare return.
Function Add(left, right) {
    return left + right
}

Function StopEarly() {
    return
}

Meta Announce(message) {
    Show("Announcement: " + message)
}

Show(Add(2, 3), StopEarly())
Announce("ready")

// try / catch / finally and throw.
try {
    if not active {
        throw "The feature is disabled"
    }
    Show("try completed")
}
catch (error) {
    Show("caught: {error}")
}
finally {
    Show("always runs")
}

// Classes, inheritance, Constructor, this, super, static/public/private,
// instance methods, and Meta methods.
Class Parent {
    Constructor(label) {
        this.label = label
    }

    Function ParentLabel() {
        return "parent method"
    }
}

Class Child: Parent {
    Constructor(label) {
        this.label = label
        this.visits = 0
    }

    Function Describe() {
        return super.ParentLabel() + ": " + this.label
    }

    Meta Visit() {
        this.visits += 1
    }

    static Function MakeLabel(value) {
        return "static: " + value
    }

    static Meta ReportStatic() {
        Show("static Meta")
    }

    public Function PublicMethod() {
        return this.label
    }

    private Meta PrivateMethod() {
        Show("private Meta")
    }
}

var child = Child("BlazeLang")
child.Visit()
Show(child.Describe(), child.PublicMethod(), child.visits)
Show(Child.MakeLabel("value"))
Child.ReportStatic()
child.PrivateMethod()

// Imports made above expose properties and call syntax for every standard module.
var mathValues = [Math.PI, Math.E, Math.Abs(-4), Math.Sqrt(9), Math.Pow(2, 3), Math.Sin(0), Math.Cos(0), Math.Tan(0), Math.Log(1), Math.Log10(10), Math.Exp(1), Math.Floor(2.9), Math.Ceil(2.1), Math.Round(2.345, 2), Math.Min(3, 1, 2), Math.Max(3, 1, 2), Math.Clamp(12, 0, 10), LegacyMath.PI]
var randomValues = [RandomModule.Int(1, 2), RandomModule.Float(), RandomModule.Bool(), RandomModule.Choice(values), RandomModule.Shuffle(values), RandomModule.String(4)]
var dateValues = [Date.Today(), Date.Year(), Date.Month(), Date.Day(), Date.Weekday(), Date.Format("yyyy-MM-dd")]
var timeValues = [Time.Now(), Time.Hour(), Time.Minute(), Time.Second()]
var pathValue = Path.Join("examples", "syntax_showcase.blz")
var pathValues = [Path.Normalize(pathValue), Path.FileName(pathValue), Path.Directory(pathValue), Path.Extension(pathValue), Path.Parent(pathValue)]
var systemValues = [System.Platform(), System.Version(), System.CurrentDirectory(), System.Arguments()]
var environmentValues = [Env.Set("BLAZELANG_SYNTAX", "on"), Env.Get("BLAZELANG_SYNTAX", "off"), Env.Exists("BLAZELANG_SYNTAX"), Env.Remove("BLAZELANG_SYNTAX")]
var jsonText = Json.Stringify(profile)
var jsonValues = [Json.Parse(jsonText), Json.Pretty(profile), Json.Validate(jsonText)]
Show(mathValues, randomValues, dateValues, timeValues, pathValues, systemValues, environmentValues, jsonValues)

// File calls (use a disposable directory if you run this section).
File.CreateDirectory("syntax_temp")
File.Write("syntax_temp/example.txt", "first\n")
File.Append("syntax_temp/example.txt", "second\n")
var fileValues = [File.Exists("syntax_temp/example.txt"), File.Read("syntax_temp/example.txt"), File.Size("syntax_temp/example.txt"), File.Extension("syntax_temp/example.txt"), File.ListFiles("syntax_temp"), File.ListDirectories("syntax_temp")]
File.Copy("syntax_temp/example.txt", "syntax_temp/copy.txt")
File.Move("syntax_temp/copy.txt", "syntax_temp/moved.txt")
File.Rename("syntax_temp/moved.txt", "syntax_temp/renamed.txt")
File.Delete("syntax_temp/renamed.txt")
File.Delete("syntax_temp/example.txt")
File.DeleteDirectory("syntax_temp", false)
Show(fileValues)

// HTTP calls return response objects. These are examples only; uncomment to make network requests.
// var response = Http.Get("https://example.com", { headers: { Accept: "text/html" }, query: { page: 1 }, timeout: 5000 })
// var posted = Http.Post("https://example.com/api", { title: "BlazeLang" })
// Http.Put("https://example.com/api/1", { updated: true })
// Http.Patch("https://example.com/api/1", { updated: true })
// Http.Delete("https://example.com/api/1")
// Http.Head("https://example.com")
// Http.Options("https://example.com")
// Http.Download("https://example.com/logo.png", "downloads/logo.png")
// Http.Upload("https://example.com/upload", "syntax_temp/example.txt")

// Sleep takes seconds; Exit terminates the process, so they are intentionally not invoked.
// Sleep(0.1)
// Exit(0)
// Time.Sleep(10) // milliseconds
// System.Exit(0)
```

## Exporting module (`modules/syntax_module.blz`)

```blz
Export var namedValue = "named export"
Export constant fixedValue = 7

Export Function add(left, right) {
    return left + right
}

Export Meta Log(message) {
    Show(message)
}

Export Class ExportedClass {
    Function Name() {
        return "ExportedClass"
    }
}

Export Default var DefaultThing = "default export"
```

## Side-effect-only module (`modules/side_effect.blz`)

```blz
Show("This local module was loaded for its side effect.")
```

## Notes on parser-supported forms

- Declarations do not require an initializer (`var declaredLater`).
- Array and object literals accept a trailing comma. Object keys must be identifiers.
- `static`, `public`, and `private` are accepted only before `Function` or `Meta` inside a class; the current interpreter records the methods but does not enforce access control or give `static` methods separate storage.
- `super` resolves the parent class. Calling a parent method that relies on `this` is not currently bound to the child instance, so the `ParentLabel` example intentionally needs no instance state.
- Comments are supported by the implementation. Semicolons are not tokenized, so omit them.
