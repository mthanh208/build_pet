# -*- coding: utf-8 -*-
import networkx as nx


class GraphRAGEngine:
    """
    GraphRAG Engine phiên bản nhẹ.

    - Phát hiện community từ knowledge graph
    - Tạo community summary
    - Truy hồi theo cụm chủ đề
    - Hỗ trợ System 2 trả lời câu hỏi tổng hợp
    """

    def __init__(self, pet):
        self.pet = pet
        self.communities = []
        self.built = False

    def build_communities(self):
        self.communities = []

        try:
            g = self.pet.graph_engine.graph.to_undirected()
        except Exception:
            self.built = True
            return

        if g.number_of_nodes() < 4:
            self.built = True
            return

        comms = []

        try:
            from networkx.algorithms.community import greedy_modularity_communities
            comms = list(greedy_modularity_communities(g))
        except Exception:
            try:
                comms = list(nx.connected_components(g))
            except Exception:
                comms = []

        for i, comm in enumerate(comms[:20]):
            nodes = sorted(
                comm,
                key=lambda n: g.degree(n) if g.has_node(n) else 0,
                reverse=True
            )[:10]

            summary = self._summarize_community(nodes)
            self.communities.append({
                "id": i,
                "nodes": nodes,
                "summary": summary
            })

        self.built = True

    def _summarize_community(self, nodes):
        if not nodes:
            return ""

        top = [str(n) for n in nodes[:6]]
        return "Nhóm chủ đề liên quan: " + ", ".join(top)

    def query_context(self, query):
        if not self.built:
            self.build_communities()

        if not self.communities:
            return {
                "community_summary": "",
                "docs": []
            }

        entities = []
        try:
            entities = self.pet.graph_engine.extract_entities(query)
        except Exception:
            entities = []

        if not entities:
            entities = [query]

        matched = []

        for ent in entities[:5]:
            ent_low = str(ent).lower()
            for comm in self.communities:
                if comm in matched:
                    continue

                for node in comm.get("nodes", []):
                    node_low = str(node).lower()
                    if ent_low in node_low or node_low in ent_low:
                        matched.append(comm)
                        break

        if not matched:
            return {
                "community_summary": "",
                "docs": []
            }

        summary = " | ".join([c.get("summary", "") for c in matched[:2]])

        docs = []
        for doc in self.pet.documents[-800:]:
            text_low = doc.get("text", "").lower()

            for comm in matched[:2]:
                for node in comm.get("nodes", [])[:5]:
                    if str(node).lower() in text_low:
                        docs.append(doc)
                        break

            if len(docs) >= 3:
                break

        return {
            "community_summary": summary,
            "docs": docs
        }

    def stats(self):
        return {
            "communities": len(self.communities),
            "built": self.built
        }
