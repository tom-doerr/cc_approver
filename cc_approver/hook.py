from __future__ import annotations
import json, os, sys, logging
from pathlib import Path
from typing import Dict, Any
from .approver import ApproverProgram, configure_lm, try_load_compiled, run_program
from .settings import load_settings_chain, get_dspy_config, get_policy_text
from .constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, HOOK_EVENT_NAME
from .validators import normalize_decision, truncate_reason

logger = logging.getLogger(__name__)

def main() -> None:
    try: 
        payload: Dict[str, Any] = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError) as e:
        logger.debug(f"Failed to parse JSON from stdin: {e}")
        payload = {}
    tool: str = payload.get("tool_name","") or ""
    tinput: Dict[str, Any] = payload.get("tool_input",{}) or {}
    tpath: str = payload.get("transcript_path","") or ""

    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    settings, _ = load_settings_chain(proj)
    cfg = get_dspy_config(settings, proj)

    configure_lm(cfg["model"], temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS)
    candidates = [cfg["compiledModelPath"],
                  str(Path(proj)/".claude/models/approver.compiled.json"),
                  str(Path.home()/".claude/models/approver.compiled.json")]
    program = try_load_compiled(candidates) or ApproverProgram()

    policy = get_policy_text(settings)
    history = tail(tpath, cfg["historyBytes"])
    res = run_program(program, policy, tool, tinput, history)

    decision = normalize_decision(res.decision)
    reason = truncate_reason(res.reason)

    print(json.dumps({"hookSpecificOutput":{
        "hookEventName":HOOK_EVENT_NAME,
        "permissionDecision":decision,
        "permissionDecisionReason":reason
    }}))

def tail(path: str, n: int) -> str:
    if not path or n <= 0: return ""
    try:
        with open(path, "rb") as f:
            f.seek(0,2); sz=f.tell(); f.seek(max(0, sz-n))
            return f.read().decode("utf-8","ignore")[-n:]
    except (FileNotFoundError, IOError) as e:
        logger.debug(f"Failed to read file tail: {e}")
        return ""

if __name__ == "__main__":
    main()