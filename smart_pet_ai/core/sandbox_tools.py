# -*- coding: utf-8 -*-
from __future__ import annotations
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path
from core.secure_sandbox import static_scan


def _root(root=None):
    return Path(root or Path(__file__).resolve().parents[1]/'data_memory'/'sandbox_workspace').resolve()


def syntax_check(path_or_source, root=None):
    p=_root(root)
    candidate=p/path_or_source
    source=candidate.read_text(encoding='utf-8') if candidate.exists() else str(path_or_source)
    try:
        ast.parse(source)
        return {'tool':'syntax_check','passed':True,'error':None}
    except SyntaxError as e:
        return {'tool':'syntax_check','passed':False,'error':str(e)}


def compile_tree(root=None):
    p=_root(root)
    errors=[]
    for f in sorted(p.rglob('*.py')):
        try: ast.parse(f.read_text(encoding='utf-8'))
        except Exception as e: errors.append({'file':str(f.relative_to(p)),'error':str(e)})
    return {'tool':'compile_tree','passed':not errors,'files_checked':len(list(p.rglob('*.py'))),'errors':errors}


def static_security(path_or_source, root=None):
    p=_root(root)
    candidate=p/path_or_source
    source=candidate.read_text(encoding='utf-8') if candidate.exists() else str(path_or_source)
    r=static_scan(source)
    return {'tool':'static_security','passed':r['safe'],'findings':r['findings']}


def unittest(root=None):
    p=_root(root)
    tests=p/'tests'
    if not tests.exists(): return {'tool':'unittest','passed':False,'error':'no tests directory'}
    cp=subprocess.run([sys.executable,'-I','-m','unittest','discover','-s',str(tests)],cwd=str(p),capture_output=True,text=True,timeout=30)
    return {'tool':'unittest','passed':cp.returncode==0,'returncode':cp.returncode,'stdout':cp.stdout[-6000:],'stderr':cp.stderr[-6000:]}


def pytest_check(root=None):
    p=_root(root)
    pytest=shutil.which('pytest')
    if not pytest: return {'tool':'pytest','passed':None,'available':False,'error':'pytest not installed; tool skipped'}
    cp=subprocess.run([pytest,'-q'],cwd=str(p),capture_output=True,text=True,timeout=30)
    return {'tool':'pytest','passed':cp.returncode==0,'returncode':cp.returncode,'stdout':cp.stdout[-6000:],'stderr':cp.stderr[-6000:]}


def smoke_run(path, root=None):
    p=_root(root)
    target=(p/path).resolve()
    if p not in target.parents or target.suffix != '.py':
        return {'tool':'smoke_run','passed':False,'error':'target must be a .py file inside sandbox'}
    source=target.read_text(encoding='utf-8')
    security=static_scan(source)
    if not security['safe']:
        return {'tool':'smoke_run','passed':False,'error':'security policy blocked execution','findings':security['findings']}
    # Deliberately do not execute on host here. The secure agent path should call SecureSandbox.run_python.
    return {'tool':'smoke_run','passed':None,'error':'Use SecureSandbox.run_python for actual isolated execution'}

TOOL_DESCRIPTIONS = {
    'syntax_check':'Parse one Python file/source with AST before execution.',
    'compile_tree':'Parse every Python file under sandbox_workspace.',
    'static_security':'Reject high-risk imports/calls/system paths.',
    'unittest':'Run unittest discovery inside the isolated sandbox workflow.',
    'pytest':'Run pytest when installed; otherwise report unavailable.',
    'smoke_run':'Validate a Python target and hand execution to SecureSandbox.',
}
