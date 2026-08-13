# -*- coding: utf-8 -*-
"""PET autonomous toolbox. This module is documentation + lightweight checks.
Actual code execution is performed by core.secure_sandbox outside this file."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parent

def check_syntax(code):
    try:
        ast.parse(code)
        return {'valid':True,'error':None}
    except SyntaxError as e:
        return {'valid':False,'error':str(e)}

def list_workspace():
    return [str(p.relative_to(ROOT)) for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]

def inspect_file(relative):
    p=(ROOT/relative).resolve()
    if ROOT not in p.parents:
        raise ValueError('outside sandbox')
    return p.read_text(encoding='utf-8')
