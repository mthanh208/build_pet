# -*- coding: utf-8 -*-
from __future__ import annotations
import array, hashlib, json, re, sqlite3, threading, time
from pathlib import Path

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    np = None
    HAS_NUMPY = False

EMBEDDING_VERSION = 'rag2026-hash-embed-v1-dim512'
TOKEN_RE = re.compile(r'[\w-]{2,}', re.UNICODE)


class VectorIndex2026:
    def __init__(self, store, dim=512):
        self.store = store
        self.dim = int(dim)
        base = Path(store.db_path).parent
        self.meta_path = base / 'rag2026_vectors.meta.json'
        self.npy_path = base / 'rag2026_vectors.npy'
        self.bin_path = base / 'rag2026_vectors.bin'
        self.ids = []
        self.vectors = None
        self._lock = threading.RLock()
        self._bg = None
        self._stop = threading.Event()
        self._load_meta()
        self._ensure_db_meta()

    def _ensure_db_meta(self):
        try:
            with sqlite3.connect(str(self.store.db_path), timeout=30) as c:
                c.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)')
                c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('embedding_version',?)", (EMBEDDING_VERSION,))
        except Exception:
            pass

    def _load_meta(self):
        try:
            if self.meta_path.exists():
                data = json.loads(self.meta_path.read_text(encoding='utf-8'))
                self.ids = [int(x) for x in data.get('ids', [])]
                self.dim = int(data.get('dim', self.dim))
        except Exception:
            self.ids = []
        self._load_vectors()

    def _load_vectors(self):
        try:
            if HAS_NUMPY and self.npy_path.exists():
                self.vectors = np.load(self.npy_path, mmap_mode='r')
            elif self.bin_path.exists() and self.ids:
                arr = array.array('f')
                expected = len(self.ids) * self.dim
                with open(self.bin_path, 'rb') as f:
                    arr.fromfile(f, expected)
                self.vectors = arr
        except Exception:
            self.vectors = None

    def _save_meta(self):
        payload = {
            'ids': self.ids,
            'dim': self.dim,
            'embedding_version': EMBEDDING_VERSION,
            'count': len(self.ids),
            'updated_at': time.time(),
            'mmap': bool(HAS_NUMPY and self.npy_path.exists())
        }
        self.meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def _normalize(self, vec):
        if HAS_NUMPY and isinstance(vec, np.ndarray):
            n = float(np.linalg.norm(vec))
            if n > 0:
                vec = vec / n
            return vec.astype(np.float32, copy=False)
        norm = float(sum(x * x for x in vec) ** 0.5)
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _embed(self, text):
        vec = np.zeros(self.dim, dtype=np.float32) if HAS_NUMPY else [0.0] * self.dim
        tokens = TOKEN_RE.findall(str(text or '').lower())
        if not tokens:
            return self._normalize(vec)

        for i, t in enumerate(tokens):
            h = hashlib.sha256(t.encode('utf-8')).digest()
            idx = int.from_bytes(h[:4], 'little') % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            weight = 1.0 + min(3.0, len(t) / 8.0)
            vec[idx] += sign * weight

            if i + 1 < len(tokens):
                bg = t + '_' + tokens[i + 1]
                h2 = hashlib.sha256(bg.encode('utf-8')).digest()
                idx2 = int.from_bytes(h2[:4], 'little') % self.dim
                sign2 = 1.0 if h2[4] & 1 else -1.0
                vec[idx2] += sign2 * 0.5

        return self._normalize(vec)

    def build_incremental(self, limit=500):
        with self._lock:
            existing = set(int(x) for x in self.ids)
            new_ids = []
            new_vecs = []

            for d in self.store.iter_docs(batch=500):
                try:
                    cid = int(d.get('id'))
                except Exception:
                    continue
                if cid in existing:
                    continue
                text = ' '.join(str(d.get(k, '')) for k in ('heading', 'context', 'text'))
                new_ids.append(cid)
                new_vecs.append(self._embed(text))
                existing.add(cid)
                if len(new_ids) >= limit:
                    break

            if not new_ids:
                return 0

            self.ids.extend(new_ids)

            if HAS_NUMPY:
                old = None
                if self.npy_path.exists():
                    try:
                        old = np.load(self.npy_path, mmap_mode='r')
                    except Exception:
                        old = None
                new_arr = np.asarray(new_vecs, dtype=np.float32)
                arr = new_arr if old is None else np.vstack([old, new_arr])
                np.save(self.npy_path, arr.astype(np.float32, copy=False))
                self.vectors = np.load(self.npy_path, mmap_mode='r')
            else:
                if not isinstance(self.vectors, array.array):
                    self._load_vectors()
                if not isinstance(self.vectors, array.array):
                    self.vectors = array.array('f')
                for v in new_vecs:
                    self.vectors.extend(v)
                with open(self.bin_path, 'wb') as f:
                    self.vectors.tofile(f)

            self._save_meta()
            return len(new_ids)

    def search(self, query, top_n=40):
        if not self.ids:
            self.build_incremental(limit=500)
        if not self.ids:
            return []
        if self.vectors is None:
            self._load_vectors()

        q = self._embed(query)

        if HAS_NUMPY and hasattr(self.vectors, 'shape'):
            scores = np.asarray(self.vectors, dtype=np.float32) @ np.asarray(q, dtype=np.float32)
            n = min(int(top_n), len(scores))
            if n <= 0:
                return []
            idx = np.argpartition(-scores, n - 1)[:n]
            idx = idx[np.argsort(-scores[idx])]
            return [(int(self.ids[i]), float(scores[i])) for i in idx if scores[i] > 0]

        out = []
        dim = self.dim
        for i, cid in enumerate(self.ids):
            off = i * dim
            s = 0.0
            for j in range(dim):
                s += self.vectors[off + j] * q[j]
            if s > 0:
                out.append((int(cid), float(s)))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_n]

    def start_background_build(self, delay=0.5):
        if self._bg and self._bg.is_alive():
            return

        def worker():
            time.sleep(delay)
            while not self._stop.is_set():
                try:
                    n = self.build_incremental(limit=300)
                    if not n:
                        self._stop.wait(5.0)
                    else:
                        self._stop.wait(0.2)
                except Exception:
                    self._stop.wait(2.0)

        self._bg = threading.Thread(target=worker, daemon=True, name='rag2026-vector-index')
        self._bg.start()

    def stop(self):
        self._stop.set()

    def stats(self):
        return {
            'embedding_version': EMBEDDING_VERSION,
            'vectors': len(self.ids),
            'dim': self.dim,
            'mmap': bool(HAS_NUMPY and self.npy_path.exists()),
            'persistent': True
        }
