# -*- coding: utf-8 -*-
import re

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False

try:
    from underthesea import word_tokenize as underthesea_tokenize
    HAS_UNDERTHESEA = True
except (ImportError, Exception):
    HAS_UNDERTHESEA = False

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENT_RE = re.compile(r'[^.!?…]+[.!?…]+', re.UNICODE)
_VI_PATTERNS = {
    "question": re.compile(r'(là gì|như thế nào|tại sao|vì sao|làm sao|có không|được không|ai|cái gì|ở đâu|khi nào|bao nhiêu)', re.IGNORECASE),
    "definition": re.compile(r'(là một|là dạng|là loại|được định nghĩa|được hiểu|bao gồm|gồm có)', re.IGNORECASE),
    "comparison": re.compile(r'(so sánh|khác nhau|giống nhau|khác biệt|tương tự|so với)', re.IGNORECASE),
    "causal": re.compile(r'(vì|do|bởi vì|tại sao|dẫn đến|khiến|gây ra|làm cho|tạo ra)', re.IGNORECASE),
    "emotion": re.compile(r'(cảm thấy|buồn|vui|giận|sợ|yêu|thương|nhớ|ghét|thích)', re.IGNORECASE),
    "instruction": re.compile(r'(hãy|làm ơn|vui lòng|giúp|xin hãy|đừng|hướng dẫn)', re.IGNORECASE),
}

class NLPEngine:
    def __init__(self):
        self.nlp = None
        self.available = HAS_SPACY
        if HAS_SPACY:
            for model_name in ["vi_spacy_core", "en_core_web_sm", "xx_ent_wiki_sm"]:
                try:
                    self.nlp = spacy.load(model_name)
                    break
                except: continue
            if self.nlp is None:
                try: self.nlp = spacy.blank("vi")
                except:
                    try: self.nlp = spacy.blank("en")
                    except:
                        self.nlp = None
                        self.available = False

    def tokenize(self, text):
        if HAS_UNDERTHESEA:
            try: return underthesea_tokenize(text)
            except: pass
        return _WORD_RE.findall(text)

    def sentences(self, text):
        sents = _SENT_RE.findall(text)
        if sents: return [s.strip() for s in sents]
        return [text.strip()]

    def extract_entities(self, text):
        if self.nlp:
            try:
                doc = self.nlp(text)
                return [(ent.text, ent.label_) for ent in doc.ents]
            except: pass
        words = _WORD_RE.findall(text)
        entities = []
        buffer = []
        for w in words:
            if len(w) > 1 and w[0].isupper():
                buffer.append(w)
            else:
                if buffer:
                    entities.append((" ".join(buffer), "PROPN"))
                    buffer = []
        if buffer:
            entities.append((" ".join(buffer), "PROPN"))
        return entities

    def detect_intent(self, text):
        low = text.lower()
        intents = []
        for intent, pattern in _VI_PATTERNS.items():
            if pattern.search(low): intents.append(intent)
        if not intents:
            if "?" in text or text.endswith("?"): intents.append("question")
            else: intents.append("statement")
        return intents

    def extract_keywords(self, text, limit=10):
        words = self.tokenize(text)
        freq = {}
        stopwords = {"tôi", "bạn", "củ", "là", "và", "hoặc", "nhưng", "vì", "nên", "the", "a", "an", "is", "are", "was", "were", "in", "on", "at"}
        for w in words:
            wl = w.lower()
            if len(wl) > 2 and wl not in stopwords:
                freq[wl] = freq.get(wl, 0) + 1
        ranked = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in ranked[:limit]]

    def stats(self):
        return {"available": self.available, "underthesea": HAS_UNDERTHESEA, "model_loaded": self.nlp is not None}
