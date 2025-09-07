import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from cc_approver.tui import (
    detect_scope_default, main_menu, init_menu, optimize_menu
)

class TestDetectScopeDefault:
    def test_detect_scope_project_settings_exists(self, temp_dir):
        """Test detecting project scope when settings exist."""
        settings_file = temp_dir / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.touch()
        
        with patch('cc_approver.tui.Path.cwd', return_value=temp_dir):
            result = detect_scope_default()
            assert result == "project"
    
    def test_detect_scope_global_default(self, temp_dir):
        """Test detecting global scope when no project settings."""
        with patch('os.getcwd', return_value=str(temp_dir)):
            with patch.dict('os.environ', {'CLAUDE_PROJECT_DIR': ''}, clear=True):
                result = detect_scope_default()
                assert result == "global"

class TestMainMenu:
    @patch('cc_approver.tui.q.select')
    def test_main_menu_exit(self, mock_select):
        """Test main menu exit option."""
        mock_select.return_value.ask.return_value = "Exit"
        result = main_menu()
        assert result == "Exit"
        mock_select.assert_called_once()
    
    @patch('cc_approver.tui.q.select')
    def test_main_menu_init(self, mock_select):
        """Test main menu init option."""
        mock_select.return_value.ask.return_value = "Init"
        result = main_menu()
        assert result == "Init"
        mock_select.assert_called_once()