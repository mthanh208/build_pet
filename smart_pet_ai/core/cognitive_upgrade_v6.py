# -*- coding: utf-8 -*-
import os
import time

from core.cognitive_cache import PersistentLRU
from core.meta_prompt_engine import MetaPromptEngine
from core.theory_of_mind import TheoryOfMindEngine
from core.react_tool_agent import ReactToolAgent
from core.graphrag_engine import GraphRAGEngine
from core.reflection_engine import ReflectionEngine
from core.system2_reasoner import System2Reasoner
from core.dual_process_router import DualProcessRouter


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_MEMORY = os.path.join(BASE_DIR, "data_memory")


def _v6_stats_text(pet):
    lines = ["🧠 V6 Cognitive Architecture:"]

    try:
        lines.append(pet.dual_router.stats_text())
    except Exception:
        lines.append("  • Dual-Process Router: unavailable")

    try:
        g = pet.graphrag.stats()
        lines.append(f"  • GraphRAG communities: {g.get('communities', 0)}")
    except Exception:
        pass

    try:
        r = pet.reflection.stats()
        lines.append(f"  • Reflections: {r.get('reflections', 0)}")
    except Exception:
        pass

    try:
        s2 = pet.system2.stats()
        lines.append(f"  • System2 runs: {s2.get('run_count', 0)}")
    except Exception:
        pass

    try:
        react = pet.react.stats()
        lines.append(f"  • ReAct tool uses: {react.get('use_count', 0)}")
    except Exception:
        pass

    return "\n".join(lines)


def install_v6(pet):
    """
    Cài đặt kiến trúc v6 vào Pet hiện tại.
    Không train lại model, chỉ thêm engine mới.
    """

    if getattr(pet, "_v6_installed", False):
        return

    os.makedirs(DATA_MEMORY, exist_ok=True)

    # Meta-prompt engine
    pet.meta_prompt = MetaPromptEngine(
        save_path=os.path.join(DATA_MEMORY, "meta_prompts.json")
    )

    # Theory of Mind
    pet.tom = TheoryOfMindEngine(pet)

    # ReAct tool agent
    pet.react = ReactToolAgent(pet)

    # GraphRAG
    pet.graphrag = GraphRAGEngine(pet)

    # Reflection
    pet.reflection = ReflectionEngine(
        pet,
        save_path=os.path.join(DATA_MEMORY, "reflections.json")
    )

    # System 2
    pet.system2 = System2Reasoner(pet)

    # System 1 cache
    system1_cache = PersistentLRU(
        save_path=os.path.join(DATA_MEMORY, "system1_cache.json"),
        max_size=300
    )

    # Dual-Process Router
    pet.dual_router = DualProcessRouter(
        pet=pet,
        system2=pet.system2,
        cache=system1_cache
    )

    # Background reflection task
    try:
        pet.scheduler._add_task(
            "v6_reflection",
            900,
            pet.reflection.reflect_now
        )
    except Exception:
        pass

    def answer_v6(user_input):
        text = str(user_input).strip()
        if not text:
            return "", "Bạn nói gì tui cũng nghe, nhưng câu trống quá."

        low = text.lower()

        # V6 commands
        if low in ("v6", "v6 stats", "router stats", "dual process"):
            return None, _v6_stats_text(pet)

        if low in ("reflect", "suy ngẫm", "suy ngam"):
            insight = pet.reflection.reflect_now()
            if insight:
                return None, f"🪞 {insight}"
            return None, "Tui chưa đủ ký ức để suy ngẫm sâu hơn."

        # Dual-process routing
        handled, think_block, answer, route = pet.dual_router.process(text)

        if handled and answer:
            # Cập nhật memory, emotion, personality tương tự orchestrator cũ
            try:
                pet.memory.add_turn("user", text)
                pet.last_interaction = time.time()

                detected_emotion = pet.emotion_graph.feel(text, intensity=0.5)

                sentiment = pet._check_feedback(text)
                if sentiment != 0:
                    pet.apply_feedback(sentiment)

                    try:
                        if route in ("S1", "S1-cache"):
                            pet.meta_prompt.record_feedback("s1_chitchat", sentiment > 0)
                        else:
                            pet.meta_prompt.record_feedback("s2_answer", sentiment > 0)
                    except Exception:
                        pass

                pet.personality.update_from_interaction(text, sentiment)
                pet.memory.add_turn("pet", answer)
                pet.memory.tag_emotion("v6_route", detected_emotion, pet.emotion_graph.intensity)
            except Exception:
                pass

            full_think = f"🧭 Route: {route}\n{think_block}" if think_block else f"🧭 Route: {route}"
            return full_think, answer

        # Fallback về pipeline cũ
        return pet.answer(text)

    pet.answer_v6 = answer_v6
    pet._v6_installed = True
