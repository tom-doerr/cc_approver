import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock
import os

from cc_approver.settings import (
    settings_paths, load_settings_chain, ensure_policy_text,
    ensure_dspy_config, merge_pretooluse_hook, get_policy_text,
    get_dspy_config, write_settings
)

class TestSettingsPaths:
    def test_settings_paths_default(self):
        """Test settings_paths with default project directory."""
        paths = settings_paths()
        assert len(paths) == 3
        assert ".claude/settings.local.json" in str(paths[0])
        assert ".claude/settings.json" in str(paths[1])
        assert str(Path.home()) in str(paths[2])
    
    def test_settings_paths_custom_dir(self):
        """Test settings_paths with custom project directory."""
        paths = settings_paths("/custom/dir")
        assert "/custom/dir/.claude/settings.local.json" == str(paths[0])
        assert "/custom/dir/.claude/settings.json" == str(paths[1])

class TestEnsurePolicyText:
    def test_ensure_policy_text_empty(self):
        """Test ensure_policy_text with empty settings."""
        settings = {}
        result = ensure_policy_text(settings, "Default policy")
        assert result["policy"]["approverInstructions"] == "Default policy"
    
    def test_ensure_policy_text_existing(self):
        """Test ensure_policy_text preserves existing text."""
        settings = {"policy": {"approverInstructions": "Existing"}}
        result = ensure_policy_text(settings)
        assert result["policy"]["approverInstructions"] == "Existing"

class TestGetPolicyText:
    def test_get_policy_text_exists(self):
        """Test get_policy_text with existing policy."""
        settings = {"policy": {"approverInstructions": "Test policy"}}
        assert get_policy_text(settings) == "Test policy"
    
    def test_get_policy_text_missing(self):
        """Test get_policy_text with missing policy."""
        assert get_policy_text({}) == ""

class TestMergePreToolUseHook:
    def test_merge_hook_new(self):
        """Test adding new hook to empty settings."""
        settings = {}
        result = merge_pretooluse_hook(settings, command="test-cmd")
        assert len(result["hooks"]["PreToolUse"]) == 1
        assert result["hooks"]["PreToolUse"][0]["matcher"] == "Bash|Edit|Write"

class TestLoadSettingsChain:
    @patch('cc_approver.settings._read_json')
    def test_load_settings_chain_with_files(self, mock_read):
        """Test load_settings_chain with existing files."""
        mock_read.side_effect = [
            {"key1": "val1"},  # settings.local.json - this will be returned
            {"key2": "val2"},  # settings.json
            {"key3": "val3"}   # global settings
        ]
        settings, path = load_settings_chain("/test/dir")
        assert settings == {"key1": "val1"}
        assert mock_read.call_count == 1  # Stops after first found

class TestEnsureDspyConfig:
    def test_ensure_dspy_config_empty(self):
        """Test ensure_dspy_config with empty settings."""
        settings = {}
        result = ensure_dspy_config(settings, model="test-model", 
                                   history_bytes=100, compiled_path="/path/to/model")
        assert "dspyApprover" in result
        assert result["dspyApprover"]["model"] == "test-model"
        assert result["dspyApprover"]["historyBytes"] == 100

class TestWriteSettings:
    @patch('cc_approver.settings._write_json')
    def test_write_settings(self, mock_write):
        """Test write_settings function."""
        from pathlib import Path
        settings = {"key": "value"}
        path = Path("/test/path.json")
        write_settings(settings, path)
        mock_write.assert_called_once_with(path, settings)