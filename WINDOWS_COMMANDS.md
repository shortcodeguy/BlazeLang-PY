# BlazeLang Windows Commands

The `Output` folder contains three standalone executables. They include the Python runtime; users do not need Python installed.

| File | Purpose | Example |
| --- | --- | --- |
| `blz.exe` | Full BlazeLang command-line tool. | `blz run main.blz` |
| `blzinterpreter.exe` | Interactive interpreter. Enter exactly one BlazeLang statement at each `blz>` prompt. | `blzinterpreter` |
| `blzcompiler.exe` | Runs one `.blz` program directly. | `blzcompiler main.blz` |

## PowerShell

```powershell
.\Output\blz.exe run .\main.blz
.\Output\blzinterpreter.exe
.\Output\blzcompiler.exe .\main.blz
```

## Command Prompt and Windows Terminal

```cmd
Output\blz.exe run main.blz
Output\blzinterpreter.exe
Output\blzcompiler.exe main.blz
```

To use `blz`, `blzinterpreter`, and `blzcompiler` from any directory, add the project's `Output` folder to the Windows `PATH` environment variable, then open a new terminal.

The interactive interpreter keeps variables and imports from earlier lines. Use `:help` for help and `:exit` or `:quit` to close it. Blocks such as functions, classes, loops, and `if` statements must be entered on one physical line.
