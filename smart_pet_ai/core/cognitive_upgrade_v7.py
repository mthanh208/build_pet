# -*- coding: utf-8 -*-
import os
import time
import types


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_MEMORY = os.path.join(BASE_DIR, "data_memory")


GREETING_MARKERS = [
    "chào", "hello", "hi", "hey", "xin chào", "alo", "yo", "ê"
]

KNOWLEDGE_MARKERS = [
    "là gì", "là ai", "như thế nào", "tại sao", "vì sao",
    "so sánh", "khác gì", "phân tích", "cách", "hướng dẫn",
    "ví dụ", "định nghĩa", "giải thích", "nghĩa là",
    "nguyên nhân", "kết quả", "ứng dụng", "khái niệm"
]


def _is_greeting(text):
    low = str(text).lower()
    return any(g in low for g in GREETING_MARKERS) and len(low.split()) <= 12


def _is_knowledge(text):
    low = str(text).lower()
    return any(k in low for k in KNOWLEDGE_MARKERS)


def _v7_stats(pet):
    lines = ["🧠 V7 Deep Cognitive Architecture:"]

    try:
        lines.append(pet.ebbinghaus.stats_text())
    except Exception:
        lines.append("  • Ebbinghaus: unavailable")

    try:
        lines.append(pet.memory_consolidator.stats_text())
    except Exception:
        lines.append("  • Consolidation: unavailable")

    try:
        lines.append(pet.curiosity.stats_text())
    except Exception:
        lines.append("  • Curiosity: unavailable")

    try:
        lines.append(pet.data_analyst.stats_text())
    except Exception:
        lines.append("  • Data Analyst: unavailable")

    try:
        lines.append(pet.adversarial.stats_text())
    except Exception:
        lines.append("  • Adversarial: unavailable")

    return "\n".join(lines)


def _decay_task(pet):
    try:
        with pet.lock:
            pet.ebbinghaus.decay_documents(pet.documents)
            pet.ebbinghaus.decay_episodic(pet.memory)
            pet.save_all()
    except Exception:
        pass


def _consolidation_task(pet):
    try:
        with pet.lock:
            facts = pet.memory_consolidator.consolidate(pet, max_episodes=6)

            if facts:
                pet.rebuild_index()

                if len(pet.documents) < 3000 and hasattr(pet, "rebuild_vector"):
                    pet.rebuild_vector()

                pet.save_all()
    except Exception:
        pass


def _curiosity_task(pet):
    try:
        idle = time.time() - pet.last_interaction
        pet.curiosity.update_idle(idle)

        if idle > 900:
            pet.curiosity.idle_think(pet)
    except Exception:
        pass


def _v7_dream_once(self):
    """
    DreamEngine v7:
      - Memory Consolidation
      - Ebbinghaus decay
      - Curiosity idle thinking
    """
    pet = self.pet

    try:
        with pet.lock:
            facts = pet.memory_consolidator.consolidate(pet, max_episodes=6)

            pet.ebbinghaus.decay_documents(pet.documents)
            pet.ebbinghaus.decay_episodic(pet.memory)

            thought = pet.curiosity.idle_think(pet, force=False)

            if facts:
                pet.narrative.grow("Đã nén ký ức thành tri thức cốt lõi.", 0.25)

            if thought:
                print(f"\n💭 [Dream/Curiosity] {thought}")
                print("🐾 Bạn: ", end="", flush=True)

            if facts:
                pet.rebuild_index()

            pet.save_all()

    except Exception:
        pass


def install_v7(pet):
    """
    Cài đặt V7 Deep Cognitive Upgrade.
    """

    if getattr(pet, "_v7_installed", False):
        return

    from core.ebbinghaus_engine import EbbinghausEngine
    from core.memory_consolidator import MemoryConsolidator
    from core.curiosity_engine import CuriosityEngine
    from core.data_analyst_agent import DataAnalystAgent
    from core.adversarial_checker import AdversarialChecker

    os.makedirs(DATA_MEMORY, exist_ok=True)

    # ---------------------------------------------------------------
    # 1. Khởi tạo engines
    # ---------------------------------------------------------------
    pet.ebbinghaus = EbbinghausEngine(
        save_path=os.path.join(DATA_MEMORY, "ebbinghaus.json")
    )

    pet.memory_consolidator = MemoryConsolidator(
        save_path=os.path.join(DATA_MEMORY, "memory_consolidator.json")
    )

    pet.curiosity = CuriosityEngine(
        save_path=os.path.join(DATA_MEMORY, "curiosity.json")
    )

    pet.data_analyst = DataAnalystAgent(pet)
    pet.adversarial = AdversarialChecker()

    # ---------------------------------------------------------------
    # 2. Wrap search để củng cố trí nhớ khi truy hồi
    # ---------------------------------------------------------------
    original_search = pet.search

    def search_v7(query, top_n=5):
        results = original_search(query, top_n=top_n)

        try:
            for doc, score in results:
                if isinstance(doc, dict):
                    pet.ebbinghaus.reinforce_doc(doc)
        except Exception:
            pass

        return results

    pet.search = search_v7

    # ---------------------------------------------------------------
    # 3. Wrap memory retrieval để củng cố episodic memory
    # ---------------------------------------------------------------
    original_memory_retrieve = pet.memory.retrieve_relevant

    def retrieve_v7(query, emotion_state=None, limit=5):
        results = original_memory_retrieve(query, emotion_state=emotion_state, limit=limit)

        try:
            for item in results:
                if item.get("source") == "episodic":
                    for ep in pet.memory.episodic:
                        if ep.get("summary") == item.get("text"):
                            pet.ebbinghaus.reinforce_episodic(ep)
                            break
        except Exception:
            pass

        return results

    pet.memory.retrieve_relevant = retrieve_v7

    # ---------------------------------------------------------------
    # 4. Nâng cấp DreamEngine
    # ---------------------------------------------------------------
    try:
        pet.dream_engine._dream_once = types.MethodType(
            _v7_dream_once,
            pet.dream_engine
        )
    except Exception:
        pass

    # ---------------------------------------------------------------
    # 5. Background tasks
    # ---------------------------------------------------------------
    try:
        pet.scheduler._add_task(
            "v7_forgetting_decay",
            300,
            lambda: _decay_task(pet)
        )
    except Exception:
        pass

    try:
        pet.scheduler._add_task(
            "v7_memory_consolidation",
            900,
            lambda: _consolidation_task(pet)
        )
    except Exception:
        pass

    try:
        pet.scheduler._add_task(
            "v7_curiosity",
            600,
            lambda: _curiosity_task(pet)
        )
    except Exception:
        pass

    # ---------------------------------------------------------------
    # 6. answer_v7
    # ---------------------------------------------------------------
    previous_answer = getattr(pet, "answer_v6", None) or pet.answer

    def answer_v7(user_input):
        text = str(user_input).strip()
        if not text:
            return None, "Bạn nói gì tui cũng nghe, nhưng câu trống quá."

        low = text.lower()

        # -----------------------------------------------------------
        # V7 commands
        # -----------------------------------------------------------
        if low in ("v7", "v7 stats", "deep stats"):
            return None, _v7_stats(pet)

        if low in ("forget", "quên", "quên bớt", "decay"):
            try:
                with pet.lock:
                    weak_docs = pet.ebbinghaus.decay_documents(pet.documents)
                    removed_eps = pet.ebbinghaus.decay_episodic(pet.memory)
                    pruned = pet.ebbinghaus.prune_documents(pet)

                    if pruned:
                        pet.rebuild_index()
                        pet.rebuild_markov()
                        pet.rebuild_vector()

                    pet.save_all()

                return None, (
                    f"🧹 Ebbinghaus cleanup:\n"
                    f"  • Tài liệu yếu: {len(weak_docs)}\n"
                    f"  • Episodic đã quên: {removed_eps}\n"
                    f"  • Docs đã prune: {pruned}"
                )
            except Exception as e:
                return None, f"⚠️ Lỗi khi forget: {e}"

        if low in ("consolidate", "nén ký ức", "nén trí nhớ", "memory consolidate"):
            try:
                with pet.lock:
                    facts = pet.memory_consolidator.consolidate(pet, max_episodes=10)

                    if facts:
                        pet.rebuild_index()

                        if len(pet.documents) < 3000 and hasattr(pet, "rebuild_vector"):
                            pet.rebuild_vector()

                    pet.save_all()

                if facts:
                    return None, "🧠 Đã nén ký ức thành tri thức:\n" + "\n".join(f"- " + f for f in facts[:5])

                return None, "🧠 Chưa có ký ức đủ mạnh để nén."
            except Exception as e:
                return None, f"⚠️ Lỗi consolidation: {e}"

        if low in ("curious", "tò mò", "buồn chán"):
            thought = pet.curiosity.idle_think(pet, force=True)
            if thought:
                return None, f"🌱 {thought}"
            return None, "Tui chưa tìm ra chủ đề mới để tò mò."

        # -----------------------------------------------------------
        # Data Analyst
        # -----------------------------------------------------------
        try:
            if pet.data_analyst.can_handle(text):
                think, answer = pet.data_analyst.run(text)

                if answer:
                    pet.memory.add_turn("user", text)
                    pet.last_interaction = time.time()
                    pet.memory.add_turn("pet", answer)
                    return think, answer
        except Exception:
            pass

        # -----------------------------------------------------------
        # Gọi pipeline cũ / v6
        # -----------------------------------------------------------
        think, answer = previous_answer(text)

        # -----------------------------------------------------------
        # Proactive curiosity khi chào hỏi
        # -----------------------------------------------------------
        if _is_greeting(low):
            try:
                proactive = pet.curiosity.consume()
                if proactive:
                    answer = proactive + " " + answer
            except Exception:
                pass

        # -----------------------------------------------------------
        # Adversarial fact-check cho câu hỏi kiến thức
        # -----------------------------------------------------------
        if _is_knowledge(low):
            try:
                answer, critique = pet.adversarial.check(pet, text, answer)

                if critique:
                    think = (think or "") + "\n" + critique
            except Exception:
                pass

        return think, answer

    pet.answer_v7 = answer_v7
    pet._v7_installed = True
