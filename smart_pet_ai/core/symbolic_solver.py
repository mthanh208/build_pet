# -*- coding: utf-8 -*-
import re

try:
    from sympy import symbols, solve, sympify, Eq, simplify, expand, factor, Symbol
    from sympy.logic.boolalg import And, Or, Not, Implies, to_cnf, satisfiable
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

_EQ_PATTERN = re.compile(r'(.+?)\s*(?:=|==|bằng|equals)\s*(.+?)(?:$|;|,|\n)', re.MULTILINE)
_VAR_PATTERN = re.compile(r'([a-zA-Z_]\w*)')
_MATH_KEYWORDS = ["giải", "solve", "tính", "compute", "nghiệm", "root", "phương trình", "equation", "đạo hàm", "derivative", "tích phân", "integral", "rút gọn", "simplify"]

class SymbolicSolver:
    def __init__(self):
        self.available = HAS_SYMPY
        self.solved_count = 0
        self._var_cache = {}

    def can_handle(self, text):
        low = text.lower()
        if any(kw in low for kw in _MATH_KEYWORDS): return True
        if _EQ_PATTERN.search(text): return True
        if re.search(r'[a-z]\s*[\+\-\*/\^]\s*[a-z0-9]', text, re.IGNORECASE): return True
        return False

    def _extract_vars(self, expr_str):
        found = _VAR_PATTERN.findall(expr_str)
        result = {}
        for name in found:
            if name not in ("Eq", "solve", "simplify", "expand", "factor", "sin", "cos", "tan", "log", "exp", "sqrt", "pi", "E"):
                if name not in result:
                    result[name] = Symbol(name)
        return result

    def solve_equation(self, text):
        if not HAS_SYMPY: return None
        match = _EQ_PATTERN.search(text)
        if not match:
            clean = text.replace("giải", "").replace("solve", "").replace("tính", "").strip()
            if "=" in clean:
                parts = clean.split("=", 1)
                lhs_str = parts[0].strip()
                rhs_str = parts[1].strip()
            else: return None
        else:
            lhs_str = match.group(1).strip()
            rhs_str = match.group(2).strip()
        try:
            lhs = sympify(lhs_str)
            rhs = sympify(rhs_str)
            eq = Eq(lhs, rhs)
            vars_in_eq = list(self._extract_vars(lhs_str + " " + rhs_str).values())
            if not vars_in_eq: return None
            solutions = solve(eq, vars_in_eq)
            self.solved_count += 1
            if isinstance(solutions, list):
                return {"type": "equation", "equation": f"{lhs} = {rhs}", "solutions": [str(s) for s in solutions], "variables": [str(v) for v in vars_in_eq]}
            elif isinstance(solutions, dict):
                return {"type": "equation", "equation": f"{lhs} = {rhs}", "solutions": {str(k): str(v) for k, v in solutions.items()}, "variables": [str(v) for v in vars_in_eq]}
            else:
                return {"type": "equation", "equation": f"{lhs} = {rhs}", "solutions": [str(solutions)], "variables": [str(v) for v in vars_in_eq]}
        except: return None

    def simplify_expression(self, expr_str):
        if not HAS_SYMPY: return None
        try:
            expr = sympify(expr_str)
            simplified = simplify(expr)
            expanded = expand(expr)
            factored = factor(expr)
            self.solved_count += 1
            return {"type": "simplify", "original": str(expr), "simplified": str(simplified), "expanded": str(expanded), "factored": str(factored)}
        except: return None

    def process(self, text):
        if not self.available: return None
        if not self.can_handle(text): return None
        result = self.solve_equation(text)
        if result: return result
        clean = text.replace("rút gọn", "").replace("simplify", "").strip()
        result = self.simplify_expression(clean)
        if result: return result
        return None

    def stats(self):
        return {"available": self.available, "solved_count": self.solved_count}
