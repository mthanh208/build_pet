# -*- coding: utf-8 -*-
import json, os, time, re, pickle
from collections import Counter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans, MiniBatchKMeans
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.decomposition import TruncatedSVD
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

def _tokenize(text):
    return _WORD_RE.findall(text.lower())

class MLEngine:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.available = HAS_SKLEARN and HAS_NUMPY
        self.vectorizer = None
        self.clusterer = None
        self.classifier = None
        self.anomaly_detector = None
        self.svd = None
        self.doc_clusters = {}
        self.intent_labels = []
        self.training_count = 0
        self.last_trained = 0
        if self.available:
            self.vectorizer = TfidfVectorizer(tokenizer=_tokenize, max_features=5000, ngram_range=(1, 2), sublinear_tf=True)
        if save_path and os.path.exists(save_path): self.load()

    def train_clustering(self, documents, n_clusters=None):
        if not self.available or not documents: return False
        texts = [d.get("text", "") for d in documents]
        if len(texts) < 3: return False
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            if n_clusters is None: n_clusters = min(max(3, len(texts) // 10), 20)
            n_clusters = min(n_clusters, len(texts))
            self.clusterer = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init=3, max_iter=100)
            labels = self.clusterer.fit_predict(tfidf_matrix)
            self.doc_clusters = {}
            for i, label in enumerate(labels):
                cluster_id = int(label)
                if cluster_id not in self.doc_clusters: self.doc_clusters[cluster_id] = []
                self.doc_clusters[cluster_id].append(documents[i].get("id", i))
            self.training_count += 1
            self.last_trained = time.time()
            return True
        except: return False

    def train_classifier(self, documents, labels):
        if not self.available or not documents or not labels: return False
        if len(documents) != len(labels): return False
        if len(set(labels)) < 2: return False
        try:
            texts = [d.get("text", "") if isinstance(d, dict) else str(d) for d in documents]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            self.classifier = LogisticRegression(max_iter=200, random_state=42)
            self.classifier.fit(tfidf_matrix, labels)
            self.intent_labels = list(set(labels))
            self.training_count += 1
            return True
        except: return False

    def train_anomaly(self, documents):
        if not self.available or not documents: return False
        try:
            texts = [d.get("text", "") for d in documents]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
            self.anomaly_detector.fit(tfidf_matrix)
            return True
        except: return False

    def classify(self, text):
        if not self.available or not self.classifier: return None, 0.0
        try:
            vec = self.vectorizer.transform([text])
            pred = self.classifier.predict(vec)[0]
            proba = self.classifier.predict_proba(vec)[0]
            confidence = float(max(proba))
            return str(pred), confidence
        except: return None, 0.0

    def detect_anomaly(self, text):
        if not self.available or not self.anomaly_detector: return False, 0.0
        try:
            vec = self.vectorizer.transform([text])
            pred = self.anomaly_detector.predict(vec)[0]
            score = self.anomaly_detector.score_samples(vec)[0]
            return pred == -1, float(score)
        except: return False, 0.0

    def get_similar_documents(self, query, documents, top_n=5):
        if not self.available or not documents: return []
        try:
            texts = [d.get("text", "") for d in documents]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            query_vec = self.vectorizer.transform([query])
            sims = cosine_similarity(query_vec, tfidf_matrix)[0]
            ranked = sorted(enumerate(sims), key=lambda x: -x[1])
            return [(documents[i], float(score)) for i, score in ranked[:top_n] if score > 0.01]
        except: return []

    def get_cluster_summary(self):
        if not self.doc_clusters: return None
        return {"num_clusters": len(self.doc_clusters), "cluster_sizes": {str(k): len(v) for k, v in self.doc_clusters.items()}}

    def save(self):
        if not self.save_path or not self.available: return
        try:
            data = {"doc_clusters": {str(k): v for k, v in self.doc_clusters.items()}, "intent_labels": self.intent_labels, "training_count": self.training_count, "last_trained": self.last_trained}
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.doc_clusters = {int(k): v for k, v in data.get("doc_clusters", {}).items()}
            self.intent_labels = data.get("intent_labels", [])
            self.training_count = data.get("training_count", 0)
            self.last_trained = data.get("last_trained", 0)
        except: pass

    def stats(self):
        return {"available": self.available, "clusters": len(self.doc_clusters), "intents": len(self.intent_labels), "training_count": self.training_count}
