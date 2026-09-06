"""Windows platform adapter."""
from __future__ import annotations

import subprocess

from app.system.base import ActiveWindowInfo, AppLaunchError, FocusWindowError, PlatformAdapter


class WindowsAdapter(PlatformAdapter):
    platform_name = "windows"

    # Friendly name -> real command. The LLM only ever supplies the friendly
    # name; it never controls the actual command string that gets executed.
    application_registry = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "file_explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "task_manager": "taskmgr.exe",
        "control_panel": "control.exe",
        "paint": "mspaint.exe",
        "vscode": "code",
        "chrome": "chrome",
        "edge": "msedge",
        "word": "winword",
        "excel": "excel",
    }

    def launch_application(self, name: str) -> int:
        command = self.application_registry.get(name.lower())
        if command is None:
            raise AppLaunchError(
                f"'{name}' is not in the application registry. Known: {self.known_applications()}"
            )
        try:
            # shell=True is required here to resolve PATH-based commands
            # (e.g. "code", "chrome") the same way the Windows "Run" dialog
            # would; `command` always comes from our own fixed registry above,
            # never from raw user/model input.
            process = subprocess.Popen(command, shell=True)
        except OSError as exc:
            raise AppLaunchError(f"Failed to launch '{name}': {exc}") from exc
        return process.pid

    def get_active_window(self) -> ActiveWindowInfo:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)

        pid: int | None = None
        process_name: str | None = None
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                process_name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass

        return ActiveWindowInfo(title=title, process_name=process_name, pid=pid)

    def focus_window(self, title_substring: str) -> ActiveWindowInfo:
        import psutil
        import win32con
        import win32gui
        import win32process

        target = title_substring.lower()
        matches: list[int] = []

        def _collect(hwnd: int, _: object) -> None:
            if win32gui.IsWindowVisible(hwnd) and target in win32gui.GetWindowText(hwnd).lower():
                matches.append(hwnd)

        win32gui.EnumWindows(_collect, None)
        if not matches:
            raise FocusWindowError(f"No visible window found with title containing '{title_substring}'")

        hwnd = matches[0]
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            raise FocusWindowError(f"Could not focus window: {exc}") from exc

        title = win32gui.GetWindowText(hwnd)
        pid: int | None = None
        process_name: str | None = None
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                process_name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass

        return ActiveWindowInfo(title=title, process_name=process_name, pid=pid)
