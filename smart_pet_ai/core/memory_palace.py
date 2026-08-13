# -*- coding: utf-8 -*-
import json, os, time, random, re
from collections import defaultdict
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

def tokenize(text): return _WORD_RE.findall(text.lower())

class MemoryPalace:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.working = []
        self.episodic = []
        self.emotional_tags = defaultdict(list)
        self.facts_about_user = {}
        self.last_topics = []
        if save_path and os.path.exists(save_path): self.load()

    def add_turn(self, role, text):
        self.working.append({"role": role, "text": text, "time": time.time()})
        if len(self.working) > 30: self._consolidate_working()

    def _consolidate_working(self):
        if len(self.working) < 6: return
        chunk = self.working[:10]
        self.working = self.working[5:]
        summary = " ".join([t["text"] for t in chunk])
        importance = self._estimate_importance(summary)
        self.episodic.append({"summary": summary[:300], "importance": importance, "time": time.time(), "turns": len(chunk)})
        if len(self.episodic) > 200: self.episodic = sorted(self.episodic, key=lambda x: x["importance"], reverse=True)[:150]

    def _estimate_importance(self, text):
        score = 0.0
        low = text.lower()
        strong = ["yêu", "ghét", "buồn", "vui", "giận", "sợ", "nhớ", "quý", "thương", "đau", "hạnh phúc"]
        for w in strong:
            if w in low: score += 0.3
        if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text): score += 0.4
        score += min(len(text.split()) / 50.0, 0.3)
        return min(score, 1.0)

    def tag_emotion(self, entity, emotion, intensity):
        self.emotional_tags[entity].append({"emotion": emotion, "intensity": intensity, "time": time.time()})

    def remember_fact(self, key, value):
        self.facts_about_user[key] = {"value": value, "time": time.time()}

    def recall_facts(self, query):
        tokens = set(tokenize(query))
        results = []
        for k, v in self.facts_about_user.items():
            k_tokens = set(tokenize(k))
            if tokens & k_tokens:
                results.append((k, v["value"], v["time"]))
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:3]

    def retrieve_relevant(self, query, emotion_state=None, limit=5):
        tokens = set(tokenize(query))
        scored = []
        now = time.time()
        for turn in reversed(self.working[-10:]):
            t_tokens = set(tokenize(turn["text"]))
            overlap = len(tokens & t_tokens)
            recency = 1.0 / (1.0 + (now - turn["time"]) / 60.0)
            score = overlap * 2.0 + recency * 1.5
            scored.append(("working", turn["text"], score, turn["time"]))
        for ep in self.episodic:
            t_tokens = set(tokenize(ep["summary"]))
            overlap = len(tokens & t_tokens)
            recency = 1.0 / (1.0 + (now - ep["time"]) / 3600.0)
            salience = ep["importance"]
            score = overlap * 1.0 + recency * 0.8 + salience * 1.5
            scored.append(("episodic", ep["summary"], score, ep["time"]))
        scored.sort(key=lambda x: x[2], reverse=True)
        seen = set()
        results = []
        for src, text, score, ts in scored:
            if text not in seen:
                seen.add(text)
                results.append({"source": src, "text": text, "score": score})
            if len(results) >= limit: break
        return results

    def get_conversation_context(self, n=3, role=None):
        if role:
            filtered = [t for t in self.working if t["role"] == role]
            return filtered[-n:] if filtered else []
        return self.working[-n:] if self.working else []

    def get_user_profile_summary(self):
        if not self.facts_about_user: return None
        items = sorted(self.facts_about_user.items(), key=lambda x: x[1]["time"], reverse=True)[:5]
        return ", ".join([f"{k}: {v['value']}" for k, v in items])

    def save(self):
        if self.save_path:
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"episodic": self.episodic, "emotional_tags": dict(self.emotional_tags), "facts_about_user": self.facts_about_user}, f, ensure_ascii=False)
            except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.episodic = data.get("episodic", [])
            self.emotional_tags = defaultdict(list, data.get("emotional_tags", {}))
            self.facts_about_user = data.get("facts_about_user", {})
        except: pass
