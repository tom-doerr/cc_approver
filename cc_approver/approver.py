from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import dspy
from .constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)

class Approver(dspy.Signature):
    """Decide permission for a tool use.
    Inputs: policy, tool, tool_input_json, history_tail (optional).
    Outputs: decision ∈ {allow, deny, ask}, reason (short)."""
    policy = dspy.InputField()
    tool = dspy.InputField()
    tool_input_json = dspy.InputField()
    history_tail = dspy.InputField(optional=True)
    decision = dspy.OutputField(desc="allow|deny|ask")
    reason = dspy.OutputField()

class ApproverProgram(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.step = dspy.Predict(Approver)
    def forward(self, policy: str, tool: str, tool_input_json: str, 
                history_tail: str = "") -> dspy.Prediction:
        return self.step(policy=policy, tool=tool,
                         tool_input_json=tool_input_json,
                         history_tail=history_tail or "")

def configure_lm(model: str, temperature: float = DEFAULT_TEMPERATURE, 
                 max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
    """Configure global DSPy LM (LiteLLM handles provider keys)."""
    dspy.configure(lm=dspy.LM(model, temperature=temperature, max_tokens=max_tokens))

def try_load_compiled(paths: List[Union[str, Path]]) -> Optional[ApproverProgram]:
    """Load first existing compiled program."""
    prog = ApproverProgram()
    for p in paths:
        q = Path(p).expanduser()
        if q.exists():
            try:
                prog.load(str(q))
                return prog
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to load compiled program from {q}: {e}")
                continue
    return None

def run_program(program: ApproverProgram,
                policy: str, tool: str, tool_input: Dict[str, Any], 
                history_tail: str) -> dspy.Prediction:
    j = json.dumps(tool_input, ensure_ascii=False)[:8000]
    return program(policy=policy or "", tool=tool or "",
                   tool_input_json=j, history_tail=history_tail or "")