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
