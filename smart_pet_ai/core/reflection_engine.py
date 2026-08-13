# -*- coding: utf-8 -*-
import json
import os
import time


class ReflectionEngine:
    """
    Generative Reflection Engine.

    Đọc episodic memory, tạo insight cấp cao.
    Lấy cảm hứng từ Stanford Generative Agents.
    """

    def __init__(self, pet, save_path=None):
        self.pet = pet
        self.save_path = save_path
        self.reflections = []

        if save_path and os.path.exists(save_path):
            self.load()

    def reflect_now(self):
        try:
            with self.pet.lock:
                episodes = self.pet.memory.episodic[-12:]
                if not episodes:
                    return None

                important = sorted(
                    episodes,
                    key=lambda x: x.get("importance", 0),
                    reverse=True
                )[:4]

                text = " ".join([ep.get("summary", "") for ep in important])
                keywords = []

                try:
                    keywords = self.pet.nlp_engine.extract_keywords(text, limit=6)
                except Exception:
                    keywords = []

                emotion = self.pet.emotion_graph.current_emotion

                insight = None

                if self.pet.neural_engine.available:
                    prompt = (
                        "Bạn là Pet AI đang tự suy ngẫm về các cuộc trò chuyện gần đây.\n"
                        f"Cảm xúc hiện tại: {emotion}\n"
                        f"Chủ đề nổi bật: {', '.join(keywords[:5])}\n"
                        f"Ký ức tóm tắt: {text[:500]}\n"
                        "Hãy viết một câu insight ngắn gọn, sâu sắc, ngôi thứ nhất, không sến.\n"
                        "Insight:"
                    )

                    insight = self.pet.neural_engine.generate(
                        prompt,
                        max_tokens=80,
                        temperature=0.6
                    )

                if not insight or len(str(insight).strip()) < 10:
                    if keywords:
                        insight = (
                            f"Gần đây tui nhận thấy các chủ đề "
                            f"{', '.join(keywords[:3])} xuất hiện nhiều. "
                            f"Tui sẽ chú ý hơn đến cảm xúc của bạn."
                        )
                    else:
                        insight = "Tui đang học cách lắng nghe bạn tốt hơn mỗi ngày."

                insight = str(insight).strip()

                self.reflections.append({
                    "time": time.time(),
                    "insight": insight,
                    "emotion": emotion,
                    "keywords": keywords[:6]
                })

                if len(self.reflections) > 50:
                    self.reflections = self.reflections[-30:]

                try:
                    self.pet.narrative.self_reflections.append(insight)
                    if len(self.pet.narrative.self_reflections) > 50:
                        self.pet.narrative.self_reflections = self.pet.narrative.self_reflections[-30:]
                except Exception:
                    pass

                try:
                    self.pet.memory.remember_fact("insight_gan_nhat", insight)
                except Exception:
                    pass

                self.save()
                return insight

        except Exception:
            return None

    def latest(self):
        if not self.reflections:
            return None
        return self.reflections[-1].get("insight")

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({"reflections": self.reflections}, f, ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.reflections = data.get("reflections", [])
        except Exception:
            self.reflections = []

    def stats(self):
        return {"reflections": len(self.reflections)}
