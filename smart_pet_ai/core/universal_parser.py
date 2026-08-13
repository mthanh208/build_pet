# -*- coding: utf-8 -*-
import json, re, os, hashlib
from typing import Any, Dict, List, Optional, Tuple

THINK_PATTERNS = [
    re.compile(r'<think(?:ing)?>(.*?)</think(?:ing)?>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<reasoning>(.*?)</reasoning>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<thought>(.*?)</thought>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<analysis>(.*?)</analysis>', re.DOTALL | re.IGNORECASE),
    re.compile(r'\[think\](.*?)\[/think\]', re.DOTALL | re.IGNORECASE),
]

TEXT_FIELD_NAMES = {
    "text","content","noi_dung","body","message","messages","msg",
    "prompt","response","answer","output","completion","instruction",
    "input","question","query","reply","utterance","sentence",
    "paragraph","passage","document","doc","article","description",
    "summary","abstract","explanation","human","assistant","system",
    "user","ai","bot","model","turn","dialog","dialogue","conversation",
    "chat","value","data","fact","rule","knowledge","concept",
}

METADATA_FIELDS = {
    "id","uid","uuid","source","src","origin","file","filename",
    "tag","tags","label","labels","category","categories","type",
    "topic","topics","domain","field","subject","author","creator",
    "date","timestamp","time","created_at","role","name","title",
}

IGNORE_FIELDS = {
    "embedding","embeddings","vector","vectors","encoding",
    "token_count","char_count","hash",
}

def extract_think_blocks(text: str) -> Tuple[List[str], str]:
    blocks = []
    cleaned = text
    for pattern in THINK_PATTERNS:
        found = pattern.findall(text)
        blocks.extend([b.strip() for b in found if b.strip()])
        cleaned = pattern.sub('', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return blocks, cleaned

def _extract_text_recursive(obj, texts, think_blocks, metadata, parent_key=""):
    if obj is None: return
    if isinstance(obj, str):
        stripped = obj.strip()
        if len(stripped) < 2: return
        thinks, cleaned = extract_think_blocks(stripped)
        if thinks: think_blocks.extend(thinks)
        if cleaned and len(cleaned) >= 2:
            texts.append(cleaned)
        return
    if isinstance(obj, (int, float, bool)):
        if parent_key and parent_key.lower() in METADATA_FIELDS:
            metadata[parent_key] = obj
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower() if isinstance(key, str) else str(key).lower()
            if key_lower in IGNORE_FIELDS: continue
            if key_lower in METADATA_FIELDS:
                if isinstance(value, (str, int, float, bool)):
                    metadata[key] = value
                else:
                    _extract_text_recursive(value, texts, think_blocks, metadata, key)
            elif key_lower in TEXT_FIELD_NAMES:
                if isinstance(value, str):
                    thinks, cleaned = extract_think_blocks(value)
                    if thinks: think_blocks.extend(thinks)
                    if cleaned and len(cleaned) >= 2: texts.append(cleaned)
                else:
                    _extract_text_recursive(value, texts, think_blocks, metadata, key)
            else:
                _extract_text_recursive(value, texts, think_blocks, metadata, key)
        return
    if isinstance(obj, list):
        for item in obj:
            _extract_text_recursive(item, texts, think_blocks, metadata, parent_key)
        return

def parse_jsonl_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line: return None
    if line.startswith("//") or line.startswith("#"): return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        if len(line) > 5:
            thinks, cleaned = extract_think_blocks(line)
            if cleaned:
                return {"texts": [cleaned], "think_blocks": thinks, "metadata": {}}
        return None
    texts, think_blocks, metadata = [], [], {}
    _extract_text_recursive(obj, texts, think_blocks, metadata)
    if not texts and not think_blocks:
        if isinstance(obj, str) and len(obj) > 5:
            thinks, cleaned = extract_think_blocks(obj)
            if cleaned: texts.append(cleaned)
            think_blocks.extend(thinks)
    if not texts and not think_blocks: return None
    return {"texts": texts, "think_blocks": think_blocks, "metadata": metadata}

def parse_jsonl_file(filepath: str) -> List[Dict[str, Any]]:
    results = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                parsed = parse_jsonl_line(line)
                if parsed:
                    parsed["line_number"] = line_num
                    parsed["file"] = os.path.basename(filepath)
                    results.append(parsed)
    except: pass
    return results

def parse_any_file(filepath: str) -> List[Dict[str, Any]]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            if isinstance(data, list):
                results = []
                for i, item in enumerate(data):
                    texts, think_blocks, metadata = [], [], {}
                    _extract_text_recursive(item, texts, think_blocks, metadata)
                    if texts or think_blocks:
                        results.append({"texts": texts, "think_blocks": think_blocks, "metadata": metadata, "line_number": i, "file": os.path.basename(filepath)})
                return results
            elif isinstance(data, dict):
                texts, think_blocks, metadata = [], [], {}
                _extract_text_recursive(data, texts, think_blocks, metadata)
                if texts or think_blocks:
                    return [{"texts": texts, "think_blocks": think_blocks, "metadata": metadata, "line_number": 1, "file": os.path.basename(filepath)}]
        except: pass
        return []
    elif ext in (".jsonl", ".ndjson", ".jsonlines"):
        return parse_jsonl_file(filepath)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            thinks, cleaned = extract_think_blocks(content)
            if cleaned:
                chunks = re.split(r'\n\s*\n', cleaned)
                chunks = [c.strip() for c in chunks if len(c.strip()) > 5]
                if not chunks: chunks = [cleaned]
                return [{"texts": chunks, "think_blocks": thinks, "metadata": {"source": "plain_text"}, "line_number": 1, "file": os.path.basename(filepath)}]
        except: pass
    return []

class UniversalParser:
    def __init__(self):
        self.total_parsed = 0
        self.total_think_blocks = 0
        self.reasoning_patterns = []

    def parse_line(self, line): return parse_jsonl_line(line)
    def parse_file(self, filepath):
        results = parse_any_file(filepath)
        for r in results:
            self.total_parsed += len(r.get("texts", []))
            self.total_think_blocks += len(r.get("think_blocks", []))
            for tb in r.get("think_blocks", []): self._extract_reasoning_pattern(tb)
        return results
    def parse_text(self, text):
        thinks, cleaned = extract_think_blocks(text)
        for tb in thinks: self._extract_reasoning_pattern(tb)
        return {"texts": [cleaned] if cleaned else [], "think_blocks": thinks, "metadata": {}}

    def _extract_reasoning_pattern(self, think_text):
        markers = ["vì", "do", "bởi vì", "nhờ", "nên", "do đó", "kết quả là", "vì vậy", "tuy nhiên", "nếu", "thì"]
        low = think_text.lower()
        found_markers = [m for m in markers if m in low]
        if found_markers:
            self.reasoning_patterns.append({"markers": found_markers, "preview": think_text[:120]})
            if len(self.reasoning_patterns) > 500: self.reasoning_patterns = self.reasoning_patterns[-250:]

    def stats(self):
        return {"total_parsed": self.total_parsed, "total_think_blocks": self.total_think_blocks, "reasoning_patterns": len(self.reasoning_patterns)}
