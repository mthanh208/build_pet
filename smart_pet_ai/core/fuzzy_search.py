# -*- coding: utf-8 -*-
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

class FuzzySearch:
    def __init__(self):
        self.available = HAS_RAPIDFUZZ
        self.concepts = []

    def set_concepts(self, concepts):
        self.concepts = list(set(concepts))

    def search(self, query, limit=5, threshold=60):
        if not self.available or not self.concepts:
            return self._fallback_search(query, limit)
        try:
            results = process.extract(query, self.concepts, scorer=fuzz.WRatio, limit=limit)
            return [(match, score) for match, score, _ in results if score >= threshold]
        except:
            return self._fallback_search(query, limit)

    def _fallback_search(self, query, limit=5):
        low_query = query.lower()
        scored = []
        for concept in self.concepts:
            low_concept = concept.lower()
            if low_query in low_concept or low_concept in low_query:
                score = 80 + (10 if low_concept.startswith(low_query) else 0)
            else:
                common = set(low_query.split()) & set(low_concept.split())
                if common: score = 50 + len(common) * 10
                else: continue
            scored.append((concept, score))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]

    def best_match(self, query, threshold=70):
        results = self.search(query, limit=1, threshold=threshold)
        if results: return results[0]
        return None, 0

    def stats(self):
        return {"available": self.available, "concepts": len(self.concepts)}
