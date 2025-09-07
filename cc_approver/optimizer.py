from __future__ import annotations
import json, random, sys, logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import dspy
from .approver import ApproverProgram
from .settings import get_policy_text
from .constants import (
    VALID_DECISIONS, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS,
    REFLECTION_TEMPERATURE, REFLECTION_MAX_TOKENS,
    VALIDATION_SPLIT_RATIO, RANDOM_SEED
)

logger = logging.getLogger(__name__)

# ---------- Data ----------

def _normalize_tool_input(obj: dict) -> str:
    """Extract tool input from various formats."""
    if isinstance(obj.get("tool_input_json"), str):
        return obj["tool_input_json"]
    elif isinstance(obj.get("tool_input"), (dict, list)):
        return json.dumps(obj["tool_input"], ensure_ascii=False)
    elif isinstance(obj.get("tool_input_preview"), str):
        return obj["tool_input_preview"]
    return "{}"

def _read_history(obj: dict, history_bytes: int) -> str:
    """Read history from transcript or return existing."""
    hist = obj.get("history_tail") or ""
    if hist or history_bytes <= 0:
        return hist
    path = obj.get("transcript_path")
    if not isinstance(path, str):
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            sz = f.tell()
            f.seek(max(0, sz - history_bytes))
            return f.read().decode("utf-8", "ignore")[-history_bytes:]
    except (FileNotFoundError, IOError):
        return ""

def _normalize(obj: dict, policy: str, history_bytes: int) -> dict:
    tool = obj.get("tool_name") or obj.get("tool") or ""
    ti = _normalize_tool_input(obj)
    hist = _read_history(obj, history_bytes)
    label = (obj.get("label") or obj.get("decision") or "").strip().lower()
    return {"tool": tool, "tool_input_json": ti, "history_tail": hist, "label": label, "policy": policy}

def read_jsonl(path: Path, policy: str, history_bytes: int) -> List[dspy.Example]:
    out: List[dspy.Example] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: 
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"Skipping invalid JSON line: {line[:50]}...")
                continue
            ex = _normalize(obj, policy, history_bytes)
            if ex["label"] not in VALID_DECISIONS: continue
            out.append(dspy.Example(
                policy=ex["policy"], tool=ex["tool"],
                tool_input_json=ex["tool_input_json"], history_tail=ex["history_tail"],
                decision=ex["label"]
            ).with_inputs("policy","tool","tool_input_json","history_tail"))
    return out

# ---------- Metrics ----------

def acc_metric(ex: dspy.Example, pred: dspy.Prediction, **kwargs) -> float:
    y, yhat = (ex.decision or "").strip().lower(), (pred.decision or "").strip().lower()
    return 1.0 if y == yhat and yhat in VALID_DECISIONS else 0.0

def gepa_metric(gold: dspy.Example, pred: dspy.Prediction, **_):
    y, yhat = (gold.decision or "").strip().lower(), (pred.decision or "").strip().lower()
    if y == yhat and yhat in VALID_DECISIONS:
        return {"score": 1.0, "feedback": "Correct. Keep responses concise."}
    return {"score": 0.0, "feedback": f"Expected {y}, got {yhat}. Emphasize policy and safety."}

# ---------- Optimize ----------

def _prepare_datasets(train_path: Path, val_path: Optional[Path], 
                      policy: str, history_bytes: int) -> Tuple[List[dspy.Example], List[dspy.Example]]:
    """Load and prepare training and validation datasets."""
    train = read_jsonl(train_path, policy, history_bytes)
    if not train:
        raise ValueError("No training examples found")
    
    if val_path:
        dev = read_jsonl(val_path, policy, history_bytes)
    else:
        random.Random(RANDOM_SEED).shuffle(train)
        k = max(1, int(VALIDATION_SPLIT_RATIO * len(train)))
        dev, train = train[:k], train[k:]
    
    return train, dev

def optimize_from_files(*, task_model: str, train_path: Path, val_path: Optional[Path],
                        optimizer: str, auto: str, settings: dict,
                        prompt_model: Optional[str], reflection_model: Optional[str],
                        eval_model: Optional[str], history_bytes: int,
                        warm_start: Optional[Path]) -> tuple[ApproverProgram, float]:
    dspy.configure(lm=dspy.LM(task_model, temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS))
    policy = get_policy_text(settings)
    train = read_jsonl(train_path, policy, history_bytes)
    if not train:
        print("No training examples.", file=sys.stderr); sys.exit(1)
    if val_path: dev = read_jsonl(val_path, policy, history_bytes)
    else:
        random.Random(RANDOM_SEED).shuffle(train); k = max(1, int(VALIDATION_SPLIT_RATIO*len(train))); dev, train = train[:k], train[k:]

    prog = ApproverProgram()
    if warm_start and Path(warm_start).exists():
        try:
            prog.load(str(warm_start))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to load warm start model: {e}")

    if optimizer == "mipro":
        try:
            from dspy.teleprompt import MIPROv2
            tp = MIPROv2(metric=acc_metric, auto=auto)
            if prompt_model:
                try: 
                    tp = MIPROv2(metric=acc_metric, auto=auto, prompt_model=dspy.LM(prompt_model))
                except TypeError:
                    logger.debug("MIPROv2 doesn't support prompt_model parameter")
        except ImportError:
            from dspy.optimizers import MIPROv2
            tp = MIPROv2(metric=acc_metric, auto=auto)
        compiled = tp.compile(prog, trainset=train, valset=dev)
    else:
        try:
            from dspy.teleprompt import GEPA
        except ImportError:
            from dspy.optimizers import GEPA
        refl = dspy.LM(reflection_model or task_model, temperature=REFLECTION_TEMPERATURE, max_tokens=REFLECTION_MAX_TOKENS)
        tp = GEPA(metric=gepa_metric, auto=auto, reflection_lm=refl, track_stats=False)
        compiled = tp.compile(prog, trainset=train, valset=dev)

    if eval_model:
        with dspy.context(lm=dspy.LM(eval_model, temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS)):
            correct = sum(1 for ex in dev if (ex.decision.strip().lower() ==
                      (compiled(policy=ex.policy, tool=ex.tool, tool_input_json=ex.tool_input_json, history_tail=ex.history_tail).decision or "").strip().lower()))
    else:
        correct = sum(1 for ex in dev if (ex.decision.strip().lower() ==
                  (compiled(policy=ex.policy, tool=ex.tool, tool_input_json=ex.tool_input_json, history_tail=ex.history_tail).decision or "").strip().lower()))
    acc = correct / max(1, len(dev))
    return compiled, acc