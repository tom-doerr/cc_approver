import os
import sys
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
import dspy

# Preserve PYTHONPATH so subprocesses find editable installs
# even when tests override HOME (which breaks .pth discovery).
# Resolve actual package source paths from loaded modules.
_extra_paths = set()
for _mod in [dspy]:
    _src = str(Path(_mod.__path__[0]).parent)
    _extra_paths.add(_src)
_real_pythonpath = os.pathsep.join(list(_extra_paths) + sys.path)

@pytest.fixture(autouse=True)
def _preserve_pythonpath():
    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = _real_pythonpath
    yield
    if old is None:
        os.environ.pop("PYTHONPATH", None)
    else:
        os.environ["PYTHONPATH"] = old

@pytest.fixture(autouse=True)
def _reset_dspy():
    """Reset DSPy global LM between tests."""
    yield
    dspy.settings.configure(lm=None)

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