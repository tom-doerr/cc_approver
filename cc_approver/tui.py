from __future__ import annotations
import os
from pathlib import Path
import questionary as q

GEMINI_CHOICES = [
    "openrouter/google/gemini-2.5-flash-lite",
    "openrouter/google/gemini-2.5-flash",
    "openrouter/google/gemini-2.5-pro",
]

def detect_scope_default() -> str:
    here = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return "project" if (Path(here)/".claude").exists() else "global"

def main_menu():
    return q.select("What do you want to do?", choices=["Init", "Optimize", "Exit"]).ask()

def init_menu():
    scope = q.select("Scope?", choices=["project","global"], default=detect_scope_default()).ask()
    model = q.select("Task model?", choices=GEMINI_CHOICES, default=GEMINI_CHOICES[0]).ask()
    history = q.text("History bytes (0 = disabled):", default="0").ask()
    standalone = q.confirm("Copy physical hook file into .claude/hooks/?", default=True).ask()
    matcher = q.text("Matcher (regex of tools):", default="Bash|Edit|Write").ask()
    timeout = q.text("Hook timeout (seconds):", default="10").ask()
    policy = q.text("Policy text (approverInstructions):",
                    default="Deny destructive ops; ask on ambiguous; allow read-only or tests.").ask()
    return {
        "scope": scope,
        "model": model,
        "history_bytes": int(history or "0"),
        "standalone": bool(standalone),
        "matcher": matcher or "Bash|Edit|Write",
        "timeout": int(timeout or "10"),
        "policy_text": policy or "",
    }

def optimize_menu():
    scope = q.select("Scope?", choices=["project","global"], default=detect_scope_default()).ask()
    optimizer = q.select("Optimizer?", choices=["mipro","gepa"], default="mipro").ask()
    auto = q.select("Auto budget?", choices=["light","medium","heavy"], default="light").ask()
    task_model = q.select("Task model?", choices=GEMINI_CHOICES, default=GEMINI_CHOICES[0]).ask()
    prompt_model = q.select("Prompt/teacher model (MIPROv2)?", choices=["(same as task)"] + GEMINI_CHOICES,
                            default="(same as task)").ask()
    reflection_model = q.select("Reflection model (GEPA)?", choices=["(same as task)"] + GEMINI_CHOICES,
                                default="(same as task)").ask()
    eval_model = q.select("Eval model?", choices=["(same as task)"] + GEMINI_CHOICES,
                          default="(same as task)").ask()
    train = q.text("Training JSONL path:").ask()
    val = q.text("Validation JSONL path (optional):").ask()
    history = q.text("History bytes for dataset (0 = disabled):", default="0").ask()
    return {
        "scope": scope, "optimizer": optimizer, "auto": auto,
        "task_model": task_model,
        "prompt_model": None if prompt_model == "(same as task)" else prompt_model,
        "reflection_model": None if reflection_model == "(same as task)" else reflection_model,
        "eval_model": None if eval_model == "(same as task)" else eval_model,
        "train": train, "val": (val or None),
        "history_bytes": int(history or "0"),
    }