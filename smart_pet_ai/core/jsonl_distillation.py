# -*- coding: utf-8 -*-
import json
import os
import re

from core.universal_parser import extract_think_blocks
from core.rag_utils import normalize_text, text_hash, smart_chunk_text


QUERY_KEYS = [
    "instruction", "input", "query", "question", "prompt", "user",
    "human", "task", "request", "ask", "problem"
]

ANSWER_KEYS = [
    "output", "response", "answer", "completion", "assistant",
    "ai", "reply", "result", "solution", "bot", "model"
]

THINK_KEYS = [
    "think", "thinking", "reasoning", "thought", "analysis",
    "chain_of_thought", "cot", "rationale", "explanation"
]

META_KEYS = {
    "id", "uid", "uuid", "source", "src", "origin", "file", "filename",
    "tag", "tags", "label", "labels", "category", "categories", "type",
    "topic", "topics", "domain", "field", "subject", "author", "creator",
    "date", "timestamp", "time", "created_at", "role", "name", "title",
    "source_model", "model", "distilled_from", "language", "lang",
    "quality", "confidence", "score", "rating", "weight"
}

CONF_KEYS = [
    "confidence", "quality", "score", "rating", "prob", "probability", "trust"
]

IGNORE_KEYS = {
    "embedding", "embeddings", "vector", "vectors", "encoding",
    "token_count", "char_count", "hash", "embedding_text", "dense_vector"
}


def _as_scalar(v):
    if isinstance(v, (str, int, float, bool)):
        return v
    return None


def _get_field_ci(obj, keys):
    if not isinstance(obj, dict):
        return None

    lower_map = {}
    for k in obj.keys():
        lower_map[str(k).lower()] = k

    for key in keys:
        if key in lower_map:
            return obj[lower_map[key]]

    return None


def _to_text(v, depth=0):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if depth > 3:
        return ""

    if isinstance(v, list):
        parts = []
        for item in v[:8]:
            t = _to_text(item, depth + 1)
            if t:
                parts.append(t)
        return " ".join(parts)

    if isinstance(v, dict):
        parts = []
        for _, val in list(v.items())[:8]:
            t = _to_text(val, depth + 1)
            if t:
                parts.append(t)
        return " ".join(parts)

    return str(v)


def _extract_meta(obj):
    meta = {}

    if not isinstance(obj, dict):
        return meta

    for k, v in obj.items():
        kl = str(k).lower()
        scalar = _as_scalar(v)
        if kl in META_KEYS and scalar is not None:
            meta[k] = scalar

        if isinstance(v, dict) and kl in ("metadata", "meta", "info"):
            for k2, v2 in v.items():
                scalar2 = _as_scalar(v2)
                if scalar2 is not None:
                    meta[k2] = scalar2

    return meta


def _extract_tags(obj):
    tags = []

    raw = _get_field_ci(obj, ["tags", "tag", "labels", "topics", "domains", "keywords"])
    if raw is None:
        return tags

    if isinstance(raw, str):
        parts = re.split(r"[,;|/]", raw)
        tags = [normalize_text(p) for p in parts if normalize_text(p)]
    elif isinstance(raw, list):
        for item in raw[:20]:
            t = normalize_text(_to_text(item))
            if t:
                tags.append(t)
    elif isinstance(raw, dict):
        for item in list(raw.values())[:20]:
            t = normalize_text(_to_text(item))
            if t:
                tags.append(t)

    return list(dict.fromkeys(tags))


def _extract_confidence(obj):
    for key in CONF_KEYS:
        raw = _get_field_ci(obj, [key])
        if raw is None:
            continue
        try:
            val = float(raw)
            if 0.0 <= val <= 1.0:
                return val
            if 0.0 <= val <= 100.0:
                return val / 100.0
            if 0.0 <= val <= 5.0:
                return val / 5.0
            if 0.0 <= val <= 10.0:
                return val / 10.0
        except Exception:
            continue

    return 0.75


def _extract_think(obj, out, depth=0):
    if depth > 4:
        return

    if isinstance(obj, str):
        blocks, _ = extract_think_blocks(obj)
        out.extend(blocks)
        return

    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in THINK_KEYS and isinstance(v, str):
                blocks, _ = extract_think_blocks(v)
                out.extend(blocks)
            else:
                _extract_think(v, out, depth + 1)
        return

    if isinstance(obj, list):
        for item in obj[:20]:
            _extract_think(item, out, depth + 1)
        return


def _collect_texts(obj, out, depth=0, limit=8):
    if len(out) >= limit or depth > 4:
        return

    if isinstance(obj, str):
        s = normalize_text(obj)
        if len(s) >= 20:
            out.append(s)
        return

    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in IGNORE_KEYS or kl in META_KEYS or kl in THINK_KEYS:
                continue
            if kl in QUERY_KEYS or kl in ANSWER_KEYS:
                continue
            _collect_texts(v, out, depth + 1, limit)
        return

    if isinstance(obj, list):
        for item in obj[:12]:
            _collect_texts(item, out, depth + 1, limit)
        return


def _looks_like_fact(text):
    low = text.lower()
    markers = [
        "là", "bao gồm", "gồm", "được", "có thể", "là một", "là loại",
        "là dạng", "được định nghĩa", "được hiểu", "có nghĩa", "giúp"
    ]
    return any(m in low for m in markers)


def _make_unit(
    kind,
    text,
    question="",
    answer="",
    meta=None,
    confidence=0.75,
    tags=None,
    source_hint="",
    line=0
):
    text = normalize_text(text)
    if not text:
        return None

    question = normalize_text(question)
    answer = normalize_text(answer)

    unit = {
        "kind": kind,
        "question": question,
        "answer": answer,
        "text": text,
        "tags": tags or [],
        "metadata": meta or {},
        "confidence": float(max(0.0, min(1.0, confidence))),
        "rag_source": source_hint,
        "line_number": line,
        "hash": text_hash(text),
    }

    if kind in ("qa", "qa_parent", "qa_chunk", "fact"):
        unit["weight"] = 1.30
    elif kind == "reasoning":
        unit["weight"] = 1.05
    else:
        unit["weight"] = 1.10

    return unit


def _qa_units(question, answer, meta, confidence, tags, source_file, line):
    question = normalize_text(question)
    answer = normalize_text(answer)

    if not question or not answer:
        return []

    units = []

    if len(answer) <= 1200:
        text = f"Q: {question}\nA: {answer}"
        unit = _make_unit(
            kind="qa",
            text=text,
            question=question,
            answer=answer,
            meta=meta,
            confidence=confidence,
            tags=tags,
            source_hint=source_file,
            line=line
        )
        if unit:
            units.append(unit)
        return units

    chunks = smart_chunk_text(answer, max_chars=900, overlap=100)
    if not chunks:
        return []

    parent_answer_preview = chunks[0][:600]
    parent_text = f"Q: {question}\nA: {parent_answer_preview}"

    parent = _make_unit(
        kind="qa_parent",
        text=parent_text,
        question=question,
        answer=parent_answer_preview,
        meta=meta,
        confidence=confidence,
        tags=tags,
        source_hint=source_file,
        line=line
    )
    if parent:
        units.append(parent)

    n = len(chunks)
    for i, chunk in enumerate(chunks[:10], 1):
        text = f"Q: {question}\nA phần {i}/{n}: {chunk}"
        unit = _make_unit(
            kind="qa_chunk",
            text=text,
            question=question,
            answer=chunk,
            meta=meta,
            confidence=confidence,
            tags=tags,
            source_hint=source_file,
            line=line
        )
        if unit:
            units.append(unit)

    return units


def _normalize_messages(messages, meta, confidence, tags, source_file, line):
    out = []
    pending_question = None

    for m in messages[:30]:
        if not isinstance(m, dict):
            continue

        role_raw = _get_field_ci(m, ["role", "sender", "author", "from", "speaker"])
        role = normalize_text(_to_text(role_raw)).lower()

        content_raw = _get_field_ci(m, ["content", "text", "message", "value", "msg", "utterance"])
        content = normalize_text(_to_text(content_raw))

        if not content:
            continue

        if any(x in role for x in ["user", "human", "người dùng", "client", "question"]):
            pending_question = content
        elif any(x in role for x in ["assistant", "ai", "bot", "model", "answer", "pet"]):
            if pending_question:
                out.extend(
                    _qa_units(
                        pending_question,
                        content,
                        meta,
                        confidence,
                        tags,
                        source_file,
                        line
                    )
                )
                pending_question = None
            else:
                unit = _make_unit(
                    kind="text",
                    text=content,
                    answer=content,
                    meta=meta,
                    confidence=confidence,
                    tags=tags,
                    source_hint=source_file,
                    line=line
                )
                if unit:
                    out.append(unit)
        else:
            unit = _make_unit(
                kind="text",
                text=content,
                meta=meta,
                confidence=confidence * 0.9,
                tags=tags,
                source_hint=source_file,
                line=line
            )
            if unit:
                out.append(unit)

    if pending_question:
        unit = _make_unit(
            kind="fact",
            text=pending_question,
            question=pending_question,
            meta=meta,
            confidence=confidence * 0.8,
            tags=tags,
            source_hint=source_file,
            line=line
        )
        if unit:
            out.append(unit)

    return out[:15]


def _normalize_object(obj, source_file, line):
    if obj is None:
        return []

    if isinstance(obj, str):
        unit = _make_unit(
            kind="fact" if _looks_like_fact(obj) else "text",
            text=obj,
            confidence=0.55,
            source_hint=source_file,
            line=line
        )
        return [unit] if unit else []

    meta = _extract_meta(obj)
    confidence = _extract_confidence(obj)
    tags = _extract_tags(obj)

    think_blocks = []
    _extract_think(obj, think_blocks)
    think_blocks = list(dict.fromkeys(think_blocks))

    messages = _get_field_ci(obj, [
        "messages", "conversation", "dialogue", "dialog", "turns", "chat", "history"
    ])

    if isinstance(messages, list) and messages:
        return _normalize_messages(messages, meta, confidence, tags, source_file, line)

    question = normalize_text(_to_text(_get_field_ci(obj, QUERY_KEYS)))
    answer = normalize_text(_to_text(_get_field_ci(obj, ANSWER_KEYS)))

    if question and answer:
        return _qa_units(question, answer, meta, confidence, tags, source_file, line)

    texts = []
    _collect_texts(obj, texts, limit=8)

    units = []
    for t in texts[:8]:
        kind = "fact" if _looks_like_fact(t) else "text"
        unit = _make_unit(
            kind=kind,
            text=t,
            answer=t if kind == "fact" else "",
            meta=meta,
            confidence=confidence,
            tags=tags,
            source_hint=source_file,
            line=line
        )
        if unit:
            units.append(unit)

    if not units and think_blocks:
        for tb in think_blocks[:5]:
            unit = _make_unit(
                kind="reasoning",
                text=tb,
                answer=tb,
                meta=meta,
                confidence=confidence * 0.75,
                tags=tags,
                source_hint=source_file,
                line=line
            )
            if unit:
                units.append(unit)

    return units


def parse_jsonl_file_rag(filepath):
    units = []
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".json":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            items = data if isinstance(data, list) else [data]
            for i, item in enumerate(items, 1):
                units.extend(_normalize_object(item, filename, i))

        else:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("//") or line.startswith("#"):
                        continue

                    try:
                        obj = json.loads(line)
                    except Exception:
                        unit = _make_unit(
                            kind="fact" if _looks_like_fact(line) else "text",
                            text=line,
                            confidence=0.45,
                            source_hint=filename,
                            line=line_num
                        )
                        if unit:
                            units.append(unit)
                        continue

                    units.extend(_normalize_object(obj, filename, line_num))

    except Exception:
        pass

    return [u for u in units if u]
