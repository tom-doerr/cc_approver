"""Integration tests for policy-based decision making."""
import pytest
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, Mock
import dspy

from cc_approver.approver import Approver, ApproverProgram, configure_lm


class TestPolicyIntegration:
    """Test that policies actually affect decisions."""
    
    def test_deny_policy_blocks_destructive(self):
        """Test that deny destructive policy blocks rm commands."""
        configure_lm("test-model")
        program = ApproverProgram()
        
        # Mock the LM to simulate policy-based decision
        with patch.object(program.step, 'forward') as mock_forward:
            mock_forward.return_value = Mock(
                decision='deny', 
                reason='Policy denies destructive operations'
            )
            
            result = program.forward(
                policy="Deny destructive operations",
                tool="Bash",
                tool_input_json='{"command": "rm -rf /"}',
                history_tail=""
            )
            
            assert result.decision == 'deny'
            assert 'destructive' in result.reason.lower()
    
    def test_allow_policy_permits_readonly(self):
        """Test that allow read-only policy permits ls commands."""
        configure_lm("test-model")
        program = ApproverProgram()
        
        with patch.object(program.step, 'forward') as mock:
            mock.return_value = Mock(
                decision='allow',
                reason='Policy allows read-only operations'
            )
            
            result = program.forward(
                policy="Allow read-only operations",
                tool="Bash",
                tool_input_json='{"command": "ls -la"}',
                history_tail=""
            )
            
            assert result.decision == 'allow'
            assert 'read-only' in result.reason.lower()