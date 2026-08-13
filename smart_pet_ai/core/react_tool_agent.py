# -*- coding: utf-8 -*-
import re


class ReactToolAgent:
    """
    ReAct Tool Agent.

    Phát hiện các tác vụ có thể giải bằng tool:
      - toán học
      - hỏi giờ/ngày
    Sau đó chạy trong Sandbox.
    """

    MATH_KEYWORDS = [
        "tính", "compute", "calculator", "bằng bao nhiêu",
        "bao nhiêu", "nhân", "chia", "cộng", "trừ"
    ]

    TIME_KEYWORDS = [
        "mấy giờ", "giờ nào", "hôm nay là ngày", "ngày mấy", "bây giờ là"
    ]

    def __init__(self, pet):
        self.pet = pet
        self.use_count = 0

    def _safe_math_expression(self, text):
        # Lấy biểu thức toán đơn giản
        m = re.search(r"([0-9\.,\s\+\-\*/\%\(\)\^]+)", text)
        if not m:
            return None

        expr = m.group(1).strip()
        expr = expr.replace("^", "**")
        expr = expr.replace(",", ".")
        expr = re.sub(r"\s+", "", expr)

        if not expr:
            return None

        if not re.fullmatch(r"[0-9\.\+\-\*/\%\(\)]+", expr):
            return None

        if not re.search(r"\d", expr):
            return None

        return expr

    def try_solve(self, query):
        low = str(query).lower()
        self.use_count += 1

        # Hỏi giờ/ngày
        if any(k in low for k in self.TIME_KEYWORDS):
            code = "import datetime; print(datetime.datetime.now().strftime('%H:%M ngày %d/%m/%Y'))"
            result = self.pet.sandbox.run_python(code, timeout=5)
            if result.get("success"):
                output = result.get("output", "").strip()
                return {
                    "success": True,
                    "tool": "datetime",
                    "answer": f"Bây giờ là {output}.",
                    "confidence": 0.95
                }

        # Toán học
        if any(k in low for k in self.MATH_KEYWORDS) or re.search(r"\d\s*[\+\-\*/\^]\s*\d", query):
            expr = self._safe_math_expression(query)
            if expr:
                code = (
                    "expr = " + repr(expr) + "\n"
                    "try:\n"
                    "    result = eval(expr, {'__builtins__': {}}, {})\n"
                    "    print(result)\n"
                    "except Exception as e:\n"
                    "    print('ERROR:', e)\n"
                )

                result = self.pet.sandbox.run_python(code, timeout=6)
                if result.get("success"):
                    output = result.get("output", "").strip()
                    if output and "ERROR:" not in output:
                        return {
                            "success": True,
                            "tool": "math_eval",
                            "answer": f"Tui tính thử: {expr} = {output}.",
                            "confidence": 0.95
                        }

        return {
            "success": False,
            "tool": None,
            "answer": "",
            "confidence": 0.0
        }

    def stats(self):
        return {"use_count": self.use_count}
