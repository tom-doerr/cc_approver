from __future__ import annotations
import argparse, json, os, sys, logging
from pathlib import Path
from typing import Optional, Dict, Any
from .settings import (
    load_settings_chain, write_settings, ensure_policy_text, ensure_dspy_config,
    merge_pretooluse_hook, get_policy_text, get_dspy_config, _read_json
)
from .optimizer import optimize_from_files
from . import tui

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
    p.add_argument("--verbose", action="store_true", help="Show verbose debug output")
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
        "matcher": args.matcher, "timeout": args.timeout,
        "policy_text": args.policy_text
    }
    sel["prompt_model"] = getattr(args, "prompt_model", None)
    sel["eval_model"] = getattr(args, "eval_model", None)
    sel["reflection_model"] = getattr(args, "reflection_model", None)
    _run_init(**sel)

def _run_init(scope, model, history_bytes, matcher, timeout, policy_text,
              prompt_model=None, eval_model=None, reflection_model=None):
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    
    # Determine target path based on scope
    if scope == "global":
        path = Path.home() / ".claude" / "settings.json"
        settings = _read_json(path) or {}
    else:  # project scope
        path = Path(proj) / ".claude" / "settings.json"
        settings = _read_json(path) or {}
    
    compiled_path = ("$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
                     if scope == "project" else str(Path.home()/".claude/models/approver.compiled.json"))
    command = "cc-approver hook"
    settings = ensure_policy_text(settings, policy_text)
    settings = ensure_dspy_config(settings, model=model, history_bytes=history_bytes,
                                  compiled_path=compiled_path, optimizer="mipro", auto="light",
                                  prompt_model=prompt_model, eval_model=eval_model,
                                  reflection_model=reflection_model)
    settings = merge_pretooluse_hook(settings, command=command, matcher=matcher, timeout=timeout)
    write_settings(settings, path)
    print(f"Initialized settings at {path}")

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
    # Set verbose flag if provided
    if getattr(args, "verbose", False):
        os.environ["CC_APPROVER_VERBOSE"] = "true"
    
    # Call the hook main function
    from . import hook
    hook.main()

