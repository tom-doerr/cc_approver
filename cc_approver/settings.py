from __future__ import annotations
import os, json, logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from .constants import (
    DEFAULT_MATCHER, DEFAULT_TIMEOUT, DEFAULT_MODEL,
    DEFAULT_HISTORY_BYTES, DEFAULT_COMPILED_PATH
)

logger = logging.getLogger(__name__)

def _read_json(p: Path) -> Optional[dict]:
    try:
        with p.open("r", encoding="utf-8") as f: 
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        logger.debug(f"Failed to read JSON file {p}: {e}")
        return None

def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")

def settings_paths(project_dir: Optional[str] = None) -> Tuple[Path, Path, Path]:
    project_dir = project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    proj = Path(project_dir)
    return (proj/".claude"/"settings.local.json",
            proj/".claude"/"settings.json",
            Path.home()/".claude"/"settings.json")

def load_settings_chain(project_dir: Optional[str] = None) -> Tuple[Dict[str, Any], Path]:
    for p in settings_paths(project_dir):
        d = _read_json(p)
        if isinstance(d, dict): return d, p
    _, project_path, _ = settings_paths(project_dir)
    return {}, project_path

def ensure_policy_text(settings: dict, default_text: str = "") -> dict:
    pol = settings.setdefault("policy", {})
    if not isinstance(pol.get("approverInstructions"), str):
        pol["approverInstructions"] = default_text
    return settings

def ensure_dspy_config(settings: dict, *,
                       model: str, history_bytes: int,
                       compiled_path: str, optimizer: str = "mipro",
                       auto: str = "light",
                       prompt_model: str | None = None,
                       eval_model: str | None = None,
                       reflection_model: str | None = None):
    cfg = settings.setdefault("dspyApprover", {})
    cfg.setdefault("model", model)
    cfg.setdefault("historyBytes", history_bytes)
    cfg.setdefault("compiledModelPath", compiled_path)
    cfg.setdefault("optimizer", optimizer)
    cfg.setdefault("auto", auto)
    if prompt_model is not None: cfg["promptModel"] = prompt_model
    if eval_model is not None: cfg["evalModel"] = eval_model
    if reflection_model is not None: cfg["reflectionModel"] = reflection_model
    return settings

def merge_pretooluse_hook(settings: dict, *, command: str,
                          matcher: str = DEFAULT_MATCHER, timeout: int = DEFAULT_TIMEOUT):
    hooks = settings.setdefault("hooks", {})
    lst = hooks.setdefault("PreToolUse", [])
    for h in lst:
        if isinstance(h, dict):
            for spec in h.get("hooks") or []:
                if isinstance(spec, dict) and "cc-approver" in str(spec.get("command","")):
                    h["matcher"] = matcher; spec["command"] = command; spec["timeout"] = timeout
                    return settings
    lst.append({"matcher": matcher, "hooks":[{"type":"command","command":command,"timeout":timeout}]})
    return settings

def get_policy_text(settings: dict) -> str:
    pol = settings.get("policy") or {}
    t = pol.get("approverInstructions")
    return t if isinstance(t, str) else ""

def _resolve(s: str, project_dir: Optional[str]) -> str:
    root = project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return s.replace("$CLAUDE_PROJECT_DIR", root)

def get_dspy_config(settings: dict, project_dir: Optional[str] = None) -> dict:
    cfg = settings.get("dspyApprover") or {}
    model = cfg.get("model") or DEFAULT_MODEL
    hbytes = int(cfg.get("historyBytes") or DEFAULT_HISTORY_BYTES)
    cmp_raw = cfg.get("compiledModelPath") or DEFAULT_COMPILED_PATH
    compiled = _resolve(cmp_raw, project_dir)
    return {
        "model": model,
        "historyBytes": hbytes,
        "compiledModelPath": compiled,
        "promptModel": cfg.get("promptModel"),
        "evalModel": cfg.get("evalModel"),
        "reflectionModel": cfg.get("reflectionModel"),
    }

def write_settings(settings: dict, path: Path) -> None:
    _write_json(path, settings)