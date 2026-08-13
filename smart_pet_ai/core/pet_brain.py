# -*- coding: utf-8 -*-
import os, re, json, glob, time, pickle, random, threading, hashlib
from rank_bm25 import BM25Okapi
import markovify

from core.graph_engine import GraphEngine
from core.emotion_graph import EmotionGraph
from core.memory_palace import MemoryPalace
from core.personality_engine import PersonalityEngine
from core.reasoning_engine import ReasoningEngine
from core.abstraction_engine import AbstractionEngine
from core.narrative_identity import NarrativeIdentity
from core.dialogue_synthesizer import DialogueSynthesizer
from core.conversation_orchestrator import ConversationOrchestrator
from core.dream_engine import DreamEngine
from core.universal_parser import UniversalParser
from core.expert_system import ExpertSystem
from core.symbolic_solver import SymbolicSolver
from core.state_machine import PetStateMachine
from core.ml_engine import MLEngine
from core.vector_search import VectorSearch
from core.fuzzy_search import FuzzySearch
from core.nlp_engine import NLPEngine
from core.schema_validator import SchemaValidator
from core.workflow_engine import WorkflowEngine
from core.scheduler import PetScheduler
from core.verification import VerificationEngine
from core.sandbox import Sandbox
from core.neural_engine import NeuralEngine
from core.rag2026_store import RAGStore, LazyDocuments
from core.super_rag import SuperRAG
from core.jsonl_distillation import parse_jsonl_file_rag
from core.rag_utils import text_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_HOT_TXT = os.path.join(BASE_DIR, "data_hot", "tai_lieu_RAG")
DATA_HOT_JSONL = os.path.join(BASE_DIR, "data_hot", "kien_thuc_jsonl")
DATA_MEMORY = os.path.join(BASE_DIR, "data_memory")

DATA_PATH = os.path.join(DATA_MEMORY, "brain_data.json")
HASH_PATH = os.path.join(DATA_MEMORY, "data_hash.txt")
BM25_PATH = os.path.join(DATA_MEMORY, "brain_index.pkl")
MARKOV_PATH = os.path.join(DATA_MEMORY, "markov_model.json")
GRAPH_PATH = os.path.join(DATA_MEMORY, "knowledge_graph.gpickle")
EMOTION_PATH = os.path.join(DATA_MEMORY, "emotion_state.json")
MEMORY_PATH = os.path.join(DATA_MEMORY, "memory_palace.json")
PERSONALITY_PATH = os.path.join(DATA_MEMORY, "personality.json")
ABSTRACTION_PATH = os.path.join(DATA_MEMORY, "abstraction.json")
NARRATIVE_PATH = os.path.join(DATA_MEMORY, "narrative.json")
EXPERT_PATH = os.path.join(DATA_MEMORY, "expert_rules.json")
ML_PATH = os.path.join(DATA_MEMORY, "ml_engine.json")
VECTOR_PATH = os.path.join(DATA_MEMORY, "vector_index")

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

class UltimateCognitivePetPro:
    NEGATIVE_WORDS = ["sai", "ngu", "không đúng", "không", "tệ", "dở", "sai rồi", "nhảm"]
    POSITIVE_WORDS = ["đúng", "giỏi", "chuẩn", "hay", "tốt", "chính xác", "đúng rồi", "tuyệt"]
    TOT_TRIGGERS = ["so sánh", "tại sao", "vì sao", "phân tích", "khác nhau", "khác biệt", "giải thích"]

    def __init__(self):
        os.makedirs(DATA_HOT_TXT, exist_ok=True)
        os.makedirs(DATA_HOT_JSONL, exist_ok=True)
        os.makedirs(DATA_MEMORY, exist_ok=True)

        self.PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.rag2026 = RAGStore(self.PROJECT_ROOT)
        self.documents = LazyDocuments(self.rag2026)
        self.bm25 = None
        self.tokenized_corpus = []
        self.markov_model = None

        self.graph_engine = GraphEngine()
        self.emotion_graph = EmotionGraph(save_path=EMOTION_PATH)
        self.memory = MemoryPalace(save_path=MEMORY_PATH)
        self.personality = PersonalityEngine(save_path=PERSONALITY_PATH)
        self.reasoning = ReasoningEngine(self.graph_engine)
        self.abstraction = AbstractionEngine(save_path=ABSTRACTION_PATH)
        self.narrative = NarrativeIdentity(save_path=NARRATIVE_PATH)
        self.dialogue = DialogueSynthesizer()
        self.orchestrator = ConversationOrchestrator(self)

        self.universal_parser = UniversalParser()
        self.expert_system = ExpertSystem(save_path=EXPERT_PATH)
        self.symbolic_solver = SymbolicSolver()
        self.state_machine = PetStateMachine()
        self.ml_engine = MLEngine(save_path=ML_PATH)
        self.vector_search = VectorSearch(save_path=VECTOR_PATH)
        self.fuzzy_search = FuzzySearch()
        self.nlp_engine = NLPEngine()
        self.schema_validator = SchemaValidator()
        self.workflow = WorkflowEngine(self)
        self.scheduler = PetScheduler(self)
        self.verification = VerificationEngine(self)
        self.sandbox = Sandbox()
        self.dream_engine = DreamEngine(self)

        self.neural_engine = NeuralEngine()
        self.dialogue.set_neural(self.neural_engine)

        self.lock = threading.RLock()
        self.last_interaction = time.time()
        self.last_answer_doc_ids = []
        self._id_counter = 0
        self._seen_hashes = set()
        self.super_rag = None

        self._load_docs_only()
        self._seen_hashes = {
            d.get("hash") or text_hash(d.get("text", ""))
            for d in self.documents
        }
        if not self.documents:
            self._seed_default_knowledge()

        self.super_rag = SuperRAG(self)

        # FAST BOOT: persistent RAG lives on disk; ingestion is background-only.
        self._load_prebuilt_indices()
        try:
            self.rag2026.start_background_ingest()
        except Exception:
            pass
        self.dialogue.set_markov(self.markov_model)
        self.scheduler.start()

    def _load_docs_only(self):
        # Runtime source of truth is the persistent SQLite RAG store.
        self._id_counter = self.rag2026.max_id()
        self.markov_model = None

    def _load_prebuilt_indices(self):
        return True

    def _has_new_data(self):
        return False

    def next_id(self):
        self._id_counter += 1
        return self._id_counter

    @staticmethod
    def tokenize(text):
        return _TOKEN_RE.findall(text.lower())

    def _seed_default_knowledge(self):
        seeds = [
            "Trí Tuệ Nhân Tạo là lĩnh vực khoa học máy tính nghiên cứu cách tạo ra máy móc có khả năng suy nghĩ và học hỏi giống con ngườ.",
            "Đồ Thị Tri Thức biểu diễn các thực thể và mối quan hệ giữa chúng dưới dạng mạng lưới gồm node và cạnh, giúp máy tính suy luận liên kết.",
            "Markov Chain là mô hình toán học mô tả chuỗi sự kiện, trong đó xác suất của trạng thái tiếp theo chỉ phụ thuộc vào trạng thái hiện tại.",
            "Thuật Toán BM25 là một hàm xếp hạng được dùng rộng rãi trong truy hồi thông tin để tìm tài liệu liên quan nhất với một truy vấn cho trước.",
            "Học Tăng Cường là phương pháp huấn luyện mô hình dựa trên phần thưởng và hình phạt nhận được từ môi trường xung quanh theo thờ gian.",
            "Cảm xúc là phản ứng tâm lý phức tạp liên quan đến tâm trạng, tính khí và động lực của một sinh thể.",
            "Suy luận nhân quả giúp ta hiểu mối liên hệ giữa nguyên nhân và kết quả trong hệ thống phức tạp.",
            "Trí nhớ phân tầng bao gồm trí nhớ ngắn hạn, trí nhớ dài hạn và trí nhớ cảm xúc, tạo nên bản sắc của một sinh thể nhận thức.",
            "Expert System là hệ thống sử dụng luật IF/THEN để suy luận, mô phỏng chuyên gia con ngườ.",
            "Vector Search sử dụng embeddings để tìm kiếm ngữ nghĩa, ngay cả khi không có LLM có thể dùng TF-IDF.",
            "State Machine quản lý các trạng thái nhận thức, giúp agent chuyển đổi mượt mà giữa các mode suy nghĩ.",
            "Self-verification là khả năng tự kiểm tra câu trả lờ trước khi xuất, đảm bảo chất lượng.",
        ]
        for s in seeds:
            self._add_document(s, source="seed_knowledge")
        self.save_all()

    def _add_document(self, text, source, think_blocks=None, extra=None):
        text = text.strip()
        if not text:
            return None

        if not hasattr(self, "_seen_hashes"):
            self._seen_hashes = set()

        h = text_hash(text)
        if h in self._seen_hashes:
            return None

        doc = {
            "id": self.next_id(),
            "text": text,
            "source": source,
            "weight": 1.0,
            "hash": h,
        }

        if think_blocks:
            doc["think_blocks"] = think_blocks

        if extra:
            for k, v in extra.items():
                if k in ("id", "hash"):
                    continue
                if v is None:
                    continue
                doc[k] = v

        self._seen_hashes.add(h)
        self.documents.append(doc)

        self.graph_engine.update_graph(text, source=source)
        self.abstraction.digest_text(text, source=source)
        return doc

    def digest_hot_folder(self, verbose=True):
        try:
            self.rag2026.start_background_ingest(delay=0.0)
        except Exception:
            pass
        return 0

    def rebuild_index(self):
        return True

    def rebuild_markov(self):
        self.markov_model = None
        return True

    def rebuild_vector(self):
        return True

    def _update_fuzzy_concepts(self):
        concepts = set()
        for d in self.documents[-2000:]:
            concepts.update(self.graph_engine.extract_entities(d["text"]))
        self.fuzzy_search.set_concepts(list(concepts))

    def _train_ml(self):
        with self.lock:
            if len(self.documents) >= 5 and self.ml_engine.available:
                self.ml_engine.train_clustering(self.documents[-5000:])
                self.ml_engine.train_anomaly(self.documents[-5000:])
                self.ml_engine.save()

    def _generate_expert_rules(self):
        with self.lock:
            patterns = self.abstraction.find_patterns(min_count=2)
            for p in patterns[:10]:
                self.expert_system.add_rule_from_schema(p)
            self.expert_system.save()

    def save_all(self):
        with self.lock:
            for obj, meth in ((self.emotion_graph,'save'),(self.memory,'save'),(self.personality,'save'),(self.abstraction,'save'),(self.narrative,'save'),(self.expert_system,'save'),(self.ml_engine,'save')):
                try: getattr(obj,meth)()
                except Exception: pass
            try: self.graph_engine.save(GRAPH_PATH)
            except Exception: pass
            try: self.rag2026._ensure_schema()
            except Exception: pass

    def search(self, query, top_n=3):
        with self.lock:
            if self.bm25 is None or not self.documents: return []
            tokens = self.tokenize(query)
            if not tokens: return []
            raw_scores = self.bm25.get_scores(tokens)
            weighted = [(doc, raw_scores[i] * doc.get("weight", 1.0)) for i, doc in enumerate(self.documents)]
            weighted.sort(key=lambda x: x[1], reverse=True)
            return [(d, s) for d, s in weighted[:top_n] if s > 0]

    def _check_feedback(self, text):
        words = text.strip().split()
        if len(words) > 4: return 0
        low = text.lower()
        for w in self.NEGATIVE_WORDS:
            if w in low: return -1
        for w in self.POSITIVE_WORDS:
            if w in low: return 1
        return 0

    def apply_feedback(self, sentiment):
        with self.lock:
            if not self.last_answer_doc_ids: return
            for doc in self.documents:
                if doc["id"] in self.last_answer_doc_ids:
                    if sentiment > 0: doc["weight"] = round(min(doc.get("weight", 1.0) * 1.2, 5.0), 4)
                    elif sentiment < 0: doc["weight"] = round(max(doc.get("weight", 1.0) * 0.8, 0.05), 4)
            self.save_all()

    def is_complex_query(self, text):
        return any(trig in text.lower() for trig in self.TOT_TRIGGERS)

    def _generate_sub_queries(self, query):
        entities = self.graph_engine.extract_entities(query)
        tokens = [t for t in self.tokenize(query) if len(t) > 3]
        keywords = entities if entities else tokens[:4]
        if not keywords: keywords = [query]
        kw1 = keywords[0]
        kw2 = keywords[1] if len(keywords) > 1 else kw1
        return [query, f"khái niệm định nghĩa {kw1}", f"đặc điểm vai trò ứng dụng {kw2}"]

    def answer(self, user_input):
        return self.orchestrator.process(user_input)

    def run_sandbox(self, code):
        return self.sandbox.run_python(code)

    def shutdown(self):
        self.dream_engine.stop()
        self.scheduler.stop()
        self.save_all()
