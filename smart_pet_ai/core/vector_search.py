# -*- coding: utf-8 -*-
import os, pickle, time
from collections import defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    faiss = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

import re
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

def _tokenize(text):
    return _WORD_RE.findall(text.lower())

class VectorSearch:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.available = HAS_NUMPY
        self.use_faiss = HAS_FAISS
        self.vectorizer = None
        self.index = None
        self.doc_ids = []
        self.vectors = None
        self.dim = 0
        if HAS_SKLEARN:
            self.vectorizer = TfidfVectorizer(tokenizer=_tokenize, max_features=2000, ngram_range=(1, 2), sublinear_tf=True)
        if save_path and os.path.exists(save_path): self.load()

    def build_index(self, documents):
        if not self.available or not documents: return False
        texts = [d.get("text", "") for d in documents]
        if len(texts) < 2: return False
        try:
            if self.vectorizer is None: return False
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            vectors = tfidf_matrix.toarray().astype('float32')
            if HAS_NUMPY:
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                vectors = vectors / norms
            self.vectors = vectors
            self.doc_ids = [d.get("id", i) for i, d in enumerate(documents)]
            self.dim = vectors.shape[1] if len(vectors) > 0 else 0
            if self.use_faiss and self.dim > 0:
                try:
                    self.index = faiss.IndexFlatIP(self.dim)
                    self.index.add(vectors)
                except:
                    self.use_faiss = False
                    self.index = None
            return True
        except: return False

    def search(self, query, top_n=5):
        if not self.available or self.vectorizer is None: return []
        if self.vectors is None or len(self.vectors) == 0: return []
        try:
            query_vec = self.vectorizer.transform([query]).toarray().astype('float32')
            if HAS_NUMPY:
                norm = np.linalg.norm(query_vec, axis=1, keepdims=True)
                norm[norm == 0] = 1.0
                query_vec = query_vec / norm
            if self.use_faiss and self.index is not None:
                scores, indices = self.index.search(query_vec, min(top_n, len(self.doc_ids)))
                results = []
                for i, idx in enumerate(indices[0]):
                    if idx >= 0 and scores[0][i] > 0.01:
                        results.append((int(self.doc_ids[idx]), float(scores[0][i])))
                return results
            else:
                if not HAS_NUMPY: return []
                sims = cosine_similarity(query_vec, self.vectors)[0]
                ranked = sorted(enumerate(sims), key=lambda x: -x[1])
                return [(int(self.doc_ids[i]), float(score)) for i, score in ranked[:top_n] if score > 0.01]
        except: return []

    def save(self):
        if not self.save_path or not self.available: return
        try:
            data = {"doc_ids": self.doc_ids, "dim": self.dim, "use_faiss": self.use_faiss}
            with open(self.save_path + ".meta", "wb") as f:
                pickle.dump(data, f)
            if self.vectors is not None and HAS_NUMPY:
                np.save(self.save_path + ".npy", self.vectors)
        except: pass

    def load(self):
        try:
            with open(self.save_path + ".meta", "rb") as f:
                data = pickle.load(f)
            self.doc_ids = data.get("doc_ids", [])
            self.dim = data.get("dim", 0)
            self.use_faiss = data.get("use_faiss", False) and HAS_FAISS
            if os.path.exists(self.save_path + ".npy") and HAS_NUMPY:
                self.vectors = np.load(self.save_path + ".npy", mmap_mode="r")  # Turbo Boot: mmap
        except: pass

    def stats(self):
        return {"available": self.available, "use_faiss": self.use_faiss, "vectors": len(self.doc_ids), "dim": self.dim}
