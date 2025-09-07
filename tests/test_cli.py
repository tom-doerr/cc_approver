import pytest
from unittest.mock import patch, Mock
import argparse
import sys

from cc_approver.cli import (
    main, _tui_entry, cmd_init_or_tui, 
    cmd_optimize_or_tui, cmd_hook, _run_init
)
from cc_approver.hook import tail

class TestTailFunction:
    def test_tail_empty_path(self):
        """Test tail with empty path."""
        assert tail("", 100) == ""
    
    def test_tail_invalid_bytes(self):
        """Test tail with invalid byte count."""
        assert tail("/path", -1) == ""

class TestMain:
    @patch('sys.argv', ['cc-approver'])
    @patch('cc_approver.cli._tui_entry')
    def test_main_no_args_launches_tui(self, mock_tui):
        """Test that main with no args launches TUI."""
        main()
        mock_tui.assert_called_once()
    
    @patch('sys.argv', ['cc-approver', 'init', '--scope', 'project'])
    @patch('cc_approver.cli.cmd_init_or_tui')
    def test_main_init_command(self, mock_init):
        """Test main with init command."""
        main()
        mock_init.assert_called_once()
    
    @patch('sys.argv', ['cc-approver', 'optimize', '--scope', 'global'])
    @patch('cc_approver.cli.cmd_optimize_or_tui')
    def test_main_optimize_command(self, mock_optimize):
        """Test main with optimize command."""
        main()
        mock_optimize.assert_called_once()
    
    @patch('sys.argv', ['cc-approver', 'hook'])
    @patch('cc_approver.cli.cmd_hook')
    def test_main_hook_command(self, mock_hook):
        """Test main with hook command."""
        main()
        mock_hook.assert_called_once()

class TestCmdInitOrTui:
    @patch('cc_approver.cli._run_init')
    def test_cmd_init_with_all_args(self, mock_run):
        """Test cmd_init_or_tui with all arguments."""
        args = Mock(
            scope='project', model='test-model', history_bytes=100,
            standalone=True, matcher='Bash.*', timeout=5,
            policy_text='Test policy', prompt_model=None,
            eval_model=None, reflection_model=None
        )
        cmd_init_or_tui(args)
        mock_run.assert_called_once()
    
    @patch('cc_approver.tui.init_menu')
    @patch('cc_approver.cli._run_init')
    def test_cmd_init_launches_tui(self, mock_run, mock_menu):
        """Test cmd_init_or_tui launches TUI when no args."""
        args = Mock(scope=None, model=None, history=None,
                   standalone=None, matcher=None, timeout=None,
                   policy=None)
        mock_menu.return_value = {
            'scope': 'global', 'model': 'test', 'history_bytes': 0,
            'standalone': False, 'matcher': 'Bash', 'timeout': 10,
            'policy_text': 'Policy'
        }
        cmd_init_or_tui(args)
        mock_menu.assert_called_once()
        mock_run.assert_called_once()

class TestRunInit:
    @patch('cc_approver.cli.write_settings')
    @patch('cc_approver.cli.merge_pretooluse_hook')
    @patch('cc_approver.cli.ensure_dspy_config')
    @patch('cc_approver.cli.ensure_policy_text')
    @patch('cc_approver.cli._read_json')
    def test_run_init_project_scope(self, mock_load, 
                                   mock_ensure_policy, mock_ensure_dspy, 
                                   mock_merge, mock_write):
        """Test _run_init with project scope."""
        from cc_approver.cli import _run_init
        mock_load.return_value = {}
        
        _run_init('project', 'model', 100, 'Bash', 10, 'Policy')
        
        mock_load.assert_called_once()
        mock_ensure_policy.assert_called_once()
        mock_ensure_dspy.assert_called_once()
        mock_merge.assert_called_once()
        mock_write.assert_called_once()

class TestCmdHook:
    def test_cmd_hook(self, capsys):
        """Test cmd_hook function."""
        import io, json
        stdin_data = json.dumps({"tool_name": "Bash", "tool_input": {}})
        with patch('sys.stdin', io.StringIO(stdin_data)):
            args = Mock()
            cmd_hook(args)
            captured = capsys.readouterr()
            assert "hookSpecificOutput" in captured.out