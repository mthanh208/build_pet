# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_universal_parser():
    from core.universal_parser import UniversalParser
    p = UniversalParser()
    r = p.parse_line('{"text": "hello world"}')
    assert r is not None
    assert "hello world" in r["texts"]
    r = p.parse_line('{"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}')
    assert r is not None
    assert len(r["texts"]) >= 2
    r = p.parse_line('{"text": "result <thinking>because of X</thinking>"}')
    assert r is not None
    assert len(r["think_blocks"]) >= 1
    assert "because of X" in r["think_blocks"][0]
    print("✅ Universal Parser passed")

def test_graph_engine():
    from core.graph_engine import GraphEngine
    g = GraphEngine()
    g.update_graph("Trí Tuệ Nhân Tạo là lĩnh vực khoa học máy tính.", "test")
    assert g.graph.number_of_nodes() > 0
    print("✅ Graph Engine passed")

def test_expert_system():
    from core.expert_system import ExpertSystem
    e = ExpertSystem()
    fired = e.infer("chào bạn", emotion="vui", confidence=0.8)
    assert len(fired) > 0
    print("✅ Expert System passed")

def test_symbolic_solver():
    from core.symbolic_solver import SymbolicSolver
    s = SymbolicSolver()
    if s.available:
        r = s.solve_equation("2*x + 3 = 7")
        assert r is not None
        assert len(r["solutions"]) > 0
        print("✅ Symbolic Solver passed")
    else:
        print("⏭️  Symbolic Solver skipped (no sympy)")

def test_sandbox():
    from core.sandbox import Sandbox
    sb = Sandbox(timeout=5)
    r = sb.run_python("print(1+1)")
    assert r["success"]
    assert "2" in r["output"]
    print("✅ Sandbox passed")

if __name__ == "__main__":
    test_universal_parser()
    test_graph_engine()
    test_expert_system()
    test_symbolic_solver()
    test_sandbox()
    print("\n🎉 All tests passed!")
