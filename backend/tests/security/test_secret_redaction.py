"""Security tests: secret leakage (spec section 70's security-test list).

Corresponds to spec section 71's test_secret_redaction(). Registers
throwaway tools whose handlers deliberately raise exceptions embedding
secrets, then runs them through the *real* ToolRouter (the same code path
every live tool call goes through) to prove redaction happens at that
shared boundary -- not just inside the pure redact() unit test.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.core.config import get_settings
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter


class _NoArgs(BaseModel):
    pass


async def _connection_string_leak_handler(_args: _NoArgs) -> ToolResult:
    raise RuntimeError(
        "connection failed: postgresql+asyncpg://aurora:aurora@localhost:5432/aurora is unreachable"
    )


async def _api_key_leak_handler(_args: _NoArgs) -> ToolResult:
    raise RuntimeError("upstream rejected key sk-fake-test-key-abc123")


def _router_with(name: str, handler) -> ToolRouter:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name=name,
            description="test",
            args_model=_NoArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            handler=handler,
        )
    )
    return ToolRouter(registry)


async def test_connection_string_password_is_redacted_through_the_real_router():
    """The URL-shape regex fires unconditionally -- it protects against any
    connection string leaking, not only the one this deployment happens to
    be configured with."""
    router = _router_with("leaky_connection_tool", _connection_string_leak_handler)
    result = await router.execute("leaky_connection_tool", {})

    assert result.success is False
    assert "aurora:aurora@" not in result.error.message
    assert "***REDACTED***" in result.error.message
    assert "localhost:5432/aurora" in result.error.message  # non-secret parts survive


async def test_configured_api_key_is_redacted_through_the_real_router(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key-abc123")
    get_settings.cache_clear()
    try:
        router = _router_with("leaky_key_tool", _api_key_leak_handler)
        result = await router.execute("leaky_key_tool", {})

        assert result.success is False
        assert "sk-fake-test-key-abc123" not in result.error.message
        assert "***REDACTED***" in result.error.message
    finally:
        get_settings.cache_clear()
