# -*- coding: utf-8 -*-
import random, json, os

class PersonalityEngine:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.traits = {"openness": 0.6, "conscientiousness": 0.5, "extraversion": 0.4, "agreeableness": 0.7, "neuroticism": 0.3}
        self.mood = {"valence": 0.3, "arousal": 0.3, "dominance": 0.5}
        self.relationship = {"closeness": 0.2, "trust": 0.5, "playfulness": 0.6}
        self.style = {"formality": 0.2, "poetic": 0.4, "warmth": 0.7, "verbosity": 0.5, "metaphor": 0.4}
        self.experience_count = 0
        if save_path and os.path.exists(save_path): self.load()

    def update_from_interaction(self, user_text, sentiment=0):
        self.experience_count += 1
        low = user_text.lower()
        if sentiment > 0:
            self.relationship["trust"] = min(1.0, self.relationship["trust"] + 0.05)
            self.relationship["closeness"] = min(1.0, self.relationship["closeness"] + 0.03)
            self.mood["valence"] = min(1.0, self.mood["valence"] + 0.1)
        elif sentiment < 0:
            self.relationship["trust"] = max(0.0, self.relationship["trust"] - 0.03)
            self.mood["valence"] = max(-1.0, self.mood["valence"] - 0.15)
            self.traits["neuroticism"] = min(1.0, self.traits["neuroticism"] + 0.01)
        else:
            self.relationship["closeness"] = min(1.0, self.relationship["closeness"] + 0.01)
        if any(w in low for w in ["yêu", "thương", "quý", "nhớ", "hạnh phúc"]):
            self.mood["valence"] = min(1.0, self.mood["valence"] + 0.2)
            self.style["warmth"] = min(1.0, self.style["warmth"] + 0.05)
        if any(w in low for w in ["giận", "bực", "chán", "tệ", "dở"]):
            self.mood["valence"] = max(-1.0, self.mood["valence"] - 0.15)
            self.style["warmth"] = max(0.0, self.style["warmth"] - 0.03)
        if any(w in low for w in ["học", "biết", "tại sao", "như thế nào"]):
            self.traits["openness"] = min(1.0, self.traits["openness"] + 0.02)
        self.mood["valence"] *= 0.98
        self.mood["arousal"] = 0.3 + (self.mood["arousal"] - 0.3) * 0.95
        self.save()

    def get_language_register(self):
        reg = {}
        reg["formality"] = max(0.0, self.style["formality"] - self.relationship["closeness"] * 0.3)
        reg["warmth"] = self.style["warmth"] + self.mood["valence"] * 0.2
        reg["verbosity"] = self.style["verbosity"] + self.traits["openness"] * 0.2
        reg["poetic"] = self.style["poetic"] + (self.mood["arousal"] + self.traits["openness"]) * 0.15
        reg["metaphor"] = self.style["metaphor"] + self.traits["openness"] * 0.2
        return {k: max(0.0, min(1.0, v)) for k, v in reg.items()}

    def get_opening(self):
        reg = self.get_language_register()
        if reg["warmth"] > 0.7: return random.choice(["À, ", "Ơ hay, ", "Ừm, ", ""])
        elif reg["formality"] > 0.5: return random.choice(["Về vấn đề này, ", "Xét trên phương diện đó, ", ""])
        else: return random.choice(["Tui nghĩ là ", "Theo tui thì ", "Hmm, ", "Ừ, ", ""])

    def get_closing(self):
        reg = self.get_language_register()
        if self.relationship["closeness"] > 0.6 and reg["warmth"] > 0.6:
            return random.choice([" Bạn thấy sao?", " Còn bạn, bạn nghĩ gì?", " Nhỉ?", ""])
        elif reg["formality"] > 0.5: return random.choice([" Đó là quan điểm của tôi.", " Trên đây là phân tích.", ""])
        return ""

    def affect(self, base_text):
        reg = self.get_language_register()
        result = base_text
        if reg["warmth"] > 0.8 and random.random() < 0.3:
            warm_tags = [" 💕", " 🌸", " ✨"]
            result += random.choice(warm_tags)
        elif self.mood["valence"] < -0.3 and random.random() < 0.2:
            result += random.choice([" ...", " 😔", ""])
        return result

    def save(self):
        if self.save_path:
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"traits": self.traits, "mood": self.mood, "relationship": self.relationship, "style": self.style, "experience_count": self.experience_count}, f, ensure_ascii=False)
            except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.traits = data.get("traits", self.traits)
            self.mood = data.get("mood", self.mood)
            self.relationship = data.get("relationship", self.relationship)
            self.style = data.get("style", self.style)
            self.experience_count = data.get("experience_count", 0)
        except: pass
