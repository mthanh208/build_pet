# -*- coding: utf-8 -*-
import threading, time, random

class DreamEngine(threading.Thread):
    def __init__(self, pet, idle_seconds=60, check_interval=5):
        super().__init__(daemon=True, name="PetDreamEngine")
        self.pet = pet
        self.idle_seconds = idle_seconds
        self.check_interval = max(1, check_interval)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.check_interval)
            if self._stop_event.is_set(): break
            idle_for = time.time() - self.pet.last_interaction
            if idle_for >= self.idle_seconds:
                try: self._dream_once()
                except: pass
                self.pet.last_interaction = time.time()

    def _dream_once(self):
        pet = self.pet
        with pet.lock:
            candidates = [d for d in pet.documents if len(d.get("text", "").split()) > 4]
            if len(candidates) < 2: return
            d1, d2 = random.sample(candidates, 2)
            dream_text = self._stitch(pet, d1, d2)
            if not dream_text or len(dream_text.split()) <= 10: return
            emotion = pet.emotion_graph.current_emotion
            dream_text = f"[{emotion}] {dream_text}"
            new_doc = {"id": pet.next_id(), "text": dream_text, "source": "Pet's Dream", "weight": 1.0}
            pet.documents.append(new_doc)
            pet.graph_engine.update_graph(dream_text, source="dream")
            pet.abstraction.digest_text(dream_text, source="dream")
            pet.memory.tag_emotion("dream", emotion, pet.emotion_graph.intensity)
            pet.narrative.grow(f"Mơ về {d1['text'][:30]}... và {d2['text'][:30]}...", 0.2)
        pet.rebuild_index()
        pet.rebuild_markov()
        pet.save_all()
        print(f"\n💤 Pet đang mơ [{emotion}]...")
        print(f"   🌙 \"{dream_text}\"")
        print("🐾 Bạn: ", end="", flush=True)

    @staticmethod
    def _stitch(pet, d1, d2):
        s1 = s2 = None
        if pet.markov_model:
            try:
                s1 = pet.markov_model.make_sentence(tries=60)
                s2 = pet.markov_model.make_sentence(tries=60)
            except: pass
        if s1 and s2 and s1.strip() != s2.strip():
            tail = s2.strip()
            tail = tail[0].lower() + tail[1:] if len(tail) > 1 else tail
            return f"{s1.strip()} Từ đó, ta liên tưởng rằng {tail}"
        if s1: return s1.strip()
        frag1 = " ".join(d1["text"].split()[:14])
        frag2 = " ".join(d2["text"].split()[:14])
        return f"{frag1} ... và điều này có thể liên hệ tới ... {frag2}"
