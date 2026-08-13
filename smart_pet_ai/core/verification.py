# -*- coding: utf-8 -*-
import re, time
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

class VerificationEngine:
    def __init__(self, pet):
        self.pet = pet
        self.checks_passed = 0
        self.checks_failed = 0
        self.history = []

    def verify(self, response, query, evidence_docs, reasoning_results):
        checks = {}
        query_tokens = set(_WORD_RE.findall(query.lower()))
        response_tokens = set(_WORD_RE.findall(response.lower()))
        overlap = len(query_tokens & response_tokens)
        checks["relevance"] = overlap > 0

        evidence_text = " ".join([d.get("text", "") if isinstance(d, dict) else str(d) for d in evidence_docs[:3]])
        evidence_tokens = set(_WORD_RE.findall(evidence_text.lower()))
        evidence_overlap = len(response_tokens & evidence_tokens)
        checks["evidence_based"] = evidence_overlap > 2 if evidence_tokens else True

        checks["completeness"] = len(response.split()) >= 5

        neg_words = ["không", "không phải", "sai"]
        pos_words = ["đúng", "chính xác", "đúng rồi"]
        has_neg = any(w in response.lower() for w in neg_words)
        has_pos = any(w in response.lower() for w in pos_words)
        checks["consistency"] = not (has_neg and has_pos and any(n in response.lower() for n in neg_words) and any(p in response.lower() for p in pos_words))

        strategies = reasoning_results.get("strategies", [])
        concepts = reasoning_results.get("concepts", [])
        checks["has_reasoning"] = len(strategies) > 0 or len(concepts) > 0

        checks["no_repetition"] = len(response) > 20 and not any(response[:40] in h.get("response", "")[:40] for h in self.history[-5:])

        all_pass = all(checks.values())
        if all_pass: self.checks_passed += 1
        else: self.checks_failed += 1

        self.history.append({"response": response[:100], "checks": checks, "passed": all_pass, "time": time.time()})
        if len(self.history) > 100: self.history = self.history[-50:]

        return all_pass, checks

    def get_confidence(self, checks):
        if not checks: return 0.0
        return sum(1 for v in checks.values() if v) / len(checks)

    def suggest_improvement(self, checks):
        suggestions = []
        if not checks.get("relevance"): suggestions.append("cần liên hệ hơn với câu hỏi")
        if not checks.get("evidence_based"): suggestions.append("cần dẫn chứng cụ thể hơn")
        if not checks.get("completeness"): suggestions.append("cần trả lờ chi tiết hơn")
        if not checks.get("has_reasoning"): suggestions.append("cần suy luận sâu hơn")
        if not checks.get("no_repetition"): suggestions.append("tránh lặp lại")
        return suggestions

    def stats(self):
        total = self.checks_passed + self.checks_failed
        return {"total_checks": total, "passed": self.checks_passed, "failed": self.checks_failed, "pass_rate": self.checks_passed / total if total > 0 else 0.0}
