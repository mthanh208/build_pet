# -*- coding: utf-8 -*-
import json
import os
import time


class PersistentLRU:
    """
    Cache LRU có lưu đĩa, dùng cho System 1 và các module nhẹ.
    """

    def __init__(self, save_path=None, max_size=200):
        self.save_path = save_path
        self.max_size = max_size
        self.items = []
        self.hits = 0
        self.misses = 0

        if save_path and os.path.exists(save_path):
            self.load()

    def get(self, key):
        for i, item in enumerate(self.items):
            if item.get("k") == key:
                self.hits += 1
                self.items.append(self.items.pop(i))
                self.save()
                return item.get("v")

        self.misses += 1
        return None

    def set(self, key, value, meta=None):
        self.items = [it for it in self.items if it.get("k") != key]
        self.items.append({
            "k": key,
            "v": value,
            "ts": time.time(),
            "meta": meta or {}
        })

        if len(self.items) > self.max_size:
            self.items = self.items[-self.max_size:]

        self.save()

    def clear(self):
        self.items = []
        self.hits = 0
        self.misses = 0
        self.save()

    def save(self):
        if not self.save_path:
            return

        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "items": self.items,
                    "hits": self.hits,
                    "misses": self.misses
                }, f, ensure_ascii=False, indent=0)
        except Exception:
            pass

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.items = data.get("items", [])
                self.hits = data.get("hits", 0)
                self.misses = data.get("misses", 0)
        except Exception:
            self.items = []

    def stats(self):
        return {
            "size": len(self.items),
            "hits": self.hits,
            "misses": self.misses
        }
