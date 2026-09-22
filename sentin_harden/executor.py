"""Running shell commands.

One interface for both platforms: PowerShell on Windows, bash on Linux. The rest
of the application does not know which shell a rule is written in.

Commands are written to a temporary script file rather than passed on the
command line. Rule commands are multi-line and contain quotes and backslashes;
passing them as arguments turns quoting into a source of silent corruption.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 90

# Prepended to every PowerShell script so output reaches us as UTF-8 rather than
# the console code page, which on a Polish Windows mangles accented characters.
_PS_PREAMBLE = (
    "$ErrorActionPreference = 'Continue'\n"
    "try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }\n"
)

_SH_PREAMBLE = "#!/bin/sh\n"


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

    @property
    def last_line(self) -> str:
        """Last non-empty output line.

        Rules report a single value, but a command may legitimately print
        progress before it. Taking the last line keeps both possible.
        """
        for line in reversed(self.stdout.splitlines()):
            if line.strip():
                return line.strip()
        return ""


class Executor:
    """Runs a command in the shell a rule was written for."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def run(self, shell: str, script: str) -> CommandResult:
        if shell == "powershell":
            return self._run_powershell(script)
        if shell == "bash":
            return self._run_bash(script)
        raise ValueError(f"Unsupported shell: {shell}")

    # -- internals ---------------------------------------------------------

    def _run_powershell(self, script: str) -> CommandResult:
        path = self._write_script(_PS_PREAMBLE + script, suffix=".ps1")
        try:
            return self._launch(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(path),
                ]
            )
        finally:
            path.unlink(missing_ok=True)

    def _run_bash(self, script: str) -> CommandResult:
        path = self._write_script(_SH_PREAMBLE + script, suffix=".sh")
        try:
            os.chmod(path, 0o700)
            return self._launch(["bash", str(path)])
        finally:
            path.unlink(missing_ok=True)

    def _write_script(self, content: str, suffix: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8", newline="\n"
        )
        with handle:
            handle.write(content)
        return Path(handle.name)

    def _launch(self, argv: list[str]) -> CommandResult:
        creation_flags = 0
        if os.name == "nt":
            # Keep the console window from flashing when the application is
            # frozen into a windowed executable.
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                timeout=self.timeout,
                creationflags=creation_flags,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(stdout="", stderr="timeout", exit_code=-1, timed_out=True)
        except FileNotFoundError as missing:
            return CommandResult(stdout="", stderr=str(missing), exit_code=-1)

        return CommandResult(
            stdout=completed.stdout.decode("utf-8", errors="replace"),
            stderr=completed.stderr.decode("utf-8", errors="replace"),
            exit_code=completed.returncode,
        )
