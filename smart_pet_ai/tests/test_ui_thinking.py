from core.neural_engine import needs_thinking,sanitize,NeuralEngine
assert needs_thinking('xin chào') is False
assert needs_thinking('hãy phân tích lỗi Python này') is True
assert sanitize('<think>secret</think>Xin chào!')=='Xin chào!'
assert sanitize('<reasoning>secret</reasoning>Pet: Xin chào!').endswith('Xin chào!')
n=NeuralEngine(); assert not n.model_loaded
print('UI_THINK_TESTS_PASS')
