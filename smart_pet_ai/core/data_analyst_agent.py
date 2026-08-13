# -*- coding: utf-8 -*-
import glob
import os


class DataAnalystAgent:
    """
    Advanced Data Analyst & Code Interpreter.

    Phát hiện file CSV/JSON/JSONL trong data_hot/,
    tự viết code pandas, chạy trong Sandbox, rồi trả lời.
    """

    KEYWORDS = [
        "phân tích", "thống kê", "analyze", "analysis",
        "csv", "json", "jsonl", "dữ liệu", "dataset",
        "xu hướng", "tổng kết", "vẽ", "báo cáo"
    ]

    def __init__(self, pet):
        self.pet = pet
        self.stats = {"runs": 0}

        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_hot = os.path.join(self.base_dir, "data_hot")

    def can_handle(self, query):
        low = str(query).lower()

        if not any(k in low for k in self.KEYWORDS):
            return False

        return self._find_file(query) is not None

    def _find_file(self, query):
        files = []

        patterns = ["*.csv", "*.json", "*.jsonl", "*.tsv"]

        for pat in patterns:
            files.extend(glob.glob(os.path.join(self.data_hot, pat)))
            files.extend(glob.glob(os.path.join(self.data_hot, "**", pat), recursive=True))

        if not files:
            return None

        low = str(query).lower()

        for f in files:
            if os.path.basename(f).lower() in low:
                return f

        try:
            return max(files, key=os.path.getmtime)
        except Exception:
            return files[0]

    def _build_code(self, path, ext):
        if ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","

            return f'''
import pandas as pd

path = {path!r}

try:
    df = pd.read_csv(path, sep={sep!r}, encoding="utf-8", errors="ignore")
except Exception as e:
    print("ERROR:", e)
    raise SystemExit(0)

print("SHAPE:", df.shape)
print("COLUMNS:", ", ".join(map(str, df.columns[:20])))

print("HEAD:")
print(df.head(3).to_string())

num = df.select_dtypes(include="number")
if not num.empty:
    print("NUMERIC_SUMMARY:")
    print(num.describe().to_string())

cat = df.select_dtypes(include="object")
if not cat.empty:
    print("CATEGORICAL_HEAD:")
    print(cat.head(2).to_string())
'''

        if ext in (".json", ".jsonl"):
            return f'''
import json
import pandas as pd

path = {path!r}
rows = []

try:
    with open(path, encoding="utf-8", errors="ignore") as f:
        first = f.read(1).strip()
        f.seek(0)

        if first == "[":
            data = json.load(f)
            if isinstance(data, list):
                rows = [r if isinstance(r, dict) else {{"value": r}} for r in data[:5000]]
        else:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    rows.append(obj if isinstance(obj, dict) else {{"value": obj}})
                except Exception:
                    pass

                if len(rows) >= 5000:
                    break

except Exception as e:
    print("ERROR:", e)
    raise SystemExit(0)

if not rows:
    print("NO_ROWS")
    raise SystemExit(0)

df = pd.DataFrame(rows)

print("SHAPE:", df.shape)
print("COLUMNS:", ", ".join(map(str, df.columns[:20])))

print("HEAD:")
print(df.head(3).to_string())

num = df.select_dtypes(include="number")
if not num.empty:
    print("NUMERIC_SUMMARY:")
    print(num.describe().to_string())
'''

        return f'''
print("Unsupported file type: {ext}")
'''

    def run(self, query):
        f = self._find_file(query)

        if not f:
            return None, "Tui không tìm thấy file dữ liệu nào trong data_hot/."

        ext = os.path.splitext(f)[1].lower()
        code = self._build_code(f, ext)

        result = self.pet.sandbox.run_python(code, timeout=30)
        self.stats["runs"] += 1

        if result.get("success"):
            out = str(result.get("output", "")).strip()

            answer = (
                f"Tui đã phân tích file {os.path.basename(f)}.\n"
                f"{out[:1800]}"
            )

            think = (
                "📊 Data Analyst Agent:\n"
                f"  • File: {os.path.basename(f)}\n"
                f"  • Sandbox: success\n"
                f"  • Output length: {len(out)}"
            )

            return think, answer

        err = str(result.get("error", "không rõ lỗi"))[:300]
        return None, f"Tui thử phân tích dữ liệu nhưng gặp lỗi: {err}"

    def stats_text(self):
        return f"📊 Data Analyst runs: {self.stats.get('runs', 0)}"
