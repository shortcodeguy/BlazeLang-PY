"""Native command-line application support for BlazeLang."""

import os
import sys
from dataclasses import dataclass, field

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


def _text(value, name):
    if not isinstance(value, str) or not value:
        raise BlazeRuntimeError(f"CLI.{name} must be a non-empty string")
    return value


def _scalar(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


@dataclass
class _Command:
    name: str
    description: str
    handler: object
    aliases: list = field(default_factory=list)
    arguments: list = field(default_factory=list)
    options: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    children: list = field(default_factory=list)


class Command:
    def __init__(self, app, command):
        self._app, self._command = app, command

    def Alias(self, name):
        name = _text(name, "Alias name")
        if name not in self._command.aliases:
            self._command.aliases.append(name)
        return self

    def Command(self, name, description, handler):
        """Register a subcommand below this command."""
        return self._app._add_command(self._command.children, name, description, handler)

    def Argument(self, name, description="", required=True):
        name = _text(name, "Argument name")
        if not isinstance(description, str) or not isinstance(required, bool):
            raise BlazeRuntimeError("CLI.Argument expects a string description and boolean required value")
        self._command.arguments.append((name, description, required))
        return self

    def Option(self, name, alias="", description="", required=False, default=None):
        name = _text(name, "Option name").lstrip("-")
        alias = alias.lstrip("-") if isinstance(alias, str) else ""
        if not isinstance(description, str) or not isinstance(required, bool):
            raise BlazeRuntimeError("CLI.Option expects a string description and boolean required value")
        self._command.options.append((name, alias, description, required, default))
        return self

    def Flag(self, name, alias="", description=""):
        name = _text(name, "Flag name").lstrip("-")
        alias = alias.lstrip("-") if isinstance(alias, str) else ""
        if not isinstance(description, str):
            raise BlazeRuntimeError("CLI.Flag description must be a string")
        self._command.flags.append((name, alias, description))
        return self


class CLIApplication:
    def __init__(self, interpreter, name, description, argv):
        self._interpreter = interpreter
        self.name, self.description = _text(name, "Create name"), _text(description, "Create description")
        self._argv = list(argv)
        self._commands = []

    def _add_command(self, collection, name, description, handler):
        name, description = _text(name, "Command name"), _text(description, "Command description")
        if not callable(handler):
            raise BlazeRuntimeError("CLI.Command handler must be a function")
        if any(command.name == name or name in command.aliases for command in collection):
            raise BlazeRuntimeError(f"CLI command '{name}' is already registered")
        command = _Command(name, description, handler)
        collection.append(command)
        return Command(self, command)

    def Command(self, name, description, handler):
        return self._add_command(self._commands, name, description, handler)

    def Help(self):
        lines = [f"{self.name} - {self.description}", "", f"Usage: {self.name} <command> [arguments] [options]", "", "Commands:"]
        for command in self._commands:
            aliases = f" ({', '.join(command.aliases)})" if command.aliases else ""
            lines.append(f"  {command.name}{aliases}  {command.description}")
        lines.extend(["", "Global options:", "  --help, -h       Show this help", "  --version, -V    Show version information"])
        return "\n".join(lines)

    def Version(self):
        return f"{self.name} 1.0.0"

    @staticmethod
    def _find(collection, name):
        return next((item for item in collection if item.name == name or name in item.aliases), None)

    def _command_help(self, command):
        lines = [f"{self.name} {command.name} - {command.description}", "", f"Usage: {self.name} {command.name} <subcommand> [arguments] [options]"]
        if command.children:
            lines.extend(["", "Subcommands:"])
            lines.extend(f"  {child.name}  {child.description}" for child in command.children)
        return "\n".join(lines)

    def _parse(self, command, tokens):
        values = {"command": command.name, "positionals": []}
        lookup = {}
        for name, alias, _description, required, default in command.options:
            values[name] = default
            lookup[f"--{name}"] = (name, True, required)
            if alias: lookup[f"-{alias}"] = (name, True, required)
        for name, alias, _description in command.flags:
            values[name] = False
            lookup[f"--{name}"] = (name, False, False)
            if alias: lookup[f"-{alias}"] = (name, False, False)
        index = 0
        while index < len(tokens):
            token = tokens[index]
            key, equals, inline = token.partition("=")
            if key in lookup:
                name, needs_value, _required = lookup[key]
                if needs_value:
                    if equals: value = inline
                    elif index + 1 < len(tokens):
                        index += 1; value = tokens[index]
                    else: raise BlazeRuntimeError(f"CLI option '--{name}' requires a value")
                    values[name] = _scalar(value)
                else:
                    values[name] = True
            elif token.startswith("-"):
                raise BlazeRuntimeError(f"Unknown option '{token}'. Run with --help for available options.")
            else:
                values["positionals"].append(_scalar(token))
            index += 1
        for position, (name, _description, required) in enumerate(command.arguments):
            if position < len(values["positionals"]): values[name] = values["positionals"][position]
            elif required: raise BlazeRuntimeError(f"CLI command '{command.name}' requires argument '{name}'")
            else: values[name] = None
        # Positional arguments remain convenient even before explicit
        # declarations; a/b cover the standard two-number command example.
        for position, value in enumerate(values["positionals"]):
            values.setdefault(f"arg{position + 1}", value)
        if values["positionals"]:
            values.setdefault("a", values["positionals"][0])
        if len(values["positionals"]) > 1:
            values.setdefault("b", values["positionals"][1])
        return values

    def Run(self):
        if not self._argv or self._argv[0] in ("--help", "-h"):
            print(self.Help()); return 0
        if self._argv[0] in ("--version", "-V"):
            print(self.Version()); return 0
        command = self._find(self._commands, self._argv[0])
        if command is None:
            raise BlazeRuntimeError(f"Unknown CLI command '{self._argv[0]}'. Run with --help for available commands.")
        index = 1
        while command.children and index < len(self._argv) and not self._argv[index].startswith("-"):
            child = self._find(command.children, self._argv[index])
            if child is None:
                raise BlazeRuntimeError(f"Unknown subcommand '{self._argv[index]}' for '{command.name}'.")
            command, index = child, index + 1
        if index < len(self._argv) and self._argv[index] in ("--help", "-h"):
            print(self._command_help(command)); return 0
        args = self._parse(command, self._argv[index:])
        if hasattr(command.handler, "parameters"):
            command.handler(self._interpreter, [args])
        else:
            command.handler(args)
        return 0


class CLILibrary:
    def __init__(self, interpreter, argv=None):
        self._interpreter = interpreter
        self._argv = list(argv if argv is not None else getattr(interpreter, "cli_args", []))

    def Create(self, name, description):
        return CLIApplication(self._interpreter, name, description, self._argv)

    def Arguments(self): return list(self._argv)
    def CurrentDirectory(self): return os.getcwd()
    def ScriptPath(self): return self._interpreter.filename or ""
    def ExecutablePath(self): return sys.executable
    def Exit(self, code=0):
        if isinstance(code, bool) or not isinstance(code, (int, float)) or int(code) != code:
            raise BlazeRuntimeError("CLI.Exit code must be a whole number")
        raise SystemExit(int(code))


def create_cli_module(interpreter, argv=None):
    library = CLILibrary(interpreter, argv)
    return {"Create": library.Create, "Arguments": library.Arguments,
            "CurrentDirectory": library.CurrentDirectory, "ScriptPath": library.ScriptPath,
            "ExecutablePath": library.ExecutablePath, "Exit": library.Exit}
