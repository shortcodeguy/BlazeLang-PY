"""Process and terminal helpers for BlazeLang."""

import os
import platform
import sys
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


class SystemLibrary:
    def platform(self): return platform.system()
    def version(self): return "1.6"
    def exit(self, code=0):
        try: raise SystemExit(int(code))
        except (TypeError, ValueError): raise BlazeRuntimeError("System.Exit code must be an integer")
    def current_directory(self): return os.getcwd()
    def set_current_directory(self, path):
        try: os.chdir(str(path)); return os.getcwd()
        except OSError as error: raise BlazeRuntimeError(f"Unable to set current directory: {error}")
    def arguments(self): return list(sys.argv[1:])
    def clear(self): print("\033[2J\033[H", end="", flush=True)
    def beep(self): print("\a", end="", flush=True)


def create_system_module():
    library = SystemLibrary()
    return {"Platform": library.platform, "Version": library.version, "Exit": library.exit,
            "CurrentDirectory": library.current_directory, "SetCurrentDirectory": library.set_current_directory,
            "Arguments": library.arguments, "Clear": library.clear, "Beep": library.beep}
