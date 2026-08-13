# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict
import re
from pathlib import Path

try:
    from core.rag2026_store import RAGStore, sentence_compress, normalize_text
except Exception:
    from core.rag2026_store import RAGStore

    def normalize_text(text):
        return re.sub(r'\s+', ' ', str(text or '')).strip()

    def sentence_compress(text, query, max_chars=900):
        return str(text or '')[:max_chars]

try:
    from core.rag2026_vector_index import VectorIndex2026, EMBEDDING_VERSION
except Exception:
    VectorIndex2026 = None
    EMBEDDING_VERSION = None


class RAGConfig:
    SPARSE_LIMIT = 60
    DENSE_LIMIT = 60
    FINAL_CANDIDATES = 30
    FINAL_LIMIT = 10
    NEIGHBOR_RADIUS = 1
    MMR_LAMBDA = 0.78
    CONTEXT_CHARS = 3000


def _tokens(text):
    return set(re.findall(r'[\w-]{2,}', str(text or '').lower()))


def rrf_merge(*ranked_lists, k=60):
    scores = defaultdict(float)
    for lst in ranked_lists:
        for rank, item in enumerate(lst or []):
            cid, score = item
            cid = int(cid)
            scores[cid] += 1.0 / (k + rank + 1)
            if score:
                scores[cid] += min(0.08, float(score) * 0.02)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class SuperRAG:
    def __init__(self, pet):
        self.pet = pet
        root = getattr(pet, 'PROJECT_ROOT', None) or Path(__file__).resolve().parents[1]
        self.store = getattr(pet, 'rag2026', None) or RAGStore(root)
        self.config = RAGConfig()
        try:
            self.vector = VectorIndex2026(self.store) if VectorIndex2026 else None
        except Exception:
            self.vector = None
        self.built = False
        self.doc_map = {}

    def build(self):
        try:
            if self.vector:
                self.vector.build_incremental(limit=1000)
                self.vector.start_background_build(delay=0.4)
        except Exception:
            pass
        self.built = True
        return True

    def _variants(self, query):
        q = normalize_text(query)
        out = [q]
        low = q.lower()
        if any(k in low for k in ('tại sao', 'vì sao', 'why', 'nguyên nhân')):
            out += [q + ' nguyên nhân', q + ' giải thích']
        elif any(k in low for k in ('cách', 'làm sao', 'how', 'hướng dẫn')):
            out += [q + ' cách làm', q + ' hướng dẫn']
        return list(dict.fromkeys(out))[:4]

    def _dense(self, query):
        if self.vector:
            try:
                return self.vector.search(query, self.config.DENSE_LIMIT)
            except Exception:
                pass

        vs = getattr(self.pet, 'vector_search', None)
        if vs and getattr(vs, 'available', False):
            try:
                res = vs.search(query, self.config.DENSE_LIMIT)
                out = []
                for x in res or []:
                    if isinstance(x, (list, tuple)) and len(x) >= 2:
                        out.append((int(x[0]), float(x[1])))
                return out
            except Exception:
                pass
        return []

    def retrieve(self, query, top_n=8):
        if not self.built:
            self.build()

        variants = self._variants(query)
        sparse = []
        seen = set()

        for v in variants:
            try:
                items = self.store.search_bm25(v, self.config.SPARSE_LIMIT)
            except Exception:
                items = []
            for cid, sc in items:
                cid = int(cid)
                if cid not in seen:
                    sparse.append((cid, sc))
                    seen.add(cid)

        dense = self._dense(query)
        fused = rrf_merge(sparse, dense)
        fused = fused[:self.config.FINAL_CANDIDATES]
        docs = self.store.get_many([cid for cid, _ in fused])
        qtok = _tokens(query)
        rer = []

        for cid, base in fused:
            d = docs.get(cid)
            if not d:
                continue
            text = ' '.join([str(d.get('context', '')), str(d.get('heading', '')), str(d.get('text', ''))])
            dtok = _tokens(text)
            overlap = len(qtok & dtok) / float(len(qtok)) if qtok else 0.0
            exact = 0.12 if normalize_text(query).lower() in text.lower() else 0.0
            source_bonus = 0.05 if str(d.get('source', '')).lower().endswith(('.jsonl', '.md', '.txt')) else 0.0
            score = float(base) * (0.72 + 0.55 * overlap) + exact + source_bonus
            rer.append((cid, score))

        rer.sort(key=lambda x: x[1], reverse=True)

        expanded = []
        seen2 = set()
        for cid, score in rer[:self.config.FINAL_CANDIDATES]:
            if cid not in seen2:
                expanded.append((cid, score))
                seen2.add(cid)
            try:
                nb = self.store.neighbors(cid, self.config.NEIGHBOR_RADIUS)
            except Exception:
                nb = []
            for nid in nb:
                nid = int(nid)
                if nid not in seen2:
                    expanded.append((nid, score * 0.92))
                    seen2.add(nid)

        docs2 = self.store.get_many([cid for cid, _ in expanded])
        selected = []
        selected_tokens = []

        while expanded and len(selected) < top_n:
            best_i = -1
            best_score = -1e9

            for i, (cid, score) in enumerate(expanded):
                d = docs2.get(cid)
                if not d:
                    continue
                toks = _tokens(d.get('text', ''))
                redundancy = 0.0
                for st in selected_tokens:
                    union = len(toks | st) or 1
                    redundancy = max(redundancy, len(toks & st) / float(union))
                mmr = self.config.MMR_LAMBDA * score - (1 - self.config.MMR_LAMBDA) * redundancy
                if mmr > best_score:
                    best_score = mmr
                    best_i = i

            if best_i < 0:
                break

            cid, score = expanded.pop(best_i)
            d = docs2.get(cid)
            if not d:
                continue

            selected.append((d, score))
            selected_tokens.append(_tokens(d.get('text', '')))

        self.doc_map = {d.get('id'): d for d, _ in selected}
        return selected

    def build_context(self, query, top_n=5, max_chars=None):
        max_chars = max_chars or self.config.CONTEXT_CHARS
        results = self.retrieve(query, top_n=max(top_n, 6))
        lines = []
        evidences = []
        used = 0

        for i, (d, score) in enumerate(results, 1):
            snippet = sentence_compress(d.get('text', ''), query, 700)
            source = d.get('source', 'unknown')
            heading = d.get('heading', '')
            line = f'[{i}] nguồn={source}'
            if heading:
                line += f' | mục={heading}'
            line += '\n' + snippet

            if lines and used + len(line) > max_chars:
                break

            lines.append(line)
            used += len(line)
            evidences.append({
                'id': d.get('id'),
                'score': float(score),
                'doc': d,
                'snippet': snippet,
                'source': source
            })

        return evidences, '\n\n'.join(lines)

    def search(self, query, top_n=3):
        return [d for d, _ in self.retrieve(query, top_n=top_n)]

    def stats(self):
        st = self.store.stats()
        st['embedding_version'] = EMBEDDING_VERSION
        if self.vector:
            st['vector_index'] = self.vector.stats()
        return st
