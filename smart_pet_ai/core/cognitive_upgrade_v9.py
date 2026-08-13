# -*- coding: utf-8 -*-
def install_v9(pet):
    if getattr(pet,'_v9_installed',False): return
    from core.agent_executor import AgentExecutor
    pet.agent_executor=AgentExecutor(pet)
    previous=getattr(pet,'answer_v8',None) or getattr(pet,'answer_v7',None) or getattr(pet,'answer_v6',None) or pet.answer
    def answer_v9(user_input):
        text=str(user_input).strip()
        if not text:return None,'Bạn nói gì tui cũng nghe, nhưng câu trống quá.'
        if text.lower().startswith('agent '):
            task=text[6:].strip()
            if not task:return None,'⚠️ Dùng: agent <nhiệm vụ>'
            report,think=pet.agent_executor.run_task(task)
            return think,report
        return previous(text)
    pet.answer_v9=answer_v9; pet._v9_installed=True
