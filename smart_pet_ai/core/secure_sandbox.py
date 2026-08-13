# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
    HAS_RESOURCE = True
except Exception:
    HAS_RESOURCE = False

BLOCKED_IMPORTS = {
    "socket", "requests", "urllib", "urllib3", "httpx",
    "ctypes", "pty", "telnetlib", "paramiko", "ftplib", "nntplib",
    "multiprocessing", "signal", "subprocess"
}

BLOCKED_CALLS = {
    ("os", "system"), ("os", "popen"), ("os", "spawnv"), ("os", "spawnve"),
    ("os", "execv"), ("os", "execve"), ("os", "execl"), ("os", "execlp"),
    ("os", "execle"), ("os", "execvp"), ("os", "execvpe"),
    ("shutil", "move")
}

# Cho phép eval/exec/compile để agent linh hoạt hơn.
# Nếu bạn muốn chặt hơn, thêm lại: "eval", "exec", "compile", "__import__".
BLOCKED_NAMES = set()

DELETE_CALLS = {
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("shutil", "rmtree")
}

GENERIC_DANGEROUS_RES = [
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bdoas\b", re.I),
    re.compile(r"\bpkexec\b", re.I),
    re.compile(r"\bsu\s", re.I),
    re.compile(r"\bdd\b", re.I),
    re.compile(r"\bmkfs", re.I),
    re.compile(r"\bfdisk\b", re.I),
    re.compile(r"\bparted\b", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\breboot\b", re.I),
    re.compile(r"\bhalt\b", re.I),
    re.compile(r"\bpoweroff\b", re.I),
    re.compile(r"\binit\s+[06]", re.I),
    re.compile(r"\bsystemctl\b", re.I),
    re.compile(r"\bservice\b", re.I),
    re.compile(r"\biptables\b", re.I),
    re.compile(r"\bufw\b", re.I),
    re.compile(r"\bnft\b", re.I),
    re.compile(r"\buseradd\b", re.I),
    re.compile(r"\buserdel\b", re.I),
    re.compile(r"\busermod\b", re.I),
    re.compile(r"\bpasswd\b", re.I),
    re.compile(r"\bchown\b", re.I),
    re.compile(r"\bchmod\s+(-[a-z]+\s+)*777\s+/", re.I),
    re.compile(r"\bcurl\b.*\|\s*(ba|z)?sh", re.I),
    re.compile(r"\bwget\b.*\|\s*(ba|z)?sh", re.I),
    re.compile(r"\bapt(-get)?\b", re.I),
    re.compile(r"\bdpkg\b", re.I),
    re.compile(r"\bsnap\b", re.I),
    re.compile(r"\bflatpak\b", re.I),
    re.compile(r"\bpip3?\s+install\b", re.I),
    re.compile(r"\bnpm\s+install\s+-g", re.I),
    re.compile(r"\byarn\s+global\b", re.I),
    re.compile(r"\bkillall\b", re.I),
    re.compile(r"\bpkill\b", re.I),
    re.compile(r"\bkill\s+1\b", re.I),
    re.compile(r"\bkill\s+-9\s+1\b", re.I)
]


class SecurityViolation(Exception):
    pass


def _is_safe_workspace_path(value, allowed_prefixes=('/workspace/',)):
    s = str(value or '').replace('\\', '/')
    if not s:
        return False

    if '..' in s.split('/'):
        return False

    if s.startswith('~') or s.startswith('$'):
        return False

    if os.path.isabs(s):
        for p in allowed_prefixes:
            base = str(p).replace('\\', '/').rstrip('/')
            if s == base or s.startswith(base + '/'):
                return True
        return False

    return True


def _is_dangerous_command_text(text):
    low = str(text or '').lower()
    if not low.strip():
        return False

    for rx in GENERIC_DANGEROUS_RES:
        if rx.search(low):
            return True

    tokens = [t.strip('\'"') for t in re.findall(r'[^\s;|&]+', low)]

    for i, t in enumerate(tokens):
        if t in {'rm', 'rmdir', 'unlink', 'shred'}:
            for target in tokens[i + 1:]:
                if target.startswith('-'):
                    continue

                if target in {'/', '~', '$home', '..', '.', './'}:
                    return True

                if target.startswith('~') or target.startswith('$'):
                    return True

                if '..' in target.split('/'):
                    return True

                if target.startswith('/'):
                    if target.startswith('/workspace/'):
                        continue
                    return True

    return False


def _call_target(node):
    f = node.func
    if isinstance(f, ast.Name):
        return ('', f.id)

    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return (f.value.id, f.attr)

    return ('', '')


def static_scan(source, allowed_prefixes=('/workspace/',)):
    findings = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"safe": False, "syntax_error": str(e), "findings": ["invalid_python"]}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if root in BLOCKED_IMPORTS:
                    findings.append(f"blocked import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or '').split('.')[0]
            if root in BLOCKED_IMPORTS:
                findings.append(f"blocked import: {node.module}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_NAMES:
                findings.append(f"blocked builtin: {node.func.id}")

            pair = _call_target(node)

            if pair in BLOCKED_CALLS:
                findings.append(f"blocked call: {pair[0]}.{pair[1]}")

            if pair in DELETE_CALLS:
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if not _is_safe_workspace_path(arg.value, allowed_prefixes):
                            findings.append(f"delete outside sandbox: {arg.value}")

            if pair in {('', 'open'), ('builtins', 'open')}:
                if node.args:
                    path_node = node.args[0]
                    mode = 'r'

                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        mode = node.args[1].value
                    else:
                        for kw in node.keywords:
                            if kw.arg == 'mode' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                mode = kw.value.value

                    if any(ch in mode.lower() for ch in ('w', 'a', 'x')):
                        if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
                            if not _is_safe_workspace_path(path_node.value, allowed_prefixes):
                                findings.append(f"write/open outside sandbox: {path_node.value}")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_dangerous_command_text(node.value):
                findings.append("dangerous command/system text in code")

    return {"safe": not findings, "syntax_error": None, "findings": findings}


class SecureSandbox:
    def __init__(self, root, workspace=None):
        self.project_root = Path(root).resolve()
        self.workspace = Path(workspace or self.project_root / 'data_memory' / 'sandbox_workspace').resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.artifacts_dir = self.workspace / 'artifacts'
        self.runs_dir = self.workspace / 'runs'
        self.reports_dir = self.workspace / 'reports'
        self.home_dir = self.workspace / '.home'

        for p in (self.artifacts_dir, self.runs_dir, self.reports_dir, self.home_dir):
            p.mkdir(parents=True, exist_ok=True)

        self.bwrap = shutil.which('bwrap')
        self.python = os.environ.get('PET_SANDBOX_PYTHON') or sys.executable or shutil.which('python3') or '/usr/bin/python3'
        self.timeout_seconds = int(os.environ.get('PET_SANDBOX_TIMEOUT', '25'))
        self.memory_mb = int(os.environ.get('PET_SANDBOX_MEMORY_MB', '512'))
        self.max_output = int(os.environ.get('PET_SANDBOX_MAX_OUTPUT', '12000'))
        self.allow_host_fallback = os.environ.get('PET_SANDBOX_HOST_FALLBACK', '1') not in ('0', 'false', 'no', 'off')

    @property
    def isolated(self):
        return bool(self.bwrap and os.path.exists(self.bwrap))

    def status(self):
        return {
            'workspace': str(self.workspace),
            'bubblewrap': self.bwrap or None,
            'isolated': self.isolated,
            'network': 'disabled' if self.isolated else 'host-fallback limited',
            'host_fallback': self.allow_host_fallback
        }

    def _bwrap_cmd(self, cmd):
        b = self.bwrap
        if not b:
            raise RuntimeError('bubblewrap is not installed; execution is fail-closed')

        args = [
            b,
            '--die-with-parent',
            '--new-session',
            '--unshare-all',
            '--clearenv'
        ]

        for p in ('/usr', '/bin', '/lib', '/lib64', '/etc'):
            if os.path.exists(p):
                args += ['--ro-bind', p, p]

        args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
        args += ['--bind', str(self.workspace), '/workspace']
        args += ['--chdir', '/workspace']
        args += ['--setenv', 'HOME', '/workspace/.home']
        args += ['--setenv', 'PATH', '/usr/bin:/bin']
        args += ['--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
        args += ['--'] + cmd
        return args

    def _make_preexec(self, memory_mb=512, cpu_seconds=25, file_mb=10):
        def limit():
            if not HAS_RESOURCE:
                return

            try:
                mem = int(memory_mb * 1024 * 1024)
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            except Exception:
                pass

            try:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            except Exception:
                pass

            try:
                fsize = int(file_mb * 1024 * 1024)
                resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
            except Exception:
                pass

        return limit

    def run_python(self, source, timeout=None, memory_mb=None, safe=True):
        allowed_prefixes = ('/workspace/', str(self.workspace))

        # Luôn quét dangerous, kể cả safe=False, để giữ chặn sudo/lệnh nguy hiểm.
        scan = static_scan(source, allowed_prefixes=allowed_prefixes)

        if not scan['safe']:
            return {
                'success': False,
                'output': '',
                'error': 'SECURITY_BLOCK: ' + '; '.join(scan['findings']),
                'security': scan
            }

        timeout = int(timeout or self.timeout_seconds)
        memory = int(memory_mb or self.memory_mb)

        run_id = time.strftime('%Y%m%d_%H%M%S')
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        script = run_dir / 'main.py'
        script.write_text(source, encoding='utf-8')

        if self.isolated:
            script_name = shlex.quote('/workspace/' + str(script.relative_to(self.workspace)))
            shell = f"ulimit -v {memory * 1024}; exec {shlex.quote(str(self.python))} -I -B {script_name}"
            cmd = self._bwrap_cmd(['/bin/sh', '-c', shell])

            try:
                cp = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )

                out = (cp.stdout or '')[:self.max_output]
                err = (cp.stderr or '')[:self.max_output]

                return {
                    'success': cp.returncode == 0,
                    'returncode': cp.returncode,
                    'output': out,
                    'error': err,
                    'security': scan,
                    'run_dir': str(run_dir)
                }

            except subprocess.TimeoutExpired as e:
                return {
                    'success': False,
                    'output': (e.stdout or '') if isinstance(e.stdout, str) else '',
                    'error': f'TIMEOUT after {timeout}s',
                    'security': scan,
                    'run_dir': str(run_dir)
                }

        if not self.allow_host_fallback:
            return {
                'success': False,
                'output': '',
                'error': 'SANDBOX_UNAVAILABLE: bubblewrap missing and host fallback disabled',
                'security': scan
            }

        cmd = [str(self.python), '-I', '-B', str(script)]
        env = {
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONDONTWRITEBYTECODE': '1',
            'HOME': str(self.home_dir)
        }

        preexec = None
        if os.name == 'posix':
            preexec = self._make_preexec(memory, timeout, 10)

        try:
            cp = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace),
                env=env,
                preexec_fn=preexec,
                check=False
            )

            out = (cp.stdout or '')[:self.max_output]
            err = (cp.stderr or '')[:self.max_output]

            return {
                'success': cp.returncode == 0,
                'returncode': cp.returncode,
                'output': out,
                'error': err,
                'security': scan,
                'run_dir': str(run_dir)
            }

        except subprocess.TimeoutExpired as e:
            return {
                'success': False,
                'output': (e.stdout or '') if isinstance(e.stdout, str) else '',
                'error': f'TIMEOUT after {timeout}s',
                'security': scan,
                'run_dir': str(run_dir)
            }

        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'security': scan,
                'run_dir': str(run_dir)
            }

    def write_text(self, relative, content):
        p = (self.workspace / relative).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation('path escapes sandbox workspace')

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return str(p)

    def read_text(self, relative):
        p = (self.workspace / relative).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation('path escapes sandbox workspace')

        return p.read_text(encoding='utf-8')
