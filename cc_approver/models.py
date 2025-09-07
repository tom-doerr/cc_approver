"""Data models for cc_approver package."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from .constants import (
    DEFAULT_MODEL, DEFAULT_HISTORY_BYTES, DEFAULT_COMPILED_PATH,
    DEFAULT_MATCHER, DEFAULT_TIMEOUT, VALID_DECISIONS
)
from .validators import normalize_decision, normalize_label

class DspyConfig(BaseModel):
    """Configuration for DSPy approver."""
    model: str = Field(default=DEFAULT_MODEL, description="Model name")
    historyBytes: int = Field(default=DEFAULT_HISTORY_BYTES, ge=0)
    compiledModelPath: str = Field(default=DEFAULT_COMPILED_PATH)
    promptModel: Optional[str] = None
    evalModel: Optional[str] = None
    reflectionModel: Optional[str] = None

class PolicyConfig(BaseModel):
    """Policy configuration."""
    approverInstructions: str = Field(default="", description="Policy text")

class HookConfig(BaseModel):
    """Hook configuration."""
    name: str = "cc-approver"
    command: str
    matcher: str = Field(default=DEFAULT_MATCHER)
    timeout: int = Field(default=DEFAULT_TIMEOUT, gt=0)

class TrainingExample(BaseModel):
    """Training example for optimizer."""
    tool_name: Optional[str] = Field(None, alias="tool")
    tool_input_json: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    label: str
    transcript_path: Optional[str] = None
    history_tail: Optional[str] = None
    
    @validator('label')
    def normalize_label_field(cls, v: str) -> str:
        return normalize_label(v)

class DecisionResult(BaseModel):
    """Decision result from approver."""
    decision: str
    reason: str
    
    @validator('decision')
    def normalize_decision_field(cls, v: str) -> str:
        return normalize_decision(v)