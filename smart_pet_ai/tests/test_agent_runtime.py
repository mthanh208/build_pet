# -*- coding: utf-8 -*-
"""Regression tests for the unified agent execution path."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.sandbox import Sandbox
from core.secure_sandbox import SecureSandbox, static_scan


def test_legacy_sandbox_uses_secure_backend():
    sb = Sandbox(timeout=5)
    assert isinstance(sb._sandbox, SecureSandbox)
    result = sb.run_python("print(1 + 1)")
    assert result["success"]
    assert "2" in result["output"]


def test_security_scan_blocks_dangerous_import():
    result = static_scan("import subprocess\nsubprocess.run(['id'])")
    assert result["safe"] is False
    assert any("blocked import" in item for item in result["findings"])


def test_security_scan_blocks_host_delete():
    result = static_scan("import os\nos.remove('/etc/passwd')")
    assert result["safe"] is False
    assert any("delete outside sandbox" in item for item in result["findings"])


def test_secure_sandbox_blocks_dangerous_code_before_execution(tmp_path):
    sb = SecureSandbox(root=str(tmp_path), workspace=str(tmp_path / "workspace"))
    result = sb.run_python("import subprocess\nsubprocess.run(['echo', 'bad'])")
    assert result["success"] is False
    assert result["error"].startswith("SECURITY_BLOCK:")


def test_secure_sandbox_allows_workspace_write(tmp_path):
    workspace = tmp_path / "workspace"
    sb = SecureSandbox(root=str(tmp_path), workspace=str(workspace))
    result = sb.run_python("open('/workspace/test.txt', 'w').write('ok')")
    assert result["success"]
    assert (workspace / "test.txt").read_text(encoding="utf-8") == "ok"
