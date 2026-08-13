# -*- coding: utf-8 -*-
import random

class ReasoningEngine:
    def __init__(self, graph_engine):
        self.graph = graph_engine

    def causal_chain(self, start, end, max_depth=4):
        chain = self.graph.find_causal_chain(start, end, max_depth)
        if chain: return chain, "causal"
        related = self.graph.find_related_concepts(start, depth=max_depth)
        if end in related: return [start, end], "associative"
        return [], "unknown"

    def analogical_reasoning(self, concept):
        if concept not in self.graph.graph: return []
        val = self.graph.get_emotional_valence(concept)
        neighbors = set(self.graph.graph.neighbors(concept))
        candidates = []
        for node in self.graph.graph.nodes:
            if node == concept: continue
            node_val = self.graph.get_emotional_valence(node)
            node_neighbors = set(self.graph.graph.neighbors(node))
            overlap = len(neighbors & node_neighbors)
            val_sim = 1.0 - abs(val - node_val)
            if overlap >= 2 or val_sim > 0.8:
                candidates.append((node, overlap + val_sim))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:5]]

    def abductive_explain(self, observation):
        if observation not in self.graph.graph: return []
        preds = []
        for pred in self.graph.graph.predecessors(observation):
            edge = self.graph.graph[pred][observation]
            if edge.get("type") in ("causes", "caused_by"):
                w = edge.get("causal_weight", 1)
                preds.append((pred, w))
        preds.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in preds[:5]]

    def multi_hop_reasoning(self, query_entities, depth=3):
        if not query_entities: return []
        frontier = set(query_entities)
        visited = set(query_entities)
        for _ in range(depth):
            new_frontier = set()
            for node in frontier:
                if node in self.graph.graph:
                    new_frontier.update(self.graph.graph.neighbors(node))
            new_frontier -= visited
            visited.update(new_frontier)
            frontier = new_frontier
        scores = {}
        for node in visited:
            conn = sum(1 for q in query_entities if q in self.graph.graph and node in self.graph.graph.neighbors(q))
            if conn >= 2:
                scores[node] = conn + self.graph.graph.nodes[node].get("count", 0) * 0.1
        result = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [r[0] for r in result[:8]]

    def counterfactual(self, premise, alternative):
        if premise not in self.graph.graph:
            return f"Nếu không có {premise}, mọi thứ có thể khác đi rất nhiều."
        effects = [n for n in self.graph.graph.successors(premise) if self.graph.graph[premise][n].get("type") in ("causes", "caused_by")][:5]
        if not effects:
            return f"Nếu {premise} không tồn tại, có lẽ {alternative} sẽ lấp đầy khoảng trống đó."
        lines = [f"Nếu thay vì {premise}, ta có {alternative}:", "  • Những điều sau có thể thay đổi:"]
        for eff in effects:
            lines.append(f"    – {eff} có thể không còn như cũ")
        lines.append(f"  • Thay vào đó, {alternative} có thể tạo ra những kết nối mới.")
        return "\n".join(lines)

    def synthesize_thought(self, query, evidence_docs, related_concepts):
        lines = ["🧠 Suy nghĩ của tui:"]
        if evidence_docs:
            lines.append("  Tui tìm thấy những mảnh kiến thức liên quan:")
            for i, doc in enumerate(evidence_docs[:3], 1):
                preview = doc["text"][:80] + "…" if len(doc["text"]) > 80 else doc["text"]
                lines.append(f"    {i}. {preview}")
        if related_concepts:
            lines.append(f"  🔗 Các khái niệm kết nối: {', '.join(related_concepts[:6])}")
        if evidence_docs:
            ents = self.graph.extract_entities(evidence_docs[0]["text"])
            if ents:
                analogs = self.analogical_reasoning(ents[0])
                if analogs:
                    lines.append(f"  🔄 Tương tự như: {', '.join(analogs[:3])}")
        return "\n".join(lines)
