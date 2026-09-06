"""Native process management module for BlazeLang."""

import os
import shlex
import subprocess
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


class ProcessLibrary:
    def __init__(self):
        self._processes = {}

    def _parse_cmd_and_args(self, cmd, args=None):
        if isinstance(cmd, list):
            cmd_list = [str(x) for x in cmd]
            if args is not None:
                if isinstance(args, list):
                    cmd_list.extend([str(x) for x in args])
                else:
                    cmd_list.append(str(args))
            return cmd_list

        if args is not None:
            cmd_list = [str(cmd)]
            if isinstance(args, list):
                cmd_list.extend([str(x) for x in args])
            else:
                cmd_list.append(str(args))
            return cmd_list

        if isinstance(cmd, str):
            try:
                cmd_list = shlex.split(cmd, posix=(os.name != "nt"))
            except Exception:
                cmd_list = [cmd]
            return cmd_list if cmd_list else [str(cmd)]

        return [str(cmd)]

    def _get_popen(self, handle):
        if isinstance(handle, dict):
            if "_popen" in handle and isinstance(handle["_popen"], subprocess.Popen):
                return handle["_popen"]
            if "pid" in handle and handle["pid"] in self._processes:
                return self._processes[handle["pid"]]["_popen"]
        elif isinstance(handle, int) and handle in self._processes:
            return self._processes[handle]["_popen"]
        raise BlazeRuntimeError(f"Invalid process handle: {handle}")

    def start(self, cmd, args=None):
        cmd_list = self._parse_cmd_and_args(cmd, args)
        try:
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            raise BlazeRuntimeError(f"Process failed to start: command '{cmd_list[0]}' not found")
        except PermissionError:
            raise BlazeRuntimeError(f"Process failed to start: permission denied for '{cmd_list[0]}'")
        except Exception as e:
            raise BlazeRuntimeError(f"Process failed to start: {e}")

        handle = {
            "pid": proc.pid,
            "_popen": proc,
            "command": cmd_list,
        }
        self._processes[proc.pid] = handle
        return handle

    def run(self, cmd, args=None):
        cmd_list = self._parse_cmd_and_args(cmd, args)
        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        except FileNotFoundError:
            raise BlazeRuntimeError(f"Process failed to run: command '{cmd_list[0]}' not found")
        except PermissionError:
            raise BlazeRuntimeError(f"Process failed to run: permission denied for '{cmd_list[0]}'")
        except Exception as e:
            raise BlazeRuntimeError(f"Process failed to run: {e}")

    def pid(self, handle):
        if isinstance(handle, dict) and "pid" in handle:
            return handle["pid"]
        if isinstance(handle, int):
            return handle
        raise BlazeRuntimeError("Invalid process handle for Process.PID")

    def is_running(self, handle):
        popen = self._get_popen(handle)
        return popen.poll() is None

    def exit_code(self, handle):
        popen = self._get_popen(handle)
        return popen.poll()

    def wait(self, handle, timeout=None):
        popen = self._get_popen(handle)
        try:
            timeout_val = float(timeout) if timeout is not None else None
            popen.wait(timeout=timeout_val)
            return popen.returncode
        except subprocess.TimeoutExpired:
            raise BlazeRuntimeError("Process wait timed out")
        except Exception as e:
            raise BlazeRuntimeError(f"Process wait failed: {e}")

    def kill(self, handle):
        popen = self._get_popen(handle)
        try:
            if popen.poll() is None:
                popen.kill()
                popen.wait(timeout=2.0)
            return True
        except (OSError, subprocess.SubprocessError):
            return True


def create_process_module():
    library = ProcessLibrary()
    return {
        "Start": library.start,
        "Run": library.run,
        "Wait": library.wait,
        "Kill": library.kill,
        "IsRunning": library.is_running,
        "PID": library.pid,
        "ExitCode": library.exit_code,
    }
