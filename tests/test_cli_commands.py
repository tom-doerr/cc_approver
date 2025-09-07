"""Test CLI commands for cc_approver."""
import pytest
import json
import subprocess
import tempfile
import os
from pathlib import Path
import sys


class TestCLICommands:
    """Test CLI command functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path):
        """Setup test environment."""
        self.project_dir = tmp_path / "project"
        self.project_claude = self.project_dir / ".claude"
        self.project_claude.mkdir(parents=True)
        
        self.original_project = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.project_dir)
        
        yield
        
        if self.original_project:
            os.environ["CLAUDE_PROJECT_DIR"] = self.original_project
    
    def test_init_command_project_scope(self):
        """Test init command with project scope."""
        cmd = [
            sys.executable, "-m", "cc_approver", "init",
            "--scope", "project",
            "--model", "test-model",
            "--history-bytes", "0",
            "--matcher", "Bash",
            "--timeout", "30",
            "--policy-text", "Test policy"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        
        # Check settings file was created
        settings_file = self.project_claude / "settings.json"
        assert settings_file.exists()
        
        # Verify settings content
        with open(settings_file) as f:
            settings = json.load(f)
        
        assert settings["policy"]["approverInstructions"] == "Test policy"
        assert settings["dspyApprover"]["model"] == "test-model"
        assert settings["dspyApprover"]["historyBytes"] == 0
        assert settings["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
        assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] == 30
    
    def test_init_command_global_scope(self, tmp_path):
        """Test init command with global scope."""
        # Create temp home
        home_dir = tmp_path / "home"
        home_claude = home_dir / ".claude"
        home_claude.mkdir(parents=True)
        
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home_dir)
        
        try:
            cmd = [
                sys.executable, "-m", "cc_approver", "init",
                "--scope", "global",
                "--model", "global-model",
                "--history-bytes", "100",
                "--matcher", "Edit|Write",
                "--timeout", "60",
                "--policy-text", "Global policy"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            assert result.returncode == 0
            
            # Check global settings file
            settings_file = home_claude / "settings.json"
            assert settings_file.exists()
            
            with open(settings_file) as f:
                settings = json.load(f)
            
            assert settings["policy"]["approverInstructions"] == "Global policy"
            assert settings["dspyApprover"]["model"] == "global-model"
            assert settings["dspyApprover"]["historyBytes"] == 100
        finally:
            if original_home:
                os.environ["HOME"] = original_home
    
    def test_hook_command_with_settings(self):
        """Test hook command uses settings correctly."""
        # Create settings
        settings = {
            "policy": {
                "approverInstructions": "Allow read-only"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite",
                "historyBytes": 0
            }
        }
        
        with open(self.project_claude / "settings.json", "w") as f:
            json.dump(settings, f)
        
        # Test hook
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        cmd = [sys.executable, "-m", "cc_approver", "hook"]
        result = subprocess.run(
            cmd,
            input=json.dumps(input_data),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"]["permissionDecision"] in ["allow", "deny", "ask"]
    
    def test_verbose_flag(self):
        """Test --verbose flag works."""
        # Create minimal settings
        settings = {
            "policy": {"approverInstructions": "Test"},
            "dspyApprover": {"model": "openrouter/google/gemini-2.5-flash-lite"}
        }
        
        with open(self.project_claude / "settings.json", "w") as f:
            json.dump(settings, f)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "transcript_path": ""
        }
        
        cmd = [sys.executable, "-m", "cc_approver", "hook", "--verbose"]
        result = subprocess.run(
            cmd,
            input=json.dumps(input_data),
            capture_output=True,
            text=True
        )
        
        # Should have verbose output in stderr
        assert "VERBOSE:" in result.stderr
        assert "Tool=Bash" in result.stderr
    
    def test_main_entry_point(self):
        """Test main entry point without arguments shows help or TUI."""
        cmd = [sys.executable, "-m", "cc_approver", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()


class TestSettingsMerge:
    """Test settings merging functionality."""
    
    @pytest.fixture
    def setup_dirs(self, tmp_path):
        """Setup directory structure."""
        self.home_dir = tmp_path / "home"
        self.project_dir = tmp_path / "project"
        self.home_claude = self.home_dir / ".claude"
        self.project_claude = self.project_dir / ".claude"
        
        self.home_claude.mkdir(parents=True)
        self.project_claude.mkdir(parents=True)
        
        self.original_home = os.environ.get("HOME")
        self.original_project = os.environ.get("CLAUDE_PROJECT_DIR")
        
        os.environ["HOME"] = str(self.home_dir)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.project_dir)
        
        yield
        
        if self.original_home:
            os.environ["HOME"] = self.original_home
        if self.original_project:
            os.environ["CLAUDE_PROJECT_DIR"] = self.original_project
    
    def run_hook_with_input(self, input_data):
        """Helper to run hook with input."""
        cmd = [sys.executable, "-m", "cc_approver", "hook", "--verbose"]
        result = subprocess.run(
            cmd,
            input=json.dumps(input_data),
            capture_output=True,
            text=True
        )
        return result
    
    def test_global_only(self, setup_dirs):
        """Test with only global settings."""
        global_settings = {
            "policy": {
                "approverInstructions": "Global policy only"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        
        with open(self.home_claude / "settings.json", "w") as f:
            json.dump(global_settings, f)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        result = self.run_hook_with_input(input_data)
        assert "GLOBAL RULES: Global policy only" in result.stderr
    
    def test_global_and_local_append(self, setup_dirs):
        """Test global + local with append strategy."""
        global_settings = {
            "policy": {
                "approverInstructions": "Global rules"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        
        local_settings = {
            "policy": {
                "approverInstructions": "Local rules",
                "mergeStrategy": "append"
            }
        }
        
        with open(self.home_claude / "settings.json", "w") as f:
            json.dump(global_settings, f)
        
        with open(self.project_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        result = self.run_hook_with_input(input_data)
        assert "GLOBAL RULES:" in result.stderr
        assert "PROJECT-SPECIFIC RULES:" in result.stderr
    
    def test_local_replace_strategy(self, setup_dirs):
        """Test local replaces global with replace strategy."""
        global_settings = {
            "policy": {
                "approverInstructions": "Global rules to be replaced"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        
        local_settings = {
            "policy": {
                "approverInstructions": "Local rules only",
                "mergeStrategy": "replace"
            }
        }
        
        with open(self.home_claude / "settings.json", "w") as f:
            json.dump(global_settings, f)
        
        with open(self.project_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        result = self.run_hook_with_input(input_data)
        # Should only have local policy
        assert "Local rules only" in result.stderr
        assert "Global rules to be replaced" not in result.stderr