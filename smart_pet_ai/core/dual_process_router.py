# -*- coding: utf-8 -*-
import re
import time


class DualProcessRouter:
    """
    Dual-Process Router.

    System 1: nhanh, cache, pattern, emotion, chit-chat.
    System 2: chậm, retrieval, GraphRAG, debate, self-correction.
    """

    GREETING_PATTERNS = [
        "chào", "hello", "hi", "hey", "xin chào", "alo", "yo"
    ]

    EMOTION_PATTERNS = [
        "buồn", "vui", "mệt", "giận", "sợ", "cô đơn", "nhớ", "thương",
        "áp lực", "stress", "chán", "hạnh phúc", "đau", "khó chịu"
    ]

    KNOWLEDGE_MARKERS = [
        "là gì", "là ai", "như thế nào", "tại sao", "vì sao",
        "so sánh", "khác gì", "phân tích", "cách", "hướng dẫn",
        "ví dụ", "định nghĩa", "giải thích", "nghĩa là",
        "nguyên nhân", "kết quả", "ứng dụng", "khái niệm"
    ]

    def __init__(self, pet, system2, cache):
        self.pet = pet
        self.system2 = system2
        self.cache = cache

        self.enabled = False
        self.sys1_threshold = 0.66
        self.sys2_threshold = 0.45
        self.debate_threshold = 0.72

        self.stats = {
            "system1": 0,
            "system2": 0,
            "cache": 0,
            "fallback": 0
        }

    def _normalize(self, text):
        return re.sub(r"\s+", " ", str(text)).strip().lower()

    def _detect_emotion(self, query):
        low = str(query).lower()
        for emo in self.EMOTION_PATTERNS:
            if emo in low:
                return emo
        return None

    def _features(self, query):
        low = str(query).lower()
        words = str(query).split()
        word_count = len(words)

        entities = []
        try:
            entities = self.pet.graph_engine.extract_entities(query)
        except Exception:
            entities = []

        has_knowledge_marker = any(k in low for k in self.KNOWLEDGE_MARKERS)
        has_complex_trigger = any(k in low for k in getattr(self.pet, "TOT_TRIGGERS", []))
        is_greeting = any(g in low for g in self.GREETING_PATTERNS)
        emotion = self._detect_emotion(query)
        is_question = "?" in query

        math_like = bool(re.search(r"\d\s*[\+\-\*/\^]\s*\d", query))
        time_like = any(k in low for k in ["mấy giờ", "ngày mấy", "hôm nay là ngày"])

        complexity = 0.0

        if has_knowledge_marker:
            complexity += 0.30
        if has_complex_trigger:
            complexity += 0.25
        if word_count > 18:
            complexity += 0.15
        if len(entities) >= 2:
            complexity += 0.15
        if is_question and has_knowledge_marker:
            complexity += 0.10
        if math_like or time_like:
            complexity += 0.15

        complexity = max(0.0, min(1.0, complexity))

        return {
            "low": low,
            "word_count": word_count,
            "entities": entities,
            "has_knowledge_marker": has_knowledge_marker,
            "has_complex_trigger": has_complex_trigger,
            "is_greeting": is_greeting,
            "emotion": emotion,
            "is_question": is_question,
            "math_like": math_like,
            "time_like": time_like,
            "complexity": complexity
        }

    def _system1(self, query, features):
        think = ["⚡ System 1: tư duy nhanh"]

        # Feedback ngắn
        try:
            sentiment = self.pet._check_feedback(query)
        except Exception:
            sentiment = 0

        if sentiment != 0 and features["word_count"] <= 5:
            if sentiment > 0:
                answer = self.pet.dialogue.synthesize_emotional(
                    "vui",
                    0.7,
                    self.pet.personality.get_language_register(),
                    "Cảm ơn bạn đã phản hồi tốt!"
                )
            else:
                answer = self.pet.dialogue.synthesize_emotional(
                    "buồn",
                    0.5,
                    self.pet.personality.get_language_register(),
                    "Tui xin lỗi, tui sẽ điều chỉnh lại."
                )

            think.append("System 1: feedback route")
            return answer, 0.92, "\n".join(think)

        # Không xử lý nhanh nếu là câu hỏi kiến thức rõ ràng
        if features["has_knowledge_marker"]:
            return None, 0.0, "\n".join(think)

        # Greeting / chit-chat
        if features["is_greeting"] or features["word_count"] <= 12:
            try:
                answer = self.pet.orchestrator._chitchat_response(
                    query,
                    self.pet.emotion_graph.current_emotion,
                    unknown=False
                )

                if answer and len(answer.strip()) > 3:
                    conf = 0.78
                    if features["is_greeting"]:
                        conf = 0.88
                    elif features["emotion"]:
                        conf = 0.80

                    think.append("System 1: chit-chat route")
                    return answer, conf, "\n".join(think)
            except Exception:
                pass

        # Emotion route
        if features["emotion"] and features["word_count"] <= 20:
            emotion_map = {
                "buồn": "buồn",
                "đau": "buồn",
                "chán": "buồn",
                "vui": "vui",
                "hạnh phúc": "vui",
                "giận": "tức giận",
                "sợ": "sợ",
                "cô đơn": "cô đơn",
                "nhớ": "nhớ nhung",
                "thương": "yêu thương"
            }

            emo = emotion_map.get(features["emotion"], "bình yên")
            answer = self.pet.dialogue.synthesize_emotional(
                emo,
                0.6,
                self.pet.personality.get_language_register(),
                "Tui cảm nhận được điều bạn đang nói."
            )

            think.append("System 1: emotion route")
            return answer, 0.78, "\n".join(think)

        # Neural short chit-chat
        if self.pet.neural_engine.available and features["word_count"] <= 12 and not features["is_question"]:
            try:
                tom_state = self.pet.tom.analyze(query)
                style = tom_state.get("style_hint", "tự nhiên")

                prompt = self.pet.meta_prompt.render("s1_chitchat", {
                    "emotion": self.pet.emotion_graph.current_emotion,
                    "style": style,
                    "query": query
                })

                self.pet.meta_prompt.record_usage("s1_chitchat")

                resp = self.pet.neural_engine.generate(
                    prompt,
                    max_tokens=70,
                    temperature=0.8
                )

                if resp and len(resp.strip()) > 3:
                    think.append("System 1: neural chit-chat route")
                    return resp.strip(), 0.74, "\n".join(think)
            except Exception:
                pass

        return None, 0.0, "\n".join(think)

    def process(self, query):
        if not self.enabled:
            return False, "", "", "disabled"

        start = time.time()
        norm = self._normalize(query)

        # Cache
        cached = self.cache.get(norm)
        if cached:
            self.stats["cache"] += 1
            elapsed = time.time() - start
            think = f"⚡ System 1 cache hit ({elapsed:.3f}s)"
            return True, think, cached, "S1-cache"

        features = self._features(query)

        # System 1
        s1_answer, s1_conf, s1_think = self._system1(query, features)

        if s1_answer and s1_conf >= self.sys1_threshold and features["complexity"] < self.sys2_threshold:
            self.stats["system1"] += 1
            if len(s1_answer) < 300:
                self.cache.set(norm, s1_answer, meta={"route": "S1"})

            elapsed = time.time() - start
            think = s1_think + f"\n⏱️ System1 latency: {elapsed:.3f}s"
            return True, think, s1_answer, "S1"

        # System 2
        try:
            answer, think2, conf = self.system2.reason(query, features["complexity"])
        except Exception:
            self.stats["fallback"] += 1
            return False, "", "", "fallback"

        if not answer or conf < 0.22:
            self.stats["fallback"] += 1
            return False, think2, "", "fallback"

        self.stats["system2"] += 1

        if len(answer) < 350:
            self.cache.set(norm, answer, meta={"route": "S2", "conf": conf})

        elapsed = time.time() - start
        think = f"{think2}\n🧭 Route: System2\n⏱️ Total latency: {elapsed:.2f}s"
        return True, think, answer, "S2"

    def stats_text(self):
        cache_stats = self.cache.stats()
        return (
            "🧠 Dual-Process Router stats:\n"
            f"  • System 1: {self.stats['system1']}\n"
            f"  • System 2: {self.stats['system2']}\n"
            f"  • Cache hit: {self.stats['cache']}\n"
            f"  • Fallback: {self.stats['fallback']}\n"
            f"  • Cache size: {cache_stats['size']}, hits={cache_stats['hits']}, misses={cache_stats['misses']}"
        )
