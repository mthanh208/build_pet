# -*- coding: utf-8 -*-
"""
AgentExecutor — sinh code, KIỂM THỬ trong sandbox, rồi mới lưu file sạch.
Flow:
  1. Sinh code qua LLM
  2. Kiểm tra cú pháp (AST)
  3. Kiểm tra bảo mật (static_scan)
  4. Thực thi trong sandbox
  5. Nếu lỗi → sửa và retry (tối đa 3 lần)
  6. Lưu file sạch vào artifacts/
  7. Trả về báo cáo có kết quả thực thi
"""
from __future__ import annotations
import ast
import os
import re
import time
from pathlib import Path

from core.secure_sandbox import SecureSandbox, static_scan


class AgentExecutor:
    def __init__(self, pet):
        self.pet = pet
        workspace = getattr(getattr(pet, 'smart_sandbox', None), 'workspace', None)
        if not workspace:
            root = Path(__file__).resolve().parents[1]
            workspace = root / 'data_memory' / 'sandbox_workspace'
        self.workspace = str(workspace)
        self.artifacts_dir = os.path.join(self.workspace, 'artifacts')
        self.runs_dir = os.path.join(self.workspace, 'runs')
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)
        self._sandbox = SecureSandbox(
            root=str(Path(self.workspace).parent.parent),
            workspace=self.workspace
        )

    # ------------------------------------------------------------------
    # 1. Sinh code qua LLM
    # ------------------------------------------------------------------
    def _generate_code(self, task, error_context=''):
        engine = getattr(self.pet, 'neural_engine', None)
        if engine is None or not getattr(engine, 'available', False):
            return None, 'Neural engine không khả dụng.'

        prompts = [
            (
                f'Bạn là một lập trình viên Python tự trị.\n'
                f'Nhiệm vụ: {task}\n'
                f'Yêu cầu bắt buộc:\n'
                f'- Viết code Python hoàn chỉnh, chạy được ngay.\n'
                f'- Cuối file PHẢI có phần chạy thử / ví dụ sử dụng để chứng minh code hoạt động.\n'
                f'- Không dùng thư viện ngoài trừ thư viện chuẩn Python.\n'
                f'- Chỉ trả về code Python thuần, KHÔNG có markdown fence, KHÔNG có giải thích ngoài code.\n'
            ),
            (
                f'Viết code Python nhỏ gọn, đúng đắn cho: {task}\n'
                f'Bắt buộc có phần demo/test ở cuối file.\n'
                f'Chỉ trả về code Python hợp lệ.\n'
            ),
        ]
        if error_context:
            prompts[0] += f'\nLỗi lần trước:\n{error_context}\nHãy sửa lỗi này.\n'

        last_err = 'LLM trả về rỗng.'
        for prompt in prompts:
            try:
                code = engine.generate(
                    prompt,
                    max_tokens=600,
                    temperature=0.15,
                    thinking=False
                )
            except Exception as e:
                last_err = f'LLM error: {e}'
                continue
            if not code:
                last_err = 'LLM trả về rỗng.'
                continue
            code = re.sub(r'^```(?:python|py)?\s*', '', str(code).strip(), flags=re.I)
            code = re.sub(r'\s*```$', '', code).strip()
            try:
                ast.parse(code)
            except SyntaxError as e:
                last_err = f'Cú pháp không hợp lệ: {e}'
                continue
            return code, None
        return None, last_err

    # ------------------------------------------------------------------
    # 2. Kiểm tra cú pháp
    # ------------------------------------------------------------------
    def _syntax_check(self, code):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # 3. Kiểm tra bảo mật
    # ------------------------------------------------------------------
    def _security_check(self, code):
        result = static_scan(code)
        return result['safe'], result.get('findings', [])

    # ------------------------------------------------------------------
    # 4. Thực thi trong sandbox
    # ------------------------------------------------------------------
    def _execute(self, code, timeout=30):
        return self._sandbox.run_python(code, timeout=timeout, safe=True)

    # ------------------------------------------------------------------
    # 5. Lưu file sạch vào artifacts
    # ------------------------------------------------------------------
    def _save_artifact(self, task, code, exec_output, exec_success):
        ts = time.strftime('%Y%m%d_%H%M%S')
        safe_name = re.sub(r'[^\w\- ]', '', task[:60]).strip().replace(' ', '_') or 'task'
        filename = f'{safe_name}_{ts}.py'
        filepath = os.path.join(self.artifacts_dir, filename)

        header = (
            '# ' + '=' * 60 + '\n'
            f'# Nhiệm vụ: {task}\n'
            f'# Thời gian: {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'# Trạng thái thực thi: {"✅ Thành công" if exec_success else "⚠️ Chưa verify"}\n'
            '# ' + '=' * 60 + '\n\n'
        )
        footer = ''
        if exec_output:
            footer = (
                '\n\n# ' + '=' * 60 + '\n'
                '# Kết quả thực thi:\n'
                + ''.join(f'# {line}\n' for line in exec_output.strip().splitlines()[:30])
                + '# ' + '=' * 60 + '\n'
            )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + code + footer)
        return filepath, filename

    # ------------------------------------------------------------------
    # 6. Chạy task hoàn chỉnh
    # ------------------------------------------------------------------
    def run_task(self, task):
        think = ['🤖 Agent: Bắt đầu nhiệm vụ...']
        max_attempts = 3
        code = None
        last_err = None

        # Sinh code lần đầu
        code, err = self._generate_code(task)
        if not code:
            think.append(f'❌ Không sinh được code: {err}')
            return f'❌ Agent không thể sinh code: {err}', '\n'.join(think)

        final_result = None
        exec_output = ''
        exec_success = False

        for attempt in range(max_attempts):
            think.append(f'🔄 Lần thử {attempt + 1}/{max_attempts}: Kiểm tra và thực thi...')

            # B1: Kiểm tra cú pháp
            syn_ok, syn_err = self._syntax_check(code)
            if not syn_ok:
                think.append(f'❌ Cú pháp lỗi: {syn_err}')
                last_err = syn_err
                code, err = self._generate_code(task, error_context=syn_err)
                if not code:
                    break
                continue
            think.append('✅ Cú pháp hợp lệ.')

            # B2: Kiểm tra bảo mật
            sec_ok, sec_findings = self._security_check(code)
            if not sec_ok:
                think.append(f'⚠️ Bảo mật: {"; ".join(sec_findings[:3])}')
                # Không chặn hoàn toàn, chỉ cảnh báo
                think.append('⚠️ Tiếp tục với cảnh báo bảo mật.')

            # B3: Thực thi trong sandbox
            think.append('⚡ Đang thực thi trong sandbox...')
            result = self._execute(code, timeout=30)
            final_result = result

            if result.get('success'):
                exec_success = True
                exec_output = result.get('output', '')
                think.append(f'✅ Thực thi thành công!')
                if exec_output:
                    think.append(f'📤 Output: {exec_output[:300]}')
                break
            else:
                exec_output = result.get('error', '') or result.get('output', '')
                think.append(f'❌ Thực thi thất bại: {exec_output[:200]}')
                last_err = exec_output[:500]
                if attempt < max_attempts - 1:
                    think.append('🔧 Đang sửa code...')
                    new_code, err = self._generate_code(task, error_context=last_err)
                    if new_code:
                        code = new_code
                    else:
                        break

        # Lưu file sạch
        filepath, filename = self._save_artifact(task, code, exec_output, exec_success)
        think.append(f'💾 Đã lưu: {filename}')

        # Xây dựng báo cáo
        status = '✅ Thành công — đã kiểm thử' if exec_success else '⚠️ Đã lưu nhưng chưa verify thành công'
        report_lines = [
            f'🤖 BÁO CÁO AGENT:',
            f'🎯 Nhiệm vụ: {task[:120]}',
            f'📊 Trạng thái: {status}',
            '',
        ]
        if exec_success and exec_output:
            report_lines += [
                '💡 Kết quả thực thi:',
                exec_output[:800],
                '',
            ]
        elif not exec_success and exec_output:
            report_lines += [
                '⚠️ Lỗi thực thi:',
                exec_output[:400],
                '',
            ]
        report_lines += [
            f'📁 File đã lưu: {filepath}',
            f'📂 Lấy file: cp "{filepath}" ~/Desktop/',
        ]
        return '\n'.join(report_lines), '\n'.join(think)
