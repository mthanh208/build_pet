# -*- coding: utf-8 -*-
import json
import os
import time


DEFAULT_TEMPLATES = {
    "s1_chitchat": [
        "Bạn là Pet AI thân thiện. Tâm trạng: {emotion}. Phong cách: {style}. Trả lời ngắn 1-2 câu, tự nhiên, ấm áp. Người dùng: {query}\nPet:",
        "Bạn là Pet AI đáng yêu. Tâm trạng: {emotion}. Hãy trả lời rất ngắn, tự nhiên như bạn thân. Người dùng: {query}\nPet:"
    ],
    "s2_answer": [
        "Bạn là Pet AI đang suy nghĩ sâu. Tâm trạng: {emotion}. Phong cách: {style}. Dựa trên bằng chứng sau, trả lời ngắn gọn, có căn cứ. Nếu thiếu dữ kiện, nói rõ là chưa chắc.\nBằng chứng:\n{context}\nCâu hỏi: {query}\nPet:",
        "Bạn là Pet AI cẩn trọng. Tâm trạng: {emotion}. Phong cách: {style}. Hãy trả lời dựa trên bằng chứng, ưu tiên chính xác hơn dài dòng.\nBằng chứng:\n{context}\nCâu hỏi: {query}\nPet:"
    ],
    "debate_optimist": [
        "Bạn là agent lạc quan. Hãy nêu điểm mạnh của câu trả lời dựa trên bằng chứng.\nCâu hỏi: {query}\nBằng chứng:\n{context}\nĐiểm mạnh:"
    ],
    "debate_skeptic": [
        "Bạn là agent hoài nghi. Hãy chỉ ra rủi ro, thiếu sót hoặc điểm chưa chắc chắn.\nCâu hỏi: {query}\nBằng chứng:\n{context}\nRủi ro:"
    ],
    "debate_synthesizer": [
        "Bạn là agent tổng hợp. Kết hợp góc nhìn lạc quan và hoài nghi để đưa ra câu trả lời cuối cùng, ngắn gọn, an toàn.\nCâu hỏi: {query}\nLạc quan: {optimist}\nHoài nghi: {skeptic}\nTrả lời cuối:"
    ]
}


class MetaPromptEngine:
    """
    Self-Evolving Meta-Prompting.

    Lưu các template prompt, template nào hiệu quả sẽ được ưu tiên.
    Không train model, chỉ tối ưu prompt dựa trên feedback.
    """

    def __init__(self, save_path=None):
        self.save_path = save_path
        self.templates = {}
        self.stats = {}
        self.current = {}

        self._load_defaults()

        if save_path and os.path.exists(save_path):
            self.load()

    def _load_defaults(self):
        for name, prompt_list in DEFAULT_TEMPLATES.items():
            self.templates[name] = prompt_list[:]
            self.stats[name] = []
            for _ in prompt_list:
                self.stats[name].append({
                    "success": 0,
                    "fail": 0,
                    "uses": 0,
                    "last_used": 0
                })
            self.current[name] = 0

    def get_template(self, name):
        if name not in self.templates:
            return ""

        candidates = self.templates[name]
        if not candidates:
            return ""

        best_idx = 0
        best_score = -1.0

        for i, st in enumerate(self.stats.get(name, [])):
            success = st.get("success", 0)
            fail = st.get("fail", 0)
            score = (success + 1.0) / (success + fail + 2.0)
            if score > best_score:
                best_score = score
                best_idx = i

        self.current[name] = best_idx
        return candidates[best_idx]

    def render(self, name, mapping):
        template = self.get_template(name)
        if not template:
            return ""

        out = template
        for k, v in mapping.items():
            out = out.replace("{" + str(k) + "}", str(v))

        return out

    def record_usage(self, name):
        if name not in self.stats:
            return

        idx = self.current.get(name, 0)
        if idx < len(self.stats[name]):
            self.stats[name][idx]["uses"] += 1
            self.stats[name][idx]["last_used"] = time.time()
            self.save()

    def record_feedback(self, name, positive):
        if name not in self.stats:
            return

        idx = self.current.get(name, 0)
        if idx >= len(self.stats[name]):
            return

        if positive:
            self.stats[name][idx]["success"] += 1
        else:
            self.stats[name][idx]["fail"] += 1

        self.save()

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "templates": self.templates,
                    "stats": self.stats,
                    "current": self.current
                }, f, ensure_ascii=False, indent=0)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            loaded_templates = data.get("templates", {})
            loaded_stats = data.get("stats", {})
            loaded_current = data.get("current", {})

            for name in DEFAULT_TEMPLATES:
                if name in loaded_templates and loaded_templates[name]:
                    self.templates[name] = loaded_templates[name]
                    self.stats[name] = loaded_stats.get(name, [])
                    if len(self.stats[name]) != len(self.templates[name]):
                        self.stats[name] = []
                        for _ in self.templates[name]:
                            self.stats[name].append({
                                "success": 0,
                                "fail": 0,
                                "uses": 0,
                                "last_used": 0
                            })
                    self.current[name] = loaded_current.get(name, 0)

        except Exception:
            self._load_defaults()
