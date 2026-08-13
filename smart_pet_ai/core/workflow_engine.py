# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from collections import defaultdict

try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

class WorkflowEngine:
    def __init__(self, pet_brain):
        self.pet = pet_brain
        self.available = HAS_LANGGRAPH
        self.graph = None
        self.step_count = 0
        self.execution_log = []
        if self.available:
            self._build_graph()
        else:
            self._build_fallback()

    def _build_graph(self):
        try:
            workflow = StateGraph(dict)
            workflow.add_node("parse", self._step_parse)
            workflow.add_node("retrieve", self._step_retrieve)
            workflow.add_node("reason", self._step_reason)
            workflow.add_node("verify", self._step_verify)
            workflow.add_node("synthesize", self._step_synthesize)

            workflow.set_entry_point("parse")
            workflow.add_edge("parse", "retrieve")
            workflow.add_edge("retrieve", "reason")
            workflow.add_conditional_edges("reason", lambda state: "verify" if state.get("confidence", 0) > 0.3 else "synthesize", {"verify": "verify", "synthesize": "synthesize"})
            workflow.add_conditional_edges("verify", lambda state: "synthesize" if state.get("verification_passed") else "reason", {"synthesize": "synthesize", "reason": "reason"})
            workflow.add_edge("synthesize", END)
            self.graph = workflow.compile()
        except:
            self.available = False
            self._build_fallback()

    def _build_fallback(self):
        self.graph = None

    def _step_parse(self, state):
        parsed = self.pet.universal_parser.parse_text(state.get("input_text", ""))
        state["parsed"] = parsed
        self._log("parse", parsed)
        return state

    def _step_retrieve(self, state):
        query = state.get("input_text", "")
        bm25_results = self.pet.search(query, top_n=5)
        vector_results = []
        if self.pet.vector_search.available:
            vector_results = self.pet.vector_search.search(query, top_n=5)
        combined = self._fusion_rank(bm25_results, vector_results)
        state["retrieval_results"] = combined
        state["confidence"] = min(len(combined) / 5.0, 1.0)
        self._log("retrieve", {"bm25": len(bm25_results), "vector": len(vector_results), "fused": len(combined)})
        return state

    def _step_reason(self, state):
        query = state.get("input_text", "")
        results = state.get("retrieval_results", [])
        reasoning = {"strategies": [], "concepts": [], "chains": []}
        entities = self.pet.graph_engine.extract_entities(query)
        if entities:
            reasoning["concepts"] = self.pet.reasoning.multi_hop_reasoning(entities[:3])
            if len(entities) >= 2:
                chain, chain_type = self.pet.reasoning.causal_chain(entities[0], entities[1])
                if chain: reasoning["chains"] = [{"chain": chain, "type": chain_type}]
            analogs = self.pet.reasoning.analogical_reasoning(entities[0])
            if analogs: reasoning["strategies"].append({"type": "analogical", "results": analogs})
        expert_results = self.pet.expert_system.infer(query, emotion=self.pet.emotion_graph.current_emotion, confidence=state.get("confidence", 0.5))
        if expert_results:
            reasoning["strategies"].append({"type": "expert", "rules": [{"name": r.name, "action": r.action, "confidence": r.confidence} for r in expert_results[:3]]})
        symbolic_result = self.pet.symbolic_solver.process(query)
        if symbolic_result: reasoning["strategies"].append({"type": "symbolic", "result": symbolic_result})
        state["reasoning_results"] = reasoning
        if reasoning["strategies"]: state["confidence"] = min(state.get("confidence", 0.5) + 0.2, 1.0)
        self._log("reason", {"strategies": len(reasoning["strategies"]), "concepts": len(reasoning["concepts"]), "chains": len(reasoning["chains"])})
        return state

    def _step_verify(self, state):
        reasoning = state.get("reasoning_results", {})
        confidence = state.get("confidence", 0.0)
        passed = True
        if not reasoning.get("strategies") and not reasoning.get("concepts"):
            passed = False
            confidence *= 0.5
        if confidence < 0.2: passed = False
        state["verification_passed"] = passed
        state["confidence"] = confidence
        self._log("verify", {"passed": passed, "confidence": confidence})
        return state

    def _step_synthesize(self, state):
        reasoning = state.get("reasoning_results", {})
        retrieval = state.get("retrieval_results", [])
        content_parts = []
        for doc, score in retrieval[:3]:
            content_parts.append(doc.get("text", "") if isinstance(doc, dict) else str(doc))
        if reasoning.get("concepts"):
            content_parts.append(f"🔗 Khái niệm kết nối: {', '.join(reasoning['concepts'][:5])}.")
        if reasoning.get("chains"):
            for ch in reasoning["chains"][:2]:
                content_parts.append(f"🔗 Chuỗi nhân quả: {' -> '.join(ch['chain'])}.")
        for strategy in reasoning.get("strategies", []):
            if strategy["type"] == "analogical":
                content_parts.append(f"🔄 Tương tự: {', '.join(strategy['results'][:3])}.")
            elif strategy["type"] == "expert":
                for rule in strategy.get("rules", []):
                    if "response" in rule.get("action", {}): content_parts.append(rule["action"]["response"])
            elif strategy["type"] == "symbolic":
                result = strategy.get("result", {})
                if "solutions" in result: content_parts.append(f"🧮 Nghiệm: {', '.join(map(str, result['solutions']))}.")
        state["response"] = content_parts
        state["think_block"] = self._generate_think_block(state)
        self._log("synthesize", {"parts": len(content_parts)})
        return state

    def _generate_think_block(self, state):
        lines = ["🧠 [Workflow Think]"]
        reasoning = state.get("reasoning_results", {})
        retrieval = state.get("retrieval_results", [])
        lines.append(f"  📊 Retrieval: {len(retrieval)} kết quả")
        lines.append(f"  🧩 Reasoning strategies: {len(reasoning.get('strategies', []))}")
        lines.append(f"  🔗 Concepts: {', '.join(reasoning.get('concepts', [])[:5])}")
        if reasoning.get("chains"):
            for ch in reasoning["chains"][:1]: lines.append(f"  ⛓️ Chain: {' -> '.join(ch['chain'])}")
        lines.append(f"  ✅ Verify: {'pass' if state.get('verification_passed') else 'fail'}")
        lines.append(f"  📈 Confidence: {state.get('confidence', 0):.2f}")
        return "\n".join(lines)

    def _fusion_rank(self, bm25_results, vector_results):
        rrf_k = 60
        scores = defaultdict(float)
        all_docs = {}

        for i, (doc, score) in enumerate(bm25_results):
            doc_id = doc.get("id") if isinstance(doc, dict) else id(doc)
            scores[doc_id] += 1.0 / (rrf_k + i + 1)
            all_docs[doc_id] = doc

        for i, (doc_id, score) in enumerate(vector_results):
            scores[doc_id] += 1.0 / (rrf_k + i + 1)
            if doc_id not in all_docs:
                doc = next((d for d in self.pet.documents if d.get("id") == doc_id), None)
                if doc:
                    all_docs[doc_id] = doc

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [(all_docs.get(doc_id), score) for doc_id, score in ranked[:10]]

    def _log(self, step, data):
        self.step_count += 1
        self.execution_log.append({"step": step, "data": data})
        if len(self.execution_log) > 100: self.execution_log = self.execution_log[-50:]

    def run(self, input_text):
        if self.available and self.graph:
            try:
                initial_state = {"input_text": input_text}
                result = self.graph.invoke(initial_state)
                return result
            except: pass
        state = {"input_text": input_text, "confidence": 0.0}
        state = self._step_parse(state)
        state = self._step_retrieve(state)
        state = self._step_reason(state)
        state = self._step_verify(state)
        state = self._step_synthesize(state)
        return state

    def stats(self):
        return {"available": self.available, "step_count": self.step_count, "log_size": len(self.execution_log)}
