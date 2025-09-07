#!/usr/bin/env python3
# Standalone DSPy-only PreToolUse hook (kept self-contained for portability)
import json, os, sys
from pathlib import Path
import dspy

class Approver(dspy.Signature):
    policy = dspy.InputField()
    tool = dspy.InputField()
    tool_input_json = dspy.InputField()
    history_tail = dspy.InputField(optional=True)
    decision = dspy.OutputField(desc="allow|deny|ask")
    reason = dspy.OutputField()

class Program(dspy.Module):
    def __init__(self): super().__init__(); self.step = dspy.Predict(Approver)
    def forward(self, policy, tool, tool_input_json, history_tail=""):
        return self.step(policy=policy, tool=tool, tool_input_json=tool_input_json, history_tail=history_tail or "")

def _read_json(p: Path):
    try:
        with p.open("r", encoding="utf-8") as f: return json.load(f)
    except Exception: return None

def _settings_chain(project_dir: str):
    proj = Path(project_dir)
    return [proj/".claude"/"settings.local.json", proj/".claude"/"settings.json", Path.home()/".claude"/"settings.json"]

def _load_settings(project_dir: str):
    for p in _settings_chain(project_dir):
        d = _read_json(p)
        if isinstance(d, dict): return d
    return {}

def _policy(settings: dict) -> str:
    pol = settings.get("policy") or {}; t = pol.get("approverInstructions")
    return t if isinstance(t, str) else ""

def _cfg(settings: dict, project_dir: str):
    cfg = settings.get("dspyApprover") or {}
    model = cfg.get("model") or "openrouter/google/gemini-2.5-flash-lite"
    hbytes = int(cfg.get("historyBytes") or 0)
    raw = cfg.get("compiledModelPath") or "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
    cmp = raw.replace("$CLAUDE_PROJECT_DIR", project_dir)
    return model, hbytes, cmp

def _try_load(cmp: str, proj: str):
    prog = Program()
    for p in [cmp, str(Path(proj)/".claude/models/approver.compiled.json"),
              str(Path.home()/".claude/models/approver.compiled.json")]:
        if Path(p).expanduser().exists():
            try: prog.load(str(Path(p).expanduser())); return prog
            except Exception: pass
    return None

def _tail(path: str, n: int) -> str:
    if not path or n <= 0: return ""
    try:
        with open(path, "rb") as f:
            f.seek(0,2); sz=f.tell(); f.seek(max(0, sz-n))
            return f.read().decode("utf-8","ignore")[-n:]
    except Exception:
        return ""

def main():
    try: payload = json.load(sys.stdin)
    except Exception: payload = {}
    tool = payload.get("tool_name","") or ""
    tinput = payload.get("tool_input",{}) or {}
    tpath = payload.get("transcript_path","") or ""
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    settings = _load_settings(proj)
    model, hbytes, cmp = _cfg(settings, proj)
    dspy.configure(lm=dspy.LM(model, temperature=0.0, max_tokens=256))

    program = _try_load(cmp, proj) or Program()
    import json as _j
    res = program(policy=_policy(settings), tool=tool,
                  tool_input_json=_j.dumps(tinput, ensure_ascii=False)[:8000],
                  history_tail=_tail(tpath, hbytes))

    decision = (res.decision or "").strip().lower()
    if decision not in {"allow","deny","ask"}: decision = "ask"
    reason = (res.reason or "")[:500]
    print(json.dumps({"hookSpecificOutput":{
        "hookEventName":"PreToolUse",
        "permissionDecision":decision,
        "permissionDecisionReason":reason
    }}))

if __name__ == "__main__":
    main()