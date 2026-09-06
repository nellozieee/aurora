"""File tools: search, read, create, write, rename, move, copy, delete.

Every handler resolves its path(s) through `resolve_safe_path` first, so
access outside the configured allowed directories is refused before any I/O
happens. Delete requires an explicit `confirm=True` argument, enforced
centrally by `app.security.permissions` (see `ToolRouter.execute`).
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.security import prompt_injection
from app.security.validators import PathSecurityError, resolve_safe_path
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.files.extraction import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFileTypeError,
    extract_text,
    io_text_size,
    validate_json,
)
from app.tools.registry import ToolRegistry


def _safe(path: str) -> Path:
    return resolve_safe_path(path, get_settings())


class SearchFilesArgs(BaseModel):
    root: str = Field(default="", description="Directory to search (relative to an allowed root)")
    pattern: str = Field(default="*", description="Glob pattern, e.g. '*.txt' or '**/*.py'")
    max_results: int = Field(default=50, ge=1, le=500)


async def search_files(args: SearchFilesArgs) -> ToolResult:
    try:
        root = _safe(args.root or ".")
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not root.exists():
        return ToolResult.fail("NOT_FOUND", f"Directory does not exist: {root}")
    if not root.is_dir():
        return ToolResult.fail("NOT_A_DIRECTORY", f"Not a directory: {root}")

    def _search() -> list[str]:
        return [str(p) for p in root.glob(args.pattern) if p.is_file()][: args.max_results]

    matches = await asyncio.to_thread(_search)
    return ToolResult.ok(data={"matches": matches, "count": len(matches)})


class ReadFileArgs(BaseModel):
    path: str


async def read_file(args: ReadFileArgs) -> ToolResult:
    try:
        path = _safe(args.path)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not path.exists():
        return ToolResult.fail("NOT_FOUND", f"File does not exist: {args.path}")
    if not path.is_file():
        return ToolResult.fail("NOT_A_FILE", f"Not a file: {args.path}")

    settings = get_settings()
    if path.stat().st_size > settings.security_max_file_read_bytes * 4:
        # Cheap pre-check on raw bytes before spending time decoding/parsing.
        return ToolResult.fail(
            "FILE_TOO_LARGE",
            f"File is larger than the read limit ({settings.security_max_file_read_bytes} bytes "
            "of extracted text); read a smaller file or a specific section.",
        )

    try:
        text = await asyncio.to_thread(extract_text, path)
    except UnsupportedFileTypeError as exc:
        return ToolResult.fail("UNSUPPORTED_TYPE", str(exc))
    except Exception as exc:
        return ToolResult.fail("EXTRACTION_FAILED", f"Could not read file: {exc}")

    truncated = False
    size = io_text_size(text)
    if size > settings.security_max_file_read_bytes:
        text = text.encode("utf-8")[: settings.security_max_file_read_bytes].decode(
            "utf-8", errors="ignore"
        )
        truncated = True

    matches = prompt_injection.scan(text)
    if matches:
        text = prompt_injection.annotate(text, matches)

    return ToolResult.ok(
        data={"path": str(path), "content": text},
        truncated=truncated,
        size_bytes=size,
        prompt_injection_suspected=bool(matches),
    )


class CreateFileArgs(BaseModel):
    path: str
    content: str = ""
    overwrite: bool = False


async def create_file(args: CreateFileArgs) -> ToolResult:
    try:
        path = _safe(args.path)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if path.exists() and not args.overwrite:
        return ToolResult.fail(
            "ALREADY_EXISTS", f"File already exists: {args.path} (pass overwrite=true to replace)"
        )

    settings = get_settings()
    content_size = io_text_size(args.content)
    if content_size > settings.security_max_file_write_bytes:
        return ToolResult.fail(
            "CONTENT_TOO_LARGE",
            f"Content is {content_size} bytes, exceeding the {settings.security_max_file_write_bytes}-byte limit",
        )

    if path.suffix.lower() == ".json":
        try:
            validate_json(args.content)
        except ValueError as exc:
            return ToolResult.fail("INVALID_JSON", f"Content is not valid JSON: {exc}")

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.content, encoding="utf-8")

    await asyncio.to_thread(_write)
    return ToolResult.ok(data={"path": str(path)})


class WriteFileArgs(BaseModel):
    path: str
    content: str
    append: bool = False


async def write_file(args: WriteFileArgs) -> ToolResult:
    try:
        path = _safe(args.path)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not path.exists():
        return ToolResult.fail("NOT_FOUND", f"File does not exist: {args.path} (use create_file first)")
    if not path.is_file():
        return ToolResult.fail("NOT_A_FILE", f"Not a file: {args.path}")

    settings = get_settings()
    content_size = io_text_size(args.content)
    if content_size > settings.security_max_file_write_bytes:
        return ToolResult.fail(
            "CONTENT_TOO_LARGE",
            f"Content is {content_size} bytes, exceeding the {settings.security_max_file_write_bytes}-byte limit",
        )

    def _write() -> None:
        mode = "a" if args.append else "w"
        with path.open(mode, encoding="utf-8") as f:
            f.write(args.content)

    await asyncio.to_thread(_write)
    return ToolResult.ok(data={"path": str(path), "appended": args.append})


class RenameFileArgs(BaseModel):
    path: str
    new_name: str


async def rename_file(args: RenameFileArgs) -> ToolResult:
    try:
        path = _safe(args.path)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not path.exists():
        return ToolResult.fail("NOT_FOUND", f"File does not exist: {args.path}")

    if "/" in args.new_name or "\\" in args.new_name:
        return ToolResult.fail("INVALID_NAME", "new_name must be a filename, not a path")

    destination = path.with_name(args.new_name)
    try:
        _safe(str(destination))
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if destination.exists():
        return ToolResult.fail("ALREADY_EXISTS", f"Target already exists: {destination.name}")

    await asyncio.to_thread(path.rename, destination)
    return ToolResult.ok(data={"path": str(destination)})


class MoveFileArgs(BaseModel):
    source: str
    destination: str


async def move_file(args: MoveFileArgs) -> ToolResult:
    try:
        source = _safe(args.source)
        destination = _safe(args.destination)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not source.exists():
        return ToolResult.fail("NOT_FOUND", f"Source does not exist: {args.source}")
    if destination.exists():
        return ToolResult.fail("ALREADY_EXISTS", f"Destination already exists: {args.destination}")

    def _move() -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    await asyncio.to_thread(_move)
    return ToolResult.ok(data={"path": str(destination)})


class CopyFileArgs(BaseModel):
    source: str
    destination: str


async def copy_file(args: CopyFileArgs) -> ToolResult:
    try:
        source = _safe(args.source)
        destination = _safe(args.destination)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not source.exists() or not source.is_file():
        return ToolResult.fail("NOT_FOUND", f"Source file does not exist: {args.source}")
    if destination.exists():
        return ToolResult.fail("ALREADY_EXISTS", f"Destination already exists: {args.destination}")

    def _copy() -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination))

    await asyncio.to_thread(_copy)
    return ToolResult.ok(data={"path": str(destination)})


class DeleteFileArgs(BaseModel):
    path: str
    confirm: bool = False


async def delete_file(args: DeleteFileArgs) -> ToolResult:
    try:
        path = _safe(args.path)
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    if not path.exists():
        return ToolResult.fail("NOT_FOUND", f"File does not exist: {args.path}")

    # confirm=true is enforced centrally by app.security.permissions.enforce()
    # (called from ToolRouter, before this handler ever runs) -- not here.
    await asyncio.to_thread(path.unlink)
    return ToolResult.ok(data={"path": str(path), "deleted": True})


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="search_files",
            description="Search for files by glob pattern within an allowed directory.",
            args_model=SearchFilesArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            handler=search_files,
        )
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description=(
                "Read and extract text from a file "
                f"(supported: {sorted(SUPPORTED_EXTENSIONS)})."
            ),
            args_model=ReadFileArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            timeout_seconds=30.0,
            handler=read_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="create_file",
            description="Create a new file with the given content.",
            args_model=CreateFileArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=create_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description="Overwrite or append to an existing file's content.",
            args_model=WriteFileArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=write_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="rename_file",
            description="Rename a file in place.",
            args_model=RenameFileArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=rename_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="move_file",
            description="Move a file to a new location.",
            args_model=MoveFileArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=move_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="copy_file",
            description="Copy a file to a new location.",
            args_model=CopyFileArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            handler=copy_file,
        )
    )
    registry.register(
        ToolDefinition(
            name="delete_file",
            description="Permanently delete a file. Requires confirm=true.",
            args_model=DeleteFileArgs,
            risk_level=RiskLevel.HIGH,
            permission_level=PermissionLevel.CONFIRM,
            handler=delete_file,
        )
    )
