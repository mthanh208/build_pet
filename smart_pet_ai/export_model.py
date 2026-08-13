#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, pickle, json, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.pet_brain import UltimateCognitivePetPro

def export_model(output_path="pet_model.petbrain"):
    print("🧠 Đang tải Pet để xuất trọng số...")
    pet = UltimateCognitivePetPro()

    print("📦 Đang đóng gói dữ liệu...")
    model_data = {
        "documents": pet.documents[-5000:],
        "tokenized_corpus": pet.tokenized_corpus[-5000:],
        "bm25": pet.bm25,
        "graph": pet.graph_engine.graph,
        "abstraction_schemas": pet.abstraction.schemas,
        "expert_rules": [r.__dict__ for r in pet.expert_system.rules],
        "emotion_state": {
            "current": pet.emotion_graph.current_emotion,
            "intensity": pet.emotion_graph.intensity
        },
        "personality": pet.personality.__dict__,
        "narrative": pet.narrative.__dict__
    }

    with open(output_path, "wb") as f:
        pickle.dump(model_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Đã xuất model ra file: {output_path}")
    print(f"📦 Kích thước: {size_mb:.2f} MB")
    print("\n💡 Để dùng file này ở máy khác:")
    print("   1. Cài Python + rank_bm25 + networkx")
    print("   2. Đặt file .petbrain vào thư mục data_memory/")
    print("   3. Chạy main.py - Pet sẽ tự động load 'trọng số' này")

if __name__ == "__main__":
    export_model()
