# -*- coding: utf-8 -*-
import subprocess, os, sys, tempfile

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

class Sandbox:
    def __init__(self, timeout=10, max_memory=64*1024*1024):
        self.timeout = timeout
        self.max_memory = max_memory
        self.available = True
        self.execution_count = 0

    def run_python(self, code, timeout=None):
        if not code or not code.strip():
            return {"success": False, "error": "Empty code", "output": ""}
        timeout = timeout or self.timeout
        self.execution_count += 1
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
            tmp_file.write(code)
            tmp_file.close()

            proc = subprocess.Popen(
                [sys.executable, tmp_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True
            )
            try:
                stdout, stderr = proc.communicate(input="", timeout=timeout)
                return {
                    "success": proc.returncode == 0,
                    "output": stdout[:5000],
                    "error": stderr[:2000] if stderr else "",
                    "returncode": proc.returncode
                }
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return {"success": False, "error": f"Timeout after {timeout}s", "output": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}
        finally:
            if tmp_file and os.path.exists(tmp_file.name):
                try: os.unlink(tmp_file.name)
                except: pass

    def stats(self):
        return {"available": self.available, "executions": self.execution_count, "timeout": self.timeout}
