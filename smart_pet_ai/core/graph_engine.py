# -*- coding: utf-8 -*-
import re, os, pickle, itertools, random, networkx as nx

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOPWORDS = {"Tôi","Bạn","Chúng","Nó","Đây","Đó","Nếu","Khi","Vì","Nhưng","Và","Hoặc","Tuy","Do","Bởi","The","A","An","Thì","Là","Củ","Được","Bị","Đã","Sẽ","Đang","Cũng","Mà","Như","Với","Theo"}

_CAUSAL_PATTERNS = [
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:làm cho|khiến|gây ra|dẫn đến|tạo ra)\s+(\w+(?:\s+\w+){0,4})"), "causes"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:vì|do|bởi vì|nhờ)\s+(\w+(?:\s+\w+){0,4})"), "caused_by"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:là một loại|là dạng|thuộc loại)\s+(\w+(?:\s+\w+){0,4})"), "is_a"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:có tính chất|có đặc điểm|có thuộc tính)\s+(\w+(?:\s+\w+){0,4})"), "has_property"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:bao gồm|gồm có|chứa)\s+(\w+(?:\s+\w+){0,4})"), "contains"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:là một phần của|thuộc về|nằm trong)\s+(\w+(?:\s+\w+){0,4})"), "part_of"),
    (re.compile(r"(\w+(?:\s+\w+){0,4})\s+(?:trái ngược với|ngược lại với|khác với)\s+(\w+(?:\s+\w+){0,4})"), "antonym"),
]

_EMOTION_WORDS = {
    "vui":0.8,"hạnh phúc":0.9,"vui vẻ":0.7,"phấn khích":0.85,"hào hứng":0.75,
    "buồn":-0.7,"đau khổ":-0.9,"thất vọng":-0.6,"chán":-0.5,"cô đơn":-0.8,
    "tức giận":-0.8,"giận":-0.75,"bực":-0.6,"khó chịu":-0.5,
    "sợ":-0.7,"lo lắng":-0.6,"sợ hãi":-0.85,"hoảng":-0.8,
    "yêu":0.9,"thương":0.85,"quý":0.7,"trân trọng":0.8,
    "tò mò":0.4,"ngạc nhiên":0.5,"bối rối":-0.2,"bình yên":0.6,
    "nhớ":0.3,"thèm":0.2,"khao khát":0.5,"mơ ước":0.4,
}

def extract_entities(text):
    if not text: return []
    words = _WORD_RE.findall(text)
    entities = []
    buffer = []
    for w in words:
        if len(w) > 1 and w[0].isupper():
            buffer.append(w)
        else:
            if buffer:
                phrase = " ".join(buffer)
                if phrase not in _STOPWORDS and len(phrase) > 2: entities.append(phrase)
            buffer = []
    if buffer:
        phrase = " ".join(buffer)
        if phrase not in _STOPWORDS and len(phrase) > 2: entities.append(phrase)
    seen = set()
    uniq = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq

def extract_emotions(text):
    low = text.lower()
    found = {}
    for word, valence in _EMOTION_WORDS.items():
        if word in low: found[word] = valence
    return found

def extract_causal_relations(text):
    relations = []
    for pattern, rel_type in _CAUSAL_PATTERNS:
        for m in pattern.finditer(text):
            a, b = m.group(1).strip(), m.group(2).strip()
            if a and b and a != b and len(a) > 2 and len(b) > 2:
                relations.append((a, b, rel_type))
    return relations

class GraphEngine:
    def __init__(self):
        self.graph = nx.DiGraph()

    @staticmethod
    def extract_entities(text): return extract_entities(text)

    def update_graph(self, text, source="unknown"):
        entities = extract_entities(text)
        emotions = extract_emotions(text)
        causal_rels = extract_causal_relations(text)

        for e in entities:
            if self.graph.has_node(e):
                self.graph.nodes[e]["count"] = self.graph.nodes[e].get("count", 0) + 1
            else:
                self.graph.add_node(e, count=1, valence=0.0, emotions={})
            for emo, val in emotions.items():
                old_val = self.graph.nodes[e].get("valence", 0.0)
                old_count = self.graph.nodes[e].get("emo_count", 0)
                new_val = (old_val * old_count + val) / (old_count + 1)
                self.graph.nodes[e]["valence"] = new_val
                self.graph.nodes[e]["emo_count"] = old_count + 1
                emos = self.graph.nodes[e].get("emotions", {})
                emos[emo] = emos.get(emo, 0) + 1
                self.graph.nodes[e]["emotions"] = emos

        for e1, e2 in itertools.combinations(entities, 2):
            if self.graph.has_edge(e1, e2):
                self.graph[e1][e2]["weight"] = self.graph[e1][e2].get("weight", 0) + 1
                self.graph[e1][e2]["type"] = "cooccurrence"
            else:
                self.graph.add_edge(e1, e2, weight=1, type="cooccurrence")

        for a, b, rel_type in causal_rels:
            for src in [a] + [e for e in entities if a.lower() in e.lower() or e.lower() in a.lower()]:
                for dst in [b] + [e for e in entities if b.lower() in e.lower() or e.lower() in b.lower()]:
                    if src in self.graph and dst in self.graph:
                        if self.graph.has_edge(src, dst):
                            self.graph[src][dst]["causal_weight"] = self.graph[src][dst].get("causal_weight", 0) + 2
                        else:
                            self.graph.add_edge(src, dst, weight=1, causal_weight=2, type=rel_type)
        return entities

    def find_related_concepts(self, entity, depth=2, limit=10):
        if entity not in self.graph:
            low = entity.lower()
            candidates = [n for n in self.graph.nodes if low in n.lower() or n.lower() in low]
            if not candidates: return []
            entity = candidates[0]
        try:
            lengths = nx.single_source_shortest_path_length(self.graph.to_undirected(), entity, cutoff=depth)
        except Exception:
            return []
        related = [n for n, d in lengths.items() if 0 < d <= depth]
        related.sort(key=lambda n: (lengths[n], -self.graph.nodes[n].get("count", 0)))
        return related[:limit]

    def find_causal_chain(self, start, end, max_depth=4):
        if start not in self.graph or end not in self.graph: return []
        try:
            paths = list(nx.all_simple_paths(self.graph, start, end, cutoff=max_depth))
            if paths: return min(paths, key=len)
        except Exception:
            pass
        return []

    def find_analogy(self, concept_a, concept_b):
        if concept_a not in self.graph or concept_b not in self.graph: return []
        neigh_a = set(self.graph.neighbors(concept_a))
        neigh_b = set(self.graph.neighbors(concept_b))
        common = neigh_a & neigh_b
        return sorted(common, key=lambda n: -self.graph.nodes[n].get("count", 0))[:5]

    def find_intersection(self, entities, limit=8):
        entities = [e for e in entities if e in self.graph]
        if not entities: return []
        neighbor_sets = []
        for e in entities:
            neigh = set(self.graph.neighbors(e))
            neigh.discard(e)
            neighbor_sets.append(neigh)
        if len(neighbor_sets) == 1:
            common = neighbor_sets[0]
        else:
            common = set.intersection(*neighbor_sets) if neighbor_sets else set()
        result = list(common)
        result.sort(key=lambda n: -self.graph.nodes[n].get("count", 0))
        return result[:limit]

    def get_emotional_valence(self, entity):
        if entity in self.graph: return self.graph.nodes[entity].get("valence", 0.0)
        return 0.0

    def get_concept_summary(self, entity):
        if entity not in self.graph: return None
        node = self.graph.nodes[entity]
        neighbors = list(self.graph.neighbors(entity))[:8]
        causes = [n for n in self.graph.predecessors(entity) if self.graph[n][entity].get("type") != "cooccurrence"][:5]
        effects = [n for n in self.graph.successors(entity) if self.graph[entity][n].get("type") != "cooccurrence"][:5]
        return {"entity": entity, "count": node.get("count", 0), "valence": node.get("valence", 0.0), "emotions": node.get("emotions", {}), "neighbors": neighbors, "caused_by": causes, "causes": effects}

    def save(self, path):
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(self.graph, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)

    def load(self, path):
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    self.graph = pickle.load(f)
            except Exception:
                self.graph = nx.DiGraph()

    def stats(self):
        return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges()}
