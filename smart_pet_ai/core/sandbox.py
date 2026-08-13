# -*- coding: utf-8 -*-
"""Backward-compatible sandbox facade.

All Python execution is delegated to SecureSandbox so the project has one
execution backend and one security policy.  Legacy callers keep the old
Sandbox API.
"""
from __future__ import annotations

import os
from pathlib import Path

from .secure_sandbox import SecureSandbox


class Sandbox:
    """Compatibility wrapper around SecureSandbox."""

    def __init__(self, timeout=10, max_memory=64 * 1024 * 1024):
        root = Path(__file__).resolve().parents[1]
        workspace = root / "data_memory" / "sandbox_workspace"
        memory_mb = max(64, int(max_memory / (1024 * 1024)))
        self.timeout = int(timeout)
        self.max_memory = int(max_memory)
        self.available = True
        self.execution_count = 0
        self._sandbox = SecureSandbox(root=str(root), workspace=str(workspace))
        self._sandbox.timeout_seconds = self.timeout
        self._sandbox.memory_mb = memory_mb

    def run_python(self, code, timeout=None):
        if not code or not code.strip():
            return {"success": False, "error": "Empty code", "output": ""}

        self.execution_count += 1
        result = self._sandbox.run_python(
            code,
            timeout=int(timeout or self.timeout),
            memory_mb=max(64, int(self.max_memory / (1024 * 1024))),
            safe=True,
        )
        return result

    def stats(self):
        status = self._sandbox.status()
        return {
            "available": self.available,
            "executions": self.execution_count,
            "timeout": self.timeout,
            "isolated": status["isolated"],
            "host_fallback": status["host_fallback"],
        }
