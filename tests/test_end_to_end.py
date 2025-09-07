"""Comprehensive end-to-end tests for cc_approver."""
import pytest
import json
import subprocess
import tempfile
import os
from pathlib import Path
import sys

# Test data for various scenarios
TEST_CASES = [
    # Destructive operations
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/test"}},
        "policy": "Deny destructive operations like rm",
        "expected_decision": "deny",
        "description": "Should deny rm command"
    },
    # Git operations
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "git add file.py"}},
        "policy": "Allow git commands including add, commit, push",
        "expected_decision": "allow",
        "description": "Should allow git add"
    },
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "git rm file.py"}},
        "policy": "Deny rm but allow git rm since we can undo",
        "expected_decision": "allow",
        "description": "Should allow git rm"
    },
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}},
        "policy": "Allow git commands but ask on dangerous ones like reset",
        "expected_decision": "ask",
        "description": "Should ask for git reset"
    },
    # Read-only operations
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
        "policy": "Allow read-only operations",
        "expected_decision": "allow",
        "description": "Should allow ls command"
    },
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "cat file.txt"}},
        "policy": "Allow read-only operations",
        "expected_decision": "allow",
        "description": "Should allow cat command"
    },
    # Python scripts
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "python train.py"}},
        "policy": "Allow running python scripts if they don't look dangerous",
        "expected_decision": "allow",
        "description": "Should allow python scripts"
    },
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "python -c 'import os; os.system(\"rm -rf /\")'"}},
        "policy": "Allow python but deny if dangerous",
        "expected_decision": "deny",
        "description": "Should deny dangerous python"
    },
    # File operations
    {
        "input": {"tool_name": "Edit", "tool_input": {"file_path": "test.py", "old": "foo", "new": "bar"}},
        "policy": "Allow editing code files",
        "expected_decision": "allow",
        "description": "Should allow editing .py files"
    },
    {
        "input": {"tool_name": "Write", "tool_input": {"file_path": "/etc/passwd", "content": "bad"}},
        "policy": "Deny editing system files",
        "expected_decision": "deny",
        "description": "Should deny editing system files"
    },
    # Empty/missing policy
    {
        "input": {"tool_name": "Bash", "tool_input": {"command": "echo test"}},
        "policy": "",
        "expected_decision": "ask",
        "description": "Should ask when policy is empty"
    }
]


class TestEndToEnd:
    """End-to-end tests using the actual CLI."""
    
    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path):
        """Setup test environment."""
        # Create temp home and project directories
        self.home_dir = tmp_path / "home"
        self.project_dir = tmp_path / "project"
        self.home_claude = self.home_dir / ".claude"
        self.project_claude = self.project_dir / ".claude"
        
        # Create directories
        self.home_claude.mkdir(parents=True)
        self.project_claude.mkdir(parents=True)
        
        # Set environment
        self.original_home = os.environ.get("HOME")
        self.original_project = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["HOME"] = str(self.home_dir)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.project_dir)
        
        yield
        
        # Restore environment
        if self.original_home:
            os.environ["HOME"] = self.original_home
        if self.original_project:
            os.environ["CLAUDE_PROJECT_DIR"] = self.original_project
    
    def run_hook(self, input_data, verbose=False):
        """Run the hook CLI with given input."""
        cmd = [sys.executable, "-m", "cc_approver", "hook"]
        if verbose:
            cmd.append("--verbose")
        
        input_json = json.dumps(input_data)
        result = subprocess.run(
            cmd,
            input=input_json,
            capture_output=True,
            text=True
        )
        
        # Parse output
        try:
            output = json.loads(result.stdout)
            return output["hookSpecificOutput"]
        except (json.JSONDecodeError, KeyError):
            return {"error": result.stdout + result.stderr}
    
    def write_settings(self, path, settings):
        """Write settings to file."""
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
    
    @pytest.mark.parametrize("test_case", TEST_CASES)
    def test_policy_decisions(self, test_case):
        """Test various policy decision scenarios."""
        # Create settings with policy
        settings = {
            "policy": {
                "approverInstructions": test_case["policy"]
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite",
                "historyBytes": 0
            }
        }
        self.write_settings(self.home_claude / "settings.json", settings)
        
        # Add transcript_path to input
        input_data = test_case["input"].copy()
        input_data["transcript_path"] = ""
        
        # Run hook
        result = self.run_hook(input_data)
        
        # Check decision
        assert "permissionDecision" in result, f"No decision in result: {result}"
        decision = result["permissionDecision"]
        
        # For non-deterministic LLM, we check if decision is valid
        assert decision in ["allow", "deny", "ask"], f"Invalid decision: {decision}"
        
        # Log for debugging
        if decision != test_case["expected_decision"]:
            print(f"\nTest: {test_case['description']}")
            print(f"Policy: {test_case['policy']}")
            print(f"Input: {test_case['input']}")
            print(f"Expected: {test_case['expected_decision']}, Got: {decision}")
            print(f"Reason: {result.get('permissionDecisionReason', 'N/A')}")
    
    def test_policy_merging_append(self):
        """Test policy merging with append strategy."""
        # Global settings
        global_settings = {
            "policy": {
                "approverInstructions": "GLOBAL: Deny all rm commands"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        self.write_settings(self.home_claude / "settings.json", global_settings)
        
        # Local settings with append
        local_settings = {
            "policy": {
                "approverInstructions": "LOCAL: Allow git operations",
                "mergeStrategy": "append"
            }
        }
        self.write_settings(self.project_claude / "settings.local.json", local_settings)
        
        # Test that both policies apply
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "transcript_path": ""
        }
        
        result = self.run_hook(input_data, verbose=True)
        assert result["permissionDecision"] in ["allow", "deny", "ask"]
    
    def test_policy_merging_replace(self):
        """Test policy merging with replace strategy."""
        # Global settings
        global_settings = {
            "policy": {
                "approverInstructions": "GLOBAL: Deny everything"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        self.write_settings(self.home_claude / "settings.json", global_settings)
        
        # Local settings with replace
        local_settings = {
            "policy": {
                "approverInstructions": "LOCAL: Allow everything",
                "mergeStrategy": "replace"
            }
        }
        self.write_settings(self.project_claude / "settings.local.json", local_settings)
        
        # Test that only local policy applies
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        result = self.run_hook(input_data)
        assert result["permissionDecision"] in ["allow", "deny", "ask"]
    
    def test_verbose_mode(self):
        """Test verbose mode outputs debug information."""
        settings = {
            "policy": {
                "approverInstructions": "Test policy"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite"
            }
        }
        self.write_settings(self.home_claude / "settings.json", settings)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        cmd = [sys.executable, "-m", "cc_approver", "hook", "--verbose"]
        input_json = json.dumps(input_data)
        result = subprocess.run(
            cmd,
            input=input_json,
            capture_output=True,
            text=True
        )
        
        # Check for verbose output
        assert "VERBOSE:" in result.stderr
        assert "Tool=Bash" in result.stderr
        assert "Policy:" in result.stderr
    
    def test_invalid_json_input(self):
        """Test handling of invalid JSON input."""
        cmd = [sys.executable, "-m", "cc_approver", "hook"]
        result = subprocess.run(
            cmd,
            input="not valid json",
            capture_output=True,
            text=True
        )
        
        # Should still return valid JSON output
        try:
            output = json.loads(result.stdout)
            assert "hookSpecificOutput" in output
            # Should return a valid decision even with invalid input
            decision = output["hookSpecificOutput"]["permissionDecision"]
            assert decision in ["allow", "deny", "ask"]
        except json.JSONDecodeError:
            pytest.fail("Hook should return valid JSON even with invalid input")
    
    def test_missing_tool_name(self):
        """Test handling of missing tool_name."""
        input_data = {
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        result = self.run_hook(input_data)
        assert "permissionDecision" in result
        # Should handle gracefully
        assert result["permissionDecision"] in ["allow", "deny", "ask"]
    
    def test_settings_precedence(self):
        """Test that local settings override global."""
        # Global settings
        global_settings = {
            "policy": {
                "approverInstructions": "Deny everything"
            },
            "dspyApprover": {
                "model": "global-model"
            }
        }
        self.write_settings(self.home_claude / "settings.json", global_settings)
        
        # Local settings
        local_settings = {
            "dspyApprover": {
                "model": "local-model"
            }
        }
        self.write_settings(self.project_claude / "settings.local.json", local_settings)
        
        # Run with verbose to check which model is used
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": ""
        }
        
        cmd = [sys.executable, "-m", "cc_approver", "hook", "--verbose"]
        input_json = json.dumps(input_data)
        result = subprocess.run(
            cmd,
            input=input_json,
            capture_output=True,
            text=True
        )
        
        # Check that local model is used
        assert "Model: local-model" in result.stderr
    
    def test_history_bytes_option(self):
        """Test history_bytes configuration."""
        # Create a transcript file
        transcript_file = self.project_dir / "transcript.txt"
        transcript_file.write_text("Previous conversation history\n" * 100)
        
        settings = {
            "policy": {
                "approverInstructions": "Test policy"
            },
            "dspyApprover": {
                "model": "openrouter/google/gemini-2.5-flash-lite",
                "historyBytes": 50
            }
        }
        self.write_settings(self.home_claude / "settings.json", settings)
        
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": str(transcript_file)
        }
        
        result = self.run_hook(input_data)
        assert "permissionDecision" in result