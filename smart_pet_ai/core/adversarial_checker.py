# -*- coding: utf-8 -*-
import re


_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


class AdversarialChecker:
    """
    Adversarial Fact-Checking.

    Kiểm tra:
      - câu trả lời có bằng chứng RAG không
      - có được Knowledge Graph ủng hộ không
      - có mâu thuẫn nội tại không

    Nếu bằng chứng yếu, thêm cảnh báo suy luận.
    """

    def __init__(self):
        self.stats = {
            "checks": 0,
            "caveats_added": 0,
            "contradictions": 0
        }

    def _tokens(self, text):
        return set(_WORD_RE.findall(str(text).lower()))

    def _evidence_overlap(self, answer, evidence_text):
        a_tokens = self._tokens(answer)
        e_tokens = self._tokens(evidence_text)

        if not a_tokens or not e_tokens:
            return 0.0

        return len(a_tokens & e_tokens) / float(len(a_tokens))

    def _graph_support(self, pet, entities):
        if not entities:
            return 0.5

        try:
            g = pet.graph_engine.graph
            nodes = list(g.nodes())[:1000]

            hits = 0

            for ent in entities[:8]:
                if ent in g:
                    hits += 1
                    continue

                low = str(ent).lower()

                for n in nodes[:300]:
                    nl = str(n).lower()
                    if low in nl or nl in low:
                        hits += 1
                        break

            return hits / float(len(entities[:8]))
        except Exception:
            return 0.3

    def _has_contradiction(self, answer):
        low = str(answer).lower()

        positive = ["đúng", "chính xác", "có", "khẳng định"]
        negative = ["không đúng", "sai", "không phải", "phủ nhận"]

        has_pos = any(p in low for p in positive)
        has_neg = any(n in low for n in negative)

        return has_pos and has_neg

    def check(self, pet, query, answer):
        self.stats["checks"] += 1

        if not answer or len(str(answer)) < 20:
            return answer, None

        evidence = []

        try:
            evidence = pet.search(query, top_n=3)
        except Exception:
            evidence = []

        evidence_text = " ".join([
            d.get("text", "") if isinstance(d, dict) else str(d)
            for d, s in evidence
        ])

        support = self._evidence_overlap(answer, evidence_text)

        entities = []
        try:
            entities = pet.graph_engine.extract_entities(str(query) + " " + str(answer))[:8]
        except Exception:
            entities = []

        graph_support = self._graph_support(pet, entities)

        critique = []

        if support < 0.06 and graph_support < 0.25 and len(str(answer)) > 60:
            caveat = " (Tui suy luận từ nền tảng, nhưng bằng chứng RAG trực tiếp còn yếu.)"

            if caveat not in answer:
                answer = str(answer) + caveat

            critique.append("🛡️ Adversarial: bằng chứng yếu, đã thêm cảnh báo.")
            self.stats["caveats_added"] += 1

        if self._has_contradiction(answer):
            critique.append("🛡️ Adversarial: nghi ngờ mâu thuẫn nội tại.")
            self.stats["contradictions"] += 1

        if critique:
            return answer, "\n".join(critique)

        return answer, None

    def stats_text(self):
        return (
            "🛡️ Adversarial stats:\n"
            f"  • Checks: {self.stats.get('checks', 0)}\n"
            f"  • Caveats added: {self.stats.get('caveats_added', 0)}\n"
            f"  • Contradictions: {self.stats.get('contradictions', 0)}"
        )
