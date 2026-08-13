#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PET_SANDBOX_AUTONOMOUS=1
export PET_SANDBOX_NO_NETWORK=1
export PET_OUTPUT_HIDE_THINK=1
export PET_SANDBOX_ROOT="$ROOT/data_memory/sandbox_workspace"
export PET_SANDBOX_POLICY="$ROOT/data_memory/sandbox_policy.json"
export PET_SANDBOX_TIMEOUT="${PET_SANDBOX_TIMEOUT:-25}"
export PET_SANDBOX_MEMORY_MB="${PET_SANDBOX_MEMORY_MB:-512}"

mkdir -p "$PET_SANDBOX_ROOT/drop_here" "$PET_SANDBOX_ROOT/artifacts" \
         "$PET_SANDBOX_ROOT/runs" "$PET_SANDBOX_ROOT/reports" \
         "$PET_SANDBOX_ROOT/scratch" "$PET_SANDBOX_ROOT/tools" "$PET_SANDBOX_ROOT/.home"
chmod 700 "$PET_SANDBOX_ROOT" "$PET_SANDBOX_ROOT/.home"

case "${1:-}" in
  status)
    python3 - <<'PY_STATUS' "$ROOT"
from pathlib import Path
import shutil,sys
r=Path(sys.argv[1]); s=r/'data_memory'/'sandbox_workspace'
print('PET_SANDBOX_AUTONOMOUS=1')
print('PET_OUTPUT_HIDE_THINK=1')
print('WORKSPACE=',s)
print('BWRAP=',shutil.which('bwrap') or 'MISSING — execution fail-closed')
print('DROP_HERE=',s/'drop_here')
print('ARTIFACTS=',s/'artifacts')
print('TOOLS=',s/'tools')
PY_STATUS
    ;;
  verify)
    cd "$ROOT"
    python3 -m py_compile main.py core/*.py
    PYTHONPATH="$ROOT" python3 - <<'PY_VERIFY'
from core.secure_sandbox import SecureSandbox
from core.sandbox_tools import syntax_check,static_security,compile_tree,smoke_run
from pathlib import Path
s=SecureSandbox(Path('.'))
print('SECURE_SANDBOX=',s.status())
print('SYNTAX=',syntax_check('print(1)'))
print('SECURITY=',static_security('import subprocess\nsubprocess.run(["id"])'))
print('COMPILE=',compile_tree())
PY_VERIFY
    ;;
  *)
    cd "$ROOT"
    exec python3 main.py "$@"
    ;;
esac
