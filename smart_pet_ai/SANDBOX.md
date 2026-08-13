# PET SANDBOX CONTRACT

Pet may enter `data_memory/sandbox_workspace/` autonomously for coding/debugging work.

Input: `data_memory/sandbox_workspace/drop_here/`
Output: `data_memory/sandbox_workspace/artifacts/`
Execution logs: `data_memory/sandbox_workspace/runs/`
Reports: `data_memory/sandbox_workspace/reports/`
Additional tools: `data_memory/sandbox_workspace/tools/`

Execution policy:
- bubblewrap namespace required for generated-code execution;
- network disabled;
- workspace is writable, host system is not;
- dangerous Python APIs are blocked before execution;
- no host shell escape is granted to generated code;
- if the isolation runtime is missing, execution is refused rather than falling back to the host.

Recommended interaction:
"Đọc và sửa file X trong sandbox, chạy toàn bộ kiểm thử phù hợp và lưu bản hoàn chỉnh vào artifacts." 

Pet does not need a separate command to enter the sandbox. The agent workflow treats it as the normal coding workspace.
