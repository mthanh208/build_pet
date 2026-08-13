#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os,sys,time,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from core.pet_brain import UltimateCognitivePetPro
from core.agent_executor import AgentExecutor
class C:
    RESET='\033[0m'; CYAN='\033[96m'; YELLOW='\033[93m'; GREEN='\033[92m'; MAGENTA='\033[95m'; DIM='\033[2m'; RED='\033[91m'; BOLD='\033[1m'
BANNER=f'''{C.CYAN}{C.BOLD}
╔═══════════════════════════════════════════════════════════╗
║  🐾🌟🧠  ULTIMATE COGNITIVE PET AI v4.2  🧠🌟🐾           ║
║  Society of Mind · 24 Engines · Universal JSONL · Think   ║
║  Neural GGUF Integrated · 100% Offline · Self-Verifying   ║
╚═══════════════════════════════════════════════════════════╝
{C.RESET}'''
THINK_BLOCK=re.compile(r'<think(?:ing)?\b[^>]*>.*?</think(?:ing)?\s*>|<reasoning\b[^>]*>.*?</reasoning\s*>|<thought\b[^>]*>.*?</thought\s*>|<analysis\b[^>]*>.*?</analysis\s*>',re.I|re.S)
THINK_TAG=re.compile(r'</?(?:think(?:ing)?|reasoning|thought|analysis)\b[^>]*>',re.I)
def clean_answer(text):
    text=str(text or '').replace('\x00',' ').strip(); text=THINK_BLOCK.sub(' ',text); text=THINK_TAG.sub(' ',text)
    if re.search(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:',text,re.I):
        m=re.findall(r'(?:^|\n)\s*(?:Pet|Assistant)\s*:\s*(.+?)(?=\n|$)',text,re.I); text=m[-1] if m else re.split(r'(?:^|\n)\s*(?:Người\s*dùng|User)\s*:\s*',text,flags=re.I)[0]
    text=re.sub(r'(?im)^\s*(?:Chain[- ]of[- ]thought|Reasoning|Analysis|Thoughts?)\s*:\s*','',text)
    return re.sub(r'\n{3,}','\n\n',text).strip()
def typewriter(text,delay=None,color=C.CYAN):
    text=clean_answer(text)
    if not text:return
    delay=delay if delay is not None else (0.018 if len(text)<160 else 0.010)
    for ch in text:
        sys.stdout.write(f'{color}{ch}{C.RESET}'); sys.stdout.flush(); time.sleep(delay*(2.0 if ch in '.!?…' else 1.3 if ch==',' else 1.0))
    print()
def stats(pet):
    s=pet.neural_engine.last_stats
    if s:
        mode='think' if s.get('thinking') else 'fast'; print(f'{C.DIM}⚡ {s["tokens"]} tok | {s["time"]}s | {s["tok_per_sec"]} tok/s | mode={mode}{C.RESET}'); pet.neural_engine.last_stats=None
def should_use_code_agent(prompt):
    """Route genuine coding/debugging requests to the sandbox agent."""
    s=str(prompt or '').strip().lower()
    code_markers=(
        'python','code','debug','bug','lỗi','sửa code','viết hàm','hàm ',
        'chạy thử','kiểm tra code','test code','unit test','pytest','unittest',
        'traceback','exception','syntaxerror','refactor','compile','compile_tree',
        'sandbox','file .py','tạo script','viết script','sửa file','kiểm thử'
    )
    action_markers=('viết','tạo','sửa','debug','kiểm tra','test','chạy','phân tích','refactor','fix')
    return any(k in s for k in code_markers) and any(a in s for a in action_markers)

def load_upgrade(pet, version):
    """Load V6..V9 regardless of historical installer naming."""
    import importlib
    mod=importlib.import_module(f'core.cognitive_upgrade_{version}')
    n=version[-1]
    for name in (f'install_{version}', f'install_{n}'):
        fn=getattr(mod,name,None)
        if callable(fn):
            fn(pet)
            return True
    return False

def answer_agent(task, pet, agent_holder):
    """Run coding work inside the autonomous sandbox; return only final report."""
    agent=agent_holder.get('agent')
    if agent is None:
        agent=AgentExecutor(pet)
        agent_holder['agent']=agent
    report,_hidden=agent.run_task(task)
    return clean_answer(report)

def main():
    print(BANNER); print('⏳ Đang khởi động 24 bộ não Pet v4.2...'); start=time.time(); pet=UltimateCognitivePetPro()
    for v in ('v6','v7','v8','v9'):
        try:
            if not load_upgrade(pet,v):
                print(f'⚠️ {v.upper()} skip: installer không tồn tại')
        except Exception as e:
            print(f'⚠️ {v.upper()} skip: {e}')
    ns=pet.neural_engine.stats(); print(f'{C.GREEN}🧠 Pet v4.2 đã sẵn sàng! (Khởi động trong {time.time()-start:.2f}s){C.RESET}'); print(f'{C.DIM}   • Kiến thức: {len(pet.documents)} docs'); print(f'   • Cảm xúc: {pet.emotion_graph.current_emotion}')
    status='✅ GGUF đã load' if ns.get('model_loaded') else ('🟢 GGUF sẵn sàng — lazy load' if ns.get('model_exists') else '❌ Không tìm thấy GGUF')
    print(f'   • Neural LLM: {status}'); print(f'   • Model: {ns.get("model_path","unknown")}{C.RESET}'); print(f'   • Gõ "help" để xem lệnh.{C.RESET}\n'); 
    _agent_holder={'agent':None}
    try:
        while True:
            try:u=input(f'{C.YELLOW}🐾 Bạn: {C.RESET}').strip()
            except EOFError:break
            if not u:continue
            low=u.lower()
            if low in ('thoát','thoat','exit','quit'):break
            if low=='help':_,a=pet.answer('help');typewriter(a,0.006,C.DIM);continue
            if low=='stats':_,a=pet.answer('stats');typewriter(a,0.006,C.DIM);continue
            if low in ('engines','bộ não','engines status'):_,a=pet.answer('engines');typewriter(a,0.006,C.DIM);continue
            if low=='feed':n=pet.digest_hot_folder();typewriter(f'📚 Đã tiếp nhận {n} nguồn thay đổi.' if n else '📭 data_hot/ không có nguồn mới.',0.008,C.DIM);continue
            if low in ('identity','bạn là ai','whoareyou'):typewriter(f'🌟 Pet: {pet.narrative.introduce_self()}',0.014);continue
            if low in ('emotion','cảm xúc','mood'):e=pet.emotion_graph;typewriter(f'💫 Pet đang cảm thấy: {e.current_emotion} (cường độ {e.intensity:.2f})',0.014,C.MAGENTA);continue
            if low=='dream':typewriter('💤 Pet đang chờ giấc mơ tiếp theo...',0.008,C.DIM);continue
            if low in ('verify','verification'):v=pet.verification.stats();typewriter(f'🔍 Verification: passed={v["passed"]}, failed={v["failed"]}, rate={v["pass_rate"]:.1%}',0.008,C.DIM);continue
            if low in ('export','save model','xuất model'):import export_model;export_model.export_model();continue
            # Coding/debugging requests automatically enter the sandbox agent.
            if should_use_code_agent(u):
                try:
                    a=answer_agent(u,pet,_agent_holder)
                except Exception as e:
                    a=f'Tui không thể hoàn thành tác vụ trong sandbox: {e}'
                typewriter(f'🌟 Pet: {a}'); stats(pet); continue
            if hasattr(pet,'answer_v9'):_,a=pet.answer_v9(u)
            elif hasattr(pet,'answer_v8'):_,a=pet.answer_v8(u)
            elif hasattr(pet,'answer_v7'):_,a=pet.answer_v7(u)
            elif hasattr(pet,'answer_v6'):_,a=pet.answer_v6(u)
            else:r=pet.answer(u);_,a=r if isinstance(r,tuple) else (None,r)
            typewriter(f'🌟 Pet: {clean_answer(a) or "Tui chưa tạo được câu trả lời sạch từ model."}');stats(pet)
    except KeyboardInterrupt:print(f'\n{C.YELLOW}👋 Tạm biệt!{C.RESET}')
    finally:
        try:pet.shutdown()
        except Exception:pass
        typewriter('💾 Đã lưu trạng thái Pet. Hẹn gặp lại! 🐾',0.008,C.GREEN)
if __name__=='__main__':main()
