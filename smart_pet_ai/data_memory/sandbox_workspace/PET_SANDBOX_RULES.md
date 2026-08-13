# PET AUTONOMOUS SANDBOX RULES

The sandbox is your default coding home.

When a task involves code, debugging, refactoring, tests, generated files, or documents containing code:
1. Inspect `drop_here/` first.
2. Inspect existing files before editing them.
3. Work only inside this sandbox workspace.
4. Use the available tools: `syntax_check`, `compile_tree`, `static_security`, `unittest`, `pytest`, and `smoke_run`.
5. After any code change, run the smallest relevant checks and then a broader check when practical.
6. Save finished artifacts under `artifacts/` and diagnostic runs under `runs/`.
7. Never request permission merely to enter the sandbox. Enter it autonomously whenever the task requires code work.
8. Never attempt host administration, package installation, network access, credential access, or writes outside the workspace.
9. If a tool is unavailable, report it and continue with safe alternatives.
10. A green syntax check is not proof of correctness. Prefer tests and observable behavior.

Human-provided files dropped into `drop_here/` are input material and may be edited only by creating a safe copy or by explicit task intent; preserve originals when practical.
