#!/usr/bin/env python3
"""Test policy merging functionality."""
import json
import tempfile
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from cc_approver.settings import load_and_merge_settings, get_merged_policy

def test_policy_merging():
    """Test different policy merging strategies."""
    
    # Create temp directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup paths
        home_claude = Path(tmpdir) / "home" / ".claude"
        proj_claude = Path(tmpdir) / "project" / ".claude"
        
        home_claude.mkdir(parents=True)
        proj_claude.mkdir(parents=True)
        
        # Create global settings with policy
        global_settings = {
            "policy": {
                "approverInstructions": "GLOBAL: Deny all rm commands; Allow read-only operations"
            },
            "dspyApprover": {
                "model": "global-model"
            }
        }
        with open(home_claude / "settings.json", "w") as f:
            json.dump(global_settings, f)
        
        # Test 1: No local policy - should use global only
        print("Test 1: Global policy only")
        os.environ["HOME"] = str(Path(tmpdir) / "home")
        os.environ["CLAUDE_PROJECT_DIR"] = str(Path(tmpdir) / "project")
        
        settings, _ = load_and_merge_settings()
        policy = get_merged_policy(settings)
        print(f"Policy: {policy}\n")
        
        # Test 2: Local policy with append (default)
        print("Test 2: Local policy appended to global")
        local_settings = {
            "policy": {
                "approverInstructions": "LOCAL: Allow git operations; Deny network access"
            }
        }
        with open(proj_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        settings, _ = load_and_merge_settings()
        policy = get_merged_policy(settings)
        print(f"Policy: {policy}\n")
        
        # Test 3: Local policy with prepend strategy
        print("Test 3: Local policy prepended (higher priority)")
        local_settings["policy"]["mergeStrategy"] = "prepend"
        with open(proj_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        settings, _ = load_and_merge_settings()
        policy = get_merged_policy(settings)
        print(f"Policy: {policy}\n")
        
        # Test 4: Local policy with replace strategy
        print("Test 4: Local policy replaces global")
        local_settings["policy"]["mergeStrategy"] = "replace"
        with open(proj_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        settings, _ = load_and_merge_settings()
        policy = get_merged_policy(settings)
        print(f"Policy: {policy}\n")
        
        # Test 5: Explicit local and global instructions
        print("Test 5: Explicit localInstructions field")
        local_settings["policy"] = {
            "localInstructions": "PROJECT SPECIFIC: Special rules for this project",
            "mergeStrategy": "append"
        }
        with open(proj_claude / "settings.local.json", "w") as f:
            json.dump(local_settings, f)
        
        settings, _ = load_and_merge_settings()
        policy = get_merged_policy(settings)
        print(f"Policy: {policy}\n")

if __name__ == "__main__":
    test_policy_merging()