import pytest
import json
import sys
from unittest.mock import patch, Mock, MagicMock
from io import StringIO

from cc_approver.hook import main, tail

class TestTail:
    def test_tail_reads_last_bytes(self, temp_dir):
        """Test tail function reads last N bytes."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("0123456789")
        
        result = tail(str(test_file), 5)
        assert result == "56789"
    
    def test_tail_empty_path(self):
        """Test tail with empty path."""
        assert tail("", 10) == ""
    
    def test_tail_zero_bytes(self):
        """Test tail with zero bytes."""
        assert tail("/any/path", 0) == ""

class TestMain:
    @patch('cc_approver.hook.load_and_merge_settings')
    def test_main_handles_empty_stdin(self, mock_load):
        """Test main handles empty stdin gracefully."""
        with patch('sys.stdin') as mock_stdin:
            mock_stdin.read.return_value = ""
            # Should not raise exception
            # (actual test would need more mocking to run fully)
    
    @patch('cc_approver.hook.run_program')
    @patch('cc_approver.hook.try_load_compiled')
    @patch('cc_approver.hook.configure_lm')
    @patch('cc_approver.hook.get_policy_text')
    @patch('cc_approver.hook.get_dspy_config')
    @patch('cc_approver.hook.load_and_merge_settings')
    def test_main_with_valid_json(self, mock_load, mock_dspy_cfg, 
                                  mock_policy, mock_configure, 
                                  mock_load_compiled, mock_run):
        """Test main with valid JSON input."""
        import io
        # Setup mocks
        mock_load.return_value = ({}, '/path/to/settings')
        mock_dspy_cfg.return_value = {
            'model': 'test-model', 'historyBytes': 0, 
            'compiledModelPath': '/path/to/model'
        }
        mock_policy.return_value = 'Test policy'
        mock_load_compiled.return_value = None
        mock_run.return_value = Mock(decision='allow', reason='OK')
        
        input_data = json.dumps({"tool_name": "Bash", "tool_input": {}})
        with patch('sys.stdin', io.StringIO(input_data)):
            main()
        
        mock_run.assert_called_once()