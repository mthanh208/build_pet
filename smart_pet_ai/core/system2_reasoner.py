# -*- coding: utf-8 -*-
import time


class DebateEngine:
    """
    Multi-Agent Debate:
      - Optimist
      - Skeptic
      - Synthesizer
    """

    def __init__(self, pet):
        self.pet = pet

    def _context_from_docs(self, docs, graphrag_context):
        parts = []

        if graphrag_context and graphrag_context.get("community_summary"):
            parts.append("GraphRAG: " + graphrag_context["community_summary"])

        for doc in docs[:3]:
            text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            parts.append(text[:300])

        return "\n".join(parts)

    def _find_risks(self, query, docs):
        query_tokens = set(str(query).lower().split())
        doc_tokens = set()

        for doc in docs[:3]:
            text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_tokens.update(text.lower().split())

        missing = [w for w in query_tokens if len(w) > 3 and w not in doc_tokens]

        if not docs:
            return "Không tìm thấy bằng chứng trực tiếp."

        if missing:
            return "Một số khái niệm trong câu hỏi chưa xuất hiện rõ trong bằng chứng: " + ", ".join(missing[:4])

        return "Bằng chứng có vẻ đủ, nhưng vẫn nên trả lời thận trọng."

    def run(self, query, docs, graphrag_context):
        think = []
        context = self._context_from_docs(docs, graphrag_context)

        if self.pet.neural_engine.available:
            try:
                opt_prompt = self.pet.meta_prompt.render("debate_optimist", {
                    "query": query,
                    "context": context[:1200]
                })
                opt = self.pet.neural_engine.generate(opt_prompt, max_tokens=70, temperature=0.5)

                skep_prompt = self.pet.meta_prompt.render("debate_skeptic", {
                    "query": query,
                    "context": context[:1200]
                })
                skep = self.pet.neural_engine.generate(skep_prompt, max_tokens=70, temperature=0.4)

                synth_prompt = self.pet.meta_prompt.render("debate_synthesizer", {
                    "query": query,
                    "optimist": opt or "",
                    "skeptic": skep or ""
                })
                final = self.pet.neural_engine.generate(synth_prompt, max_tokens=120, temperature=0.4)

                if final and len(final.strip()) > 10:
                    think.append("🤝 Multi-Agent Debate: optimist -> skeptic -> synthesizer")
                    return final.strip(), think, 0.80
            except Exception:
                pass

        # Heuristic fallback
        positive = ""
        if docs:
            positive = docs[0].get("text", "")[:220] if isinstance(docs[0], dict) else str(docs[0])[:220]

        risks = self._find_risks(query, docs)

        answer = (
            "Tui thấy điểm mạnh là: " + positive +
            " Tuy nhiên, " + risks +
            " Kết luận an toàn: câu trả lời nên dựa trên bằng chứng hiện có và cần thận trọng nếu thiếu dữ kiện."
        )

        think.append("🤝 Multi-Agent Debate heuristic: optimist + skeptic + synthesizer")
        return answer, think, 0.65


class System2Reasoner:
    """
    System 2: tư duy chậm.

    Luồng:
      1. ReAct tool
      2. GraphRAG context
      3. Retrieval
      4. Debate hoặc synthesis
      5. Self-correction
    """

    def __init__(self, pet):
        self.pet = pet
        self.debate = DebateEngine(pet)
        self.run_count = 0

    def _retrieve(self, query, graphrag_context):
        docs = []

        try:
            bm25 = self.pet.search(query, top_n=5)
            docs.extend([d for d, s in bm25])
        except Exception:
            pass

        if graphrag_context and graphrag_context.get("docs"):
            docs = graphrag_context["docs"] + docs

        seen = set()
        unique = []
        for d in docs:
            if not isinstance(d, dict):
                continue
            did = d.get("id")
            if did in seen:
                continue
            seen.add(did)
            unique.append(d)

        return unique[:5]

    def _synthesize(self, query, docs, graphrag_context):
        context_parts = []

        if graphrag_context and graphrag_context.get("community_summary"):
            context_parts.append("Khái quát chủ đề: " + graphrag_context["community_summary"])

        for doc in docs[:3]:
            text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            context_parts.append(text[:350])

        context = "\n".join(context_parts)

        tom_state = {}
        style_hint = "tự nhiên, ấm áp"

        try:
            tom_state = self.pet.tom.analyze(query)
            style_hint = tom_state.get("style_hint", style_hint)
        except Exception:
            pass

        if self.pet.neural_engine.available:
            try:
                prompt = self.pet.meta_prompt.render("s2_answer", {
                    "emotion": self.pet.emotion_graph.current_emotion,
                    "style": style_hint,
                    "context": context[:2000],
                    "query": query
                })

                self.pet.meta_prompt.record_usage("s2_answer")

                resp = self.pet.neural_engine.generate(
                    prompt,
                    max_tokens=160,
                    temperature=0.45
                )

                if resp and len(resp.strip()) > 10:
                    conf = min(0.50 + 0.08 * len(docs), 0.88)
                    return resp.strip(), conf
            except Exception:
                pass

        # Extractive fallback
        parts = []

        if graphrag_context and graphrag_context.get("community_summary"):
            parts.append("Tui thấy chủ đề này nằm trong: " + graphrag_context["community_summary"] + ".")

        for doc in docs[:2]:
            text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            sentences = text.split("。")
            if not sentences or len(sentences[0]) < 5:
                sentences = text.split(". ")
            if sentences:
                parts.append(sentences[0].strip())

        if not parts:
            return "Tui chưa đủ bằng chứng chắc chắn cho câu này. Bạn có thể diễn đạt khác giúp tui không?", 0.20

        answer = " ".join(parts[:3])
        conf = min(0.35 + 0.07 * len(docs), 0.70)
        return answer, conf

    def _verify(self, query, answer, docs):
        try:
            reasoning_results = {
                "strategies": [{"type": "system2"}],
                "concepts": []
            }

            passed, checks = self.pet.verification.verify(
                answer,
                query,
                docs[:3],
                reasoning_results
            )
            return passed, checks
        except Exception:
            return True, {}

    def _revise(self, answer, checks):
        answer = str(answer)

        if not checks.get("completeness", True):
            answer = answer + " Tui đang cố trả lời ngắn, nhưng có thể cần thêm dữ kiện."

        if not checks.get("evidence_based", True):
            answer = "Tui chưa chắc chắn hoàn toàn, nhưng dựa trên kiến thức hiện có: " + answer

        if len(answer) > 500:
            answer = answer[:480] + "…"

        return answer

    def reason(self, query, complexity=0.5):
        self.run_count += 1
        start = time.time()
        think = ["🧠 System 2: tư duy chậm được kích hoạt"]

        # 1. ReAct tool
        try:
            tool_result = self.pet.react.try_solve(query)
            if tool_result and tool_result.get("success"):
                think.append(f"🛠️ ReAct tool: {tool_result.get('tool')}")
                return tool_result.get("answer", ""), "\n".join(think), 0.95
        except Exception:
            pass

        # 2. GraphRAG
        graphrag_context = {}
        try:
            graphrag_context = self.pet.graphrag.query_context(query)
            if graphrag_context.get("community_summary"):
                think.append("🕸️ GraphRAG: " + graphrag_context["community_summary"][:140])
        except Exception:
            graphrag_context = {}

        # 3. Retrieval
        docs = self._retrieve(query, graphrag_context)
        think.append(f"📚 Bằng chứng truy hồi: {len(docs)} docs")

        # 4. Debate hoặc synthesis
        if complexity >= 0.72 and len(docs) >= 2:
            answer, debate_think, conf = self.debate.run(query, docs, graphrag_context)
            think.extend(debate_think)
        else:
            answer, conf = self._synthesize(query, docs, graphrag_context)

        # 5. Self-correction
        passed, checks = self._verify(query, answer, docs)
        if not passed:
            answer = self._revise(answer, checks)
            conf *= 0.70
            think.append("🔧 Self-correction: đã điều chỉnh câu trả lời")

        elapsed = time.time() - start
        think.append(f"⏱️ System2 latency: {elapsed:.2f}s")

        return answer, "\n".join(think), conf

    def stats(self):
        return {"run_count": self.run_count}
