# -*- coding: utf-8 -*-
import json
import math
import os
import time


class EbbinghausEngine:
    """
    Ebbinghaus Forgetting Engine.

    Mô phỏng đường cong quên lãng:
      R = 0.5 ** (t / S)

    Trong đó:
      R = retention
      t = thời gian trôi qua
      S = stability

    Stability tăng khi:
      - được truy hồi nhiều lần
      - có importance / confidence cao
      - được feedback tốt
    """

    def __init__(self, save_path=None):
        self.save_path = save_path

        # Tài liệu RAG: quên chậm hơn episodic memory
        self.doc_half_life_hours = 24 * 30
        self.episodic_half_life_hours = 24 * 7

        self.min_weight = 0.02
        self.prune_threshold = 0.03

        self.stats = {
            "decay_runs": 0,
            "reinforced_docs": 0,
            "reinforced_eps": 0,
            "forgotten_docs": 0,
            "forgotten_eps": 0,
            "pruned_docs": 0
        }

        if save_path and os.path.exists(save_path):
            self.load()

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "stats": self.stats,
                    "doc_half_life_hours": self.doc_half_life_hours,
                    "episodic_half_life_hours": self.episodic_half_life_hours,
                    "min_weight": self.min_weight,
                    "prune_threshold": self.prune_threshold
                }, f, ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.stats = data.get("stats", self.stats)
            self.doc_half_life_hours = data.get("doc_half_life_hours", self.doc_half_life_hours)
            self.episodic_half_life_hours = data.get("episodic_half_life_hours", self.episodic_half_life_hours)
            self.min_weight = data.get("min_weight", self.min_weight)
            self.prune_threshold = data.get("prune_threshold", self.prune_threshold)
        except Exception:
            pass

    def ensure_doc_meta(self, doc):
        now = time.time()
        doc.setdefault("created_at", now)
        doc.setdefault("last_accessed", now)
        doc.setdefault("retrieval_count", 0)
        doc.setdefault("base_weight", float(doc.get("weight", 1.0)))

    def reinforce_doc(self, doc, amount=1.0):
        try:
            self.ensure_doc_meta(doc)
            doc["retrieval_count"] = int(doc.get("retrieval_count", 0)) + 1
            doc["last_accessed"] = time.time()

            base = float(doc.get("base_weight", 1.0))
            doc["base_weight"] = round(min(3.0, base + 0.02 * amount), 4)

            self.stats["reinforced_docs"] += 1
        except Exception:
            pass

    def reinforce_episodic(self, ep):
        try:
            ep["retrieval_count"] = int(ep.get("retrieval_count", 0)) + 1
            ep["last_accessed"] = time.time()
            self.stats["reinforced_eps"] += 1
        except Exception:
            pass

    def retention(self, elapsed_hours, stability_hours):
        if stability_hours <= 0:
            stability_hours = 1.0

        return 0.5 ** max(0.0, float(elapsed_hours) / float(stability_hours))

    def doc_stability(self, doc):
        retrieval_count = int(doc.get("retrieval_count", 0))

        importance = 0.5
        try:
            importance = float(doc.get("confidence", doc.get("importance", 0.5)) or 0.5)
        except Exception:
            importance = 0.5

        importance = max(0.1, min(1.0, importance))

        feedback = 1.0
        try:
            feedback = float(doc.get("base_weight", 1.0))
        except Exception:
            feedback = 1.0

        feedback = max(0.2, min(3.0, feedback))

        stability = (
            self.doc_half_life_hours
            * (1.0 + math.log2(1.0 + retrieval_count))
            * (0.6 + 0.8 * importance)
            * (0.5 + 0.5 * feedback)
        )

        return max(1.0, stability)

    def episodic_stability(self, ep):
        retrieval_count = int(ep.get("retrieval_count", 0))
        importance = float(ep.get("importance", 0.5))
        importance = max(0.1, min(1.0, importance))

        stability = (
            self.episodic_half_life_hours
            * (1.0 + math.log2(1.0 + retrieval_count))
            * (0.5 + importance)
        )

        return max(1.0, stability)

    def decay_documents(self, documents):
        now = time.time()
        forgotten = []

        for doc in documents:
            try:
                self.ensure_doc_meta(doc)

                elapsed_hours = (now - float(doc.get("last_accessed", now))) / 3600.0
                stability = self.doc_stability(doc)
                r = self.retention(elapsed_hours, stability)

                base_weight = float(doc.get("base_weight", 1.0))
                new_weight = base_weight * max(0.0, r)

                # Seed knowledge không nên bị quên hoàn toàn
                if doc.get("source") == "seed_knowledge":
                    new_weight = max(new_weight, 0.20)

                if r > 0.05:
                    new_weight = max(new_weight, self.min_weight)
                else:
                    new_weight = max(new_weight, 0.0)

                doc["weight"] = round(new_weight, 4)
                doc["retention"] = round(r, 4)

                if doc["weight"] < self.prune_threshold and doc.get("source") != "seed_knowledge":
                    forgotten.append(doc.get("id"))
            except Exception:
                continue

        self.stats["decay_runs"] += 1
        self.stats["forgotten_docs"] = len(forgotten)
        self.save()

        return forgotten

    def decay_episodic(self, memory):
        now = time.time()
        kept = []
        removed = 0

        episodic = getattr(memory, "episodic", [])

        for ep in episodic:
            try:
                ep.setdefault("time", now)
                ep.setdefault("last_accessed", ep.get("time", now))
                ep.setdefault("retrieval_count", 0)
                ep.setdefault("importance", 0.5)

                elapsed_hours = (now - float(ep.get("last_accessed", ep.get("time", now)))) / 3600.0
                stability = self.episodic_stability(ep)
                r = self.retention(elapsed_hours, stability)

                ep["retention"] = round(r, 4)

                age_seconds = now - float(ep.get("time", now))

                if r >= 0.15 or float(ep.get("importance", 0.5)) > 0.75 or age_seconds < 3600:
                    kept.append(ep)
                else:
                    removed += 1
            except Exception:
                continue

        memory.episodic = kept[-200:]
        self.stats["forgotten_eps"] = removed
        self.save()

        return removed

    def prune_documents(self, pet):
        archive_path = None

        if self.save_path:
            base_dir = os.path.dirname(self.save_path)
            archive_path = os.path.join(base_dir, "forgotten_documents.jsonl")

        active = []
        archived = []

        for doc in pet.documents:
            try:
                w = float(doc.get("weight", 1.0))
                source = doc.get("source", "")

                if w < self.prune_threshold and source != "seed_knowledge":
                    archived.append(doc)
                else:
                    active.append(doc)
            except Exception:
                active.append(doc)

        if archived:
            pet.documents = active

            if archive_path:
                try:
                    with open(archive_path, "a", encoding="utf-8") as f:
                        for d in archived:
                            f.write(json.dumps(d, ensure_ascii=False) + "\n")
                except Exception:
                    pass

            self.stats["pruned_docs"] += len(archived)
            self.save()

        return len(archived)

    def stats_text(self):
        return (
            "🧠 Ebbinghaus stats:\n"
            f"  • Decay runs: {self.stats.get('decay_runs', 0)}\n"
            f"  • Reinforced docs: {self.stats.get('reinforced_docs', 0)}\n"
            f"  • Reinforced episodic: {self.stats.get('reinforced_eps', 0)}\n"
            f"  • Weak docs: {self.stats.get('forgotten_docs', 0)}\n"
            f"  • Forgotten episodic: {self.stats.get('forgotten_eps', 0)}\n"
            f"  • Pruned docs: {self.stats.get('pruned_docs', 0)}"
        )
