"""Unit tests for app.tools.terminal.sandbox.validate_code (the denylist gate).

Corresponds to spec section 71's "unsafe terminal commands" family at the
pure-function level (no subprocess actually spawned).
"""
from __future__ import annotations

import pytest

from app.tools.terminal.sandbox import UnsafeCodeError, validate_code


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('dir')",
        "import subprocess\nsubprocess.run(['dir'])",
        "import shutil\nshutil.rmtree('C:/')",
        "__import__('os').listdir('.')",
        "open('C:\\\\Windows\\\\System32\\\\config', 'r')",
        "open('/etc/passwd', 'r')",
        "import ctypes\nctypes.windll.kernel32",
        "import socket\nsocket.socket()",
    ],
)
def test_disallowed_patterns_are_rejected(code):
    with pytest.raises(UnsafeCodeError):
        validate_code(code)


@pytest.mark.parametrize(
    "code",
    [
        "print('hello world')",
        "x = sum(range(10))\nprint(x)",
        "import math\nprint(math.sqrt(16))",
        "data = [1, 2, 3]\nprint(sorted(data, reverse=True))",
    ],
)
def test_plain_computational_code_is_allowed(code):
    validate_code(code)  # must not raise
