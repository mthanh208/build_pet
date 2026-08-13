# -*- coding: utf-8 -*-
import hashlib
import json
import os
import re
import time


class MemoryConsolidator:
    """
    Memory Consolidation Engine.

    Nén episodic memory quan trọng thành semantic facts.
    Giống cơ chế não bộ chuyển ký ức ngắn hạn thành tri thức dài hạn.
    """

    def __init__(self, save_path=None):
        self.save_path = save_path
        self.stats = {
            "consolidations": 0,
            "facts_created": 0,
            "episodes_consolidated": 0
        }

        if save_path and os.path.exists(save_path):
            self.load()

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({"stats": self.stats}, f, ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.stats = data.get("stats", self.stats)
        except Exception:
            pass

    def _tokenize(self, text):
        return set(re.findall(r"[^\W\d_]+", str(text).lower()))

    def _cluster(self, episodes):
        groups = []

        for ep in episodes:
            tokens = self._tokenize(ep.get("summary", ""))

            placed = False
            for g in groups:
                if len(g["tokens"] & tokens) >= 2:
                    g["eps"].append(ep)
                    g["tokens"] |= tokens
                    placed = True
                    break

            if not placed:
                groups.append({
                    "eps": [ep],
                    "tokens": tokens
                })

        return [g["eps"] for g in groups[:4]]

    def _summarize_group(self, pet, group):
        text_parts = []
        for ep in group[:4]:
            text_parts.append(str(ep.get("summary", ""))[:150])

        text = " | ".join(text_parts)

        if getattr(pet, "neural_engine", None) and pet.neural_engine.available:
            try:
                prompt = (
                    "Bạn là Pet AI đang nén ký ức thành kiến thức cốt lõi. "
                    "Hãy viết một câu fact ngắn gọn, súc tích, không cảm xúc, từ các ký ức sau:\n"
                    f"{text}\n"
                    "Fact:"
                )

                out = pet.neural_engine.generate(
                    prompt,
                    max_tokens=60,
                    temperature=0.3
                )

                if out and len(out.strip()) > 8:
                    return out.strip()
            except Exception:
                pass

        keywords = []
        try:
            keywords = pet.nlp_engine.extract_keywords(text, limit=6)
        except Exception:
            keywords = []

        if not keywords:
            keywords = text.split()[:6]

        return f"Trải nghiệm nổi bật liên quan đến: {', '.join(keywords[:5])}."

    def _add_semantic_fact(self, pet, fact, group):
        fact = str(fact).strip()
        if not fact:
            return False

        h = hashlib.sha1(fact.encode("utf-8", errors="ignore")).hexdigest()

        for d in pet.documents:
            if d.get("source") == "memory_consolidation" and d.get("text") == fact:
                return False

        extra = {
            "kind": "fact",
            "confidence": 0.78,
            "tags": ["memory", "consolidation"],
            "hash": h,
            "importance": 0.75
        }

        try:
            if hasattr(pet, "_add_document"):
                try:
                    pet._add_document(fact, source="memory_consolidation", extra=extra)
                except TypeError:
                    pet._add_document(fact, source="memory_consolidation")
            else:
                doc = {
                    "id": pet.next_id(),
                    "text": fact,
                    "source": "memory_consolidation",
                    "weight": 1.2
                }
                pet.documents.append(doc)

            pet.graph_engine.update_graph(fact, source="memory_consolidation")
            return True
        except Exception:
            return False

    def consolidate(self, pet, max_episodes=8, min_importance=0.45):
        eps = getattr(pet.memory, "episodic", [])

        if not eps or len(eps) < 4:
            return []

        now = time.time()
        candidates = []

        for ep in eps:
            try:
                if ep.get("consolidated"):
                    continue

                age = now - float(ep.get("time", now))
                if age < 300:
                    continue

                if float(ep.get("importance", 0.5)) >= min_importance:
                    candidates.append(ep)
            except Exception:
                continue

        if not candidates:
            return []

        candidates.sort(
            key=lambda x: (float(x.get("importance", 0.5)), float(x.get("time", 0))),
            reverse=True
        )

        selected = candidates[:max_episodes]
        groups = self._cluster(selected)

        facts = []

        for group in groups:
            fact = self._summarize_group(pet, group)
            if fact:
                if self._add_semantic_fact(pet, fact, group):
                    facts.append(fact)
                    self.stats["facts_created"] += 1

                for ep in group:
                    ep["consolidated"] = True

                self.stats["episodes_consolidated"] += len(group)

        pet.memory.episodic = [
            ep for ep in eps
            if not ep.get("consolidated") or (now - float(ep.get("time", now))) < 3600
        ][-200:]

        try:
            pet.memory.save()
        except Exception:
            pass

        self.stats["consolidations"] += 1
        self.save()

        return facts

    def stats_text(self):
        return (
            "🧠 Memory Consolidation stats:\n"
            f"  • Consolidations: {self.stats.get('consolidations', 0)}\n"
            f"  • Facts created: {self.stats.get('facts_created', 0)}\n"
            f"  • Episodes consolidated: {self.stats.get('episodes_consolidated', 0)}"
        )
