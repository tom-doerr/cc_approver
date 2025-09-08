"""Test that init command preserves existing hooks in settings."""
import pytest
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch
import subprocess

from cc_approver.cli import main, _run_init
from cc_approver.settings import merge_pretooluse_hook, write_settings, _read_json


class TestHookPreservation:
    """Test that existing hooks are preserved when initializing cc-approver."""
    
    @pytest.fixture
    def test_env(self, tmp_path):
        """Setup test environment."""
        project_dir = tmp_path / "project"
        home_dir = tmp_path / "home"
        project_dir.mkdir()
        home_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (home_dir / ".claude").mkdir()
        
        original_env = {
            "HOME": os.environ.get("HOME"),
            "CLAUDE_PROJECT_DIR": os.environ.get("CLAUDE_PROJECT_DIR")
        }
        
        os.environ["HOME"] = str(home_dir)
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_dir)
        
        yield {
            "project_dir": project_dir,
            "home_dir": home_dir,
            "original_env": original_env
        }
        
        # Restore environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    def test_preserves_other_pretooluse_hooks(self, test_env):
        """Test that other PreToolUse hooks are preserved."""
        project_dir = test_env["project_dir"]
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Create existing settings with multiple hooks
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash.*",
                        "hooks": [
                            {"type": "command", "command": "echo 'Running bash'", "timeout": 10}
                        ]
                    },
                    {
                        "matcher": "Edit.*",
                        "hooks": [
                            {"type": "command", "command": "validate-edit", "timeout": 5}
                        ]
                    }
                ]
            },
            "otherSetting": "should remain"
        }
        
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f)
        
        # Run init
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'test-model',
            '--history-bytes', '0',
            '--matcher', 'Write',
            '--timeout', '30',
            '--policy-text', 'Test policy'
        ]):
            main()
        
        # Load updated settings
        with open(settings_file) as f:
            updated_settings = json.load(f)
        
        # Check that all hooks are preserved
        hooks = updated_settings["hooks"]["PreToolUse"]
        
        # Should have 3 hooks now (2 original + 1 cc-approver)
        assert len(hooks) == 3
        
        # Check original hooks are unchanged
        assert any(h["matcher"] == "Bash.*" and 
                  "echo 'Running bash'" in str(h["hooks"]) 
                  for h in hooks)
        assert any(h["matcher"] == "Edit.*" and 
                  "validate-edit" in str(h["hooks"]) 
                  for h in hooks)
        
        # Check cc-approver hook was added
        assert any(h["matcher"] == "Write" and 
                  "cc-approver" in str(h["hooks"]) 
                  for h in hooks)
        
        # Check other settings preserved
        assert updated_settings["otherSetting"] == "should remain"
    
    def test_updates_existing_ccapprover_hook(self, test_env):
        """Test that existing cc-approver hook is updated, not duplicated."""
        project_dir = test_env["project_dir"]
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Create settings with existing cc-approver hook
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "OldPattern",
                        "hooks": [
                            {"type": "command", "command": "cc-approver hook", "timeout": 10}
                        ]
                    },
                    {
                        "matcher": "Bash.*",
                        "hooks": [
                            {"type": "command", "command": "other-hook", "timeout": 5}
                        ]
                    }
                ]
            }
        }
        
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f)
        
        # Run init with new settings
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'new-model',
            '--history-bytes', '100',
            '--matcher', 'NewPattern',
            '--timeout', '60',
            '--policy-text', 'New policy'
        ]):
            main()
        
        # Load updated settings
        with open(settings_file) as f:
            updated_settings = json.load(f)
        
        hooks = updated_settings["hooks"]["PreToolUse"]
        
        # Should still have 2 hooks (updated cc-approver + other)
        assert len(hooks) == 2
        
        # Check cc-approver hook was updated
        cc_hook = next((h for h in hooks if "cc-approver" in str(h["hooks"])), None)
        assert cc_hook is not None
        assert cc_hook["matcher"] == "NewPattern"
        assert cc_hook["hooks"][0]["timeout"] == 60
        
        # Check other hook preserved
        assert any(h["matcher"] == "Bash.*" and "other-hook" in str(h["hooks"]) for h in hooks)
    
    def test_preserves_other_hook_types(self, test_env):
        """Test that other hook types (PostToolUse, etc.) are preserved."""
        project_dir = test_env["project_dir"]
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Create settings with various hook types
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash.*",
                        "hooks": [{"type": "command", "command": "pre-bash", "timeout": 5}]
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [{"type": "command", "command": "log-tool-use", "timeout": 10}]
                    }
                ],
                "PrePrompt": [
                    {
                        "hooks": [{"type": "command", "command": "validate-prompt", "timeout": 15}]
                    }
                ]
            }
        }
        
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f)
        
        # Run init
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'test-model',
            '--history-bytes', '0',
            '--matcher', 'Edit',
            '--timeout', '30',
            '--policy-text', 'Policy'
        ]):
            main()
        
        # Load updated settings
        with open(settings_file) as f:
            updated_settings = json.load(f)
        
        # Check all hook types preserved
        assert "PostToolUse" in updated_settings["hooks"]
        assert "PrePrompt" in updated_settings["hooks"]
        
        # Check PostToolUse unchanged
        post_hooks = updated_settings["hooks"]["PostToolUse"]
        assert len(post_hooks) == 1
        assert "log-tool-use" in str(post_hooks[0]["hooks"])
        
        # Check PrePrompt unchanged
        pre_prompt = updated_settings["hooks"]["PrePrompt"]
        assert len(pre_prompt) == 1
        assert "validate-prompt" in str(pre_prompt[0]["hooks"])
        
        # Check PreToolUse has both original and cc-approver
        pre_tool = updated_settings["hooks"]["PreToolUse"]
        assert len(pre_tool) == 2
    
    def test_handles_empty_hooks_section(self, test_env):
        """Test that it works when hooks section doesn't exist."""
        project_dir = test_env["project_dir"]
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Create settings without hooks
        existing_settings = {
            "someSetting": "value",
            "anotherSetting": {"nested": "data"}
        }
        
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f)
        
        # Run init
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'test-model',
            '--history-bytes', '0',
            '--matcher', 'Bash',
            '--timeout', '30',
            '--policy-text', 'Policy'
        ]):
            main()
        
        # Load updated settings
        with open(settings_file) as f:
            updated_settings = json.load(f)
        
        # Check original settings preserved
        assert updated_settings["someSetting"] == "value"
        assert updated_settings["anotherSetting"]["nested"] == "data"
        
        # Check cc-approver hook added
        assert "hooks" in updated_settings
        assert "PreToolUse" in updated_settings["hooks"]
        assert len(updated_settings["hooks"]["PreToolUse"]) == 1
        assert "cc-approver" in str(updated_settings["hooks"]["PreToolUse"][0]["hooks"])
    
    def test_multiple_init_calls_dont_duplicate(self, test_env):
        """Test that running init multiple times doesn't duplicate hooks."""
        project_dir = test_env["project_dir"]
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Run init first time
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'model1',
            '--history-bytes', '0',
            '--matcher', 'Pattern1',
            '--timeout', '10',
            '--policy-text', 'Policy 1'
        ]):
            main()
        
        # Run init second time with different settings
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'model2',
            '--history-bytes', '100',
            '--matcher', 'Pattern2',
            '--timeout', '20',
            '--policy-text', 'Policy 2'
        ]):
            main()
        
        # Run init third time
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'project',
            '--model', 'model3',
            '--history-bytes', '200',
            '--matcher', 'Pattern3',
            '--timeout', '30',
            '--policy-text', 'Policy 3'
        ]):
            main()
        
        # Load settings
        with open(settings_file) as f:
            settings = json.load(f)
        
        hooks = settings["hooks"]["PreToolUse"]
        
        # Should only have 1 cc-approver hook (updated, not duplicated)
        assert len(hooks) == 1
        
        cc_hooks = [h for h in hooks if "cc-approver" in str(h["hooks"])]
        assert len(cc_hooks) == 1
        
        # Should have latest settings
        assert cc_hooks[0]["matcher"] == "Pattern3"
        assert cc_hooks[0]["hooks"][0]["timeout"] == 30
        assert settings["policy"]["approverInstructions"] == "Policy 3"
        assert settings["dspyApprover"]["model"] == "model3"
    
    def test_global_scope_preserves_hooks(self, test_env):
        """Test that global scope also preserves existing hooks."""
        home_dir = test_env["home_dir"]
        settings_file = home_dir / ".claude" / "settings.json"
        
        # Create existing global settings with hooks
        existing_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": "global-validator", "timeout": 15}
                        ]
                    }
                ]
            },
            "globalConfig": "preserved"
        }
        
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f)
        
        # Run init with global scope
        with patch('sys.argv', [
            'cc-approver', 'init', '--scope', 'global',
            '--model', 'global-model',
            '--history-bytes', '0',
            '--matcher', 'Bash|Edit',
            '--timeout', '45',
            '--policy-text', 'Global policy'
        ]):
            main()
        
        # Load updated settings
        with open(settings_file) as f:
            updated_settings = json.load(f)
        
        # Check both hooks present
        hooks = updated_settings["hooks"]["PreToolUse"]
        assert len(hooks) == 2
        
        # Check original hook preserved
        assert any("global-validator" in str(h["hooks"]) for h in hooks)
        
        # Check cc-approver hook added
        assert any("cc-approver" in str(h["hooks"]) for h in hooks)
        
        # Check other settings preserved
        assert updated_settings["globalConfig"] == "preserved"


class TestMergePreToolUseHook:
    """Unit tests for merge_pretooluse_hook function."""
    
    def test_merge_adds_new_hook(self):
        """Test adding a new hook when none exists."""
        settings = {}
        result = merge_pretooluse_hook(
            settings, 
            command="cc-approver hook",
            matcher="Test.*",
            timeout=30
        )
        
        assert "hooks" in result
        assert "PreToolUse" in result["hooks"]
        assert len(result["hooks"]["PreToolUse"]) == 1
        
        hook = result["hooks"]["PreToolUse"][0]
        assert hook["matcher"] == "Test.*"
        assert hook["hooks"][0]["command"] == "cc-approver hook"
        assert hook["hooks"][0]["timeout"] == 30
    
    def test_merge_updates_existing_ccapprover(self):
        """Test updating existing cc-approver hook."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "OldPattern",
                        "hooks": [
                            {"type": "command", "command": "cc-approver old", "timeout": 10}
                        ]
                    }
                ]
            }
        }
        
        result = merge_pretooluse_hook(
            settings,
            command="cc-approver new",
            matcher="NewPattern",
            timeout=60
        )
        
        hooks = result["hooks"]["PreToolUse"]
        assert len(hooks) == 1
        assert hooks[0]["matcher"] == "NewPattern"
        assert hooks[0]["hooks"][0]["command"] == "cc-approver new"
        assert hooks[0]["hooks"][0]["timeout"] == 60
    
    def test_merge_preserves_other_hooks(self):
        """Test that other hooks are preserved."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "A", "hooks": [{"command": "hook-a"}]},
                    {"matcher": "B", "hooks": [{"command": "hook-b"}]},
                    {"matcher": "C", "hooks": [{"command": "hook-c"}]}
                ]
            }
        }
        
        result = merge_pretooluse_hook(
            settings,
            command="cc-approver hook",
            matcher="D",
            timeout=30
        )
        
        hooks = result["hooks"]["PreToolUse"]
        assert len(hooks) == 4
        
        # Check all original hooks preserved
        assert any(h["matcher"] == "A" for h in hooks)
        assert any(h["matcher"] == "B" for h in hooks)
        assert any(h["matcher"] == "C" for h in hooks)
        
        # Check new hook added
        assert any(h["matcher"] == "D" and "cc-approver" in str(h["hooks"]) for h in hooks)
    
    def test_merge_handles_malformed_hooks(self):
        """Test handling of malformed hook structures."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    None,  # Invalid entry
                    {"matcher": "Valid", "hooks": [{"command": "valid-hook"}]},
                    {},  # Empty dict
                    {"matcher": "NoHooks"},  # Missing hooks array
                ]
            }
        }
        
        result = merge_pretooluse_hook(
            settings,
            command="cc-approver hook",
            matcher="New",
            timeout=30
        )
        
        hooks = result["hooks"]["PreToolUse"]
        
        # Should preserve all entries and add new one
        assert len(hooks) == 5
        
        # Check new hook was added
        assert any(
            isinstance(h, dict) and 
            h.get("matcher") == "New" and 
            "cc-approver" in str(h.get("hooks", []))
            for h in hooks
        )


class TestSettingsIntegration:
    """Integration tests for settings preservation."""
    
    @pytest.fixture
    def complex_settings(self):
        """Create complex settings structure."""
        return {
            "version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash.*",
                        "hooks": [
                            {"type": "command", "command": "security-check", "timeout": 10},
                            {"type": "webhook", "url": "https://example.com/hook"}
                        ]
                    },
                    {
                        "matcher": "Write.*",
                        "hooks": [
                            {"type": "command", "command": "backup-file", "timeout": 5}
                        ]
                    }
                ],
                "PostToolUse": [
                    {"hooks": [{"type": "command", "command": "log-action"}]}
                ],
                "PrePrompt": [
                    {"hooks": [{"type": "command", "command": "rate-limit"}]}
                ]
            },
            "policy": {
                "existingRules": "Don't modify files in /etc"
            },
            "customSettings": {
                "theme": "dark",
                "editor": "vim"
            }
        }
    
    def test_init_preserves_complex_structure(self, tmp_path, complex_settings):
        """Test that init preserves complex settings structure."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_dir)
        
        settings_file = project_dir / ".claude" / "settings.json"
        
        # Write complex settings
        with open(settings_file, 'w') as f:
            json.dump(complex_settings, f, indent=2)
        
        # Run init
        _run_init(
            scope="project",
            model="test-model",
            history_bytes=100,
            matcher="Edit.*",
            timeout=30,
            policy_text="New approver policy"
        )
        
        # Load and verify
        with open(settings_file) as f:
            updated = json.load(f)
        
        # Check version preserved
        assert updated["version"] == "1.0"
        
        # Check custom settings preserved
        assert updated["customSettings"]["theme"] == "dark"
        assert updated["customSettings"]["editor"] == "vim"
        
        # Check existing policy preserved (but approverInstructions added)
        assert updated["policy"]["existingRules"] == "Don't modify files in /etc"
        assert updated["policy"]["approverInstructions"] == "New approver policy"
        
        # Check PostToolUse and PrePrompt unchanged
        assert updated["hooks"]["PostToolUse"] == complex_settings["hooks"]["PostToolUse"]
        assert updated["hooks"]["PrePrompt"] == complex_settings["hooks"]["PrePrompt"]
        
        # Check PreToolUse has all original hooks plus cc-approver
        pre_hooks = updated["hooks"]["PreToolUse"]
        assert len(pre_hooks) == 3  # 2 original + 1 cc-approver
        
        # Verify original hooks intact
        assert any(
            h.get("matcher") == "Bash.*" and 
            any(hook.get("command") == "security-check" for hook in h.get("hooks", []))
            for h in pre_hooks
        )
        assert any(
            h.get("matcher") == "Write.*" and
            any(hook.get("command") == "backup-file" for hook in h.get("hooks", []))
            for h in pre_hooks
        )