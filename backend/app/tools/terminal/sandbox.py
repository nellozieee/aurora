"""A constrained sandbox for running model-generated Python code.

This is deliberately narrow: it runs *Python source code* (not arbitrary
shell commands) in its own subprocess with a hard timeout and no inherited
secrets. It is not a full OS-level sandbox (no seccomp/container isolation)
-- on a single-user desktop assistant, the accepted threat model is
"contains a buggy/naive script", not "survives an adversarial one" -- but it
does keep the process off a shell and away from obvious destructive patterns.

The working directory is the first configured allowed filesystem path (the
same directory create_file/write_file use), not an unrelated temp dir --
otherwise the Coding Agent could never "save a script, then run it": a file
written by create_file and a script run here need to actually share a
filesystem for that workflow to make sense.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

# Patterns that are never acceptable in code we are about to execute
# ourselves, regardless of what the sandbox process boundary would contain.
_DENYLIST_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\.",
    r"\bshutil\.rmtree\b",
    r"\b__import__\s*\(\s*['\"]os['\"]",
    r"\bopen\s*\([^)]*['\"]([A-Za-z]:\\\\|/etc/|/dev/)",
    r"\bctypes\b",
    r"\bsocket\b",
]


class UnsafeCodeError(Exception):
    pass


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def validate_code(code: str) -> None:
    for pattern in _DENYLIST_PATTERNS:
        if re.search(pattern, code):
            raise UnsafeCodeError(
                f"Code contains a disallowed pattern ({pattern}). "
                "The sandbox only runs plain computational Python -- no "
                "shell/process/network/raw-filesystem access."
            )


def _working_directory(settings: Settings) -> Path:
    allowed = settings.allowed_filesystem_paths
    if allowed:
        path = Path(allowed[0])
        path.mkdir(parents=True, exist_ok=True)
        return path
    # No allowed paths configured (file tools are disabled entirely) --
    # fall back to a throwaway temp directory so execution still works.
    fallback = Path(tempfile.gettempdir()) / "aurora_sandbox"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


async def run_python(code: str, settings: Settings) -> ExecutionResult:
    validate_code(code)

    run_dir = _working_directory(settings)
    script_path = run_dir / f".aurora_exec_{uuid.uuid4().hex}.py"
    script_path.write_text(code, encoding="utf-8")

    timeout = settings.security_sandbox_timeout_seconds
    timed_out = False

    try:
        process = await asyncio.create_subprocess_exec(
            "python",
            "-I",  # isolated mode: ignore user site-packages / env vars / user config
            str(script_path),
            cwd=str(run_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            timed_out = True
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()

        exit_code = process.returncode if process.returncode is not None else -1
    finally:
        script_path.unlink(missing_ok=True)

    return ExecutionResult(
        stdout=stdout_bytes.decode("utf-8", errors="replace")[:20_000],
        stderr=stderr_bytes.decode("utf-8", errors="replace")[:20_000],
        exit_code=exit_code,
        timed_out=timed_out,
    )
