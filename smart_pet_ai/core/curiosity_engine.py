# -*- coding: utf-8 -*-
import json
import os
import random
import time


class CuriosityEngine:
    """
    Proactive Curiosity Engine.

    Khi user vắng mặt lâu:
      - boredom tăng
      - Pet tự chọn chủ đề mới lạ từ Knowledge Graph
      - Pet tự tạo suy nghĩ tò mò
      - lưu vào pending_thoughts
    """

    def __init__(self, save_path=None):
        self.save_path = save_path
        self.boredom = 0.2
        self.pending = []
        self.stats = {"thoughts": 0}

        if save_path and os.path.exists(save_path):
            self.load()

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "boredom": self.boredom,
                    "pending": self.pending[-10:],
                    "stats": self.stats
                }, f, ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.boredom = data.get("boredom", 0.2)
            self.pending = data.get("pending", [])
            self.stats = data.get("stats", self.stats)
        except Exception:
            pass

    def update_idle(self, idle_seconds):
        try:
            self.boredom = min(1.0, self.boredom + float(idle_seconds) / 7200.0)
            self.save()
        except Exception:
            pass

    def _pick_novel_topic(self, pet):
        try:
            g = pet.graph_engine.graph

            if g.number_of_nodes() == 0:
                return None

            nodes = list(g.nodes(data=True))

            candidates = [
                n for n, d in nodes
                if int(d.get("count", 1)) <= 5
            ]

            if len(candidates) < 5:
                candidates = [n for n, d in nodes]

            candidates.sort(key=lambda n: g.degree(n), reverse=True)

            if not candidates:
                return None

            return random.choice(candidates[:20])
        except Exception:
            return None

    def _generate_thought(self, pet, topic):
        if getattr(pet, "neural_engine", None) and pet.neural_engine.available:
            try:
                prompt = (
                    f"Bạn là Pet AI tò mò. Hãy viết một câu thắc mắc ngắn gọn, đáng yêu về chủ đề '{topic}'. "
                    "Không trả lời, chỉ thắc mắc.\n"
                    "Pet:"
                )

                out = pet.neural_engine.generate(
                    prompt,
                    max_tokens=40,
                    temperature=0.8
                )

                if out and len(out.strip()) > 5:
                    return out.strip()
            except Exception:
                pass

        return f"Tui đang tự hỏi về {topic}... Bạn có muốn cùng tui tìm hiểu không?"

    def idle_think(self, pet, force=False):
        if not force and self.boredom < 0.35:
            return None

        topic = self._pick_novel_topic(pet)
        if not topic:
            return None

        thought = self._generate_thought(pet, topic)

        self.pending.append({
            "time": time.time(),
            "topic": topic,
            "thought": thought
        })

        self.pending = self.pending[-8:]
        self.boredom = max(0.05, self.boredom - 0.45)
        self.stats["thoughts"] += 1
        self.save()

        return thought

    def consume(self):
        if not self.pending:
            return None

        item = self.pending.pop(0)
        self.save()

        return item.get("thought")

    def stats_text(self):
        return (
            "🌱 Curiosity stats:\n"
            f"  • Boredom: {self.boredom:.2f}\n"
            f"  • Pending thoughts: {len(self.pending)}\n"
            f"  • Total thoughts: {self.stats.get('thoughts', 0)}"
        )
