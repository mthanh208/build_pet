# -*- coding: utf-8 -*-
import random, json, os

_EMOTIONS = {
    "vui":{"valence":0.8,"arousal":0.6,"dominance":0.5},
    "buồn":{"valence":-0.7,"arousal":0.2,"dominance":0.1},
    "tức giận":{"valence":-0.8,"arousal":0.9,"dominance":0.7},
    "sợ":{"valence":-0.8,"arousal":0.9,"dominance":0.1},
    "yêu thương":{"valence":0.9,"arousal":0.5,"dominance":0.3},
    "nhớ nhung":{"valence":0.2,"arousal":0.4,"dominance":0.1},
    "tò mò":{"valence":0.4,"arousal":0.7,"dominance":0.5},
    "bình yên":{"valence":0.6,"arousal":0.1,"dominance":0.4},
    "hối hận":{"valence":-0.5,"arousal":0.3,"dominance":0.2},
    "tự hào":{"valence":0.7,"arousal":0.6,"dominance":0.8},
    "cô đơn":{"valence":-0.6,"arousal":0.2,"dominance":0.0},
    "biết ơn":{"valence":0.8,"arousal":0.3,"dominance":0.3},
}

_TRANSITIONS = {
    "vui":["tò mò","yêu thương","tự hào","bình yên"],
    "buồn":["nhớ nhung","cô đơn","bình yên","hối hận"],
    "tức giận":["sợ","buồn","tò mò"],
    "sợ":["tức giận","buồn","bình yên"],
    "yêu thương":["vui","nhớ nhung","biết ơn"],
    "nhớ nhung":["buồn","yêu thương","cô đơn"],
    "tò mò":["vui","tự hào","bình yên"],
    "bình yên":["vui","tò mò","biết ơn"],
    "hối hận":["buồn","bình yên"],
    "tự hào":["vui","tò mò"],
    "cô đơn":["nhớ nhung","buồn","yêu thương"],
    "biết ơn":["vui","yêu thương","bình yên"],
}

class EmotionGraph:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.current_emotion = "bình yên"
        self.intensity = 0.5
        self.history = []
        self.emotion_log = []
        if save_path and os.path.exists(save_path): self.load()

    def feel(self, trigger_text, intensity=0.5):
        low = trigger_text.lower()
        detected = None
        for emo in _EMOTIONS:
            if emo in low:
                detected = emo
                break
        if not detected:
            candidates = _TRANSITIONS.get(self.current_emotion, ["bình yên"])
            detected = random.choice(candidates)
        self.transition_to(detected, intensity)
        return detected

    def transition_to(self, emotion, intensity=0.5):
        if emotion not in _EMOTIONS: emotion = "bình yên"
        old = self.current_emotion
        self.current_emotion = emotion
        self.intensity = max(0.0, min(1.0, intensity))
        self.history.append((emotion, self.intensity))
        if len(self.history) > 100: self.history = self.history[-50:]
        self.emotion_log.append(f"{old} -> {emotion} (i={intensity:.2f})")
        if len(self.emotion_log) > 200: self.emotion_log = self.emotion_log[-100:]
        self.save()

    def get_pad(self): return _EMOTIONS.get(self.current_emotion, _EMOTIONS["bình yên"])
    def get_valence(self): return self.get_pad()["valence"] * self.intensity
    def get_arousal(self): return self.get_pad()["arousal"] * self.intensity

    def get_emotional_color(self):
        colors = {"vui":"rạng rỡ","buồn":"chùng xuống","tức giận":"nóng ran","sợ":"run run","yêu thương":"ấm áp","nhớ nhung":"da diết","tò mò":"háo hức","bình yên":"nhẹ nhàng","hối hận":"nặng trĩu","tự hào":"hân hoan","cô đơn":"lặng lẽ","biết ơn":"sâu lắng"}
        return colors.get(self.current_emotion, "bình thường")

    def decay(self, factor=0.95):
        self.intensity *= factor
        if self.intensity < 0.1: self.transition_to("bình yên", 0.3)

    def save(self):
        if self.save_path:
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"current": self.current_emotion, "intensity": self.intensity, "history": self.history[-20:]}, f, ensure_ascii=False)
            except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_emotion = data.get("current", "bình yên")
            self.intensity = data.get("intensity", 0.5)
        except: pass
