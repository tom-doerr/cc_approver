#!/usr/bin/env python3
"""Helper script to test policy-based decisions."""
import json
import sys
import os
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from cc_approver.approver import ApproverProgram, configure_lm
from cc_approver.settings import load_settings_chain, get_policy_text


def test_policy(policy_text, tool, tool_input):
    """Test a policy with a specific tool and input."""
    print(f"\n{'='*60}")
    print(f"Policy: {policy_text}")
    print(f"Tool: {tool}")
    print(f"Input: {json.dumps(tool_input)}")
    print(f"{'='*60}")
    
    # Configure DSPy
    configure_lm("openrouter/google/gemini-2.5-flash-lite")
    
    # Create program
    program = ApproverProgram()
    
    # Run decision
    result = program.forward(
        policy=policy_text,
        tool=tool,
        tool_input_json=json.dumps(tool_input),
        history_tail=""
    )
    
    print(f"Decision: {result.decision}")
    print(f"Reason: {result.reason}")
    return result


def main():
    """Run test scenarios."""
    print("Testing cc_approver policy decisions...")
    
    # Load current settings if available
    settings, _ = load_settings_chain()
    current_policy = get_policy_text(settings)
    
    if current_policy:
        print(f"\nCurrent policy: {current_policy}")
    
    # Test scenarios
    scenarios = [
        {
            "policy": "Deny destructive ops; allow read-only",
            "tool": "Bash",
            "tool_input": {"command": "rm -rf /"}
        },
        {
            "policy": "Deny destructive ops; allow read-only",
            "tool": "Bash",
            "tool_input": {"command": "ls -la"}
        },
    ]
    
    # Run tests
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n\nTest {i}:")
        test_policy(
            scenario["policy"],
            scenario["tool"],
            scenario["tool_input"]
        )
    
    # Test with current policy if available
    if current_policy:
        print(f"\n\nTesting with current policy:")
        test_policy(current_policy, "Bash", {"command": "ls"})


if __name__ == "__main__":
    main()