"""Sandboxed code execution tool, used by the Coding Agent."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.terminal.sandbox import UnsafeCodeError, run_python


class ExecutePythonArgs(BaseModel):
    code: str = Field(description="Python source code to run in the sandbox")


async def execute_python_code(args: ExecutePythonArgs) -> ToolResult:
    settings = get_settings()
    try:
        result = await run_python(args.code, settings)
    except UnsafeCodeError as exc:
        return ToolResult.fail("UNSAFE_CODE", str(exc))
    except Exception as exc:
        return ToolResult.fail("SANDBOX_ERROR", f"Sandbox execution failed: {exc}")

    if result.timed_out:
        return ToolResult.fail(
            "TIMEOUT",
            f"Code did not finish within {settings.security_sandbox_timeout_seconds}s and was terminated.",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    return ToolResult.ok(
        data={"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_code}
    )


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="execute_python_code",
            description=(
                "Run Python source code and return stdout/stderr/exit code. Runs in the same "
                "directory as read_file/write_file/create_file, so code can open files created "
                "there by relative path -- but write the full program as the `code` argument "
                "directly rather than trying to `import` a file you created; there is no "
                "package/module resolution here, just a plain script run. No shell, subprocess, "
                "network, or raw OS-path filesystem access is allowed."
            ),
            args_model=ExecutePythonArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            timeout_seconds=35.0,
            handler=execute_python_code,
        )
    )
