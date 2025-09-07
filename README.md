# cc_approver

DSPy-only **permission hook** + **optimizer** for Claude Code's **PreToolUse**.

- Pure **DSPy** (`dspy.LM`, Signatures/Modules). No heuristics.
- Trains from **JSONL** you can copy from logs (add `label`).
- Optimizers: **MIPROv2** and **GEPA**.
- Settings live in **Claude settings**: `dspyApprover` + `policy.approverInstructions`.
- **Local ↔ Global** compiled program lookup.
- **TUI** (questionary) for `init` and `optimize` if you omit flags.
- **Standalone mode** copies a physical hook file into `.claude/hooks/`.

## Install

```bash
poetry install
# or: pip install -e .
export OPENROUTER_API_KEY=sk-...   # Example provider key; LiteLLM reads it.
```

## Quick start (TUI)

```bash
cc-approver           # opens main menu (Init / Optimize / Exit)
```

### Init (example, non-interactive)

```bash
cc-approver init --scope project --standalone
```

### Optimize (example, non-interactive)

```bash
cc-approver optimize --scope project \
  --train .claude/data/approver_train.jsonl \
  --optimizer mipro --auto light \
  --task-model openrouter/google/gemini-2.5-flash-lite
```

### JSONL line example

```json
{"tool_name":"Bash","tool_input_json":"{\"command\":\"git status\"}","label":"allow"}
```

**Notes**

* **GEPA feedback** can be score-only; short feedback strings speed convergence.
* **History**: default **0** (not included). Set `historyBytes` in settings when your policy truly depends on chat state.