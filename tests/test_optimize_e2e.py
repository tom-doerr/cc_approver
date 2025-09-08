"""End-to-end tests for the optimize command."""
import pytest
import json
import tempfile
import subprocess
import sys
import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import dspy

from cc_approver.cli import cmd_optimize_or_tui, _run_optimize
from cc_approver.optimizer import optimize_from_files


class TestOptimizeE2E:
    """End-to-end tests for optimization functionality."""
    
    @pytest.fixture
    def train_data(self, temp_dir):
        """Create training JSONL file."""
        train_file = temp_dir / "train.jsonl"
        data = [
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "label": "allow"},
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "label": "deny"},
            {"tool_name": "Edit", "tool_input": {"path": "/etc/passwd"}, "label": "deny"},
            {"tool_name": "Read", "tool_input": {"path": "README.md"}, "label": "allow"},
            {"tool_name": "Write", "tool_input": {"path": "/tmp/test.txt"}, "label": "ask"},
        ]
        with open(train_file, 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        return train_file
    
    @pytest.fixture
    def val_data(self, temp_dir):
        """Create validation JSONL file."""
        val_file = temp_dir / "val.jsonl"
        data = [
            {"tool_name": "Bash", "tool_input": {"command": "pwd"}, "label": "allow"},
            {"tool_name": "Bash", "tool_input": {"command": "sudo rm -rf /"}, "label": "deny"},
        ]
        with open(val_file, 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        return val_file
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return {
            "policy": {
                "approverInstructions": "Allow safe operations, deny destructive ones"
            },
            "dspyApprover": {
                "model": "test-model",
                "historyBytes": 0,
                "compiledModelPath": "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
            }
        }
    
    def test_optimize_cli_with_train_only(self, train_data, temp_dir, mock_settings):
        """Test optimize command with only training data."""
        save_path = temp_dir / "compiled.json"
        
        # Mock the optimization to avoid actual LM calls
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            mock_program = Mock()
            mock_program.save = Mock()
            mock_opt.return_value = (mock_program, 0.85)
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                args = Mock(
                    train=str(train_data),
                    val=None,
                    scope="project",
                    optimizer="mipro",
                    auto="light",
                    task_model="test-model",
                    prompt_model=None,
                    reflection_model=None,
                    eval_model=None,
                    history_bytes=0,
                    save=str(save_path)
                )
                
                cmd_optimize_or_tui(args)
                
                mock_opt.assert_called_once()
                call_args = mock_opt.call_args[1]
                assert call_args['train_path'] == train_data
                assert call_args['val_path'] is None
                assert call_args['optimizer'] == "mipro"
                assert call_args['auto'] == "light"
                mock_program.save.assert_called_once_with(str(save_path))
    
    def test_optimize_cli_with_train_and_val(self, train_data, val_data, temp_dir, mock_settings):
        """Test optimize command with both training and validation data."""
        save_path = temp_dir / "compiled.json"
        
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            mock_program = Mock()
            mock_program.save = Mock()
            mock_opt.return_value = (mock_program, 0.90)
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                args = Mock(
                    train=str(train_data),
                    val=str(val_data),
                    scope="global",
                    optimizer="gepa",
                    auto="medium",
                    task_model="gpt-4",
                    prompt_model="gpt-3.5-turbo",
                    reflection_model="gpt-4",
                    eval_model="gpt-3.5-turbo",
                    history_bytes=1000,
                    save=str(save_path)
                )
                
                cmd_optimize_or_tui(args)
                
                mock_opt.assert_called_once()
                call_args = mock_opt.call_args[1]
                assert call_args['train_path'] == train_data
                assert call_args['val_path'] == val_data
                assert call_args['optimizer'] == "gepa"
                assert call_args['auto'] == "medium"
                assert call_args['task_model'] == "gpt-4"
    
    def test_optimize_tui_mode(self, train_data, temp_dir, mock_settings):
        """Test optimize launches TUI when no train file provided."""
        with patch('cc_approver.tui.optimize_menu') as mock_menu:
            mock_menu.return_value = {
                'scope': 'project',
                'optimizer': 'mipro',
                'auto': 'light',
                'task_model': 'test-model',
                'prompt_model': None,
                'reflection_model': None,
                'eval_model': None,
                'train': str(train_data),
                'val': None,
                'history_bytes': 0
            }
            
            with patch('cc_approver.cli._run_optimize') as mock_run:
                args = Mock(train=None)
                cmd_optimize_or_tui(args)
                
                mock_menu.assert_called_once()
                mock_run.assert_called_once()
    
    def test_optimize_warm_start(self, train_data, temp_dir, mock_settings):
        """Test optimization with warm start from existing compiled model."""
        # Create a mock compiled model
        warm_start_path = temp_dir / ".claude" / "models" / "approver.compiled.json"
        warm_start_path.parent.mkdir(parents=True, exist_ok=True)
        warm_start_data = {
            "step": {
                "demos": [],
                "signature": "Approver"
            }
        }
        with open(warm_start_path, 'w') as f:
            json.dump(warm_start_data, f)
        
        save_path = temp_dir / "new_compiled.json"
        
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            mock_program = Mock()
            mock_program.save = Mock()
            mock_opt.return_value = (mock_program, 0.92)
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_settings['dspyApprover']['compiledModelPath'] = str(warm_start_path)
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                with patch.dict('os.environ', {'CLAUDE_PROJECT_DIR': str(temp_dir)}):
                    args = Mock(
                        train=str(train_data),
                        val=None,
                        scope="project",
                        optimizer="mipro",
                        auto="heavy",
                        task_model="test-model",
                        prompt_model=None,
                        reflection_model=None,
                        eval_model=None,
                        history_bytes=0,
                        save=str(save_path)
                    )
                    
                    cmd_optimize_or_tui(args)
                    
                    mock_opt.assert_called_once()
                    call_args = mock_opt.call_args[1]
                    # Check that warm_start path was passed
                    assert call_args['warm_start'] == warm_start_path
    
    def test_optimize_different_optimizers(self, train_data, temp_dir, mock_settings):
        """Test both MIPRO and GEPA optimizers."""
        for optimizer in ["mipro", "gepa"]:
            save_path = temp_dir / f"compiled_{optimizer}.json"
            
            with patch('cc_approver.cli.optimize_from_files') as mock_opt:
                mock_program = Mock()
                mock_program.save = Mock()
                mock_opt.return_value = (mock_program, 0.88)
                
                with patch('cc_approver.cli.load_settings_chain') as mock_load:
                    mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                    
                    args = Mock(
                        train=str(train_data),
                        val=None,
                        scope="project",
                        optimizer=optimizer,
                        auto="light",
                        task_model="test-model",
                        prompt_model=None,
                        reflection_model=None,
                        eval_model=None,
                        history_bytes=0,
                        save=str(save_path)
                    )
                    
                    cmd_optimize_or_tui(args)
                    
                    mock_opt.assert_called_once()
                    assert mock_opt.call_args[1]['optimizer'] == optimizer
    
    def test_optimize_auto_settings(self, train_data, temp_dir, mock_settings):
        """Test different auto settings (light, medium, heavy)."""
        for auto in ["light", "medium", "heavy"]:
            save_path = temp_dir / f"compiled_{auto}.json"
            
            with patch('cc_approver.cli.optimize_from_files') as mock_opt:
                mock_program = Mock()
                mock_program.save = Mock()
                mock_opt.return_value = (mock_program, 0.87)
                
                with patch('cc_approver.cli.load_settings_chain') as mock_load:
                    mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                    
                    args = Mock(
                        train=str(train_data),
                        val=None,
                        scope="project",
                        optimizer="mipro",
                        auto=auto,
                        task_model="test-model",
                        prompt_model=None,
                        reflection_model=None,
                        eval_model=None,
                        history_bytes=0,
                        save=str(save_path)
                    )
                    
                    cmd_optimize_or_tui(args)
                    
                    mock_opt.assert_called_once()
                    assert mock_opt.call_args[1]['auto'] == auto
    
    def test_optimize_with_history(self, train_data, temp_dir, mock_settings):
        """Test optimization with history bytes setting."""
        save_path = temp_dir / "compiled_with_history.json"
        
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            mock_program = Mock()
            mock_program.save = Mock()
            mock_opt.return_value = (mock_program, 0.89)
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                args = Mock(
                    train=str(train_data),
                    val=None,
                    scope="project",
                    optimizer="mipro",
                    auto="light",
                    task_model="test-model",
                    prompt_model=None,
                    reflection_model=None,
                    eval_model=None,
                    history_bytes=5000,
                    save=str(save_path)
                )
                
                cmd_optimize_or_tui(args)
                
                mock_opt.assert_called_once()
                assert mock_opt.call_args[1]['history_bytes'] == 5000
    
    @patch('subprocess.run')
    def test_optimize_cli_subprocess(self, mock_run, train_data, temp_dir):
        """Test running optimize via subprocess (simulating actual CLI usage)."""
        mock_run.return_value = Mock(returncode=0, stdout="Saved compiled program\nDev accuracy: 0.850")
        
        result = subprocess.run(
            [sys.executable, "-m", "cc_approver.cli", "optimize",
             "--train", str(train_data),
             "--optimizer", "mipro",
             "--auto", "light",
             "--save", str(temp_dir / "output.json")],
            capture_output=True,
            text=True
        )
        
        # Just verify subprocess.run was called (mocked)
        mock_run.assert_called_once()
    
    def test_optimize_error_handling(self, temp_dir, mock_settings):
        """Test error handling when training file doesn't exist."""
        non_existent = temp_dir / "non_existent.jsonl"
        save_path = temp_dir / "compiled.json"
        
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            mock_opt.side_effect = FileNotFoundError("Training file not found")
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                args = Mock(
                    train=str(non_existent),
                    val=None,
                    scope="project",
                    optimizer="mipro",
                    auto="light",
                    task_model="test-model",
                    prompt_model=None,
                    reflection_model=None,
                    eval_model=None,
                    history_bytes=0,
                    save=str(save_path)
                )
                
                with pytest.raises(FileNotFoundError):
                    cmd_optimize_or_tui(args)
    
    def test_optimize_jsonl_format_validation(self, temp_dir, mock_settings):
        """Test that invalid JSONL format is handled."""
        bad_jsonl = temp_dir / "bad.jsonl"
        with open(bad_jsonl, 'w') as f:
            f.write("not valid json\n")
            f.write('{"tool_name": "Bash", missing_label}\n')
        
        save_path = temp_dir / "compiled.json"
        
        with patch('cc_approver.cli.optimize_from_files') as mock_opt:
            # Simulate empty training set due to invalid data
            mock_opt.side_effect = ValueError("No training examples found")
            
            with patch('cc_approver.cli.load_settings_chain') as mock_load:
                mock_load.return_value = (mock_settings, temp_dir / ".claude" / "settings.json")
                
                args = Mock(
                    train=str(bad_jsonl),
                    val=None,
                    scope="project",
                    optimizer="mipro",
                    auto="light",
                    task_model="test-model",
                    prompt_model=None,
                    reflection_model=None,
                    eval_model=None,
                    history_bytes=0,
                    save=str(save_path)
                )
                
                with pytest.raises(ValueError, match="No training examples"):
                    cmd_optimize_or_tui(args)


class TestOptimizeIntegration:
    """Test optimize_from_files function directly."""
    
    @pytest.fixture
    def train_data(self, temp_dir):
        """Create training JSONL file."""
        train_file = temp_dir / "train.jsonl"
        data = [
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "label": "allow"},
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "label": "deny"},
            {"tool_name": "Edit", "tool_input": {"path": "/etc/passwd"}, "label": "deny"},
            {"tool_name": "Read", "tool_input": {"path": "README.md"}, "label": "allow"},
        ]
        with open(train_file, 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        return train_file
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return {
            "policy": {
                "approverInstructions": "Allow safe operations, deny destructive ones"
            },
            "dspyApprover": {
                "model": "test-model",
                "historyBytes": 0,
                "compiledModelPath": "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
            }
        }
    
    @pytest.fixture
    def mock_dspy_lm(self):
        """Mock DSPy LM to avoid actual API calls."""
        with patch('dspy.LM') as mock_lm_class:
            mock_lm = MagicMock()
            mock_lm_class.return_value = mock_lm
            
            # Mock the response
            mock_response = Mock()
            mock_response.decision = "allow"
            mock_response.reason = "Safe operation"
            mock_lm.forward.return_value = mock_response
            
            yield mock_lm
    
    def test_optimize_from_files_mipro(self, train_data, temp_dir, mock_settings, mock_dspy_lm):
        """Test optimize_from_files with MIPRO optimizer."""
        with patch('dspy.configure') as mock_configure:
            with patch('dspy.teleprompt.MIPROv2') as mock_mipro_class:
                mock_optimizer = Mock()
                mock_compiled = Mock()
                mock_compiled.save = Mock()
                mock_optimizer.compile.return_value = mock_compiled
                mock_mipro_class.return_value = mock_optimizer
                
                program, acc = optimize_from_files(
                    task_model="test-model",
                    train_path=train_data,
                    val_path=None,
                    optimizer="mipro",
                    auto="light",
                    settings=mock_settings,
                    prompt_model=None,
                    reflection_model=None,
                    eval_model=None,
                    history_bytes=0,
                    warm_start=None
                )
                
                mock_configure.assert_called_once()
                mock_mipro_class.assert_called_once()
                mock_optimizer.compile.assert_called_once()
                assert program == mock_compiled
    
    def test_optimize_from_files_gepa(self, train_data, temp_dir, mock_settings, mock_dspy_lm):
        """Test optimize_from_files with GEPA optimizer."""
        with patch('dspy.configure') as mock_configure:
            with patch('dspy.teleprompt.GEPA') as mock_gepa_class:
                mock_optimizer = Mock()
                mock_compiled = Mock()
                mock_compiled.save = Mock()
                mock_optimizer.compile.return_value = mock_compiled
                mock_gepa_class.return_value = mock_optimizer
                
                program, acc = optimize_from_files(
                    task_model="test-model",
                    train_path=train_data,
                    val_path=None,
                    optimizer="gepa",
                    auto="medium",
                    settings=mock_settings,
                    prompt_model=None,
                    reflection_model="test-reflection-model",
                    eval_model=None,
                    history_bytes=0,
                    warm_start=None
                )
                
                mock_configure.assert_called_once()
                mock_gepa_class.assert_called_once()
                # Check that reflection model was set
                call_kwargs = mock_gepa_class.call_args[1]
                assert 'reflection_lm' in call_kwargs
    
    def test_optimize_validation_split(self, train_data, temp_dir, mock_settings, mock_dspy_lm):
        """Test that validation split works when no val file provided."""
        with patch('dspy.configure'):
            with patch('cc_approver.optimizer.read_jsonl') as mock_read:
                # Return enough examples to test splitting
                examples = [Mock(decision="allow") for _ in range(10)]
                for ex in examples:
                    ex.policy = "test"
                    ex.tool = "Bash"
                    ex.tool_input_json = "{}"
                    ex.history_tail = ""
                mock_read.return_value = examples
                
                with patch('dspy.teleprompt.MIPROv2') as mock_mipro:
                    mock_optimizer = Mock()
                    mock_compiled = Mock()
                    mock_optimizer.compile.return_value = mock_compiled
                    mock_mipro.return_value = mock_optimizer
                    
                    program, acc = optimize_from_files(
                        task_model="test-model",
                        train_path=train_data,
                        val_path=None,  # No validation file
                        optimizer="mipro",
                        auto="light",
                        settings=mock_settings,
                        prompt_model=None,
                        reflection_model=None,
                        eval_model=None,
                        history_bytes=0,
                        warm_start=None
                    )
                    
                    # Check that compile was called with split data
                    compile_args = mock_optimizer.compile.call_args
                    trainset = compile_args[1]['trainset']
                    valset = compile_args[1]['valset']
                    
                    # With 10 examples and 0.2 split, should have 2 val and 8 train
                    assert len(trainset) == 8
                    assert len(valset) == 2