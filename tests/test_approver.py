import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import dspy

from cc_approver.approver import (
    Approver, ApproverProgram, configure_lm, 
    try_load_compiled, run_program
)

class TestApprover:
    def test_approver_signature_fields(self):
        """Test Approver signature is a proper DSPy Signature."""
        # Check that Approver is a DSPy Signature class
        assert issubclass(Approver, dspy.Signature)
        # The signature should be usable with Predict
        predictor = dspy.Predict(Approver)
        assert predictor is not None

class TestApproverProgram:
    def test_program_initialization(self):
        """Test ApproverProgram initialization."""
        program = ApproverProgram()
        assert hasattr(program, 'step')
        assert isinstance(program.step, dspy.Predict)
    
    @patch('cc_approver.approver.dspy.Predict')
    def test_program_forward(self, mock_predict):
        """Test ApproverProgram forward method."""
        mock_step = Mock()
        mock_step.return_value = Mock(decision="allow", reason="Test")
        mock_predict.return_value = mock_step
        
        program = ApproverProgram()
        result = program.forward(
            policy="Test policy", 
            tool="Bash",
            tool_input_json='{"command": "ls"}',
            history_tail="history"
        )
        
        mock_step.assert_called_once()
        assert result.decision == "allow"

class TestConfigureLM:
    @patch('cc_approver.approver.dspy.configure')
    @patch('cc_approver.approver.dspy.LM')
    def test_configure_lm_default(self, mock_lm, mock_configure):
        """Test configure_lm with default parameters."""
        configure_lm("test-model")
        mock_lm.assert_called_once_with("test-model", temperature=0.0, max_tokens=256)
        mock_configure.assert_called_once()

class TestTryLoadCompiled:
    def test_load_compiled_success(self, temp_dir):
        """Test successful loading of compiled program."""
        compiled_path = temp_dir / "compiled.json"
        compiled_path.write_text("{}")
        
        with patch.object(ApproverProgram, 'load') as mock_load:
            result = try_load_compiled([str(compiled_path)])
            assert result is not None
            mock_load.assert_called_once()
    
    def test_load_compiled_not_found(self):
        """Test loading when no compiled file exists."""
        result = try_load_compiled(["/nonexistent/path.json"])
        assert result is None

class TestRunProgram:
    def test_run_program_with_dict_input(self):
        """Test run_program with dictionary tool input."""
        mock_program = Mock()
        mock_program.return_value = Mock(decision="allow", reason="OK")
        
        result = run_program(
            mock_program,
            "test policy",
            "Bash",
            {"command": "ls"},
            "history"
        )
        
        mock_program.assert_called_once()
        assert result.decision == "allow"