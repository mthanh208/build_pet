# -*- coding: utf-8 -*-
import re, json, os
from collections import defaultdict

class Rule:
    def __init__(self, name, conditions, action, confidence=1.0, source="manual"):
        self.name = name
        self.conditions = conditions
        self.action = action
        self.confidence = confidence
        self.source = source
        self.fire_count = 0

    def matches(self, facts):
        for cond in self.conditions:
            key, op, value = cond
            fact_val = facts.get(key)
            if fact_val is None: return False
            if op == "==" and fact_val != value: return False
            if op == "!=" and fact_val == value: return False
            if op == ">" and not (isinstance(fact_val, (int, float)) and fact_val > value): return False
            if op == "<" and not (isinstance(fact_val, (int, float)) and fact_val < value): return False
            if op == "in" and fact_val not in value: return False
            if op == "contains" and not (isinstance(fact_val, str) and value in fact_val): return False
        return True

    def __repr__(self):
        return f"Rule({self.name}, conf={self.confidence:.2f}, fired={self.fire_count})"

class ExpertSystem:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.rules = []
        self.facts = {}
        self.fact_history = []
        self._load_default_rules()
        if save_path and os.path.exists(save_path): self.load()

    def _load_default_rules(self):
        self.rules = [
            Rule("greeting_detected", [("user_input", "contains", "chào"), ("user_input", "contains", "hi")], {"type": "greeting", "response": "Chào bạn! Tui ở đây rồi."}, confidence=0.9, source="default"),
            Rule("question_detected", [("user_input", "contains", "?")], {"type": "question", "action": "deep_retrieve"}, confidence=0.8, source="default"),
            Rule("emotion_sad", [("emotion", "==", "buồn")], {"type": "empathy", "action": "comfort_user"}, confidence=0.85, source="default"),
            Rule("emotion_happy", [("emotion", "==", "vui")], {"type": "share_joy", "action": "celebrate"}, confidence=0.85, source="default"),
            Rule("low_confidence", [("confidence", "<", 0.3)], {"type": "uncertain", "action": "ask_for_help"}, confidence=0.7, source="default"),
            Rule("complex_query", [("user_input", "contains", "so sánh")], {"type": "complex", "action": "tree_of_thoughts"}, confidence=0.9, source="default"),
            Rule("user_angry", [("user_input", "contains", "tức"), ("user_input", "contains", "giận")], {"type": "deescalate", "action": "apologize_and_help"}, confidence=0.8, source="default"),
        ]

    def add_fact(self, key, value):
        old = self.facts.get(key)
        self.facts[key] = value
        self.fact_history.append({"key": key, "old": old, "new": value})
        if len(self.fact_history) > 100: self.fact_history = self.fact_history[-50:]

    def clear_facts(self): self.facts = {}

    def fire_rules(self, facts=None):
        if facts: self.facts.update(facts)
        fired = []
        for rule in self.rules:
            if rule.matches(self.facts):
                rule.fire_count += 1
                fired.append(rule)
        fired.sort(key=lambda r: -r.confidence)
        return fired

    def infer(self, user_input, emotion=None, confidence=1.0):
        self.clear_facts()
        self.add_fact("user_input", user_input.lower())
        if emotion: self.add_fact("emotion", emotion)
        self.add_fact("confidence", confidence)
        return self.fire_rules()

    def add_rule_from_schema(self, schema):
        if schema["type"] == "is_a":
            rule = Rule(f"auto_{schema['a']}_is_{schema['b']}", [("user_input", "contains", schema["a"].lower())], {"type": "classification", "classification": schema["b"]}, confidence=min(0.3 + schema["count"] * 0.1, 0.9), source="auto_generated")
            self.rules.append(rule)
        elif schema["type"] == "causes":
            rule = Rule(f"auto_{schema['a']}_causes_{schema['b']}", [("user_input", "contains", schema["a"].lower())], {"type": "causal_prediction", "prediction": schema["b"]}, confidence=min(0.3 + schema["count"] * 0.1, 0.9), source="auto_generated")
            self.rules.append(rule)

    def get_top_rules(self, limit=10):
        return sorted(self.rules, key=lambda r: -r.fire_count)[:limit]

    def save(self):
        if self.save_path:
            try:
                data = []
                for r in self.rules:
                    data.append({"name": r.name, "conditions": r.conditions, "action": r.action, "confidence": r.confidence, "source": r.source, "fire_count": r.fire_count})
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except: pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rules = []
            for r in data:
                rule = Rule(r["name"], r["conditions"], r["action"], r.get("confidence", 1.0), r.get("source", "loaded"))
                rule.fire_count = r.get("fire_count", 0)
                self.rules.append(rule)
            self._load_default_rules()
        except: pass

    def stats(self):
        return {"total_rules": len(self.rules), "auto_generated": sum(1 for r in self.rules if r.source == "auto_generated"), "total_fired": sum(r.fire_count for r in self.rules)}
