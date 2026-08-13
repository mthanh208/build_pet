# -*- coding: utf-8 -*-
import os
import re
import time


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_sandbox_stats_cmd(text):
    low = text.lower()
    return low in ("v8", "sandbox", "smart sandbox", "sandbox stats", "v8 stats")


def _is_note_list_cmd(text):
    low = text.lower()
    return low in ("notes", "note list", "scratch", "nháp", "nhap", "scratchpad")


def install_v8(pet):
    """
    V8 Smart Sandbox Upgrade.

    Thêm:
      - SmartSandbox
      - note/draft/scratchpad
      - safe code execution
      - math solver
      - code block runner
    """

    if getattr(pet, "_v8_installed", False):
        return

    from core.smart_sandbox import SmartSandbox

    pet.smart_sandbox = SmartSandbox(pet=pet)

    # Thay run_sandbox cũ bằng smart sandbox
    def run_sandbox_v8(code, timeout=15):
        return pet.smart_sandbox.run_python(code, timeout=timeout, memory_mb=256, safe=True)

    pet.run_sandbox = run_sandbox_v8

    previous_answer = getattr(pet, "answer_v7", None) or getattr(pet, "answer_v6", None) or pet.answer

    def answer_v8(user_input):
        text = str(user_input).strip()
        if not text:
            return None, "Bạn nói gì tui cũng nghe, nhưng câu trống quá."

        low = text.lower()

        # -------------------------------------------------------------
        # Stats
        # -------------------------------------------------------------
        if _is_sandbox_stats_cmd(text):
            return None, pet.smart_sandbox.stats_text()

        # -------------------------------------------------------------
        # Notes / Scratchpad
        # -------------------------------------------------------------
        if _is_note_list_cmd(text):
            return None, pet.smart_sandbox.list_notes()

        if low.startswith("note read "):
            name = text[len("note read "):].strip()
            return None, pet.smart_sandbox.read_note(name)

        if low.startswith("note search "):
            query = text[len("note search "):].strip()
            return None, pet.smart_sandbox.search_notes(query)

        if low.startswith("note add "):
            rest = text[len("note add "):].strip()

            if ":" in rest:
                name, content = rest.split(":", 1)
                name = name.strip()
                content = content.strip()
            else:
                name = time.strftime("note_%Y%m%d_%H%M%S")
                content = rest

            if not content:
                return None, "⚠️ Note trống."

            msg = pet.smart_sandbox.save_note(name, content)
            return None, msg

        if low.startswith("note append "):
            rest = text[len("note append "):].strip()

            if ":" in rest:
                name, content = rest.split(":", 1)
                name = name.strip()
                content = content.strip()
            else:
                return None, "⚠️ Dùng: note append <tên>: <nội dung>"

            if not content:
                return None, "⚠️ Nội dung trống."

            msg = pet.smart_sandbox.append_note(name, content)
            return None, msg

        # -------------------------------------------------------------
        # Drafting
        # -------------------------------------------------------------
        if low.startswith("draft "):
            task = text[len("draft "):].strip()
            if not task:
                return None, "⚠️ Dùng: draft <nhiệm vụ>"

            result = pet.smart_sandbox.draft(task)
            return "📝 Draft route", result

        # -------------------------------------------------------------
        # Sandbox direct code
        # -------------------------------------------------------------
        if low.startswith("sandbox "):
            code = text[len("sandbox "):].strip()

            if not code:
                return None, "⚠️ Dùng: sandbox <code_python>"

            result = pet.smart_sandbox.run_python(code, timeout=15, memory_mb=256, safe=True)

            if result.get("success"):
                out = result.get("output", "").strip()
                answer = f"🧪 Sandbox success:\n{out[:2500]}"
            else:
                err = result.get("error", "không rõ lỗi").strip()
                answer = f"⚠️ Sandbox error:\n{err[:1000]}"

            think = f"🧪 Smart Sandbox run_id={result.get('run_id', 'unknown')}"
            return think, answer

        # -------------------------------------------------------------
        # Code block / math
        # -------------------------------------------------------------
        has_code_block = "```" in text
        has_math_intent = any(k in low for k in [
            "tính", "calculator", "compute", "bằng bao nhiêu", "bao nhiêu",
            "toán", "math", "solve"
        ])
        has_run_intent = any(k in low for k in [
            "chạy code", "run code", "sandbox", "python", "script"
        ])

        if has_code_block or has_math_intent or has_run_intent:
            result = pet.smart_sandbox.smart_request(text)

            if result is not None:
                if result.get("success"):
                    out = result.get("output", "").strip()
                    answer = f"🧪 Kết quả sandbox:\n{out[:2500]}"
                else:
                    err = result.get("error", "không rõ lỗi").strip()
                    answer = f"⚠️ Sandbox không chạy được:\n{err[:1000]}"

                think = (
                    "🧪 Smart Sandbox route\n"
                    f"  • run_id: {result.get('run_id', 'unknown')}\n"
                    f"  • success: {result.get('success', False)}"
                )
                return think, answer

        # -------------------------------------------------------------
        # Fallback pipeline cũ / v6 / v7
        # -------------------------------------------------------------
        return previous_answer(text)

    pet.answer_v8 = answer_v8
    pet._v8_installed = True
