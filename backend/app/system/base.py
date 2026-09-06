"""Platform adapter interface.

OS-specific behavior (how to launch a named application) is isolated behind
this interface; everything that IS cross-platform (process listing, system
info, terminating a process by name) is implemented once here via `psutil`
rather than duplicated per OS.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

import psutil
from pydantic import BaseModel

_BOOT_TIME = psutil.boot_time()


class ProcessInfo(BaseModel):
    pid: int
    name: str
    status: str


class SystemInfo(BaseModel):
    platform: str
    platform_version: str
    hostname: str
    cpu_count: int
    cpu_percent: float
    memory_total_mb: int
    memory_available_mb: int
    memory_percent: float
    disk_total_gb: float
    disk_free_gb: float
    uptime_seconds: float


class ActiveWindowInfo(BaseModel):
    title: str
    process_name: str | None = None
    pid: int | None = None


class AppLaunchError(Exception):
    pass


class ActiveWindowUnsupportedError(Exception):
    pass


class FocusWindowError(Exception):
    pass


class PlatformAdapter(ABC):
    platform_name: str
    application_registry: dict[str, str] = {}

    @abstractmethod
    def launch_application(self, name: str) -> int:
        """Launch a registered application by friendly name. Returns its PID."""

    def known_applications(self) -> list[str]:
        return sorted(self.application_registry)

    def get_active_window(self) -> ActiveWindowInfo:
        """Identify the foreground application. Platform-specific; adapters
        that can't support this raise ActiveWindowUnsupportedError rather
        than fabricating an answer."""
        raise ActiveWindowUnsupportedError(
            f"Active window detection is not implemented on {self.platform_name}"
        )

    def focus_window(self, title_substring: str) -> ActiveWindowInfo:
        """Bring the first window whose title contains `title_substring`
        (case-insensitive) to the foreground. Raises FocusWindowError if
        none matches or this isn't implemented on this platform."""
        raise FocusWindowError(f"Window focusing is not implemented on {self.platform_name}")

    def list_processes(self, limit: int = 200) -> list[ProcessInfo]:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                info = proc.info
                processes.append(ProcessInfo(pid=info["pid"], name=info["name"] or "", status=info["status"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(processes) >= limit:
                break
        return processes

    def close_application(self, name: str) -> int:
        """Terminate every running process whose name matches (case-insensitive). Returns count."""
        target = name.lower()
        closed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                proc_name = (proc.info["name"] or "").lower()
                if target in proc_name:
                    proc.terminate()
                    closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return closed

    def get_system_info(self) -> SystemInfo:
        import platform as platform_module

        virtual_memory = psutil.virtual_memory()
        # Path.cwd().anchor is "C:\\" on Windows, "/" on Unix -- always a
        # valid disk_usage() target, unlike a hardcoded "/".
        disk = psutil.disk_usage(Path.cwd().anchor or "/")

        return SystemInfo(
            platform=platform_module.system(),
            platform_version=platform_module.version(),
            hostname=platform_module.node(),
            cpu_count=psutil.cpu_count() or 0,
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_total_mb=round(virtual_memory.total / (1024 * 1024)),
            memory_available_mb=round(virtual_memory.available / (1024 * 1024)),
            memory_percent=virtual_memory.percent,
            disk_total_gb=round(disk.total / (1024**3), 1),
            disk_free_gb=round(disk.free / (1024**3), 1),
            uptime_seconds=round(time.time() - _BOOT_TIME, 1),
        )
