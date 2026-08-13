# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import time
import hashlib
import subprocess

try:
    import resource
    HAS_RESOURCE = True
except Exception:
    HAS_RESOURCE = False


class SmartSandbox:
    """
    Smart Sandbox cho Pet AI.

    Khả năng:
      - chạy Python code trong workspace riêng
      - scratchpad / note / draft
      - lưu artifact
      - log run
      - giới hạn tài nguyên
      - static safety check
      - phát hiện math/code block
    """

    ALLOWED_IMPORTS = {
        "math", "statistics", "json", "csv", "re", "datetime",
        "collections", "itertools", "functools", "decimal",
        "fractions", "random", "textwrap", "string", "unicodedata",
        "time", "pandas", "numpy"
    }

    DENY_PATTERNS = [
        r"__import__",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bcompile\s*\(",
        r"\bopen\s*\(",
        r"\bos\.system\b",
        r"\bsubprocess\b",
        r"\bshutil\b",
        r"\bsocket\b",
        r"\brequests\b",
        r"\burllib\b",
        r"\bhttp\b",
        r"\bftplib\b",
        r"\bsmtplib\b",
        r"\bctypes\b",
        r"\bimportlib\b",
        r"\bpickle\b",
        r"\bmarshal\b",
        r"\bglobals\s*\(",
        r"\blocals\s*\(",
        r"\bgetattr\s*\(",
        r"\bsetattr\s*\(",
        r"\bdelattr\s*\(",
        r"\bbreakpoint\b",
        r"\bexit\s*\(",
        r"\bquit\s*\(",
        r"\.\./",
        r"/etc/",
        r"/root/",
        r"/home/",
    ]

    IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)
    MATH_EXPR_RE = re.compile(r"([0-9\.,\s\+\-\*/\%\(\)\^]+)")

    def __init__(self, pet=None, workspace=None):
        self.pet = pet

        if workspace:
            self.workspace = workspace
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.workspace = os.path.join(base_dir, "data_memory", "sandbox_workspace")

        self.scratch_dir = os.path.join(self.workspace, "scratch")
        self.artifacts_dir = os.path.join(self.workspace, "artifacts")
        self.runs_dir = os.path.join(self.workspace, "runs")
        self.log_path = os.path.join(self.workspace, "sandbox_log.jsonl")

        os.makedirs(self.scratch_dir, exist_ok=True)
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)

        self.stats = {
            "runs": 0,
            "success": 0,
            "errors": 0,
            "blocked": 0,
            "notes": 0,
            "drafts": 0
        }

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    def _log(self, entry):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _safe_name(self, name):
        name = str(name)
        name = re.sub(r"[^\w\-. ]+", "", name).strip()
        name = name.replace(" ", "_")
        if not name:
            name = "note"
        return name[:80]

    def _make_preexec(self, memory_mb=256, cpu_seconds=15, file_mb=10):
        def _limit():
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

        return _limit

    # -----------------------------------------------------------------
    # Safety
    # -----------------------------------------------------------------

    def static_check(self, code):
        issues = []

        if not code or not code.strip():
            return ["Code trống."]

        for pattern in self.DENY_PATTERNS:
            if re.search(pattern, code, flags=re.IGNORECASE):
                issues.append(f"Pattern nguy hiểm: {pattern}")

        for match in self.IMPORT_RE.finditer(code):
            module = match.group(1).split(".")[0]
            if module not in self.ALLOWED_IMPORTS:
                issues.append(f"Import bị chặn: {module}")

        return list(dict.fromkeys(issues))

    # -----------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------

    def run_python(self, code, timeout=15, memory_mb=256, safe=True):
        self.stats["runs"] += 1
        run_id = hashlib.sha1(f"{time.time()}{code[:80]}".encode("utf-8", errors="ignore")).hexdigest()[:12]

        if safe:
            issues = self.static_check(code)
            if issues:
                self.stats["blocked"] += 1
                result = {
                    "success": False,
                    "error": "Bị chặn bởi safety check: " + "; ".join(issues[:5]),
                    "output": "",
                    "run_id": run_id
                }
                self._log({"time": time.time(), "type": "blocked", "issues": issues[:5]})
                return result

        script_path = os.path.join(self.runs_dir, f"run_{run_id}.py")

        preamble = (
            "import sys, os\n"
            f"os.chdir({self.workspace!r})\n"
            "try:\n"
            "    sys.stdout.reconfigure(encoding='utf-8', errors='ignore')\n"
            "except Exception:\n"
            "    pass\n"
        )

        full_code = preamble + "\n" + code

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(full_code)
        except Exception as e:
            return {
                "success": False,
                "error": f"Không ghi được script: {e}",
                "output": "",
                "run_id": run_id
            }

        env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1"
        }

        try:
            proc = subprocess.run(
                [sys.executable, "-B", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace,
                env=env,
                preexec_fn=self._make_preexec(memory_mb, timeout, 10)
            )

            output = proc.stdout[:6000]
            error = proc.stderr[:2000]

            result = {
                "success": proc.returncode == 0,
                "output": output,
                "error": error,
                "returncode": proc.returncode,
                "run_id": run_id
            }

            if result["success"]:
                self.stats["success"] += 1
            else:
                self.stats["errors"] += 1

            self._log({
                "time": time.time(),
                "type": "run",
                "run_id": run_id,
                "success": result["success"],
                "timeout": timeout,
                "memory_mb": memory_mb,
                "safe": safe
            })

            return result

        except subprocess.TimeoutExpired:
            self.stats["errors"] += 1
            self._log({"time": time.time(), "type": "timeout", "run_id": run_id})
            return {
                "success": False,
                "error": f"Timeout sau {timeout}s",
                "output": "",
                "run_id": run_id
            }
        except Exception as e:
            self.stats["errors"] += 1
            self._log({"time": time.time(), "type": "exception", "run_id": run_id, "error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "run_id": run_id
            }

    # -----------------------------------------------------------------
    # Scratchpad / Notes
    # -----------------------------------------------------------------

    def save_note(self, name, content):
        name = self._safe_name(name)
        path = os.path.join(self.scratch_dir, f"{name}.md")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(content))

            self.stats["notes"] += 1
            return f"📝 Đã lưu note: {path}"
        except Exception as e:
            return f"⚠️ Không lưu được note: {e}"

    def append_note(self, name, content):
        name = self._safe_name(name)
        path = os.path.join(self.scratch_dir, f"{name}.md")

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + str(content))

            return f"📝 Đã thêm vào note: {path}"
        except Exception as e:
            return f"⚠️ Không append được note: {e}"

    def read_note(self, name):
        name = self._safe_name(name)
        path = os.path.join(self.scratch_dir, f"{name}.md")

        if not os.path.exists(path):
            return f"⚠️ Không tìm thấy note: {name}"

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content[:4000]
        except Exception as e:
            return f"⚠️ Không đọc được note: {e}"

    def list_notes(self):
        try:
            files = sorted(os.listdir(self.scratch_dir))
        except Exception:
            files = []

        if not files:
            return "🗒️ Scratchpad đang trống."

        lines = ["🗒️ Scratchpad:"]
        for f in files[:50]:
            path = os.path.join(self.scratch_dir, f)
            try:
                size = os.path.getsize(path)
            except Exception:
                size = 0
            lines.append(f"  • {f} ({size} bytes)")

        return "\n".join(lines)

    def search_notes(self, query):
        query = str(query).lower()
        results = []

        try:
            files = os.listdir(self.scratch_dir)
        except Exception:
            files = []

        for fname in files:
            path = os.path.join(self.scratch_dir, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if query in content.lower():
                    snippet = content[:200].replace("\n", " ")
                    results.append(f"• {fname}: {snippet}...")
            except Exception:
                continue

        if not results:
            return f"🔍 Không tìm thấy note nào chứa: {query}"

        return "🔍 Notes khớp:\n" + "\n".join(results[:10])

    # -----------------------------------------------------------------
    # Drafting
    # -----------------------------------------------------------------

    def draft(self, task):
        ts = time.strftime("%Y%m%d_%H%M%S")
        name = f"draft_{ts}"

        content = None

        if self.pet is not None and getattr(self.pet, "neural_engine", None) and self.pet.neural_engine.available:
            try:
                prompt = (
                    "Bạn là Pet AI đang tự nháp kế hoạch. "
                    "Hãy viết một bản nháp ngắn gọn bằng Markdown gồm: Mục tiêu, Giả định, Các bước, Rủi ro.\n"
                    f"Nhiệm vụ: {task}\n"
                    "Bản nháp:"
                )

                content = self.pet.neural_engine.generate(
                    prompt,
                    max_tokens=160,
                    temperature=0.4
                )
            except Exception:
                content = None

        if not content:
            content = (
                f"# Draft\n\n"
                f"## Nhiệm vụ\n{task}\n\n"
                f"## Mục tiêu\n- Xác định đầu vào\n- Xác định đầu ra\n- Chọn công cụ phù hợp\n\n"
                f"## Các bước dự kiến\n1. Thu thập dữ liệu\n2. Xử lý\n3. Kiểm tra\n4. Tổng hợp\n\n"
                f"## Rủi ro\n- Thiếu dữ liệu\n- Lỗi code\n- Kết quả không đủ bằng chứng\n"
            )

        self.stats["drafts"] += 1
        save_msg = self.save_note(name, content)

        return f"{save_msg}\n\n{content[:2500]}"

    # -----------------------------------------------------------------
    # Math / Code block helpers
    # -----------------------------------------------------------------

    def extract_code_block(self, text):
        m = re.search(r"```(?:python|py)?\s*\n(.*?)```", str(text), flags=re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def extract_math_expression(self, text):
        m = self.MATH_EXPR_RE.search(str(text))
        if not m:
            return None

        expr = m.group(1).strip()
        expr = expr.replace("^", "**").replace(",", ".")
        expr = re.sub(r"\s+", "", expr)

        if not expr:
            return None

        if not re.search(r"\d", expr):
            return None

        if not re.fullmatch(r"[0-9\.\+\-\*/\%\(\)]+", expr):
            return None

        return expr

    def solve_math(self, expr):
        code = f'''
import math, statistics

expr = {expr!r}

try:
    result = eval(expr, {{'__builtins__': {{}}}}, {{'math': math, 'statistics': statistics}})
    print(result)
except Exception as e:
    print('ERROR:', e)
'''
        return self.run_python(code, timeout=8, memory_mb=96, safe=False)

    def smart_request(self, query):
        """
        Phát hiện và xử lý nhanh:
          - code block
          - math expression
        """

        code = self.extract_code_block(query)
        if code:
            return self.run_python(code, timeout=15, memory_mb=256, safe=True)

        expr = self.extract_math_expression(query)
        if expr:
            return self.solve_math(expr)

        return None

    # -----------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------

    def stats_text(self):
        return (
            "🧪 Smart Sandbox stats:\n"
            f"  • Workspace: {self.workspace}\n"
            f"  • Runs: {self.stats.get('runs', 0)}\n"
            f"  • Success: {self.stats.get('success', 0)}\n"
            f"  • Errors: {self.stats.get('errors', 0)}\n"
            f"  • Blocked: {self.stats.get('blocked', 0)}\n"
            f"  • Notes: {self.stats.get('notes', 0)}\n"
            f"  • Drafts: {self.stats.get('drafts', 0)}"
        )
