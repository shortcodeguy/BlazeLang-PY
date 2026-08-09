# BlazeLang Installer

Run `BlazeLang-Setup.exe` to install BlazeLang for the current Windows user. It copies the three standalone executables to `%LOCALAPPDATA%\BlazeLang`, adds that folder to the user `PATH`, and notifies Windows about the change.

Open a new Command Prompt, PowerShell window, or Windows Terminal tab after installation, then use `blz run main.blz`, `blzinterpreter`, or `blzcompiler main.blz`. Python is not required.
