"""macOS platform adapter."""
from __future__ import annotations

import subprocess

from app.system.base import AppLaunchError, PlatformAdapter


class MacOSAdapter(PlatformAdapter):
    platform_name = "macos"

    application_registry = {
        "terminal": "Terminal",
        "finder": "Finder",
        "text_editor": "TextEdit",
        "calculator": "Calculator",
        "vscode": "Visual Studio Code",
        "chrome": "Google Chrome",
        "safari": "Safari",
    }

    def launch_application(self, name: str) -> int:
        app_name = self.application_registry.get(name.lower())
        if app_name is None:
            raise AppLaunchError(
                f"'{name}' is not in the application registry. Known: {self.known_applications()}"
            )
        try:
            process = subprocess.Popen(["open", "-a", app_name])
        except OSError as exc:
            raise AppLaunchError(f"Failed to launch '{name}': {exc}") from exc
        return process.pid
