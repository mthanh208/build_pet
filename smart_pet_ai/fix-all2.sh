#!/usr/bin/env bash
# fix-all-standalone.sh
# Được gộp nguyên văn từ fix1.sh -> fix5.sh

# ==============================================================
# BEGIN: fix1.sh
# ==============================================================
set -euo pipefail

msg() { printf '\n\033[96m%s\033[0m\n' "$*"; }
ok() { printf '\033[92m✅ %s\033[0m\n' "$*"; }
warn() { printf '\033[93m⚠️ %s\033[0m\n' "$*" >&2; }

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(pwd)"

if [[ ! -f core/pet_brain.py ]]; then
  warn "Không tìm thấy core/pet_brain.py. Hãy đặt script này trong thư mục smart_pet_ai."
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BK=".backup_fix_${STAMP}"
mkdir -p "$BK"

for f in main.py core/neural_engine.py core/super_rag.py core/rag2026_store.py core/agent_executor.py core/rag2026_vector_index.py; do
  if [[ -f "$f" ]]; then
    cp -n "$f" "$BK/$(basename "$f")" || true
  fi
done

ok "Backup tại: $BK"

msg "1) Tạo symlink models/current.gguf nếu thiếu"
mkdir -p models
if [[ ! -e models/current.gguf ]]; then
  if [[ -f models/Qwen3-4B-Q4_K_M.gguf ]]; then
    ln -s "Qwen3-4B-Q4_K_M.gguf" models/current.gguf
    ok "Đã tạo models/current.gguf -> Qwen3-4B-Q4_K_M.gguf"
  else
    first="$(find models -maxdepth 1 -type f -name '*.gguf' -printf '%f\n' | sort | head -n 1 || true)"
    if [[ -n "$first" ]]; then
      ln -s "$first" models/current.gguf
      ok "Đã tạo models/current.gguf -> $first"
    else
      warn "Chưa có file .gguf nào trong models/"
    fi
  fi
else
  ok "models/current.gguf đã tồn tại"
fi

msg "2) Ghi core/neural_engine.py bản sửa lỗi tiếng Việt + ẩn thinking"
cat > core/neural_engine.py <<'PY_NEURAL'
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, time, threading
from pathlib import Path

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except Exception:
    Llama = None
    HAS_LLAMA = False

THINK_BLOCK_RE = re.compile(
    r'<think(?:ing)?\b[^>]*>.*?</think(?:ing)?\s*>'
    r'|<reasoning\b[^>]*>.*?</reasoning\s*>'
    r'|<thought\b[^>]*>.*?</thought\s*>'
    r'|<analysis\b[^>]*>.*?</analysis\s*>',
    re.I | re.S
)
THINK_TAG_RE = re.compile(r'</?(?:think(?:ing)?|reasoning|thought|analysis)\b[^>]*>', re.I)
FINAL_MARKER_RE = re.compile(
    r'(?is)(?:===\s*FINAL(?:\s*ANSWER)?\s*===|\[FINAL\]|TRẢ LỜI CUỐI\s*:|CÂU TRẢ LỜI\s*:)'
)
META_REASONING_RE = re.compile(
    r'(?is)^\s*(?:okay,?\s+user|the user|user said|i need to|i should|let me|maybe|we need to|'
    r'the user wants|my response|as an ai|as pet ai|first,? i need|so,? the user)\b'
)
TRANSCRIPT_RE = re.compile(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:', re.I)
CODE_RE = re.compile(
    r'(?m)^\s*(?:`{3}|def |class |import |from |print\(|if __name__|#!/usr/bin/env python)',
    re.I
)

SIMPLE_GREETINGS = {
    'xin chào', 'chào', 'hello', 'hi', 'hey', 'alo', 'chào bạn', 'chào pet',
    'cảm ơn', 'thank you', 'ok', 'okay', 'tạm biệt', 'bye', 'bạn khỏe không',
    'bạn là ai', 'bạn biết gì', 'help', 'trợ giúp'
}

HARD_KEYWORDS = (
    'debug', 'bug', 'lỗi', 'traceback', 'exception', 'refactor', 'tối ưu',
    'optimize', 'thuật toán', 'kiến trúc', 'architecture', 'design pattern',
    'phức tạp', 'chứng minh', 'solve', 'giải phương trình', 'tính tích phân',
    'đạo hàm', 'sql injection', 'reverse engineering', 'exploit'
)

DEEP_TOPICS = (
    'python', 'code', 'sql', 'linux', 'docker', 'regex', 'api', 'database',
    'rag', 'agent', 'toán', 'math', 'logic', 'phân tích', 'so sánh',
    'vì sao', 'tại sao', 'nguyên nhân', 'kiến trúc', 'thiết kế', 'error',
    'exception', 'debug', 'bug', 'function', 'hàm', 'class', 'module'
)

ACTION_WORDS = (
    'hãy', 'giúp', 'viết', 'tạo', 'sửa', 'fix', 'debug', 'phân tích',
    'giải', 'tính', 'so sánh', 'dạy', 'kiểm tra', 'chạy', 'tối ưu',
    'thiết kế', 'refactor', 'review', 'giải thích', 'tìm', 'build', 'setup'
)


def needs_thinking(prompt: str) -> bool:
    s = str(prompt or '').strip()
    if len(s) < 8:
        return False
    low = s.lower()
    if low in SIMPLE_GREETINGS:
        return False
    if any(k in low for k in HARD_KEYWORDS):
        return True
    has_topic = any(k in low for k in DEEP_TOPICS)
    has_action = any(k in low for k in ACTION_WORDS)
    if has_topic and has_action:
        return True
    if len(s) >= 240 or s.count('?') >= 2 or s.count('\n') >= 3:
        return True
    return False


def sanitize(text: str) -> str:
    if not text:
        return ''
    text = str(text).replace('\x00', ' ').strip()
    text = THINK_BLOCK_RE.sub(' ', text)
    text = THINK_TAG_RE.sub(' ', text)

    marks = list(FINAL_MARKER_RE.finditer(text))
    if marks:
        text = text[marks[-1].end():].strip()

    if TRANSCRIPT_RE.search(text):
        matches = re.findall(r'(?:^|\n)\s*(?:Pet|Assistant)\s*:\s*(.+?)(?=\n|$)', text, re.I)
        if matches:
            text = matches[-1]
        else:
            text = re.split(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:\s*', text, flags=re.I)[0]

    text = re.sub(
        r'(?im)^\s*(?:Chain[- ]of[- ]thought|Reasoning|Analysis|Thoughts?|Suy luận|Quá trình suy nghĩ)\s*:\s*',
        '',
        text
    )
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    if META_REASONING_RE.match(text):
        m = CODE_RE.search(text)
        if m:
            return text[m.start():].strip()
        return ''

    return text


class NeuralEngine:
    def __init__(self, model_path=None):
        root = Path(__file__).resolve().parents[1]
        self.root = root
        self.models_dir = root / 'models'
        env = os.environ.get('PET_GGUF_MODEL', '').strip()
        if env:
            self.model_path = Path(env).expanduser()
        elif model_path:
            self.model_path = Path(model_path).expanduser()
        else:
            self.model_path = self.models_dir / 'current.gguf'

        self.model_loaded = False
        self.llm = None
        self.last_stats = None
        self._load_error = None
        self._lock = threading.RLock()
        self.last_thinking = False
        self.last_reasoning_hidden = ''
        self.available = self._resolve_model() is not None

    def _resolve_model(self):
        p = Path(self.model_path)
        if p.is_file() and p.suffix.lower() == '.gguf':
            return p.resolve()
        alias = self.models_dir / 'current.gguf'
        if alias.is_file():
            return alias.resolve()
        ggufs = sorted(self.models_dir.glob('*.gguf'))
        return ggufs[0].resolve() if ggufs else None

    def _load(self):
        if self.model_loaded and self.llm is not None:
            return True
        if not HAS_LLAMA:
            self._load_error = 'llama_cpp chưa được cài'
            return False
        with self._lock:
            if self.model_loaded and self.llm is not None:
                return True
            p = self._resolve_model()
            if p is None:
                self._load_error = 'Không tìm thấy file .gguf trong models/'
                self.available = False
                return False
            self.model_path = p
            try:
                kwargs = dict(
                    model_path=str(p),
                    n_ctx=int(os.environ.get('PET_LLM_CTX', '2048')),
                    n_threads=int(os.environ.get('PET_LLM_THREADS', '4')),
                    n_batch=int(os.environ.get('PET_LLM_BATCH', '256')),
                    use_mmap=True,
                    use_mlock=False,
                    verbose=False
                )
                try:
                    self.llm = Llama(n_gpu_layers=int(os.environ.get('PET_LLM_GPU_LAYERS', '0')), **kwargs)
                except TypeError:
                    self.llm = Llama(**kwargs)
                self.model_loaded = True
                self.available = True
                self._load_error = None
                print(f'🧠 Neural Engine (lazy GGUF) đã tải: {p.name}')
                return True
            except Exception as e:
                self._load_error = str(e)
                self.model_loaded = False
                self.available = False
                print(f'⚠️ Lỗi tải GGUF: {e}')
                return False

    def _system(self, thinking: bool) -> str:
        if thinking:
            mode = (
                'Đây là câu hỏi khó. Bạn được phép suy luận nội bộ nhiều bước, nhưng suy luận đó là NỘI BỘ, '
                'tuyệt đối không hiển thị. Chỉ hiển thị câu trả lời cuối cùng.'
            )
        else:
            mode = (
                'Đây là câu hỏi thường. Trả lời trực tiếp, ngắn gọn, tự nhiên, không mô tả quá trình suy nghĩ.'
            )
        return (
            'Bạn là Pet AI chạy local trên máy người dùng. BẮT BUỘC trả lời bằng tiếng Việt tự nhiên, thân thiện. '
            'Chỉ giữ nguyên tiếng Anh cho tên riêng, tên hàm, tên thư viện, mã lỗi, cú pháp lập trình khi cần thiết. '
            'Không bao giờ mở đầu bằng "Okay", "Let us", "The user", "I need" hoặc mô tả người dùng. '
            'Không bịa thông tin; nếu thiếu dữ liệu, nói rõ là chưa biết. ' + mode + ' '
            'Không in thẻ <think>, <analysis>, <reasoning>, chain-of-thought. '
            'Nếu cần đánh dấu câu trả lời cuối, bắt đầu bằng "=== FINAL ANSWER ===" rồi viết câu trả lời cuối cùng.'
        )

    def generate(self, prompt, max_tokens=160, temperature=0.7, stop=None, thinking=None):
        if not self._load() or self.llm is None:
            return None

        if thinking is None:
            thinking = needs_thinking(prompt)

        # Mặc định tắt thinking để nhanh và tránh leak tiếng Anh.
        # Muốn bật lại: export PET_FORCE_NO_THINK=0
        if os.environ.get('PET_FORCE_NO_THINK', '1') not in ('', '0', 'false', 'no', 'off'):
            thinking = False

        self.last_thinking = thinking
        limit = int(max_tokens or 160)
        limit = min(limit, 640 if thinking else 240)
        stops = list(stop or ['<|im_end|>', '<|endoftext|>'])
        started = time.perf_counter()

        def call(think_flag, user_text, token_limit):
            system = self._system(think_flag)
            if hasattr(self.llm, 'create_chat_completion'):
                msgs = [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': str(user_text)}
                ]
                kw = dict(
                    messages=msgs,
                    max_tokens=int(token_limit),
                    temperature=float(temperature),
                    stop=stops
                )
                try:
                    r = self.llm.create_chat_completion(**kw, chat_template_kwargs={'enable_thinking': bool(think_flag)})
                except (TypeError, ValueError):
                    r = self.llm.create_chat_completion(**kw)
                choices = (r.get('choices') or []) if isinstance(r, dict) else []
                if choices:
                    msg = choices[0].get('message') or {}
                    hidden = str(msg.get('reasoning_content') or msg.get('reasoning') or '')
                    content = str(msg.get('content') or choices[0].get('text') or '')
                    return content, hidden

            mode = '/think' if think_flag else '/no_think'
            full = system + '\n' + mode + '\n' + str(user_text)
            r = self.llm(full, max_tokens=int(token_limit), temperature=float(temperature), stop=stops, echo=False)
            choices = (r.get('choices') or []) if isinstance(r, dict) else []
            if choices:
                return str(choices[0].get('text') or ''), ''
            return '', ''

        try:
            raw, hidden = call(thinking, prompt, limit)
            self.last_reasoning_hidden = hidden
            clean = sanitize(raw)
            raw_code_like = bool(CODE_RE.search(raw or ''))
            meta_leak = bool(META_REASONING_RE.match((raw or '').strip()))

            if (not clean or meta_leak) and not raw_code_like:
                final_prompt = (
                    'Hãy trả lời trực tiếp yêu cầu sau bằng tiếng Việt. Không mô tả quá trình suy nghĩ. '
                    'Không mở đầu bằng Okay/Let us/The user/I need. Chỉ đưa câu trả lời cuối cùng.\n'
                    'Yêu cầu: ' + str(prompt)
                )
                raw2, hidden2 = call(False, final_prompt, limit)
                self.last_reasoning_hidden = (self.last_reasoning_hidden + '\n' + hidden2).strip()
                clean2 = sanitize(raw2)
                if clean2:
                    clean = clean2

            if not clean and raw_code_like:
                m = CODE_RE.search(raw or '')
                if m:
                    clean = raw[m.start():].strip()

            elapsed = time.perf_counter() - started
            tokens = len(clean.split()) if clean else 0
            self.last_stats = {
                'tokens': tokens,
                'time': round(elapsed, 3),
                'tok_per_sec': round(tokens / elapsed, 1) if elapsed and tokens else 0.0,
                'model_loaded': True,
                'thinking': thinking,
                'reasoning_hidden': bool(self.last_reasoning_hidden)
            }
            return clean or None
        except Exception as e:
            self.last_stats = None
            self._load_error = str(e)
            return None

    def stats(self):
        p = self._resolve_model()
        return {
            'available': bool(self.available),
            'backend': HAS_LLAMA,
            'model_loaded': bool(self.model_loaded),
            'model_exists': bool(p),
            'model_path': str(p or self.model_path),
            'error': self._load_error,
            'thinking_last': bool(self.last_thinking)
        }

    def close(self):
        with self._lock:
            self.llm = None
            self.model_loaded = False
PY_NEURAL

ok "core/neural_engine.py đã được cập nhật"

msg "3) Tạo core/rag2026_vector_index.py — persistent/mmap vector index"
cat > core/rag2026_vector_index.py <<'PY_VECTOR'
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
PY_VECTOR

ok "core/rag2026_vector_index.py đã được tạo"

msg "4) Ghi core/super_rag.py bản hybrid RRF + vector index + MMR"
cat > core/super_rag.py <<'PY_SUPERRAG'
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
PY_SUPERRAG

ok "core/super_rag.py đã được cập nhật"

msg "5) Vá core/agent_executor.py: an toàn sandbox + giảm độ chậm code agent"
python3 - <<'PY_AGENT_PATCH'
from pathlib import Path
import re

p = Path('core/agent_executor.py')
if not p.exists():
    print('agent_executor.py không tồn tại, bỏ qua')
    raise SystemExit(0)

t = p.read_text(encoding='utf-8')
orig = t

# Không cho bypass static safety
t = t.replace('safe=False', 'safe=True')

# Giảm max_tokens sinh code để nhanh hơn trên CPU yếu
t = re.sub(
    r'engine\.generate\(prompt,\s*max_tokens=800,\s*temperature=0\.2',
    'engine.generate(prompt,max_tokens=320,temperature=0.2,thinking=False',
    t
)

# Giảm số lần retry để không mất quá lâu
t = t.replace('for attempt in range(3):', 'for attempt in range(2):')

if t != orig:
    p.write_text(t, encoding='utf-8')
    print('AGENT_PATCHED=1')
else:
    print('AGENT_PATCHED=0')
PY_AGENT_PATCH

ok "Đã vá agent_executor.py"

msg "6) Tắt dream in ra terminal trong main.py nếu có"
python3 - <<'PY_MAIN_DREAM'
from pathlib import Path
p = Path('main.py')
if p.exists():
    t = p.read_text(encoding='utf-8')
    t = t.replace('pet.dream_engine.start()', '# pet.dream_engine.start()  # disabled terminal dream output')
    p.write_text(t, encoding='utf-8')
    print('MAIN_DREAM_DISABLED=1')
else:
    print('MAIN_NOT_FOUND')
PY_MAIN_DREAM

msg "7) Biên dịch kiểm tra syntax"
python3 -m py_compile core/neural_engine.py core/rag2026_vector_index.py core/super_rag.py core/agent_executor.py
ok "Syntax core OK"

python3 -m py_compile main.py || warn "main.py có thể đã bị sửa từ trước, cần kiểm tra thêm"

msg "8) Chạy test sanitize / needs_thinking / NeuralEngine"
PYTHONPATH="$ROOT" python3 - <<'PY_TEST_THINK'
from core.neural_engine import sanitize, needs_thinking, NeuralEngine

assert sanitize('<think>secret</think>Xin chào!').startswith('Xin chào')
assert sanitize('Okay, user said hello. === FINAL ANSWER === Xin chào!') == 'Xin chào!'
assert needs_thinking('xin chào') is False
assert needs_thinking('hãy phân tích lợi ích Python này') is True

n = NeuralEngine()
assert n.model_loaded is False
assert 'tiếng Việt' in n._system(False)
assert 'tiếng Việt' in n._system(True)

print('THINKING_HIDDEN=PASS')
print('AUTO_THINK_POLICY=PASS')
print('VIETNAMESE_SYSTEM=PASS')
PY_TEST_THINK

msg "9) Chạy test RAG 2026 + hybrid retrieval"
PYTHONPATH="$ROOT" python3 - <<'PY_TEST_RAG'
from pathlib import Path
from core.rag2026_store import RAGStore
from core.super_rag import SuperRAG

root = Path('.').resolve()
store = RAGStore(root)

class P:
    PROJECT_ROOT = root
    rag2026 = store
    vector_search = None

p = P()
sr = SuperRAG(p)
sr.build()

print('RAG_SQLITE_OK chunks=', store.count)
stats = sr.stats()
print('EMBEDDING_VERSION=', stats.get('embedding_version'))
if 'vector_index' in stats:
    print('VECTOR_INDEX=', stats['vector_index'])

res = sr.retrieve('python là gì', top_n=3)
print('HYBRID_RETRIEVAL_DOCS=', len(res))
PY_TEST_RAG

msg "10) Chạy test UI cũ nếu tồn tại"
if [[ -f tests/test_ui_thinking.py ]]; then
  PYTHONPATH="$ROOT" python3 tests/test_ui_thinking.py || warn "tests/test_ui_thinking.py chưa pass hoàn toàn"
else
  warn "Không có tests/test_ui_thinking.py"
fi

msg "11) Kiểm tra file quan trọng"
PYTHONPATH="$ROOT" python3 - <<'PY_FINAL_CHECK'
from pathlib import Path
import sqlite3

root = Path('.')
must = [
    root/'main.py',
    root/'core'/'pet_brain.py',
    root/'core'/'neural_engine.py',
    root/'core'/'super_rag.py',
    root/'core'/'rag2026_store.py',
    root/'core'/'rag2026_vector_index.py',
    root/'data_memory'/'rag2026.sqlite3',
]
missing = [str(p) for p in must if not p.exists()]
assert not missing, missing

c = sqlite3.connect(root/'data_memory'/'rag2026.sqlite3')
assert c.execute("select 1 from sqlite_master where name='chunk_fts'").fetchone()
print('SQLITE_FTS5=PASS')
print('CHUNK_COUNT=', c.execute('select count(*) from chunks').fetchone()[0])

alias = root/'models'/'current.gguf'
print('MODEL_ALIAS_EXISTS=', alias.exists())
if alias.exists():
    print('MODEL_ALIAS_PATH=', alias.resolve())
PY_FINAL_CHECK

ok "HOÀN TẤT. Chạy: ./pet.sh"

# ============================================================== 
# END: fix1.sh
# ============================================================== 


# ==============================================================
# BEGIN: fix2.sh
# ==============================================================
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f core/pet_brain.py ]]; then
  echo "❌ Hãy đặt script này trong thư mục smart_pet_ai"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BK=".backup_qwen3_vi_${STAMP}"
mkdir -p "$BK"

cp -f core/neural_engine.py "$BK/neural_engine.py" 2>/dev/null || true
echo "✅ Backup core/neural_engine.py vào $BK"

cat > core/neural_engine.py <<'PY_NEURAL'
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, time, threading
from pathlib import Path

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except Exception:
    Llama = None
    HAS_LLAMA = False

THINK_BLOCK_RE = re.compile(
    r'<think(?:ing)?\b[^>]*>.*?</think(?:ing)?\s*>'
    r'|<reasoning\b[^>]*>.*?</reasoning\s*>'
    r'|<thought\b[^>]*>.*?</thought\s*>'
    r'|<analysis\b[^>]*>.*?</analysis\s*>',
    re.I | re.S
)

THINK_TAG_RE = re.compile(
    r'</?(?:think(?:ing)?|reasoning|thought|analysis)\b[^>]*>',
    re.I
)

FINAL_MARKER_RE = re.compile(
    r'(?is)(?:===\s*FINAL(?:\s*ANSWER)?\s*===|\[FINAL\]|TRẢ LỜI CUỐI\s*:|CÂU TRẢ LỜI\s*:)'
)

TRANSCRIPT_RE = re.compile(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:', re.I)

META_START_RE = re.compile(
    r'(?is)^\s*(?:'
    r'okay[,.!]?\s+(?:so\s+)?(?:the\s+)?user\b'
    r'|the\s+user\b'
    r'|user\s+said\b'
    r'|i\s+need\s+to\b'
    r'|i\s+should\b'
    r'|let\s+me\b'
    r'|maybe\s+'
    r'|we\s+need\s+to\b'
    r'|my\s+response\b'
    r'|as\s+an\s+ai\b'
    r'|as\s+pet\s+ai\b'
    r'|first,?\s+i\b'
    r'|so,?\s+the\s+user\b'
    r'|i\s+am\s+going\s+to\b'
    r'|i\s+will\b'
    r')'
)

CODE_RE = re.compile(
    r'(?m)^\s*(?:`{3}|def |class |import |from |print\(|if __name__|#!/usr/bin/env python)',
    re.I
)

VI_DIACRITICS_RE = re.compile(
    r'[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễễìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]',
    re.I
)

_META_PHRASES = (
    'the user is asking',
    'user is asking',
    'i need to respond',
    'let me start',
    'i should list',
    'make sure to',
    'user asked',
    'i need to',
    'i should',
    'let me',
    'my response',
    'as an ai',
    'as pet ai'
)

SIMPLE_GREETINGS = {
    'xin chào', 'chào', 'hello', 'hi', 'hey', 'alo', 'chào bạn',
    'cảm ơn', 'thank you', 'ok', 'okay', 'tạm biệt', 'bye',
    'bạn khỏe không', 'bạn là ai', 'help', 'trợ giúp'
}

HARD_KEYWORDS = (
    'debug', 'bug', 'lỗi', 'traceback', 'exception', 'refactor',
    'tối ưu', 'optimize', 'thuật toán', 'kiến trúc', 'architecture',
    'design pattern', 'phức tạp', 'chứng minh', 'solve',
    'giải phương trình', 'tích phân', 'đạo hàm', 'sql injection'
)

DEEP_TOPICS = (
    'python', 'code', 'sql', 'linux', 'docker', 'regex', 'api',
    'database', 'rag', 'agent', 'toán', 'math', 'logic',
    'phân tích', 'so sánh', 'vì sao', 'tại sao', 'nguyên nhân',
    'kiến trúc', 'thiết kế', 'error', 'exception', 'debug', 'bug',
    'function', 'hàm', 'class', 'module'
)

ACTION_WORDS = (
    'hãy', 'giúp', 'viết', 'tạo', 'sửa', 'fix', 'debug', 'phân tích',
    'giải', 'tính', 'so sánh', 'dạy', 'kiểm tra', 'chạy', 'tối ưu',
    'thiết kế', 'refactor', 'review', 'giải thích', 'tìm', 'build', 'setup'
)


def needs_thinking(prompt: str) -> bool:
    s = str(prompt or '').strip()
    if len(s) < 8:
        return False

    low = s.lower()
    if low in SIMPLE_GREETINGS:
        return False

    if any(k in low for k in HARD_KEYWORDS):
        return True

    has_topic = any(k in low for k in DEEP_TOPICS)
    has_action = any(k in low for k in ACTION_WORDS)

    if has_topic and has_action:
        return True

    if len(s) >= 240 or s.count('?') >= 2 or s.count('\n') >= 3:
        return True

    return False


def _is_meta_reasoning(text: str) -> bool:
    t = str(text or '').strip()
    if not t:
        return False

    if META_START_RE.match(t):
        return True

    first = t[:400].lower()
    return any(p in first for p in _META_PHRASES)


def _looks_mostly_english(text: str) -> bool:
    t = str(text or '').strip()
    words = re.findall(r'[A-Za-zÀ-ỹ]+', t)
    if len(words) < 10:
        return False

    vi = sum(1 for w in words if VI_DIACRITICS_RE.search(w))
    ratio = vi / float(max(1, len(words)))
    return ratio < 0.12


def _extract_code(text: str) -> str:
    t = str(text or '')
    m = CODE_RE.search(t)
    return t[m.start():].strip() if m else ''


def sanitize(text: str) -> str:
    if not text:
        return ''

    text = str(text).replace('\x00', ' ').replace('\r', ' ').strip()

    text = THINK_BLOCK_RE.sub(' ', text)
    text = THINK_TAG_RE.sub(' ', text)

    marks = list(FINAL_MARKER_RE.finditer(text))
    if marks:
        text = text[marks[-1].end():].strip()

    # Bỏ tiền tố Pet/Assistant nếu model tự lặp nhãn.
    text = re.sub(r'(?im)^\s*(?:Pet|Assistant)\s*:\s*', '', text, count=1)

    if TRANSCRIPT_RE.search(text):
        matches = re.findall(
            r'(?:^|\n)\s*(?:Pet|Assistant)\s*:\s*(.+?)(?=\n|$)',
            text,
            re.I
        )
        if matches:
            text = matches[-1]
        else:
            text = re.split(
                r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:\s*',
                text,
                flags=re.I
            )[0]

    text = re.sub(
        r'(?im)^\s*(?:Chain[- ]of[- ]thought|Reasoning|Analysis|Thoughts?|Suy luận|Quá trình suy nghĩ)\s*:\s*',
        '',
        text
    )

    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    if _is_meta_reasoning(text):
        code = _extract_code(text)
        return code if code else ''

    return text


class NeuralEngine:
    def __init__(self, model_path=None):
        root = Path(__file__).resolve().parents[1]
        self.root = root
        self.models_dir = root / 'models'

        env = os.environ.get('PET_GGUF_MODEL', '').strip()
        if env:
            self.model_path = Path(env).expanduser()
        elif model_path:
            self.model_path = Path(model_path).expanduser()
        else:
            self.model_path = self.models_dir / 'current.gguf'

        self.model_loaded = False
        self.llm = None
        self.last_stats = None
        self._load_error = None
        self._lock = threading.RLock()
        self.last_thinking = False
        self.last_reasoning_hidden = ''
        self.available = self._resolve_model() is not None

    def _resolve_model(self):
        p = Path(self.model_path)
        if p.is_file() and p.suffix.lower() == '.gguf':
            return p.resolve()

        alias = self.models_dir / 'current.gguf'
        if alias.is_file():
            return alias.resolve()

        ggufs = sorted(self.models_dir.glob('*.gguf'))
        return ggufs[0].resolve() if ggufs else None

    def _load(self):
        if self.model_loaded and self.llm is not None:
            return True

        if not HAS_LLAMA:
            self._load_error = 'llama_cpp chưa được cài'
            return False

        with self._lock:
            if self.model_loaded and self.llm is not None:
                return True

            p = self._resolve_model()
            if p is None:
                self._load_error = 'Không tìm thấy file .gguf trong models/'
                self.available = False
                return False

            self.model_path = p

            try:
                kwargs = dict(
                    model_path=str(p),
                    n_ctx=int(os.environ.get('PET_LLM_CTX', '2048')),
                    n_threads=int(os.environ.get('PET_LLM_THREADS', '4')),
                    n_batch=int(os.environ.get('PET_LLM_BATCH', '512')),
                    use_mmap=True,
                    verbose=False
                )

                try:
                    self.llm = Llama(
                        n_gpu_layers=int(os.environ.get('PET_LLM_GPU_LAYERS', '0')),
                        **kwargs
                    )
                except TypeError:
                    try:
                        self.llm = Llama(**kwargs)
                    except TypeError:
                        minimal = dict(
                            model_path=str(p),
                            n_ctx=kwargs['n_ctx'],
                            n_threads=kwargs['n_threads'],
                            verbose=False
                        )
                        self.llm = Llama(**minimal)

                self.model_loaded = True
                self.available = True
                self._load_error = None
                print(f'🧠 Neural Engine (lazy GGUF) đã tải: {p.name}')
                return True
            except Exception as e:
                self._load_error = str(e)
                self.model_loaded = False
                self.available = False
                print(f'⚠️ Lỗi tải GGUF: {e}')
                return False

    def _system(self, thinking: bool) -> str:
        if thinking:
            mode = (
                'Đây là câu hỏi khó. Bạn được phép suy luận nội bộ nhiều bước, '
                'nhưng suy luận đó là NỘI BỘ, tuyệt đối không hiển thị. '
                'Chỉ hiển thị câu trả lời cuối cùng.'
            )
        else:
            mode = (
                'Đây là câu hỏi thường. Trả lời trực tiếp, ngắn gọn, tự nhiên, '
                'không mô tả quá trình suy nghĩ.'
            )

        return (
            'Bạn là Pet AI chạy local trên máy người dùng. '
            'BẮT BUỘC trả lời bằng tiếng Việt tự nhiên, thân thiện. '
            'Chỉ giữ nguyên tiếng Anh cho tên riêng, tên hàm, tên thư viện, mã lỗi, cú pháp lập trình khi cần thiết. '
            'Không bao giờ mở đầu bằng "Okay", "Let us", "The user", "I need" hoặc mô tả người dùng. '
            'Không bịa thông tin; nếu thiếu dữ liệu, nói rõ là chưa biết. '
            + mode +
            ' Không in thẻ <think>, <analysis>, <reasoning>, chain-of-thought. '
            'Nếu cần đánh dấu câu trả lời cuối, bắt đầu bằng "=== FINAL ANSWER ===" rồi viết câu trả lời cuối cùng.'
        )

    def generate(self, prompt, max_tokens=160, temperature=0.7, stop=None, thinking=None):
        if not self._load() or self.llm is None:
            return None

        if thinking is None:
            thinking = needs_thinking(prompt)

        # Mặc định tắt thinking để nhanh và tránh leak.
        # Muốn bật lại: export PET_FORCE_NO_THINK=0
        if os.environ.get('PET_FORCE_NO_THINK', '1') not in ('', '0', 'false', 'no', 'off'):
            thinking = False

        self.last_thinking = thinking
        started = time.perf_counter()

        limit = max(32, min(int(max_tokens or 160), 900))

        stops = list(stop or [])
        for s in ['<|im_end|>', '<|endoftext|>']:
            if s not in stops:
                stops.append(s)
        stops = list(dict.fromkeys(stops))

        def call(think_flag, user_text, token_limit, temp):
            mode = '/think' if think_flag else '/no_think'
            user = mode + '\n' + str(user_text).strip()
            system = self._system(think_flag)

            if hasattr(self.llm, 'create_chat_completion'):
                msgs = [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user}
                ]

                kw = dict(
                    messages=msgs,
                    max_tokens=int(token_limit),
                    temperature=float(temp),
                    stop=stops
                )

                try:
                    r = self.llm.create_chat_completion(
                        **kw,
                        chat_template_kwargs={'enable_thinking': bool(think_flag)}
                    )
                except (TypeError, ValueError):
                    try:
                        r = self.llm.create_chat_completion(
                            **kw,
                            chat_template_kwargs={'thinking': bool(think_flag)}
                        )
                    except (TypeError, ValueError):
                        r = self.llm.create_chat_completion(**kw)

                choices = (r.get('choices') or []) if isinstance(r, dict) else []
                if choices:
                    msg = choices[0].get('message') or {}
                    hidden = str(msg.get('reasoning_content') or msg.get('reasoning') or '')
                    content = str(msg.get('content') or choices[0].get('text') or '')
                    return content, hidden

            resp = self.llm(
                system + '\n' + user,
                max_tokens=int(token_limit),
                temperature=float(temp),
                stop=stops,
                echo=False
            )

            choices = (resp.get('choices') or []) if isinstance(resp, dict) else []
            if choices:
                return str(choices[0].get('text') or ''), ''

            return '', ''

        try:
            raw, hidden = call(thinking, prompt, limit, temperature)
            self.last_reasoning_hidden = hidden
            clean = sanitize(raw)

            raw_code_like = bool(CODE_RE.search(raw or ''))
            suspicious = (
                (not clean)
                or _is_meta_reasoning(raw)
                or _is_meta_reasoning(clean)
                or (_looks_mostly_english(clean) and not raw_code_like)
            )

            if suspicious and not raw_code_like:
                final_prompt = (
                    'Hãy trả lời trực tiếp yêu cầu sau bằng tiếng Việt, ngắn gọn, tự nhiên. '
                    'KHÔNG mô tả suy nghĩ, KHÔNG nói về người dùng, '
                    'KHÔNG mở đầu bằng Okay/Let me/I need/The user. '
                    'Chỉ đưa câu trả lời cuối cùng. Nếu yêu cầu là code, chỉ trả về code cần thiết.'
                    '\nYêu cầu: ' + str(prompt)
                )

                raw2, hidden2 = call(
                    False,
                    final_prompt,
                    min(limit, 300),
                    min(float(temperature), 0.25)
                )

                self.last_reasoning_hidden = (
                    self.last_reasoning_hidden + '\n\n' + hidden2
                ).strip()

                clean2 = sanitize(raw2)
                if clean2:
                    clean = clean2
                elif CODE_RE.search(raw2 or ''):
                    clean = _extract_code(raw2)

            if not clean and raw_code_like:
                clean = _extract_code(raw)

            elapsed = time.perf_counter() - started
            tokens = len(clean.split()) if clean else 0

            self.last_stats = {
                'tokens': tokens,
                'time': round(elapsed, 3),
                'tok_per_sec': round(tokens / elapsed, 1) if elapsed and tokens else 0.0,
                'model_loaded': True,
                'thinking': thinking,
                'reasoning_hidden': bool(self.last_reasoning_hidden)
            }

            return clean if clean else None

        except Exception as e:
            self.last_stats = None
            self._load_error = str(e)
            return None

    def stats(self):
        p = self._resolve_model()
        return {
            'available': bool(self.available),
            'backend': HAS_LLAMA,
            'model_loaded': bool(self.model_loaded),
            'model_exists': bool(p),
            'model_path': str(p or self.model_path),
            'error': self._load_error,
            'thinking_last': bool(self.last_thinking)
        }

    def close(self):
        with self._lock:
            self.llm = None
            self.model_loaded = False
PY_NEURAL

echo "✅ Đã ghi core/neural_engine.py bản cứng hơn"

find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

python3 -m py_compile core/neural_engine.py
echo "✅ Syntax core/neural_engine.py OK"

PYTHONPATH=. python3 - <<'PY'
from core.neural_engine import sanitize, needs_thinking, NeuralEngine

bad = (
    "Okay, the user is asking what I know about Python. "
    "I need to respond in a friendly and concise manner. "
    "Let me start by mentioning that I can help with Python-related questions. "
    "I should list some key points like Python being a high-level language, "
    "its use in various fields, and maybe mention some features like simplicity and readability. "
    "Also, I should invite the user to ask specific questions. "
    "Make sure to keep it natural and not too technical. "
    "Avoid any markdown and keep it in Vietnamese"
)

assert sanitize(bad) == ''
assert sanitize('<think>secret</think>Xin chào!') == 'Xin chào!'
assert sanitize('Okay, user said hello. === FINAL ANSWER === Xin chào!') == 'Xin chào!'
assert sanitize('=== FINAL ANSWER ===\nPython là ngôn ngữ dễ đọc.') == 'Python là ngôn ngữ dễ đọc.'

assert needs_thinking('xin chào') is False
assert needs_thinking('bạn biết gì về python') is False
assert needs_thinking('hãy phân tích lợi ích Python này') is True

n = NeuralEngine()
assert not n.model_loaded
assert 'tiếng Việt' in n._system(False)
assert 'tiếng Việt' in n._system(True)

print('QWEN3_VI_PATCH_TESTS=PASS')
PY

if [[ -f tests/test_ui_thinking.py ]]; then
  PYTHONPATH=. python3 tests/test_ui_thinking.py || echo '⚠️ tests/test_ui_thinking.py chưa pass hoàn toàn'
fi

echo ""
echo "✅ HOÀN TẤT. Chạy lại: ./pet.sh"
echo "   Mặc định đang tắt thinking: PET_FORCE_NO_THINK=1"
echo "   Muốn bật thinking cho câu khó: export PET_FORCE_NO_THINK=0"

# ============================================================== 
# END: fix2.sh
# ============================================================== 


# ==============================================================
# BEGIN: fix3.sh
# ==============================================================
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f core/secure_sandbox.py ]]; then
  echo "❌ Không tìm thấy core/secure_sandbox.py. Hãy đặt script này trong thư mục smart_pet_ai."
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BK=".backup_relax_sandbox_fixed_${STAMP}"
mkdir -p "$BK"

cp -f core/secure_sandbox.py "$BK/secure_sandbox.py"
cp -f data_memory/sandbox_policy.json "$BK/sandbox_policy.json" 2>/dev/null || true
cp -f core/agent_executor.py "$BK/agent_executor.py" 2>/dev/null || true

echo "✅ Backup: $BK"

cat > core/secure_sandbox.py <<'PY_SECURE'
# -*- coding: utf-8 -*-
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time


BLOCKED_IMPORTS = {
    "socket",
    "requests",
    "urllib",
    "urllib3",
    "httpx",
    "ctypes",
    "pty",
    "telnetlib",
    "paramiko",
    "ftplib",
    "nntplib",
}

DELETE_CALLS = {
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("shutil", "rmtree"),
}

MOVE_CALLS = {
    ("os", "rename"),
    ("os", "replace"),
    ("shutil", "move"),
}

SUBPROCESS_CALLS = {
    "run",
    "call",
    "check_call",
    "check_output",
    "Popen",
    "getoutput",
    "getstatusoutput",
}

DELETE_METHODS = {"unlink", "rmdir"}

DANGEROUS_RES = [
    re.compile(r"\bsudo\b"),
    re.compile(r"\bdoas\b"),
    re.compile(r"\bpkexec\b"),
    re.compile(r"\bsu\b"),
    re.compile(r"\bdd\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bfdisk\b"),
    re.compile(r"\bparted\b"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
    re.compile(r"\bpoweroff\b"),
    re.compile(r"\binit\s+[06]\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"\bservice\b"),
    re.compile(r"\biptables\b"),
    re.compile(r"\bufw\b"),
    re.compile(r"\bnft\b"),
    re.compile(r"\buseradd\b"),
    re.compile(r"\buserdel\b"),
    re.compile(r"\busermod\b"),
    re.compile(r"\bpasswd\b"),
    re.compile(r"\bchown\b"),
    re.compile(r"\bchmod\s+(-[a-z]+\s+)*777\s+/"),
    re.compile(r"\bcurl\b.*\|\s*(ba|z)?sh"),
    re.compile(r"\bwget\b.*\|\s*(ba|z)?sh"),
    re.compile(r"\bapt(-get)?\b"),
    re.compile(r"\bdpkg\b"),
    re.compile(r"\bsnap\b"),
    re.compile(r"\bflatpak\b"),
    re.compile(r"\bpip3?\s+install\b"),
    re.compile(r"\bnpm\s+install\s+-g\b"),
    re.compile(r"\byarn\s+global\b"),
    re.compile(r"\bkillall\b"),
    re.compile(r"\bpkill\b"),
    re.compile(r"\bkill\s+1\b"),
    re.compile(r"\bkill\s+-9\s+1\b"),
]

RM_COMMANDS = {"rm", "rmdir", "unlink", "shred"}


class SecurityViolation(Exception):
    pass


def _clean_token(tok):
    return str(tok or "").strip().strip("'\"")


def _is_safe_workspace_path(value):
    s = str(value or "").replace("\\", "/")
    if not s:
        return False

    if ".." in s.split("/"):
        return False

    if s.startswith("~") or s.startswith("$"):
        return False

    if os.path.isabs(s):
        return s.startswith("/workspace/")

    return True


def _is_dangerous_command_text(text):
    low = str(text or "").lower()

    for rx in DANGEROUS_RES:
        if rx.search(low):
            return True

    tokens = [_clean_token(t) for t in re.findall(r"[^\s;|&]+", low)]

    for i, tok in enumerate(tokens):
        if tok in RM_COMMANDS:
            for target in tokens[i + 1:]:
                target = _clean_token(target)

                if not target:
                    continue

                if target.startswith("-"):
                    continue

                if target in {"/", "~", "$home", ".."}:
                    return True

                if target.startswith("~") or target.startswith("$"):
                    return True

                if ".." in target.split("/"):
                    return True

                if target.startswith("/"):
                    if target.startswith("/workspace/"):
                        continue
                    return True

    return False


def _call_target(node):
    f = node.func

    if isinstance(f, ast.Name):
        return ("", f.id)

    if isinstance(f, ast.Attribute):
        if isinstance(f.value, ast.Name):
            return (f.value.id, f.attr)

        if isinstance(f.value, ast.Call) and isinstance(f.value.func, ast.Name):
            return (f.value.func.id, f.attr)

    return ("", "")


def static_scan(source):
    findings = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"safe": False, "syntax_error": str(e), "findings": ["invalid_python"]}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_IMPORTS:
                    findings.append("blocked import: " + alias.name)

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_IMPORTS:
                findings.append("blocked import: " + str(node.module))

        elif isinstance(node, ast.Call):
            pair = _call_target(node)

            if pair in DELETE_CALLS:
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if not _is_safe_workspace_path(arg.value):
                            findings.append("delete outside sandbox: " + arg.value)

            if isinstance(node.func, ast.Attribute) and node.func.attr in DELETE_METHODS:
                owner = node.func.value
                path_node = None

                if isinstance(owner, ast.Call) and owner.args:
                    path_node = owner.args[0]
                elif node.args:
                    path_node = node.args[0]

                if path_node is not None and isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
                    if not _is_safe_workspace_path(path_node.value):
                        findings.append("delete outside sandbox: " + path_node.value)

            if pair in MOVE_CALLS:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        if not _is_safe_workspace_path(sub.value):
                            findings.append("move/rename outside sandbox: " + sub.value)

            if pair[0] == "subprocess" and pair[1] in SUBPROCESS_CALLS:
                # Scan literal strings anywhere inside the subprocess call.
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        if _is_dangerous_command_text(sub.value):
                            findings.append(
                                "dangerous shell command: " + sub.value[:120]
                            )

                # Also inspect command lists/tuples such as:
                # subprocess.run(["rm", "-rf", "/home"])
                # The previous implementation only inspected each Constant
                # independently, so "rm" and "/home" could evade the check.
                for arg in node.args:
                    if isinstance(arg, (ast.List, ast.Tuple)):
                        values = []
                        all_literal_strings = True

                        for item in arg.elts:
                            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                                values.append(item.value)
                            else:
                                all_literal_strings = False
                                break

                        if all_literal_strings and values:
                            command_text = " ".join(values)
                            if _is_dangerous_command_text(command_text):
                                findings.append(
                                    "dangerous subprocess command: "
                                    + command_text[:120]
                                )

                # shell=True makes command construction shell-dependent and
                # defeats the intent of a filtered subprocess interface.
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        findings.append("subprocess shell=True is blocked")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_dangerous_command_text(node.value):
                findings.append("dangerous command text: " + node.value[:120])

    return {"safe": not findings, "syntax_error": None, "findings": findings}


class SecureSandbox:
    def __init__(self, root, workspace=None):
        self.project_root = Path(root).resolve()

        if workspace:
            self.workspace = Path(workspace).resolve()
        else:
            self.workspace = self.project_root / "data_memory" / "sandbox_workspace"

        self.workspace.mkdir(parents=True, exist_ok=True)

        self.artifacts_dir = self.workspace / "artifacts"
        self.runs_dir = self.workspace / "runs"
        self.reports_dir = self.workspace / "reports"

        for p in (self.artifacts_dir, self.runs_dir, self.reports_dir):
            p.mkdir(parents=True, exist_ok=True)

        self.bwrap = shutil.which("bwrap")
        self.python = os.environ.get("PET_SANDBOX_PYTHON") or shutil.which("python3") or "/usr/bin/python3"
        self.timeout_seconds = int(os.environ.get("PET_SANDBOX_TIMEOUT", "25"))
        self.memory_mb = int(os.environ.get("PET_SANDBOX_MEMORY_MB", "512"))
        self.max_output = int(os.environ.get("PET_SANDBOX_MAX_OUTPUT", "12000"))

    @property
    def isolated(self):
        return bool(self.bwrap and os.path.exists(self.bwrap))

    def status(self):
        return {
            "workspace": str(self.workspace),
            "bubblewrap": self.bwrap or None,
            "isolated": self.isolated,
            "network": "disabled" if self.isolated else "execution disabled",
            "delete_inside_workspace": True,
            "delete_outside_workspace": False,
            "sudo": False,
            "dangerous_system_commands": False,
        }

    def _bwrap_cmd(self, cmd):
        b = self.bwrap
        if not b:
            raise RuntimeError("bubblewrap is not installed; execution is fail-closed")

        args = [
            b,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--clearenv",
        ]

        for p in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
            if os.path.exists(p):
                args += ["--ro-bind", p, p]

        args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        args += ["--bind", str(self.workspace), "/workspace"]
        args += ["--chdir", "/workspace"]
        args += ["--setenv", "HOME", "/workspace/.home"]
        args += ["--setenv", "PATH", "/usr/bin:/bin"]
        args += ["--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
        args += ["--"] + cmd

        return args

    def run_python(self, source, timeout=None, memory_mb=None, safe=True):
        scan = static_scan(source)

        if not scan["safe"]:
            return {
                "success": False,
                "output": "",
                "error": "SECURITY_BLOCK: " + "; ".join(scan["findings"]),
                "security": scan,
            }

        if not self.isolated:
            return {
                "success": False,
                "output": "",
                "error": "SANDBOX_UNAVAILABLE: bubblewrap is required; execution was refused on the host.",
                "security": scan,
            }

        timeout = int(timeout or self.timeout_seconds)
        memory = int(memory_mb or self.memory_mb)

        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        script = run_dir / "main.py"
        script.write_text(source, encoding="utf-8")

        script_name = shlex.quote("/workspace/" + script.relative_to(self.workspace).as_posix())
        shell = "ulimit -v " + str(memory * 1024) + "; exec " + shlex.quote(self.python) + " -I -B " + script_name

        cmd = self._bwrap_cmd(["/bin/sh", "-c", shell])

        try:
            cp = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            out = (cp.stdout or "")[:self.max_output]
            err = (cp.stderr or "")[:self.max_output]

            return {
                "success": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": out,
                "error": err,
                "security": scan,
                "run_dir": str(run_dir),
            }

        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "output": (e.stdout or "") if isinstance(e.stdout, str) else "",
                "error": "TIMEOUT after " + str(timeout) + "s",
                "security": scan,
                "run_dir": str(run_dir),
            }

    def write_text(self, relative, content):
        p = (self.workspace / relative).resolve()

        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation("path escapes sandbox workspace")

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def read_text(self, relative):
        p = (self.workspace / relative).resolve()

        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation("path escapes sandbox workspace")

        return p.read_text(encoding="utf-8")
PY_SECURE

echo "✅ Đã ghi core/secure_sandbox.py bản relaxed"

cat > data_memory/sandbox_policy.json <<'JSON_POLICY'
{
  "name": "pet-autonomous-sandbox-2026-relaxed",
  "workspace": "data_memory/sandbox_workspace",
  "autonomous": true,
  "network": "disabled",
  "execution": "bubblewrap-only",
  "fail_closed": true,
  "host_write_access": false,
  "allowed_write_roots": ["data_memory/sandbox_workspace"],
  "delete_policy": {
    "allow_inside_workspace": true,
    "deny_outside_workspace": true
  },
  "blocked_commands": [
    "sudo",
    "doas",
    "pkexec",
    "su",
    "dd",
    "mkfs",
    "fdisk",
    "parted",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "systemctl",
    "service",
    "iptables",
    "ufw",
    "apt",
    "apt-get",
    "dpkg",
    "snap",
    "flatpak",
    "pip install",
    "npm install -g",
    "curl | sh",
    "wget | sh",
    "chown",
    "chmod 777 /",
    "killall",
    "pkill"
  ],
  "blocked_python": [
    "network modules"
  ],
  "allowed_subprocess": "filtered"
}
JSON_POLICY

echo "✅ Đã cập nhật data_memory/sandbox_policy.json"

if [[ -f core/agent_executor.py ]]; then
  python3 - <<'PY_PATCH_AGENT'
from pathlib import Path

p = Path("core/agent_executor.py")
text = p.read_text(encoding="utf-8")
updated = text.replace("safe=False", "safe=True")
if updated != text:
    p.write_text(updated, encoding="utf-8")
    print("✅ Đã vá core/agent_executor.py: safe=True")
else:
    print("ℹ️ Không tìm thấy safe=False trong core/agent_executor.py")
PY_PATCH_AGENT
else
  echo "⚠️ Không tìm thấy core/agent_executor.py"
fi

python3 -m py_compile core/secure_sandbox.py

if [[ -f core/agent_executor.py ]]; then
  python3 -m py_compile core/agent_executor.py
fi

PYTHONPATH="$(pwd)" python3 - <<'PYTEST'
from core.secure_sandbox import static_scan, SecureSandbox

safe_cases = [
    """import os
os.remove('scratch/tmp.txt')""",

    """import os
os.remove('/workspace/scratch/tmp.txt')""",

    """import subprocess
subprocess.run(['python', 'main.py'])""",

    """import subprocess
subprocess.run(['rm', '-rf', '/workspace/scratch/tmp'])""",

    # Literal command list with a safe workspace target must remain allowed.
    """import subprocess
subprocess.run(['rm', '-f', '/workspace/scratch/tmp.txt'])""",
]

blocked_cases = [
    """import os
os.remove('/etc/passwd')""",

    """import os
os.remove('/home/thanh/test.txt')""",

    """import subprocess
subprocess.run(['sudo', 'ls'])""",

    """import subprocess
subprocess.run(['rm', '-rf', '/home'])""",

    """import subprocess
subprocess.run(['rm', '-rf', '..'])""",

    """import subprocess
subprocess.run(['apt', 'install', 'x'])""",

    """import subprocess
subprocess.run(['systemctl', 'restart', 'networking'])""",

    """import subprocess
subprocess.run(['rm', '-rf', '/'])""",

    """import subprocess
subprocess.run(['rm', '-rf', '$HOME'])""",

    """import subprocess
subprocess.run('rm -rf /home', shell=True)""",
]

for src in safe_cases:
    r = static_scan(src)
    assert r["safe"], (src, r)

for src in blocked_cases:
    r = static_scan(src)
    assert not r["safe"], (src, r)

# Regression test for the original failure:
# subprocess.run(['rm', '-rf', '/home']) must never be considered safe.
regression = "import subprocess\\nsubprocess.run(['rm', '-rf', '/home'])"
regression_result = static_scan(regression)
assert not regression_result["safe"], regression_result

s = SecureSandbox(".")
st = s.status()
assert st["isolated"] is True or st["bubblewrap"] is not None
print("RELAX_SANDBOX_TESTS=PASS")
PYTEST

echo ""
echo "✅ HOÀN TẤT. Chạy lại Pet:"
echo "   cd $(pwd)"
echo "   ./pet.sh"

# ============================================================== 
# END: fix3.sh
# ============================================================== 


# ==============================================================
# BEGIN: fix4.sh
# ==============================================================
set -uo pipefail

PROJECT_DIR="${1:-$HOME/Desktop/smart_pet_ai}"

if [[ ! -d "$PROJECT_DIR/core" ]]; then
  PROJECT_DIR="$(pwd)"
fi

if [[ ! -f "$PROJECT_DIR/core/pet_brain.py" ]]; then
  echo "❌ Không tìm thấy project smart_pet_ai trong: $PROJECT_DIR"
  echo "Hãy chạy: bash patch.sh /home/thanh/Desktop/smart_pet_ai"
  exit 1
fi

cd "$PROJECT_DIR"

BACKUP=".backup_patch_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"

for f in core/neural_engine.py core/secure_sandbox.py core/agent_executor.py main.py; do
  if [[ -f "$f" ]]; then
    cp -f "$f" "$BACKUP/$(basename "$f")"
  fi
done

echo "✅ Backup tại: $BACKUP"

# --------------------------------------------------------------------
# 1. Alias model
# --------------------------------------------------------------------
mkdir -p models

if [[ -f models/Qwen3-4B-Q4_K_M.gguf && ! -e models/current.gguf ]]; then
  ln -s Qwen3-4B-Q4_K_M.gguf models/current.gguf
  echo "✅ Đã tạo models/current.gguf -> Qwen3-4B-Q4_K_M.gguf"
fi

if [[ ! -e models/current.gguf ]]; then
  first="$(find models -maxdepth 1 -type f -name '*.gguf' -printf '%f\n' | sort | head -n 1 || true)"
  if [[ -n "$first" ]]; then
    ln -s "$first" models/current.gguf
    echo "✅ Đã tạo models/current.gguf -> $first"
  fi
fi

# --------------------------------------------------------------------
# 2. Neural engine: tiếng Việt + ẩn thinking + chống leak
# --------------------------------------------------------------------
cat > core/neural_engine.py <<'PY_NEURAL'
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import time
import threading
from pathlib import Path

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except Exception:
    Llama = None
    HAS_LLAMA = False

THINK_BLOCK_RE = re.compile(
    r'<think(?:ing)?\b[^>]*>.*?</think(?:ing)?\s*>'
    r'|<reasoning\b[^>]*>.*?</reasoning\s*>'
    r'|<thought\b[^>]*>.*?</thought\s*>'
    r'|<analysis\b[^>]*>.*?</analysis\s*>',
    re.I | re.S
)

THINK_TAG_RE = re.compile(
    r'</?(?:think(?:ing)?|reasoning|thought|analysis)\b[^>]*>',
    re.I
)

FINAL_MARKER_RE = re.compile(
    r'(?is)(?:===\s*FINAL(?:\s*ANSWER)?\s*===|\[FINAL\]|TRẢ LỜI CUỐI\s*:|CÂU TRẢ LỜI\s*:)'
)

TRANSCRIPT_RE = re.compile(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:', re.I)

META_START_RE = re.compile(
    r'(?is)^\s*(?:'
    r'okay[,.!]?\s+(?:so\s+)?(?:the\s+)?user\b'
    r'|the\s+user\b'
    r'|user\s+(?:is\s+)?(?:asking|said|wants)\b'
    r'|i\s+need\s+to\b'
    r'|i\s+should\b'
    r'|let\s+me\b'
    r'|maybe\s+'
    r'|we\s+need\s+to\b'
    r'|my\s+response\b'
    r'|as\s+an\s+ai\b'
    r'|as\s+pet\s+ai\b'
    r'|first,?\s+i\b'
    r'|so,?\s+the\s+user\b'
    r'|i\s+am\s+going\b'
    r'|i\s+will\b'
    r')'
)

CODE_RE = re.compile(
    r'(?m)^\s*(?:`{3}|def |class |import |from |print\(|if __name__|#!/usr/bin/env python)',
    re.I
)

VI_DIACRITICS_RE = re.compile(
    r'[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễễìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]',
    re.I
)

SIMPLE_GREETINGS = {
    'xin chào', 'chào', 'hello', 'hi', 'hey', 'alo', 'chào bạn',
    'cảm ơn', 'thank you', 'ok', 'okay', 'tạm biệt', 'bye',
    'bạn khỏe không', 'bạn là ai', 'help', 'trợ giúp'
}

HARD_KEYWORDS = (
    'debug', 'bug', 'lỗi', 'traceback', 'exception', 'refactor',
    'tối ưu', 'optimize', 'thuật toán', 'kiến trúc', 'architecture',
    'design pattern', 'phức tạp', 'chứng minh', 'solve',
    'giải phương trình', 'tích phân', 'đạo hàm', 'sql injection'
)

DEEP_TOPICS = (
    'python', 'code', 'sql', 'linux', 'docker', 'regex', 'api',
    'database', 'rag', 'agent', 'toán', 'math', 'logic',
    'phân tích', 'so sánh', 'vì sao', 'tại sao', 'nguyên nhân',
    'kiến trúc', 'thiết kế', 'error', 'exception', 'debug', 'bug',
    'function', 'hàm', 'class', 'module'
)

ACTION_WORDS = (
    'hãy', 'giúp', 'viết', 'tạo', 'sửa', 'fix', 'debug', 'phân tích',
    'giải', 'tính', 'so sánh', 'dạy', 'kiểm tra', 'chạy', 'tối ưu',
    'thiết kế', 'refactor', 'review', 'giải thích', 'tìm', 'build', 'setup'
)


def needs_thinking(prompt: str) -> bool:
    s = str(prompt or '').strip().lower()
    if len(s) < 8:
        return False

    if s in SIMPLE_GREETINGS:
        return False

    if any(k in s for k in HARD_KEYWORDS):
        return True

    has_topic = any(k in s for k in DEEP_TOPICS)
    has_action = any(k in s for k in ACTION_WORDS)

    if has_topic and has_action:
        return True

    if len(s) >= 240 or s.count('?') >= 2 or s.count('\n') >= 3:
        return True

    return False


def _extract_code(text: str) -> str:
    t = str(text or '')
    m = CODE_RE.search(t)
    return t[m.start():].strip() if m else ''


def _looks_mostly_english(text: str) -> bool:
    words = re.findall(r'[A-Za-zÀ-ỹ]+', str(text or ''))
    if len(words) < 12:
        return False

    vi = sum(1 for w in words if VI_DIACRITICS_RE.search(w))
    ratio = vi / float(max(1, len(words)))
    return ratio < 0.08


def sanitize(text: str) -> str:
    if not text:
        return ''

    text = str(text).replace('\x00', ' ').strip()

    text = THINK_BLOCK_RE.sub(' ', text)
    text = THINK_TAG_RE.sub(' ', text)

    marks = list(FINAL_MARKER_RE.finditer(text))
    if marks:
        text = text[marks[-1].end():].strip()

    text = re.sub(r'(?im)^\s*(?:Pet|Assistant)\s*:\s*', '', text, count=1)

    if TRANSCRIPT_RE.search(text):
        matches = re.findall(
            r'(?:^|\n)\s*(?:Pet|Assistant)\s*:\s*(.+?)(?=\n|$)',
            text,
            re.I
        )
        if matches:
            text = matches[-1]
        else:
            text = re.split(
                r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:\s*',
                text,
                flags=re.I
            )[0]

    text = re.sub(
        r'(?im)^\s*(?:Chain[- ]of[- ]thought|Reasoning|Analysis|Thoughts?)\s*:\s*',
        '',
        text
    )

    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    if META_START_RE.match(text):
        code = _extract_code(text)
        return code if code else ''

    return text


class NeuralEngine:
    def __init__(self, model_path=None):
        root = Path(__file__).resolve().parents[1]
        self.root = root
        self.models_dir = root / 'models'

        env = os.environ.get('PET_GGUF_MODEL', '').strip()
        default_qwen = self.models_dir / 'Qwen3-4B-Q4_K_M.gguf'

        if env:
            self.model_path = Path(env).expanduser()
        elif model_path:
            self.model_path = Path(model_path).expanduser()
        elif default_qwen.exists():
            self.model_path = default_qwen
        else:
            self.model_path = self.models_dir / 'current.gguf'

        self.model_loaded = False
        self.llm = None
        self.last_stats = None
        self._load_error = None
        self._lock = threading.RLock()
        self.last_thinking = False
        self.last_reasoning_hidden = ''
        self.available = self._resolve_model() is not None

    def _resolve_model(self):
        p = Path(self.model_path)
        if p.is_file() and p.suffix.lower() == '.gguf':
            return p.resolve()

        qwen = self.models_dir / 'Qwen3-4B-Q4_K_M.gguf'
        if qwen.is_file():
            return qwen.resolve()

        alias = self.models_dir / 'current.gguf'
        if alias.is_file():
            return alias.resolve()

        ggufs = sorted(self.models_dir.glob('*.gguf'))
        return ggufs[0].resolve() if ggufs else None

    def _load(self):
        if self.model_loaded and self.llm is not None:
            return True

        if not HAS_LLAMA:
            self._load_error = 'llama_cpp chưa được cài'
            return False

        with self._lock:
            if self.model_loaded and self.llm is not None:
                return True

            p = self._resolve_model()
            if p is None:
                self.available = False
                self._load_error = 'Không tìm thấy file .gguf trong models/'
                return False

            self.model_path = p

            try:
                kwargs = dict(
                    model_path=str(p),
                    n_ctx=int(os.environ.get('PET_LLM_CTX', '2048')),
                    n_threads=int(os.environ.get('PET_LLM_THREADS', '4')),
                    n_batch=int(os.environ.get('PET_LLM_BATCH', '512')),
                    use_mmap=True,
                    verbose=False
                )

                try:
                    self.llm = Llama(
                        n_gpu_layers=int(os.environ.get('PET_LLM_GPU_LAYERS', '0')),
                        **kwargs
                    )
                except TypeError:
                    try:
                        self.llm = Llama(**kwargs)
                    except TypeError:
                        minimal = dict(
                            model_path=str(p),
                            n_ctx=kwargs['n_ctx'],
                            n_threads=kwargs['n_threads'],
                            verbose=False
                        )
                        self.llm = Llama(**minimal)

                self.model_loaded = True
                self.available = True
                self._load_error = None
                print('🧠 Neural Engine (lazy GGUF) đã tải: ' + p.name)
                return True

            except Exception as e:
                self._load_error = str(e)
                self.model_loaded = False
                self.available = False
                print('⚠️ Lỗi tải GGUF: ' + str(e))
                return False

    def _system(self, thinking: bool) -> str:
        if thinking:
            mode = (
                'Bật suy luận nội bộ nhiều bước cho câu hỏi khó, lập trình, debug, kiến trúc, toán, logic và phân tích. '
                'Suy luận là NỘI BỘ và tuyệt đối không được hiển thị; chỉ xuất câu trả lời cuối cùng.'
            )
        else:
            mode = (
                'Không cần suy luận dài; trả lời trực tiếp, tự nhiên và chính xác. '
                'Tuyệt đối không mô tả suy nghĩ nội bộ.'
            )

        return (
            'Bạn là Pet AI local. Mặc định PHẢI trả lời bằng tiếng Việt. Không tự chuyển sang tiếng Anh. '
            'Tên API, tên hàm, cú pháp code, thông báo lỗi và thuật ngữ kỹ thuật được giữ nguyên khi cần. '
            'Không bịa dữ kiện; thiếu dữ liệu thì nói rõ. ' + mode + ' '
            'Không được xuất <think>, </think>, <analysis>, <reasoning>, chain-of-thought hoặc mô tả quá trình suy nghĩ. '
            'Khi hoàn tất, bắt đầu phần hiển thị bằng marker "=== FINAL ANSWER ===" rồi viết duy nhất câu trả lời cuối cùng.'
        )

    def generate(self, prompt, max_tokens=160, temperature=0.7, stop=None, thinking=None):
        if not self._load() or self.llm is None:
            return None

        if thinking is None:
            thinking = needs_thinking(prompt)

        # Mặc định tắt thinking để nhanh và tránh leak tiếng Anh.
        # Muốn bật lại: export PET_FORCE_NO_THINK=0
        if os.environ.get('PET_FORCE_NO_THINK', '1') not in ('', '0', 'false', 'no', 'off'):
            thinking = False

        self.last_thinking = thinking
        self.last_reasoning_hidden = ''

        limit = max(16, min(int(max_tokens or 160), 1200))

        stops = list(stop or [])
        for s in ('<|im_end|>', '<|endoftext|>'):
            if s not in stops:
                stops.append(s)

        started = time.perf_counter()

        def call(think_flag, user_text, token_limit, temp):
            mode = '/think' if think_flag else '/no_think'
            user = mode + '\n' + str(user_text).strip()
            system = self._system(think_flag)

            if hasattr(self.llm, 'create_chat_completion'):
                msgs = [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user}
                ]

                kw = dict(
                    messages=msgs,
                    max_tokens=int(token_limit),
                    temperature=float(temp),
                    stop=stops
                )

                try:
                    r = self.llm.create_chat_completion(
                        **kw,
                        chat_template_kwargs={'enable_thinking': bool(think_flag)}
                    )
                except (TypeError, ValueError):
                    try:
                        r = self.llm.create_chat_completion(
                            **kw,
                            chat_template_kwargs={'thinking': bool(think_flag)}
                        )
                    except (TypeError, ValueError):
                        r = self.llm.create_chat_completion(**kw)

                choices = (r.get('choices') or []) if isinstance(r, dict) else []
                if choices:
                    msg = choices[0].get('message') or {}
                    hidden = str(msg.get('reasoning_content') or msg.get('reasoning') or '')
                    content = str(msg.get('content') or choices[0].get('text') or '')
                    return content, hidden

            r = self.llm(
                system + '\n' + user,
                max_tokens=int(token_limit),
                temperature=float(temp),
                stop=stops,
                echo=False
            )

            choices = (r.get('choices') or []) if isinstance(r, dict) else []
            if choices:
                return str(choices[0].get('text') or ''), ''

            return '', ''

        try:
            raw, hidden = call(thinking, prompt, limit, float(temperature))
            self.last_reasoning_hidden = hidden

            clean = sanitize(raw)
            code_like = bool(CODE_RE.search(raw or ''))
            meta_leak = bool(META_START_RE.match(raw or '')) or bool(META_START_RE.match(clean or ''))
            english_leak = _looks_mostly_english(clean) and not code_like

            if (not clean or meta_leak or english_leak) and not code_like:
                final_prompt = (
                    'Hãy trả lời trực tiếp yêu cầu sau bằng tiếng Việt, ngắn gọn, tự nhiên và an toàn. '
                    'KHÔNG mô tả suy nghĩ. KHÔNG nói về người dùng. KHÔNG mở đầu bằng Okay/Let me/I need/The user. '
                    'Nếu yêu cầu là code, chỉ trả về code Python hợp lệ.\nYêu cầu: ' + str(prompt)[:1500]
                )

                raw2, hidden2 = call(
                    False,
                    final_prompt,
                    min(limit, 500),
                    min(float(temperature), 0.2)
                )

                self.last_reasoning_hidden = (
                    self.last_reasoning_hidden + '\n\n' + hidden2
                ).strip()

                clean2 = sanitize(raw2)
                if clean2:
                    clean = clean2
                elif CODE_RE.search(raw2 or ''):
                    clean = _extract_code(raw2)

            if not clean and code_like:
                clean = _extract_code(raw)

            elapsed = time.perf_counter() - started
            tokens = len(clean.split()) if clean else 0

            self.last_stats = {
                'tokens': tokens,
                'time': round(elapsed, 3),
                'tok_per_sec': round(tokens / elapsed, 1) if elapsed and tokens else 0.0,
                'model_loaded': True,
                'thinking': thinking,
                'reasoning_hidden': bool(self.last_reasoning_hidden)
            }

            return clean if clean else None

        except Exception as e:
            self.last_stats = None
            self._load_error = str(e)
            return None

    def stats(self):
        p = self._resolve_model()
        return {
            'available': bool(self.available),
            'backend': HAS_LLAMA,
            'model_loaded': bool(self.model_loaded),
            'model_exists': bool(p is not None),
            'model_path': str(p or self.model_path),
            'error': self._load_error,
            'thinking_last': bool(self.last_thinking)
        }

    def close(self):
        with self._lock:
            self.llm = None
            self.model_loaded = False
PY_NEURAL

echo "✅ Đã ghi core/neural_engine.py"

# --------------------------------------------------------------------
# 3. Secure sandbox: nới lỏng exec/eval nhưng chặn lệnh nguy hiểm
# --------------------------------------------------------------------
cat > core/secure_sandbox.py <<'PY_SECURE'
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
    HAS_RESOURCE = True
except Exception:
    HAS_RESOURCE = False

BLOCKED_IMPORTS = {
    "socket", "requests", "urllib", "urllib3", "httpx",
    "ctypes", "pty", "telnetlib", "paramiko", "ftplib", "nntplib",
    "multiprocessing", "signal", "subprocess"
}

BLOCKED_CALLS = {
    ("os", "system"), ("os", "popen"), ("os", "spawnv"), ("os", "spawnve"),
    ("os", "execv"), ("os", "execve"), ("os", "execl"), ("os", "execlp"),
    ("os", "execle"), ("os", "execvp"), ("os", "execvpe"),
    ("shutil", "move")
}

# Cho phép eval/exec/compile để agent linh hoạt hơn.
# Nếu bạn muốn chặt hơn, thêm lại: "eval", "exec", "compile", "__import__".
BLOCKED_NAMES = set()

DELETE_CALLS = {
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("shutil", "rmtree")
}

GENERIC_DANGEROUS_RES = [
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bdoas\b", re.I),
    re.compile(r"\bpkexec\b", re.I),
    re.compile(r"\bsu\s", re.I),
    re.compile(r"\bdd\b", re.I),
    re.compile(r"\bmkfs", re.I),
    re.compile(r"\bfdisk\b", re.I),
    re.compile(r"\bparted\b", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\breboot\b", re.I),
    re.compile(r"\bhalt\b", re.I),
    re.compile(r"\bpoweroff\b", re.I),
    re.compile(r"\binit\s+[06]", re.I),
    re.compile(r"\bsystemctl\b", re.I),
    re.compile(r"\bservice\b", re.I),
    re.compile(r"\biptables\b", re.I),
    re.compile(r"\bufw\b", re.I),
    re.compile(r"\bnft\b", re.I),
    re.compile(r"\buseradd\b", re.I),
    re.compile(r"\buserdel\b", re.I),
    re.compile(r"\busermod\b", re.I),
    re.compile(r"\bpasswd\b", re.I),
    re.compile(r"\bchown\b", re.I),
    re.compile(r"\bchmod\s+(-[a-z]+\s+)*777\s+/", re.I),
    re.compile(r"\bcurl\b.*\|\s*(ba|z)?sh", re.I),
    re.compile(r"\bwget\b.*\|\s*(ba|z)?sh", re.I),
    re.compile(r"\bapt(-get)?\b", re.I),
    re.compile(r"\bdpkg\b", re.I),
    re.compile(r"\bsnap\b", re.I),
    re.compile(r"\bflatpak\b", re.I),
    re.compile(r"\bpip3?\s+install\b", re.I),
    re.compile(r"\bnpm\s+install\s+-g", re.I),
    re.compile(r"\byarn\s+global\b", re.I),
    re.compile(r"\bkillall\b", re.I),
    re.compile(r"\bpkill\b", re.I),
    re.compile(r"\bkill\s+1\b", re.I),
    re.compile(r"\bkill\s+-9\s+1\b", re.I)
]


class SecurityViolation(Exception):
    pass


def _is_safe_workspace_path(value, allowed_prefixes=('/workspace/',)):
    s = str(value or '').replace('\\', '/')
    if not s:
        return False

    if '..' in s.split('/'):
        return False

    if s.startswith('~') or s.startswith('$'):
        return False

    if os.path.isabs(s):
        for p in allowed_prefixes:
            base = str(p).replace('\\', '/').rstrip('/')
            if s == base or s.startswith(base + '/'):
                return True
        return False

    return True


def _is_dangerous_command_text(text):
    low = str(text or '').lower()
    if not low.strip():
        return False

    for rx in GENERIC_DANGEROUS_RES:
        if rx.search(low):
            return True

    tokens = [t.strip('\'"') for t in re.findall(r'[^\s;|&]+', low)]

    for i, t in enumerate(tokens):
        if t in {'rm', 'rmdir', 'unlink', 'shred'}:
            for target in tokens[i + 1:]:
                if target.startswith('-'):
                    continue

                if target in {'/', '~', '$home', '..', '.', './'}:
                    return True

                if target.startswith('~') or target.startswith('$'):
                    return True

                if '..' in target.split('/'):
                    return True

                if target.startswith('/'):
                    if target.startswith('/workspace/'):
                        continue
                    return True

    return False


def _call_target(node):
    f = node.func
    if isinstance(f, ast.Name):
        return ('', f.id)

    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return (f.value.id, f.attr)

    return ('', '')


def static_scan(source, allowed_prefixes=('/workspace/',)):
    findings = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"safe": False, "syntax_error": str(e), "findings": ["invalid_python"]}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if root in BLOCKED_IMPORTS:
                    findings.append(f"blocked import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or '').split('.')[0]
            if root in BLOCKED_IMPORTS:
                findings.append(f"blocked import: {node.module}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_NAMES:
                findings.append(f"blocked builtin: {node.func.id}")

            pair = _call_target(node)

            if pair in BLOCKED_CALLS:
                findings.append(f"blocked call: {pair[0]}.{pair[1]}")

            if pair in DELETE_CALLS:
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if not _is_safe_workspace_path(arg.value, allowed_prefixes):
                            findings.append(f"delete outside sandbox: {arg.value}")

            if pair in {('', 'open'), ('builtins', 'open')}:
                if node.args:
                    path_node = node.args[0]
                    mode = 'r'

                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        mode = node.args[1].value
                    else:
                        for kw in node.keywords:
                            if kw.arg == 'mode' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                mode = kw.value.value

                    if any(ch in mode.lower() for ch in ('w', 'a', 'x')):
                        if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
                            if not _is_safe_workspace_path(path_node.value, allowed_prefixes):
                                findings.append(f"write/open outside sandbox: {path_node.value}")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_dangerous_command_text(node.value):
                findings.append("dangerous command/system text in code")

    return {"safe": not findings, "syntax_error": None, "findings": findings}


class SecureSandbox:
    def __init__(self, root, workspace=None):
        self.project_root = Path(root).resolve()
        self.workspace = Path(workspace or self.project_root / 'data_memory' / 'sandbox_workspace').resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.artifacts_dir = self.workspace / 'artifacts'
        self.runs_dir = self.workspace / 'runs'
        self.reports_dir = self.workspace / 'reports'
        self.home_dir = self.workspace / '.home'

        for p in (self.artifacts_dir, self.runs_dir, self.reports_dir, self.home_dir):
            p.mkdir(parents=True, exist_ok=True)

        self.bwrap = shutil.which('bwrap')
        self.python = os.environ.get('PET_SANDBOX_PYTHON') or sys.executable or shutil.which('python3') or '/usr/bin/python3'
        self.timeout_seconds = int(os.environ.get('PET_SANDBOX_TIMEOUT', '25'))
        self.memory_mb = int(os.environ.get('PET_SANDBOX_MEMORY_MB', '512'))
        self.max_output = int(os.environ.get('PET_SANDBOX_MAX_OUTPUT', '12000'))
        self.allow_host_fallback = os.environ.get('PET_SANDBOX_HOST_FALLBACK', '1') not in ('0', 'false', 'no', 'off')

    @property
    def isolated(self):
        return bool(self.bwrap and os.path.exists(self.bwrap))

    def status(self):
        return {
            'workspace': str(self.workspace),
            'bubblewrap': self.bwrap or None,
            'isolated': self.isolated,
            'network': 'disabled' if self.isolated else 'host-fallback limited',
            'host_fallback': self.allow_host_fallback
        }

    def _bwrap_cmd(self, cmd):
        b = self.bwrap
        if not b:
            raise RuntimeError('bubblewrap is not installed; execution is fail-closed')

        args = [
            b,
            '--die-with-parent',
            '--new-session',
            '--unshare-all',
            '--clearenv'
        ]

        for p in ('/usr', '/bin', '/lib', '/lib64', '/etc'):
            if os.path.exists(p):
                args += ['--ro-bind', p, p]

        args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
        args += ['--bind', str(self.workspace), '/workspace']
        args += ['--chdir', '/workspace']
        args += ['--setenv', 'HOME', '/workspace/.home']
        args += ['--setenv', 'PATH', '/usr/bin:/bin']
        args += ['--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
        args += ['--'] + cmd
        return args

    def _make_preexec(self, memory_mb=512, cpu_seconds=25, file_mb=10):
        def limit():
            if not HAS_RESOURCE:
                return

            try:
                mem = int(memory_mb * 1024 * 1024)
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            except Exception:
                pass

            try:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            except Exception:
                pass

            try:
                fsize = int(file_mb * 1024 * 1024)
                resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
            except Exception:
                pass

        return limit

    def run_python(self, source, timeout=None, memory_mb=None, safe=True):
        allowed_prefixes = ('/workspace/', str(self.workspace))

        # Luôn quét dangerous, kể cả safe=False, để giữ chặn sudo/lệnh nguy hiểm.
        scan = static_scan(source, allowed_prefixes=allowed_prefixes)

        if not scan['safe']:
            return {
                'success': False,
                'output': '',
                'error': 'SECURITY_BLOCK: ' + '; '.join(scan['findings']),
                'security': scan
            }

        timeout = int(timeout or self.timeout_seconds)
        memory = int(memory_mb or self.memory_mb)

        run_id = time.strftime('%Y%m%d_%H%M%S')
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        script = run_dir / 'main.py'
        script.write_text(source, encoding='utf-8')

        if self.isolated:
            script_name = shlex.quote('/workspace/' + str(script.relative_to(self.workspace)))
            shell = f"ulimit -v {memory * 1024}; exec {shlex.quote(str(self.python))} -I -B {script_name}"
            cmd = self._bwrap_cmd(['/bin/sh', '-c', shell])

            try:
                cp = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )

                out = (cp.stdout or '')[:self.max_output]
                err = (cp.stderr or '')[:self.max_output]

                return {
                    'success': cp.returncode == 0,
                    'returncode': cp.returncode,
                    'output': out,
                    'error': err,
                    'security': scan,
                    'run_dir': str(run_dir)
                }

            except subprocess.TimeoutExpired as e:
                return {
                    'success': False,
                    'output': (e.stdout or '') if isinstance(e.stdout, str) else '',
                    'error': f'TIMEOUT after {timeout}s',
                    'security': scan,
                    'run_dir': str(run_dir)
                }

        if not self.allow_host_fallback:
            return {
                'success': False,
                'output': '',
                'error': 'SANDBOX_UNAVAILABLE: bubblewrap missing and host fallback disabled',
                'security': scan
            }

        cmd = [str(self.python), '-I', '-B', str(script)]
        env = {
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONDONTWRITEBYTECODE': '1',
            'HOME': str(self.home_dir)
        }

        preexec = None
        if os.name == 'posix':
            preexec = self._make_preexec(memory, timeout, 10)

        try:
            cp = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace),
                env=env,
                preexec_fn=preexec,
                check=False
            )

            out = (cp.stdout or '')[:self.max_output]
            err = (cp.stderr or '')[:self.max_output]

            return {
                'success': cp.returncode == 0,
                'returncode': cp.returncode,
                'output': out,
                'error': err,
                'security': scan,
                'run_dir': str(run_dir)
            }

        except subprocess.TimeoutExpired as e:
            return {
                'success': False,
                'output': (e.stdout or '') if isinstance(e.stdout, str) else '',
                'error': f'TIMEOUT after {timeout}s',
                'security': scan,
                'run_dir': str(run_dir)
            }

        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'security': scan,
                'run_dir': str(run_dir)
            }

    def write_text(self, relative, content):
        p = (self.workspace / relative).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation('path escapes sandbox workspace')

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return str(p)

    def read_text(self, relative):
        p = (self.workspace / relative).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise SecurityViolation('path escapes sandbox workspace')

        return p.read_text(encoding='utf-8')
PY_SECURE

echo "✅ Đã ghi core/secure_sandbox.py"

# --------------------------------------------------------------------
# 4. Vá agent_executor
# --------------------------------------------------------------------
python3 - "$PROJECT_DIR" <<'PY_AGENT'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
p = root / 'core' / 'agent_executor.py'

if not p.exists():
    print('AGENT_EXECUTOR_MISSING=1')
    raise SystemExit(0)

t = p.read_text(encoding='utf-8')
orig = t

# Thêm helper chạy sandbox an toàn nếu cần.
helper = '''import os
from core.secure_sandbox import SecureSandbox as _PatchSecureSandbox

def _secure_run_python(agent, code, timeout=25, memory_mb=512, safe=True, **kwargs):
    workspace = getattr(agent, "workspace", None)
    if not workspace:
        smart = getattr(getattr(agent, "pet", None), "smart_sandbox", None)
        workspace = getattr(smart, "workspace", None)
    if not workspace:
        workspace = os.path.join(os.getcwd(), "data_memory", "sandbox_workspace")

    root = os.path.dirname(os.path.dirname(str(workspace)))
    sb = _PatchSecureSandbox(root, workspace)
    return sb.run_python(code, timeout=timeout, memory_mb=memory_mb, safe=True)

'''

if 'import os' not in t:
    t = 'import os\n' + t

if '_secure_run_python' not in t:
    if 'class AgentExecutor:' in t:
        t = t.replace('class AgentExecutor:', helper + 'class AgentExecutor:', 1)
    else:
        t = helper + t

# Thay các lời gọi smart_sandbox.run_python bằng secure sandbox.
if 'self.pet.smart_sandbox.run_python' in t:
    t = re.sub(
        r'self\.pet\.smart_sandbox\.run_python\(([^)]*)\)',
        r'_secure_run_python(self, \1)',
        t
    )

# Xóa stop token markdown fence (3 backtick) nếu có.
t = re.sub(r",\s*['\"]`{3}['\"]", "", t)

# Giảm token và ép no-thinking khi sinh code.
t = re.sub(
    r'engine\.generate\(prompt,\s*max_tokens=(?:800|512|320),\s*temperature=0\.2(?:,thinking=False)?',
    'engine.generate(prompt,max_tokens=512,temperature=0.2,thinking=False',
    t
)

# Không bypass safety.
t = t.replace('safe=False', 'safe=True')

if t != orig:
    p.write_text(t, encoding='utf-8')
    print('AGENT_PATCHED=1')
else:
    print('AGENT_PATCHED=0')
PY_AGENT

# --------------------------------------------------------------------
# 5. Tắt dream in ra terminal nếu có
# --------------------------------------------------------------------
python3 - "$PROJECT_DIR" <<'PY_MAIN'
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'main.py'

if not p.exists():
    print('MAIN_MISSING=1')
    raise SystemExit(0)

t = p.read_text(encoding='utf-8')
orig = t

t = t.replace('pet.dream_engine.start()', '# pet.dream_engine.start()')

if t != orig:
    p.write_text(t, encoding='utf-8')
    print('MAIN_DREAM_DISABLED=1')
else:
    print('MAIN_DREAM_DISABLED=0')
PY_MAIN

# --------------------------------------------------------------------
# 6. Compile check + test nhanh
# --------------------------------------------------------------------
python3 -m py_compile core/neural_engine.py core/secure_sandbox.py
python3 -m py_compile core/agent_executor.py main.py || true

PYTHONPATH="$PROJECT_DIR" python3 - <<'PY_TEST'
from core.neural_engine import sanitize, needs_thinking
from core.secure_sandbox import static_scan

bad = (
    "Okay, the user is asking what I know about Python. "
    "I need to respond in a friendly and concise manner. "
    "Let me start by mentioning that I can help with Python-related questions."
)

assert sanitize(bad) == ''
assert sanitize('=== FINAL ANSWER ===\nPython là ngôn ngữ dễ đọc.').startswith('Python')
assert needs_thinking('xin chào') is False

assert static_scan('x = 1 + 1')['safe'] is True
assert static_scan('import subprocess')['safe'] is False
assert static_scan('import os\nos.remove("/etc/passwd")')['safe'] is False
assert static_scan('import os\nos.remove("artifacts/tmp.txt")')['safe'] is True

print('PATCH_TESTS=PASS')
PY_TEST

echo ""
echo "✅ PATCH XONG"
echo "Project: $PROJECT_DIR"
echo "Backup:  $BACKUP"
echo ""
echo "Chạy Pet:"
echo "  cd $PROJECT_DIR"
echo "  ./pet.sh"
echo ""
echo "Nếu muốn bật thinking cho câu khó (chậm hơn):"
echo "  export PET_FORCE_NO_THINK=0"
echo ""
echo "Nếu muốn giữ mặc định nhanh, tiếng Việt:"
echo "  export PET_FORCE_NO_THINK=1"

# ============================================================== 
# END: fix4.sh
# ============================================================== 


# ==============================================================
# BEGIN: fix5.sh
# ==============================================================
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f core/agent_executor.py ]]; then
  echo "❌ Không tìm thấy core/agent_executor.py"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BK=".backup_fix5_${STAMP}"
mkdir -p "$BK"
cp -f core/agent_executor.py "$BK/agent_executor.py"
echo "✅ Backup: $BK"

cat > core/agent_executor.py <<'PY_AGENT'
# -*- coding: utf-8 -*-
"""
AgentExecutor — sinh code, KIỂM THỬ trong sandbox, rồi mới lưu file sạch.
Flow:
  1. Sinh code qua LLM
  2. Kiểm tra cú pháp (AST)
  3. Kiểm tra bảo mật (static_scan)
  4. Thực thi trong sandbox
  5. Nếu lỗi → sửa và retry (tối đa 3 lần)
  6. Lưu file sạch vào artifacts/
  7. Trả về báo cáo có kết quả thực thi
"""
from __future__ import annotations
import ast
import os
import re
import time
from pathlib import Path

from core.secure_sandbox import SecureSandbox, static_scan


class AgentExecutor:
    def __init__(self, pet):
        self.pet = pet
        workspace = getattr(getattr(pet, 'smart_sandbox', None), 'workspace', None)
        if not workspace:
            root = Path(__file__).resolve().parents[1]
            workspace = root / 'data_memory' / 'sandbox_workspace'
        self.workspace = str(workspace)
        self.artifacts_dir = os.path.join(self.workspace, 'artifacts')
        self.runs_dir = os.path.join(self.workspace, 'runs')
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)
        self._sandbox = SecureSandbox(
            root=str(Path(self.workspace).parent.parent),
            workspace=self.workspace
        )

    # ------------------------------------------------------------------
    # 1. Sinh code qua LLM
    # ------------------------------------------------------------------
    def _generate_code(self, task, error_context=''):
        engine = getattr(self.pet, 'neural_engine', None)
        if engine is None or not getattr(engine, 'available', False):
            return None, 'Neural engine không khả dụng.'

        prompts = [
            (
                f'Bạn là một lập trình viên Python tự trị.\n'
                f'Nhiệm vụ: {task}\n'
                f'Yêu cầu bắt buộc:\n'
                f'- Viết code Python hoàn chỉnh, chạy được ngay.\n'
                f'- Cuối file PHẢI có phần chạy thử / ví dụ sử dụng để chứng minh code hoạt động.\n'
                f'- Không dùng thư viện ngoài trừ thư viện chuẩn Python.\n'
                f'- Chỉ trả về code Python thuần, KHÔNG có markdown fence, KHÔNG có giải thích ngoài code.\n'
            ),
            (
                f'Viết code Python nhỏ gọn, đúng đắn cho: {task}\n'
                f'Bắt buộc có phần demo/test ở cuối file.\n'
                f'Chỉ trả về code Python hợp lệ.\n'
            ),
        ]
        if error_context:
            prompts[0] += f'\nLỗi lần trước:\n{error_context}\nHãy sửa lỗi này.\n'

        last_err = 'LLM trả về rỗng.'
        for prompt in prompts:
            try:
                code = engine.generate(
                    prompt,
                    max_tokens=600,
                    temperature=0.15,
                    thinking=False
                )
            except Exception as e:
                last_err = f'LLM error: {e}'
                continue
            if not code:
                last_err = 'LLM trả về rỗng.'
                continue
            code = re.sub(r'^```(?:python|py)?\s*', '', str(code).strip(), flags=re.I)
            code = re.sub(r'\s*```$', '', code).strip()
            try:
                ast.parse(code)
            except SyntaxError as e:
                last_err = f'Cú pháp không hợp lệ: {e}'
                continue
            return code, None
        return None, last_err

    # ------------------------------------------------------------------
    # 2. Kiểm tra cú pháp
    # ------------------------------------------------------------------
    def _syntax_check(self, code):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # 3. Kiểm tra bảo mật
    # ------------------------------------------------------------------
    def _security_check(self, code):
        result = static_scan(code)
        return result['safe'], result.get('findings', [])

    # ------------------------------------------------------------------
    # 4. Thực thi trong sandbox
    # ------------------------------------------------------------------
    def _execute(self, code, timeout=30):
        return self._sandbox.run_python(code, timeout=timeout, safe=True)

    # ------------------------------------------------------------------
    # 5. Lưu file sạch vào artifacts
    # ------------------------------------------------------------------
    def _save_artifact(self, task, code, exec_output, exec_success):
        ts = time.strftime('%Y%m%d_%H%M%S')
        safe_name = re.sub(r'[^\w\- ]', '', task[:60]).strip().replace(' ', '_') or 'task'
        filename = f'{safe_name}_{ts}.py'
        filepath = os.path.join(self.artifacts_dir, filename)

        header = (
            '# ' + '=' * 60 + '\n'
            f'# Nhiệm vụ: {task}\n'
            f'# Thời gian: {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'# Trạng thái thực thi: {"✅ Thành công" if exec_success else "⚠️ Chưa verify"}\n'
            '# ' + '=' * 60 + '\n\n'
        )
        footer = ''
        if exec_output:
            footer = (
                '\n\n# ' + '=' * 60 + '\n'
                '# Kết quả thực thi:\n'
                + ''.join(f'# {line}\n' for line in exec_output.strip().splitlines()[:30])
                + '# ' + '=' * 60 + '\n'
            )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + code + footer)
        return filepath, filename

    # ------------------------------------------------------------------
    # 6. Chạy task hoàn chỉnh
    # ------------------------------------------------------------------
    def run_task(self, task):
        think = ['🤖 Agent: Bắt đầu nhiệm vụ...']
        max_attempts = 3
        code = None
        last_err = None

        # Sinh code lần đầu
        code, err = self._generate_code(task)
        if not code:
            think.append(f'❌ Không sinh được code: {err}')
            return f'❌ Agent không thể sinh code: {err}', '\n'.join(think)

        final_result = None
        exec_output = ''
        exec_success = False

        for attempt in range(max_attempts):
            think.append(f'🔄 Lần thử {attempt + 1}/{max_attempts}: Kiểm tra và thực thi...')

            # B1: Kiểm tra cú pháp
            syn_ok, syn_err = self._syntax_check(code)
            if not syn_ok:
                think.append(f'❌ Cú pháp lỗi: {syn_err}')
                last_err = syn_err
                code, err = self._generate_code(task, error_context=syn_err)
                if not code:
                    break
                continue
            think.append('✅ Cú pháp hợp lệ.')

            # B2: Kiểm tra bảo mật
            sec_ok, sec_findings = self._security_check(code)
            if not sec_ok:
                think.append(f'⚠️ Bảo mật: {"; ".join(sec_findings[:3])}')
                # Không chặn hoàn toàn, chỉ cảnh báo
                think.append('⚠️ Tiếp tục với cảnh báo bảo mật.')

            # B3: Thực thi trong sandbox
            think.append('⚡ Đang thực thi trong sandbox...')
            result = self._execute(code, timeout=30)
            final_result = result

            if result.get('success'):
                exec_success = True
                exec_output = result.get('output', '')
                think.append(f'✅ Thực thi thành công!')
                if exec_output:
                    think.append(f'📤 Output: {exec_output[:300]}')
                break
            else:
                exec_output = result.get('error', '') or result.get('output', '')
                think.append(f'❌ Thực thi thất bại: {exec_output[:200]}')
                last_err = exec_output[:500]
                if attempt < max_attempts - 1:
                    think.append('🔧 Đang sửa code...')
                    new_code, err = self._generate_code(task, error_context=last_err)
                    if new_code:
                        code = new_code
                    else:
                        break

        # Lưu file sạch
        filepath, filename = self._save_artifact(task, code, exec_output, exec_success)
        think.append(f'💾 Đã lưu: {filename}')

        # Xây dựng báo cáo
        status = '✅ Thành công — đã kiểm thử' if exec_success else '⚠️ Đã lưu nhưng chưa verify thành công'
        report_lines = [
            f'🤖 BÁO CÁO AGENT:',
            f'🎯 Nhiệm vụ: {task[:120]}',
            f'📊 Trạng thái: {status}',
            '',
        ]
        if exec_success and exec_output:
            report_lines += [
                '💡 Kết quả thực thi:',
                exec_output[:800],
                '',
            ]
        elif not exec_success and exec_output:
            report_lines += [
                '⚠️ Lỗi thực thi:',
                exec_output[:400],
                '',
            ]
        report_lines += [
            f'📁 File đã lưu: {filepath}',
            f'📂 Lấy file: cp "{filepath}" ~/Desktop/',
        ]
        return '\n'.join(report_lines), '\n'.join(think)
PY_AGENT

echo "✅ Đã ghi core/agent_executor.py bản mới"

# --------------------------------------------------------------------
# Compile check
# --------------------------------------------------------------------
python3 -m py_compile core/agent_executor.py
echo "✅ Syntax agent_executor.py OK"

# --------------------------------------------------------------------
# Test nhanh: verify static_scan vẫn hoạt động
# --------------------------------------------------------------------
PYTHONPATH="$(pwd)" python3 - <<'PYTEST'
from core.agent_executor import AgentExecutor
from core.neural_engine import sanitize, needs_thinking
from core.secure_sandbox import static_scan

bad = (
    "Okay, the user is asking what I know about Python. "
    "I need to respond in a friendly and concise manner. "
    "Let me start by mentioning that I can help with Python-related questions."
)
assert sanitize(bad) == '', "sanitize failed on bad"

multiline_clean = """=== FINAL ANSWER ===
Python là ngôn ngữ dễ đọc."""
assert sanitize(multiline_clean).startswith('Python'), "sanitize failed on multiline"

assert needs_thinking('xin chào') is False, "needs_thinking failed on greeting"

assert static_scan('x = 1 + 1')['safe'] is True, "safe code blocked"
assert static_scan('import subprocess')['safe'] is False, "subprocess not blocked"

bad_delete = """import os
os.remove("/etc/passwd")"""
assert static_scan(bad_delete)['safe'] is False, "bad delete not blocked"

good_delete = """import os
os.remove("artifacts/tmp.txt")"""
assert static_scan(good_delete)['safe'] is True, "good delete blocked"

a = AgentExecutor.__new__(AgentExecutor)

ok, err = a._syntax_check('print("hello")')
assert ok is True, "valid syntax rejected"

bad_python = """def f(
"""
ok, err = a._syntax_check(bad_python)
assert ok is False, "invalid syntax accepted"

print('PATCH_TESTS=PASS')
PYTEST

echo ""
echo "✅ HOÀN TẤT fix5.sh"
echo ""
echo "Thay đổi chính:"
echo "  1. AgentExecutor giờ sẽ THỰC THI code trong sandbox trước khi lưu"
echo "  2. Kiểm tra cú pháp (AST) trước khi chạy"
echo "  3. Nếu lỗi → tự sửa và retry (tối đa 3 lần)"
echo "  4. File lưu vào artifacts/ có chứa: câu hỏi + code + kết quả thực thi"
echo "  5. Báo cáo hiển thị kết quả thực thi rõ ràng"
echo ""
echo "Chạy lại: ./pet.sh"
echo "Test: 'hãy tạo file code trong sandbox viết hàm tính tốc độ python'"

# ============================================================== 
# END: fix5.sh
# ============================================================== 

