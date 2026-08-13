# -*- coding: utf-8 -*-
import re, json, os
from collections import defaultdict, Counter

_SCHEMA_PATTERNS = [
    (re.compile(r"(\w+(?:\s+\w+){0,3})\s+là\s+(?:một\s+)?(?:loại\s+|dạng\s+)?(\w+(?:\s+\w+){0,3})"), "is_a"),
    (re.compile(r"(\w+(?:\s+\w+){0,3})\s+(?:gồm|có|bao gồm|chứa)\s+(\w+(?:\s+\w+){0,3})"), "has_part"),
    (re.compile(r"(\w+(?:\s+\w+){0,3})\s+(?:cần|đòi hỏi|yêu cầu)\s+(\w+(?:\s+\w+){0,3})"), "requires"),
    (re.compile(r"(\w+(?:\s+\w+){0,3})\s+(?:tạo ra|sản sinh|sinh ra)\s+(\w+(?:\s+\w+){0,3})"), "produces"),
    (re.compile(r"(\w+(?:\s+\w+){0,3})\s+(?:giúp|hỗ trợ|làm cho)\s+(\w+(?:\s+\w+){0,3})"), "helps"),
]

class AbstractionEngine:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.schemas = []
        self.patterns = defaultdict(Counter)
        self.abstractions = {}
        if save_path and os.path.exists(save_path): self.load()

    def digest_text(self, text, source="unknown"):
        found = []
        for pattern, schema_type in _SCHEMA_PATTERNS:
            for m in pattern.finditer(text):
                a, b = m.group(1).strip(), m.group(2).strip()
                if a and b and a != b and len(a) > 2 and len(b) > 2:
                    found.append((schema_type, a, b))
                    self.patterns[schema_type][(a, b)] += 1
        for st, a, b in found:
            existing = [s for s in self.schemas if s["type"] == st and s["a"] == a and s["b"] == b]
            if existing:
                existing[0]["count"] += 1
                existing[0]["sources"].append(source)
                if len(existing[0]["sources"]) > 10: existing[0]["sources"] = existing[0]["sources"][-5:]
            else:
                self.schemas.append({"type": st, "a": a, "b": b, "count": 1, "sources": [source]})
        return found

    def generalize(self, concept, graph_engine):
        parents = [s["b"] for s in self.schemas if s["type"] == "is_a" and s["a"] == concept]
        if parents: return parents[0]
        if concept in graph_engine.graph:
            neighbors = sorted(graph_engine.graph.neighbors(concept), key=lambda n: graph_engine.graph.nodes[n].get("count", 0), reverse=True)
            if neighbors: return neighbors[0]
        return None

    def specialize(self, concept):
        return [s["a"] for s in self.schemas if s["type"] == "is_a" and s["b"] == concept]

    def find_patterns(self, min_count=2):
        strong = []
        for schema_type, counter in self.patterns.items():
            for (a, b), count in counter.items():
                if count >= min_count:
                    strong.append({"type": schema_type, "a": a, "b": b, "count": count})
        strong.sort(key=lambda x: x["count"], reverse=True)
        return strong

    def get_schema_summary(self, concept):
        related = [s for s in self.schemas if s["a"] == concept or s["b"] == concept]
        related.sort(key=lambda x: x["count"], reverse=True)
        return related[:10]

    def save(self):
        if self.save_path:
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"schemas": self.schemas}, f, ensure_ascii=False)
            except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.schemas = data.get("schemas", [])
            for s in self.schemas:
                self.patterns[s["type"]][(s["a"], s["b"])] = s.get("count", 1)
        except: pass
