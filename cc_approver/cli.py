from __future__ import annotations
import argparse, json, os, sys, shutil, logging
from pathlib import Path
from typing import Optional, Dict, Any
from .approver import ApproverProgram, configure_lm, try_load_compiled, run_program
from .settings import (
    load_settings_chain, write_settings, ensure_policy_text, ensure_dspy_config,
    merge_pretooluse_hook, get_policy_text, get_dspy_config
)
from .optimizer import optimize_from_files
from . import tui
from .constants import (
    DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, VALID_DECISIONS,
    DEFAULT_DECISION, MAX_REASON_LENGTH, HOOK_EVENT_NAME
)
from .validators import normalize_decision, truncate_reason

logger = logging.getLogger(__name__)

def main() -> None:
    if len(sys.argv) == 1:
        _tui_entry(); return

    ap = argparse.ArgumentParser(prog="cc-approver", description="DSPy-only approver for Claude Code")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Setup hook + settings (project/global)")
    p.add_argument("--scope", choices=["project","global"])
    p.add_argument("--history-bytes", type=int)
    p.add_argument("--model")
    p.add_argument("--prompt-model")
    p.add_argument("--eval-model")
    p.add_argument("--reflection-model")
    p.add_argument("--matcher")
    p.add_argument("--timeout", type=int)
    p.add_argument("--standalone", action="store_true")
    p.add_argument("--policy-text")
    p.set_defaults(func=cmd_init_or_tui)

    p = sub.add_parser("optimize", help="Train/compile from JSONL labels")
    p.add_argument("--scope", choices=["project","global"])
    p.add_argument("--train")
    p.add_argument("--val")
    p.add_argument("--optimizer", choices=["mipro","gepa"])
    p.add_argument("--auto", choices=["light","medium","heavy"])
    p.add_argument("--task-model")
    p.add_argument("--prompt-model")
    p.add_argument("--reflection-model")
    p.add_argument("--eval-model")
    p.add_argument("--save")
    p.add_argument("--history-bytes", type=int)
    p.set_defaults(func=cmd_optimize_or_tui)

    p = sub.add_parser("hook", help="Run the PreToolUse hook")
    p.add_argument("--history-bytes", type=int, help="Override settings historyBytes")
    p.set_defaults(func=cmd_hook)

    args = ap.parse_args()
    args.func(args)

def _tui_entry() -> None:
    act = tui.main_menu()
    if act == "Init": cmd_init_or_tui(argparse.Namespace())
    elif act == "Optimize": cmd_optimize_or_tui(argparse.Namespace())
    else: sys.exit(0)

def cmd_init_or_tui(args: argparse.Namespace) -> None:
    need_tui = not all(getattr(args, k, None) is not None for k in
                       ["scope","model","history_bytes","matcher","timeout","policy_text"])
    sel = tui.init_menu() if need_tui else {
        "scope": args.scope, "model": args.model, "history_bytes": args.history_bytes,
        "standalone": args.standalone, "matcher": args.matcher, "timeout": args.timeout,
        "policy_text": args.policy_text
    }
    sel["prompt_model"] = getattr(args, "prompt_model", None)
    sel["eval_model"] = getattr(args, "eval_model", None)
    sel["reflection_model"] = getattr(args, "reflection_model", None)
    _run_init(**sel)

def _run_init(scope, model, history_bytes, standalone, matcher, timeout, policy_text,
              prompt_model=None, eval_model=None, reflection_model=None):
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    settings, path = load_settings_chain(proj)
    compiled_path = ("$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
                     if scope == "project" else str(Path.home()/".claude/models/approver.compiled.json"))
    command = "cc-approver hook"
    if standalone:
        src = Path(__file__).with_name("hook_template.py")
        dst = Path(proj)/".claude"/"hooks"/"cc_approver_hook.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        # Make the hook executable
        dst.chmod(0o755)
        command = "$CLAUDE_PROJECT_DIR/.claude/hooks/cc_approver_hook.py"
    settings = ensure_policy_text(settings, policy_text)
    settings = ensure_dspy_config(settings, model=model, history_bytes=history_bytes,
                                  compiled_path=compiled_path, optimizer="mipro", auto="light",
                                  prompt_model=prompt_model, eval_model=eval_model,
                                  reflection_model=reflection_model)
    settings = merge_pretooluse_hook(settings, command=command, matcher=matcher, timeout=timeout)
    write_settings(settings, path)
    print(f"Initialized settings at {path}")
    if standalone: print(f"Hook written to {dst}")

def cmd_optimize_or_tui(args: argparse.Namespace) -> None:
    need_tui = not getattr(args, "train", None)
    sel = tui.optimize_menu() if need_tui else {
        "scope": args.scope or "project",
        "optimizer": args.optimizer or "mipro",
        "auto": args.auto or "light",
        "task_model": args.task_model,
        "prompt_model": args.prompt_model,
        "reflection_model": args.reflection_model,
        "eval_model": args.eval_model,
        "train": args.train, "val": args.val,
        "history_bytes": args.history_bytes if args.history_bytes is not None else 0,
    }
    _run_optimize(**sel, save=getattr(args, "save", None))

def _run_optimize(scope, optimizer, auto, task_model, prompt_model, reflection_model,
                  eval_model, train, val, history_bytes, save=None):
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    settings, _ = load_settings_chain(proj)
    cfg = get_dspy_config(settings, proj)
    task = task_model or cfg["model"]
    prompt = prompt_model or cfg.get("promptModel")
    refl = reflection_model or cfg.get("reflectionModel")
    evalm = eval_model or cfg.get("evalModel")

    save_path = Path(save) if save else (
        Path(cfg["compiledModelPath"]) if scope == "project" else Path.home()/".claude/models/approver.compiled.json"
    )
    save_path.parent.mkdir(parents=True, exist_ok=True)

    warm = save_path if save_path.exists() else (Path(proj)/".claude/models/approver.compiled.json")
    warm = warm if isinstance(warm, Path) and warm.exists() else (Path.home()/".claude/models/approver.compiled.json")

    compiled, acc = optimize_from_files(
        task_model=task, train_path=Path(train), val_path=Path(val) if val else None,
        optimizer=optimizer, auto=auto, settings=settings,
        prompt_model=prompt, reflection_model=refl, eval_model=evalm,
        history_bytes=history_bytes, warm_start=warm if isinstance(warm, Path) and warm.exists() else None,
    )
    compiled.save(str(save_path))
    print(f"Saved compiled program to {save_path}")
    print(f"Dev accuracy: {acc:.3f}")

def cmd_hook(args: argparse.Namespace) -> None:
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

    history_bytes = args.history_bytes if getattr(args, "history_bytes", None) is not None else cfg["historyBytes"]
    history = tail(tpath, history_bytes)
    res = run_program(program, get_policy_text(settings), tool, tinput, history)

    decision = normalize_decision(res.decision)
    reason = truncate_reason(res.reason)
    print(json.dumps({"hookSpecificOutput":{
        "hookEventName":HOOK_EVENT_NAME,"permissionDecision":decision,"permissionDecisionReason":reason}}))

def tail(path: str, n: int) -> str:
    if not path or not isinstance(n, int) or n <= 0: return ""
    try:
        with open(path, "rb") as f:
            f.seek(0,2); sz=f.tell(); f.seek(max(0, sz-n))
            return f.read().decode("utf-8","ignore")[-n:]
    except (FileNotFoundError, IOError) as e:
        logger.debug(f"Failed to read file tail: {e}")
        return ""