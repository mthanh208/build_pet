# -*- coding: utf-8 -*-
"""PET AI RAG 2026 core.

Design goals:
- boot-time work is metadata-only;
- no full-corpus load into Python RAM;
- idempotent incremental ingestion via stat fingerprint + SHA-256;
- chunk-level SHA-256 for delta indexing;
- SQLite FTS5/BM25 as disk-backed sparse index;
- deterministic contextualized chunks;
- lazy document access;
- optional background ingestion;
- no dependency on a particular embedding model or GGUF model.
"""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, threading, time
from collections.abc import MutableSequence
from pathlib import Path

SCHEMA_VERSION = 3
PARSER_VERSION = "rag2026-parser-3"
CHUNKER_VERSION = "rag2026-section-chunker-3"

_TEXT_KEYS = ("text","content","body","answer","response","completion","document","description","passage","paragraph","question","query","prompt","input")
_SKIP_DIRS = {"__pycache__",".git","node_modules","venv",".venv","site-packages"}


def normalize_text(text: str) -> str:
    text = str(text or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(normalize_text(text).encode("utf-8", errors="ignore"))


def sha256_file(path: Path, block=1024*1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stat_fingerprint(path: Path):
    st = path.stat()
    return (int(st.st_size), int(st.st_mtime_ns), int(getattr(st, "st_ino", 0)))


def safe_json(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def extract_text_from_obj(obj):
    if obj is None:
        return ""
    if isinstance(obj, str):
        return normalize_text(obj)
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, list):
        parts = [extract_text_from_obj(x) for x in obj]
        return normalize_text("\n".join(x for x in parts if x))
    if isinstance(obj, dict):
        parts = []
        # Prefer human-facing textual fields and retain question/answer structure.
        for k in _TEXT_KEYS:
            if k in obj:
                val = extract_text_from_obj(obj[k])
                if val:
                    parts.append(f"{k}: {val}")
        if not parts:
            for k, v in obj.items():
                if isinstance(v, (str, int, float, bool)):
                    parts.append(f"{k}: {v}")
        return normalize_text("\n".join(parts))
    return normalize_text(str(obj))


def _split_long(text: str, target_chars=2600, overlap=320):
    if len(text) <= target_chars:
        return [text]
    words = text.split()
    chunks, cur = [], []
    cur_len = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if cur and cur_len + add > target_chars:
            chunks.append(" ".join(cur).strip())
            tail = " ".join(cur)[-overlap:]
            cur = tail.split() if tail else []
            cur_len = len(" ".join(cur))
        cur.append(w)
        cur_len += add
    if cur:
        chunks.append(" ".join(cur).strip())
    return [x for x in chunks if x]


def chunk_text(text: str, target_chars=2600, overlap=320):
    """Structure-aware chunking: headings -> paragraphs -> sentence fallback -> bounded overlap."""
    text = normalize_text(text)
    if not text:
        return []
    lines = text.split("\n")
    sections, heading, buf = [], "", []
    for line in lines:
        s = line.strip()
        if not s:
            if buf:
                sections.append((heading, " ".join(buf)))
                buf = []
            continue
        if re.match(r"^#{1,6}\s+", s) or re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", s):
            if buf:
                sections.append((heading, " ".join(buf)))
                buf = []
            heading = s
        else:
            buf.append(s)
    if buf:
        sections.append((heading, " ".join(buf)))

    chunks = []
    for heading, body in sections:
        for part in _split_long(body, target_chars, overlap):
            chunks.append((heading, part))
    if not chunks:
        chunks = [("", text)]
    return chunks


def sentence_compress(text: str, query: str, max_chars=900):
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    q = set(re.findall(r"[\wÀ-ỹ_]{2,}", query.lower()))
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    scored = []
    for i, s in enumerate(sentences):
        toks = set(re.findall(r"[\wÀ-ỹ_]{2,}", s.lower()))
        overlap = len(q & toks)
        scored.append((overlap, -i, s))
    scored.sort(reverse=True)
    chosen, total = [], 0
    for _, _, s in scored:
        if not s:
            continue
        if total + len(s) + 1 > max_chars and chosen:
            continue
        chosen.append(s)
        total += len(s) + 1
        if total >= max_chars:
            break
    return " ".join(chosen)[:max_chars]


class RAGStore:
    def __init__(self, project_root):
        self.root = Path(project_root).resolve()
        self.db_path = self.root / "data_memory" / "rag2026.sqlite3"
        self.source_dirs = [
            self.root / "data_hot" / "tai_lieu_RAG",
            self.root / "data_hot" / "kien_thuc_jsonl",
            self.root / "data_hot" / "think_tags",
        ]
        self._lock = threading.RLock()
        self._bg = None
        self._stop = threading.Event()
        self._ensure_schema()

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA temp_store=MEMORY")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def _ensure_schema(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS files(
                path TEXT PRIMARY KEY,
                size INTEGER NOT NULL DEFAULT 0,
                mtime_ns INTEGER NOT NULL DEFAULT 0,
                inode INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                parser_version TEXT,
                chunker_version TEXT,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks(
                chunk_id INTEGER PRIMARY KEY,
                source_path TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                heading TEXT,
                context TEXT,
                text TEXT NOT NULL,
                chunk_sha256 TEXT NOT NULL UNIQUE,
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_path);
            CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_sha256);
            CREATE INDEX IF NOT EXISTS idx_chunks_filehash ON chunks(file_sha256);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                text, context, heading, source_path UNINDEXED,
                content='chunks', content_rowid='chunk_id',
                tokenize='unicode61'
            );
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
              INSERT INTO chunk_fts(rowid,text,context,heading,source_path)
              VALUES(new.chunk_id,new.text,new.context,new.heading,new.source_path);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
              INSERT INTO chunk_fts(chunk_fts,rowid,text,context,heading,source_path)
              VALUES('delete',old.chunk_id,old.text,old.context,old.heading,old.source_path);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
              INSERT INTO chunk_fts(chunk_fts,rowid,text,context,heading,source_path)
              VALUES('delete',old.chunk_id,old.text,old.context,old.heading,old.source_path);
              INSERT INTO chunk_fts(rowid,text,context,heading,source_path)
              VALUES(new.chunk_id,new.text,new.context,new.heading,new.source_path);
            END;
            """)
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('parser_version',?)", (PARSER_VERSION,))
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('chunker_version',?)", (CHUNKER_VERSION,))

    @property
    def count(self):
        with self._connect() as c:
            return int(c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def max_id(self):
        with self._connect() as c:
            return int(c.execute("SELECT COALESCE(MAX(chunk_id),0) FROM chunks").fetchone()[0])

    def iter_docs(self, batch=500):
        with self._connect() as c:
            off = 0
            while True:
                rows = c.execute("SELECT chunk_id,text,source_path,heading,context,meta_json FROM chunks ORDER BY chunk_id LIMIT ? OFFSET ?", (batch, off)).fetchall()
                if not rows:
                    break
                for r in rows:
                    try: meta = json.loads(r[5] or "{}")
                    except Exception: meta = {}
                    d = {"id": r[0], "text": r[1], "source": r[2], "heading": r[3] or "", "context": r[4] or "", **meta}
                    yield d
                off += len(rows)

    def get(self, chunk_id):
        with self._connect() as c:
            r = c.execute("SELECT chunk_id,text,source_path,heading,context,meta_json FROM chunks WHERE chunk_id=?", (int(chunk_id),)).fetchone()
        if not r:
            raise IndexError(chunk_id)
        try: meta = json.loads(r[5] or "{}")
        except Exception: meta = {}
        return {"id": r[0], "text": r[1], "source": r[2], "heading": r[3] or "", "context": r[4] or "", **meta}

    def slice(self, start, stop, step=1):
        n = self.count
        if start is None: start = 0
        if start < 0: start = max(0, n + start)
        if stop is None: stop = n
        if stop < 0: stop = max(0, n + stop)
        with self._connect() as c:
            rows = c.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id LIMIT ? OFFSET ?", (max(0, stop-start), max(0,start))).fetchall()
        ids = [r[0] for r in rows][::step]
        return [self.get(i) for i in ids]

    def upsert_legacy_doc(self, doc):
        text = normalize_text(doc.get("text") or doc.get("answer") or "")
        if not text:
            return
        source = str(doc.get("source") or "legacy")
        fhash = str(doc.get("hash") or sha256_text(text))
        chunk_hash = sha256_text(source + "|" + fhash + "|0|" + text)
        meta = dict(doc)
        meta.pop("text", None); meta.pop("id", None); meta.pop("source", None)
        now = time.time()
        with self._connect() as c:
            row = c.execute("SELECT chunk_id FROM chunks WHERE chunk_sha256=?", (chunk_hash,)).fetchone()
            if row:
                return
            c.execute("INSERT INTO chunks(chunk_id,source_path,file_sha256,chunk_index,heading,context,text,chunk_sha256,meta_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (int(doc.get("id") or self.max_id()+1), source, fhash, 0, "", source, text, chunk_hash, safe_json(meta), now))

    def ingest_path(self, path: Path, force=False):
        try: fp = str(path.resolve())
        except Exception: fp = str(path)
        try:
            size, mtime_ns, inode = stat_fingerprint(path)
        except Exception:
            return {"status":"missing","path":fp,"changed":False,"chunks":0}
        with self._connect() as c:
            old = c.execute("SELECT size,mtime_ns,inode,sha256 FROM files WHERE path=?", (fp,)).fetchone()
        if old and not force and (int(old[0]),int(old[1]),int(old[2])) == (size,mtime_ns,inode) and old[3]:
            return {"status":"unchanged","path":fp,"changed":False,"chunks":0}
        try:
            fhash = sha256_file(path)
            if old and old[3] == fhash:
                with self._connect() as c:
                    c.execute("UPDATE files SET size=?,mtime_ns=?,inode=?,status='ready',updated_at=? WHERE path=?", (size,mtime_ns,inode,time.time(),fp))
                return {"status":"same_hash","path":fp,"changed":False,"chunks":0}
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            with self._connect() as c:
                c.execute("INSERT OR REPLACE INTO files(path,size,mtime_ns,inode,sha256,status,parser_version,chunker_version,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (fp,size,mtime_ns,inode,None,'error',PARSER_VERSION,CHUNKER_VERSION,time.time()))
            return {"status":"error","path":fp,"changed":False,"chunks":0,"error":str(e)}
        suffix = path.suffix.lower()
        if suffix in {".jsonl",".ndjson"}:
            pieces=[]
            for line_no,line in enumerate(text.splitlines(),1):
                if not line.strip(): continue
                try:
                    obj=json.loads(line)
                    t=extract_text_from_obj(obj)
                except Exception:
                    t=normalize_text(line)
                if t: pieces.append((f"record {line_no}",t))
        elif suffix == ".json":
            try: pieces=[("",extract_text_from_obj(json.loads(text)))]
            except Exception: pieces=[("",normalize_text(text))]
        else:
            pieces=chunk_text(text)
        # Rebuild only this file.
        with self._connect() as c:
            c.execute("DELETE FROM chunks WHERE source_path=?", (fp,))
            now=time.time()
            idx=0
            for heading, body in pieces:
                for h2, chunk in chunk_text(body) if len(body)>3200 else [(heading,body)]:
                    chunk=normalize_text(chunk)
                    if not chunk: continue
                    contextual = "; ".join(x for x in [path.name, heading or h2, str(path.parent)] if x)
                    chash=sha256_text(f"{fhash}|{idx}|{contextual}|{chunk}")
                    meta={"file_hash":fhash,"parser_version":PARSER_VERSION,"chunker_version":CHUNKER_VERSION}
                    c.execute("INSERT INTO chunks(source_path,file_sha256,chunk_index,heading,context,text,chunk_sha256,meta_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                              (fp,fhash,idx,heading or h2,contextual,chunk,chash,safe_json(meta),now))
                    idx+=1
            c.execute("INSERT OR REPLACE INTO files(path,size,mtime_ns,inode,sha256,status,parser_version,chunker_version,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (fp,size,mtime_ns,inode,fhash,'ready',PARSER_VERSION,CHUNKER_VERSION,now))
        return {"status":"indexed","path":fp,"changed":True,"chunks":idx}

    def scan_once(self, max_files=8):
        candidates=[]
        for d in self.source_dirs:
            if not d.exists(): continue
            for p in d.rglob("*"):
                if not p.is_file() or p.name.startswith(".") or any(part in _SKIP_DIRS for part in p.parts): continue
                if p.suffix.lower() in {".txt",".md",".jsonl",".ndjson",".json"}:
                    candidates.append(p)
                    if len(candidates)>=max_files: break
            if len(candidates)>=max_files: break
        out=[]
        for p in candidates:
            out.append(self.ingest_path(p))
            time.sleep(0.01)
        return out

    def start_background_ingest(self, delay=0.75):
        if self._bg and self._bg.is_alive(): return
        def worker():
            time.sleep(delay)
            while not self._stop.is_set():
                try:
                    res=self.scan_once(max_files=4)
                    if not res:
                        self._stop.wait(5.0)
                    else:
                        self._stop.wait(0.25)
                except Exception:
                    self._stop.wait(2.0)
        self._bg=threading.Thread(target=worker,name="pet-rag2026",daemon=True)
        self._bg.start()

    def stop(self):
        self._stop.set()

    def search_bm25(self, query, limit=40):
        tokens = re.findall(r"[\wÀ-ỹ_\-.]+", str(query).lower())
        tokens = [t for t in tokens if len(t)>=2][:24]
        if not tokens: return []
        # OR query avoids dropping candidates when one token is absent.
        match = " OR ".join('"'+t.replace('"','')+'"' for t in tokens)
        with self._connect() as c:
            rows=c.execute("SELECT rowid, bm25(chunk_fts, 1.2, 0.8, 0.6, 0.2) AS score FROM chunk_fts WHERE chunk_fts MATCH ? ORDER BY score LIMIT ?", (match, int(limit))).fetchall()
        return [(int(r[0]), float(-r[1])) for r in rows]

    def get_many(self, ids):
        ids=[int(x) for x in ids]
        if not ids: return {}
        q=','.join('?' for _ in ids)
        with self._connect() as c:
            rows=c.execute(f"SELECT chunk_id,text,source_path,heading,context,meta_json FROM chunks WHERE chunk_id IN ({q})", ids).fetchall()
        out={}
        for r in rows:
            try: meta=json.loads(r[5] or '{}')
            except Exception: meta={}
            out[r[0]]={"id":r[0],"text":r[1],"source":r[2],"heading":r[3] or "","context":r[4] or "",**meta}
        return out

    def neighbors(self, chunk_id, radius=1):
        with self._connect() as c:
            base=c.execute("SELECT source_path,chunk_index FROM chunks WHERE chunk_id=?",(int(chunk_id),)).fetchone()
            if not base: return []
            rows=c.execute("SELECT chunk_id FROM chunks WHERE source_path=? AND chunk_index BETWEEN ? AND ? ORDER BY chunk_index",(base[0],max(0,base[1]-radius),base[1]+radius)).fetchall()
        return [int(r[0]) for r in rows]

    def stats(self):
        with self._connect() as c:
            files=int(c.execute("SELECT COUNT(*) FROM files WHERE status='ready'").fetchone()[0])
            chunks=int(c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return {"files":files,"chunks":chunks,"db":str(self.db_path),"schema":SCHEMA_VERSION,"persistent":True}


class LazyDocuments(MutableSequence):
    """Compatibility facade exposing list-like behavior without storing the corpus in RAM."""
    def __init__(self, store): self.store=store
    def __len__(self): return self.store.count
    def __iter__(self): return self.store.iter_docs()
    def __getitem__(self, key):
        if isinstance(key,slice): return self.store.slice(key.start,key.stop,key.step or 1)
        n=self.store.count
        idx=int(key); idx = idx if idx>=0 else n+idx
        with self.store._connect() as c:
            row=c.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id LIMIT 1 OFFSET ?",(idx,)).fetchone()
        if not row: raise IndexError(key)
        return self.store.get(row[0])
    def __setitem__(self,key,value): raise NotImplementedError("RAG documents are immutable by index; use append/upsert")
    def __delitem__(self,key): raise NotImplementedError("Use source-file incremental ingest")
    def insert(self,index,value): self.append(value)
    def append(self,value): self.store.upsert_legacy_doc(value)
    def clear(self):
        with self.store._connect() as c: c.execute("DELETE FROM chunks")