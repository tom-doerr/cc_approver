import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import dspy

from cc_approver.optimizer import (
    read_jsonl, acc_metric, gepa_metric,
    optimize_from_files
)

class TestReadJsonl:
    def test_read_jsonl_success(self, temp_dir):
        """Test reading JSONL file."""
        # Create test JSONL file
        jsonl_file = temp_dir / "train.jsonl"
        data = [
            {"tool_name": "Bash", "tool_input_json": '{"command": "ls"}', "label": "allow"},
            {"tool": "Edit", "tool_input": {"path": "test.py"}, "label": "deny"}
        ]
        with open(jsonl_file, 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        
        result = read_jsonl(jsonl_file, "Test policy", 100)
        
        assert len(result) == 2
        # Check first example
        assert result[0].tool == "Bash"
        assert result[0].decision == "allow"
        # Check second example
        assert result[1].tool == "Edit"
        assert result[1].decision == "deny"

class TestAccMetric:
    def test_acc_metric_correct(self):
        """Test accuracy metric with correct prediction."""
        ex = dspy.Example(decision="allow")
        pred = Mock(decision="allow")
        assert acc_metric(ex, pred) == 1.0
    
    def test_acc_metric_incorrect(self):
        """Test accuracy metric with incorrect prediction."""
        ex = dspy.Example(decision="allow")
        pred = Mock(decision="deny")
        assert acc_metric(ex, pred) == 0.0

class TestGepaMetric:
    def test_gepa_metric_correct(self):
        """Test GEPA metric with correct prediction."""
        gold = dspy.Example(decision="allow")
        pred = Mock(decision="allow")
        result = gepa_metric(gold, pred)
        assert result['score'] == 1.0
    
    def test_gepa_metric_incorrect(self):
        """Test GEPA metric with incorrect prediction."""
        gold = dspy.Example(decision="allow")
        pred = Mock(decision="deny")
        result = gepa_metric(gold, pred)
        assert result['score'] == 0.0

class TestNormalize:
    def test_normalize_with_tool_name(self):
        """Test _normalize with tool_name field."""
        from cc_approver.optimizer import _normalize
        
        obj = {"tool_name": "Bash", "tool_input_json": '{"cmd": "ls"}', "label": "allow"}
        result = _normalize(obj, "Test policy", 100)
        
        assert result["tool"] == "Bash"
        assert result["tool_input_json"] == '{"cmd": "ls"}'
        assert result["label"] == "allow"
        assert result["policy"] == "Test policy"
