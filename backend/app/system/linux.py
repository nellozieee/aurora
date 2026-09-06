"""Linux platform adapter."""
from __future__ import annotations

import subprocess

from app.system.base import AppLaunchError, PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    platform_name = "linux"

    application_registry = {
        "terminal": "x-terminal-emulator",
        "file_manager": "xdg-open .",
        "text_editor": "gedit",
        "calculator": "gnome-calculator",
        "vscode": "code",
        "chrome": "google-chrome",
        "firefox": "firefox",
    }

    def launch_application(self, name: str) -> int:
        command = self.application_registry.get(name.lower())
        if command is None:
            raise AppLaunchError(
                f"'{name}' is not in the application registry. Known: {self.known_applications()}"
            )
        try:
            process = subprocess.Popen(command.split())
        except OSError as exc:
            raise AppLaunchError(f"Failed to launch '{name}': {exc}") from exc
        return process.pid
