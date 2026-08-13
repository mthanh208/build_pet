# -*- coding: utf-8 -*-
import re
import hashlib
import unicodedata

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def tokenize(text):
    if not text:
        return []
    return _TOKEN_RE.findall(str(text).lower())


def normalize_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_hash(text):
    text = normalize_text(text)
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def smart_chunk_text(text, max_chars=900, overlap=120):
    """
    Chunk tài liệu thường theo câu/đoạn.
    Không dùng cho JSONL QA atomic nếu câu trả lời ngắn.
    """
    text = normalize_text(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks = []
    current = ""

    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current = f"{current} {s}".strip()
        else:
            if current:
                chunks.append(current)

            if len(s) > max_chars:
                words = s.split()
                current = ""
                for w in words:
                    if len(current) + len(w) + 1 > max_chars:
                        if current:
                            chunks.append(current)
                        current = w
                    else:
                        current = f"{current} {w}".strip()
            else:
                current = s

    if current:
        chunks.append(current)

    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail_words = chunks[i - 1][-overlap:].split()
            tail = " ".join(prev_tail_words[-12:])
            overlapped.append(f"{tail} {chunks[i]}".strip())
        chunks = overlapped

    return chunks
