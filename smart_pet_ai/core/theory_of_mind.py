# -*- coding: utf-8 -*-
import time
import random


class TheoryOfMindEngine:
    """
    Theory of Mind Engine.

    Ước lượng trạng thái tâm trí người dùng:
      - stress
      - fatigue
      - urgency
      - cần empathy
      - cần ngắn gọn
      - intent ẩn
    """

    NEGATIVE_WORDS = [
        "buồn", "mệt", "chán", "áp lực", "stress", "căng", "khó chịu",
        "bực", "giận", "tệ", "dở", "thất vọng", "cô đơn", "nhớ", "đau"
    ]

    URGENT_WORDS = [
        "gấp", "nhanh", "khẩn cấp", "ngay", "liền", "urgent", "asap"
    ]

    CONFUSED_WORDS = [
        "không hiểu", "khó hiểu", "rối", "mông lung", "mơ hồ", "chưa rõ"
    ]

    def __init__(self, pet):
        self.pet = pet
        self.user_state = {
            "stress": 0.25,
            "fatigue": 0.20,
            "trust": 0.50,
            "last_update": time.time()
        }

    def analyze(self, query):
        low = str(query).lower()
        words = str(query).split()
        word_count = len(words)

        hour = time.localtime().tm_hour
        night = hour >= 23 or hour < 5

        neg_score = sum(1 for w in self.NEGATIVE_WORDS if w in low)
        urgent_score = sum(1 for w in self.URGENT_WORDS if w in low)
        confused_score = sum(1 for w in self.CONFUSED_WORDS if w in low)

        stress = self.user_state.get("stress", 0.25)
        fatigue = self.user_state.get("fatigue", 0.20)

        stress += 0.08 * neg_score
        stress += 0.10 * urgent_score
        if night:
            fatigue += 0.15
            stress += 0.05

        if word_count > 30:
            fatigue += 0.05

        stress = max(0.0, min(1.0, stress))
        fatigue = max(0.0, min(1.0, fatigue))

        self.user_state["stress"] = stress * 0.98
        self.user_state["fatigue"] = fatigue * 0.98
        self.user_state["last_update"] = time.time()

        needs_empathy = neg_score > 0 or stress > 0.55
        needs_brevity = urgent_score > 0 or fatigue > 0.60
        needs_clarification = confused_score > 0

        hidden_intent = "normal"
        if urgent_score > 0:
            hidden_intent = "needs_fast_solution"
        elif neg_score > 0:
            hidden_intent = "needs_emotional_support"
        elif confused_score > 0:
            hidden_intent = "needs_explanation"

        style_hint = "tự nhiên, ấm áp"
        if needs_brevity:
            style_hint = "ngắn gọn, đi thẳng vào vấn đề"
        elif needs_empathy:
            style_hint = "dịu dàng, trấn an, giàu cảm xúc"
        elif needs_clarification:
            style_hint = "giải thích chậm, rõ ràng"

        return {
            "stress": stress,
            "fatigue": fatigue,
            "needs_empathy": needs_empathy,
            "needs_brevity": needs_brevity,
            "needs_clarification": needs_clarification,
            "hidden_intent": hidden_intent,
            "style_hint": style_hint,
            "night": night
        }

    def empathy_line(self, state):
        if not state:
            return ""

        if state.get("needs_empathy"):
            return random.choice([
                "Tui cảm thấy bạn đang hơi nhiều suy nghĩ.",
                "Chuyện này có vẻ không nhẹ nhàng.",
                "Tui ở đây nghe bạn nè.",
                "Bạn cứ nói tiếp, tui không vội."
            ])

        if state.get("needs_brevity"):
            return random.choice([
                "Tui sẽ nói ngắn gọn.",
                "Ok, đi thẳng vào vấn đề luôn."
            ])

        return ""
