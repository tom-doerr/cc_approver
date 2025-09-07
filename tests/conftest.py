import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
import dspy

@pytest.fixture
def mock_lm():
    """Mock DSPy LM to avoid API calls."""
    lm = Mock()
    lm.request.return_value = ["decision: allow\nreason: Test reason"]
    return lm

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_settings():
    """Sample settings dictionary."""
    return {
        "policy": {
            "approverInstructions": "Deny destructive ops; allow read-only."
        },
        "dspyApprover": {
            "model": "openrouter/google/gemini-2.5-flash-lite",
            "historyBytes": 0,
            "compiledModelPath": "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
        },
        "hooks": {
            "PreToolUse": []
        }
    }

@pytest.fixture
def sample_payload():
    """Sample hook payload."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "transcript_path": "/tmp/transcript.txt"
    }

@pytest.fixture
def mock_dspy_context(mock_lm):
    """Mock DSPy context with configured LM."""
    with dspy.context(lm=mock_lm):
        yield