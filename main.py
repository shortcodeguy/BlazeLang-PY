#!/usr/bin/env python3
"""
BlazeLang - A modern, general-purpose programming language
Main entry point for the BlazeLang CLI
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import compiler components (top-level for performance)
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter
from blazelang.errors.error_handler import BlazeError, InternalInterpreterError, ErrorFormatter


def print_banner():
    """Print the BlazeLang banner"""
    print("BlazeLang v2.0")
    print("A modern programming language - Readable, Flexible, Structured")
    print()


def is_verbose_mode():
    """
    Determine if verbose mode is enabled.
    Checks for -v, --verbose in command line arguments,
    or BLZ_DEBUG=1 environment variable.
    """
    if os.environ.get("BLZ_DEBUG") == "1":
        return True
    return "-v" in sys.argv or "--verbose" in sys.argv


def load_source(filename: str) -> str:
    """Read and return the source code from a file, with existence check."""
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found")
        sys.exit(1)

    if not filename.endswith('.blz'):
        # Warning only, not fatal
        print(f"Warning: File '{filename}' does not have .blz extension")

    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()


def print_compiler_error(error, source: str = None):
    """Display a structured source-aware BlazeLang diagnostic."""
    error_source = source
    if error.filename and os.path.isfile(error.filename):
        try:
            with open(error.filename, 'r', encoding='utf-8') as file:
                error_source = file.read()
        except OSError:
            pass
    print("\n" + ErrorFormatter.format_diagnostic(error, error_source))


def print_warnings(warnings, filename):
    """Emit non-fatal parser diagnostics without interrupting execution."""
    if not warnings:
        return
    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    yellow, reset = ("\033[93m", "\033[0m") if use_color else ("", "")
    for line, column, message in warnings:
        location = f" at {filename}:line {line}:col {column}" if line else ""
        print(f"{yellow}Warning: {message}{location}{reset}")


def print_ast(node, indent: int = 0):
    """Pretty print AST structure (used by parse command)."""
    prefix = "  " * indent

    if node is None:
        print(f"{prefix}None")
        return

    node_type = type(node).__name__

    if hasattr(node, 'statements'):
        print(f"{prefix}Program ({len(node.statements)} statements)")
        for stmt in node.statements:
            print_ast(stmt, indent + 1)
    elif hasattr(node, 'name') and hasattr(node, 'value'):
        val_str = str(node.value) if not isinstance(node.value, str) else f'"{node.value}"'
        print(f"{prefix}{node_type}: {node.name} = {val_str}")
    elif hasattr(node, 'name'):
        print(f"{prefix}{node_type}: {node.name}")
    elif hasattr(node, 'value'):
        val_str = str(node.value) if not isinstance(node.value, str) else f'"{node.value}"'
        print(f"{prefix}{node_type}: {val_str}")
    else:
        print(f"{prefix}{node_type}")


def run_file(filename: str, source: str, verbose: bool = False):
    """Execute a BlazeLang file with optional verbose output."""
    try:
        # 1. Lexical Analysis
        if verbose:
            print(f"Lexing '{filename}'...")
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()
        if verbose:
            print(f"Generated {len(tokens)} tokens")

        # 2. Parsing
        if verbose:
            print("Parsing...")
        parser = Parser(tokens)
        ast = parser.parse()
        if verbose:
            print(f"AST generated with {len(ast.statements)} statements")

        # Print warnings (always)
        print_warnings(getattr(ast, 'warnings', []), filename)

        # 3. Interpretation
        if verbose:
            print("Running...")
            print("-" * 50)

        interpreter = Interpreter(filename=filename)
        result = interpreter.interpret(ast)

        # Post-execution message only in verbose mode
        if verbose:
            print("-" * 50)
            if result is not None:
                print(f"\nProgram returned: {result}")
            else:
                print("\nProgram completed successfully")

    except BlazeError as e:
        print_compiler_error(e, source)
        sys.exit(1)
    except Exception as e:
        print_compiler_error(InternalInterpreterError(str(e), filename=filename), source)
        sys.exit(1)


def tokenize_file(filename: str, source: str):
    """Tokenize and display tokens from a BlazeLang file (debug command)."""
    try:
        print(f"\nTokenizing: {filename}")
        print("=" * 80)

        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()

        # Header
        print(f"{'#':<4} {'Type':<22} {'Value':<20} {'Line':<6} {'Col':<6}")
        print("-" * 80)

        # Token list
        for i, token in enumerate(tokens, 1):
            type_name = token.type.name
            value = str(token.value)[:18] if token.value is not None else "None"
            print(f"{i:<4} {type_name:<22} {value:<20} {token.line:<6} {token.column:<6}")

        print("=" * 80)
        print(f"Total: {len(tokens)} tokens")

    except Exception as e:
        print_compiler_error(e if isinstance(e, BlazeError) else InternalInterpreterError(str(e), filename=filename), source)
        sys.exit(1)


def parse_file(filename: str, source: str):
    """Parse and display AST from a BlazeLang file (debug command)."""
    try:
        print(f"\nParsing: {filename}")
        print("=" * 80)

        # Tokenize first
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()

        # Parse
        parser = Parser(tokens)
        ast = parser.parse()

        # Display AST
        print("AST Structure:")
        print_ast(ast)
        print("=" * 80)
        print("Parsing completed successfully")

    except Exception as e:
        print_compiler_error(e if isinstance(e, BlazeError) else InternalInterpreterError(str(e), filename=filename), source)
        sys.exit(1)


def main():
    """Main entry point for BlazeLang CLI"""
    if len(sys.argv) < 2:
        print_banner()
        print("Usage: blz <command> [options]")
        print()
        print("Commands:")
        print("  run <file>       Run a BlazeLang file")
        print("  tokenize <file>  Show tokens for a file")
        print("  parse <file>     Show AST for a file")
        print("  package <main>   Create a .blzp package")
        print("  install <repo>   Install a GitHub package (owner/repo)")
        print("  version          Show version information")
        print("  help             Show this help message")
        print()
        print("Run options:")
        print("  -v, --verbose    Enable verbose output (shows compiler stages)")
        print("  BLZ_DEBUG=1      Environment variable alternative for verbose")
        print()
        print("Examples:")
        print("  blz run examples/hello.blz")
        print("  blz run examples/hello.blz --verbose")
        print("  BLZ_DEBUG=1 blz run examples/hello.blz")
        return

    command = sys.argv[1]

    if command == "version":
        print_banner()
        print("Version: 2.0")
        print("Status: production")

    elif command == "help":
        print_banner()
        print("Usage: blz <command> [options]")
        print()
        print("Commands:")
        print("  run <file>       Run a BlazeLang file")
        print("  tokenize <file>  Show tokens for a file")
        print("  parse <file>     Show AST for a file")
        print("  package <main>   Create a .blzp package")
        print("  install <repo>   Install a GitHub package (owner/repo)")
        print("  version          Show version information")
        print("  help             Show this help message")
        print()
        print("Run options:")
        print("  -v, --verbose    Enable verbose output (shows compiler stages)")
        print("  BLZ_DEBUG=1      Environment variable alternative for verbose")

    elif command == "run":
        if len(sys.argv) < 3:
            print("Error: Please specify a file to run")
            print("Usage: blz run <file.blz> [--verbose|-v]")
            return

        filename = sys.argv[2]
        source = load_source(filename)
        verbose = is_verbose_mode()
        run_file(filename, source, verbose)

    elif command == "tokenize":
        if len(sys.argv) < 3:
            print("Error: Please specify a file to tokenize")
            print("Usage: blz tokenize <file.blz>")
            return

        filename = sys.argv[2]
        source = load_source(filename)
        tokenize_file(filename, source)

    elif command == "parse":
        if len(sys.argv) < 3:
            print("Error: Please specify a file to parse")
            print("Usage: blz parse <file.blz>")
            return

        filename = sys.argv[2]
        source = load_source(filename)
        parse_file(filename, source)

    elif command == "package":
        if len(sys.argv) != 3:
            print("Error: Usage: blz package main.blz")
            return
        try:
            from blazelang.package import create_package, PackageError
            output = create_package(sys.argv[2])
            print(f"Created package: {output}")
        except (OSError, PackageError) as error:
            print(f"Error: {error}")
            sys.exit(1)

    elif command == "install":
        if len(sys.argv) != 3:
            print("Error: Usage: blz install githubuser/repo")
            return
        try:
            from blazelang.package import install_github_package, PackageError
            metadata = install_github_package(sys.argv[2])
            print(f"Installed {metadata['name']}@{metadata.get('version', '0.0.0')}")
        except (OSError, PackageError) as error:
            print(f"Error: {error}")
            sys.exit(1)

    else:
        print(f"Error: Unknown command '{command}'")
        print("Run 'blz help' for available commands")


if __name__ == "__main__":
    main()
