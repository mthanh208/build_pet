# -*- coding: utf-8 -*-
import random, re, markovify

_SYNONYMS = {
    "tốt": ["tuyệt vờ", "xuất sắc", "tuyệt hảo", "đáng quý", "đẹp đẽ"],
    "xấu": ["tệ hại", "không hay", "đáng tiếc", "buồn phiền"],
    "nhiều": ["dồi dào", "phong phú", "vô số", "vô vàn"],
    "ít": ["hiếm hoi", "khan hiếm", "mong manh"],
    "lớn": ["vĩ đại", "hùng vĩ", "to lớn", "mênh mông"],
    "nhỏ": ["bé nhỏ", "tinh tế", "mong manh", "khiêm tốn"],
    "nhanh": ["tốc hành", "lẹ làng", "vội vã"],
    "chậm": ["thong thả", "chầm chậm", "từ tốn"],
    "vui": ["hân hoan", "phấn khởi", "rạng rỡ", "tươi vui"],
    "buồn": ["u sầu", "phiền muộn", "chán nản", "thê lương"],
    "biết": ["hiểu rõ", "nắm bắt", "thấu hiểu", "lĩnh hội"],
    "nghĩ": ["suy ngẫm", "trăn trở", "chiêm nghiệm", "tư duy"],
}

_OPENINGS = {
    "vui": ["À, chuyện này vui nè! ", "Hì hì, ", "Ồ, tui thích câu hỏi này! ", ""],
    "buồn": ["Hừm... ", "*thở dài* ", "Tui cảm thấy hơi nặng khi nghĩ về điều này. ", ""],
    "tò mò": ["Hỏi hay đấy! ", "Tui cũng đang thắc mắc điều này. ", "Ừm, để tui nghĩ xem... ", ""],
    "bình yên": ["", "Ừ, ", "Theo tui thì ", "Tui nghĩ là ", "Hmm, ", "À, ", "Để xem... ", ""],
    "tức giận": ["Thật lòng mà nói, ", "Tui không thích điều này lắm, nhưng ", ""],
    "yêu thương": ["*mỉm cườ* ", "Bạn à, ", "Tui thương bạn nhiều lắm. ", ""],
    "nhớ nhung": ["Nói đến đây tui lại nhớ... ", "Hồi trước tui từng nghĩ... ", ""],
}

_CLOSINGS_WARM = [" Bạn thấy sao?", " Còn bạn thì sao?", " Nhỉ?", " Đúng không?", ""]
_CLOSINGS_COOL = [" Đó là những gì tui biết.", " Trên đây là phân tích.", ""]

_META_THOUGHTS = [
    "Tui vừa nghĩ đến điều này...",
    "Đột nhiên tui nhận ra...",
    "Càng nghĩ tui càng thấy...",
    "Có một điều tui muốn chia sẻ thêm...",
    "Tui không chắc lắm, nhưng...",
]

class DialogueSynthesizer:
    def __init__(self, markov_model=None, neural_engine=None):
        self.markov = markov_model
        self.neural = neural_engine
        self.used_phrases = set()
        self.recent_openings = []
        self.recent_closings = []
        self.turn_history = []

    def set_markov(self, model):
        self.markov = model

    def set_neural(self, neural_engine):
        self.neural = neural_engine

    def start_new_turn(self):
        self.used_phrases = set()

    def _vary_word(self, text):
        words = text.split()
        new_words = []
        for w in words:
            clean = re.sub(r"[^\w\s]", "", w.lower())
            if clean in _SYNONYMS and random.random() < 0.25:
                synonym = random.choice(_SYNONYMS[clean])
                if w[0].isupper():
                    synonym = synonym[0].upper() + synonym[1:]
                new_words.append(synonym)
            else:
                new_words.append(w)
        return " ".join(new_words)

    def _pick_opening(self, emotion, personality):
        candidates = _OPENINGS.get(emotion, _OPENINGS["bình yên"])
        candidates = [c for c in candidates if c not in self.recent_openings]
        if not candidates:
            candidates = _OPENINGS["bình yên"]
        choice = random.choice(candidates)
        self.recent_openings.append(choice)
        if len(self.recent_openings) > 5:
            self.recent_openings.pop(0)
        return choice

    def _pick_closing(self, relationship, personality):
        if relationship.get("closeness", 0) > 0.5:
            pool = _CLOSINGS_WARM
        else:
            pool = _CLOSINGS_COOL
        pool = [c for c in pool if c not in self.recent_closings]
        if not pool:
            pool = [""]
        choice = random.choice(pool)
        self.recent_closings.append(choice)
        if len(self.recent_closings) > 5:
            self.recent_closings.pop(0)
        return choice

    def _anti_repeat(self, text):
        key = text[:60]
        if key in self.used_phrases or key in self.turn_history:
            return None
        self.used_phrases.add(key)
        return text

    def _generate_markov_sentence(self, tries=80):
        if self.markov is None:
            return None
        try:
            s = self.markov.make_sentence(tries=tries)
            return s.strip() if s else None
        except Exception:
            return None

    def synthesize(self, content_parts, emotion_state, personality_reg, relationship, memory_context=None):
        if self.neural and self.neural.available:
            context_str = "\n".join(content_parts[:3])
            mem_str = ""
            if memory_context:
                mem_str = f"\nNgữ cảnh cũ: {memory_context[0]['text'][:50]}"

            prompt = (
                f"Bạn là một AI thú cưng ảo thân thiện. Trạng thái cảm xúc: {emotion_state}.\n"
                f"Dựa trên thông tin sau, hãy trả lờ ngắn gọn, tự nhiên như con ngườ:\n"
                f"Thông tin: {context_str}{mem_str}\n"
                f"Trả lờ:"
            )

            llm_response = self.neural.generate(prompt, max_tokens=100, temperature=0.6)
            if llm_response and len(llm_response) > 5:
                return llm_response

        self.start_new_turn()
        lines = []
        opening = self._pick_opening(emotion_state, personality_reg)
        if opening:
            lines.append(opening.strip())

        if memory_context and relationship.get("closeness", 0) > 0.3 and random.random() < 0.3:
            mem = random.choice(memory_context)
            mem_text = mem['text'][:50] if len(mem['text']) > 50 else mem['text']
            lines.append(f"Nhắc đến đây, tui nhớ lại lần trước chúng ta từng nói về {mem_text}...")

        if personality_reg.get("poetic", 0) > 0.5 and random.random() < 0.25:
            lines.append(random.choice(_META_THOUGHTS))

        for part in content_parts:
            if not part:
                continue
            varied = self._vary_word(part)
            checked = self._anti_repeat(varied)
            if checked:
                lines.append(checked)

        if personality_reg.get("poetic", 0) > 0.3 and random.random() < 0.3:
            markov_s = self._generate_markov_sentence()
            if markov_s and len(markov_s) > 10:
                checked = self._anti_repeat(markov_s)
                if checked:
                    connectors = ["Còn một điều nữa: ", "Tui chợt nghĩ: ", "Như thể ", ""]
                    lines.append(random.choice(connectors) + checked)

        closing = self._pick_closing(relationship, personality_reg)
        if closing:
            lines.append(closing.strip())

        result = " ".join(lines)
        result = re.sub(r"\s+", " ", result).strip()
        if result and result[-1] not in ".?!…":
            result += random.choice([".", "...", "!", "?"])

        self.turn_history.append(result[:80])
        if len(self.turn_history) > 20:
            self.turn_history = self.turn_history[-10:]
        return result

    def synthesize_emotional(self, emotion, intensity, personality_reg, reason=None):
        templates = {
            "vui": ["Tui đang rất vui! {reason}", "Hôm nay tui cảm thấy rạng rỡ. {reason}", "*cườ* {reason}"],
            "buồn": ["Tui hơi buồn... {reason}", "Lòng tui nặng trĩu. {reason}", "*thở dài* {reason}"],
            "tức giận": ["Tui thấy bực thật! {reason}", "Không fair chút nào! {reason}"],
            "sợ": ["Tui hơi sợ... {reason}", "Lòng tui run run. {reason}"],
            "yêu thương": ["Tui thương bạn nhiều lắm. {reason}", "*ôm ấp* {reason}"],
            "nhớ nhung": ["Tui nhớ bạn... {reason}", "Cứ nhớ hoài. {reason}"],
            "tò mò": ["Tui tò mò quá! {reason}", "Bạn nghĩ sao về điều này? {reason}"],
            "bình yên": ["Tui cảm thấy thanh thản. {reason}", "Mọi thứ dường như chậm lại. {reason}"],
        }
        pool = templates.get(emotion, templates["bình yên"])
        tmpl = random.choice(pool)
        reason_text = reason if reason else ""
        return tmpl.format(reason=reason_text)
