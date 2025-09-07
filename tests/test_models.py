"""Tests for cc_approver.models module."""
import pytest
from cc_approver.models import (
    DspyConfig, PolicyConfig, HookConfig, 
    TrainingExample, DecisionResult
)
from cc_approver.constants import (
    DEFAULT_MODEL, DEFAULT_HISTORY_BYTES, DEFAULT_COMPILED_PATH,
    DEFAULT_MATCHER, DEFAULT_TIMEOUT
)

class TestDspyConfig:
    def test_default_values(self):
        """Test DspyConfig default values."""
        config = DspyConfig()
        assert config.model == DEFAULT_MODEL
        assert config.historyBytes == DEFAULT_HISTORY_BYTES
        assert config.compiledModelPath == DEFAULT_COMPILED_PATH
        assert config.promptModel is None
        assert config.evalModel is None
        assert config.reflectionModel is None

class TestPolicyConfig:
    def test_default_values(self):
        """Test PolicyConfig default values."""
        config = PolicyConfig()
        assert config.approverInstructions == ""
    
    def test_custom_values(self):
        """Test PolicyConfig with custom values."""
        config = PolicyConfig(approverInstructions="Custom policy")
        assert config.approverInstructions == "Custom policy"

class TestTrainingExample:
    def test_label_normalization(self):
        """Test label field is normalized."""
        example = TrainingExample(label="ALLOW")
        assert example.label == "allow"
        
        example = TrainingExample(label="Deny")
        assert example.label == "deny"
        
        example = TrainingExample(label="ASK")
        assert example.label == "ask"
    
    def test_invalid_label(self):
        """Test invalid label is normalized to empty string."""
        example = TrainingExample(label="invalid")
        assert example.label == ""

class TestDecisionResult:
    def test_decision_normalization(self):
        """Test decision field is normalized."""
        result = DecisionResult(decision="ALLOW", reason="OK")
        assert result.decision == "allow"
        
        result = DecisionResult(decision="Deny", reason="Not safe")
        assert result.decision == "deny"
    
    def test_invalid_decision(self):
        """Test invalid decision is normalized to ask."""
        result = DecisionResult(decision="invalid", reason="test")
        assert result.decision == "ask"