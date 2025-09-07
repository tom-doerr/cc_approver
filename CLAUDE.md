# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

cc_approver is a DSPy-only permission hook and optimizer for Claude Code's PreToolUse functionality. It provides intelligent, ML-based tool permission management without hardcoded heuristics.

## Development Commands

### Setup and Installation
```bash
poetry install              # Install all dependencies
# or: pip install -e .

export OPENROUTER_API_KEY=sk-...  # Set API key for LiteLLM provider
```

### Running Tests
```bash
pytest                      # Run all tests
pytest --cov=cc_approver    # Run with coverage report
pytest -m "not slow"        # Skip slow tests
pytest -v                   # Verbose output
pytest tests/test_hook.py   # Run specific test file
pytest -k test_deny_policy  # Run tests matching pattern
```

### Using the CLI
```bash
cc-approver                 # Launch interactive TUI menu
cc-approver init --scope project --model "openrouter/google/gemini-2.5-flash-lite"
cc-approver optimize --train data.jsonl --optimizer mipro --auto light
cc-approver hook --verbose  # Run hook with debug output
```

### Debugging Hooks
```bash
# Test hook with verbose output
echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"transcript_path":""}' | cc-approver hook --verbose

# Enable verbose mode via environment
CC_APPROVER_VERBOSE=true cc-approver hook
```

## Architecture and Key Design Decisions

### Settings Resolution Chain (Updated in v0.5.0)
Settings now **merge** from global → project → local:
1. `~/.claude/settings.json` (global) - Base settings
2. `.claude/settings.json` (project) - Merged on top of global
3. `.claude/settings.local.json` (local) - Merged on top of project

**Policy Merging**: Policies can be combined intelligently:
- **Global policy**: Base rules that apply everywhere
- **Local policy**: Project-specific rules that extend or override global

#### Policy Merge Strategies
Set `mergeStrategy` in local policy to control how policies combine:
- `"append"` (default): Global rules first, then local rules
- `"prepend"`: Local rules first (higher priority), then global
- `"replace"`: Local completely replaces global

Example local settings with policy merge:
```json
{
  "policy": {
    "approverInstructions": "Allow this project's special commands",
    "mergeStrategy": "append"  // or "prepend" or "replace"
  }
}
```

### Core Module Responsibilities

- **approver.py**: DSPy Signature (`Approver`) and Module (`ApproverProgram`) for permission decisions
- **settings.py**: Settings chain loading, policy text extraction, DSPy config management
- **hook.py**: Entry point for PreToolUse events, handles stdin/stdout JSON protocol
- **cli.py**: Command-line interface, argument parsing, command dispatch
- **optimizer.py**: Training logic for MIPROv2/GEPA optimizers from JSONL data
- **constants.py**: Centralized constants (DEFAULT_MAX_TOKENS=1024, DEFAULT_TEMPERATURE=0.0, etc.)
- **validators.py**: Input normalization (decision validation, reason truncation)
- **models.py**: Pydantic models for type-safe data structures
- **tui.py**: Interactive terminal UI using questionary

### Hook Execution Flow
1. Hook receives JSON payload via stdin with `tool_name`, `tool_input`, `transcript_path`
2. Settings loaded from chain (local → project → global)
3. Policy text extracted from `settings["policy"]["approverInstructions"]`
4. DSPy LM configured with model from settings
5. Attempts to load compiled model from paths, falls back to untrained `ApproverProgram()`
6. Runs decision through DSPy module with policy + tool info
7. Returns JSON with `permissionDecision` (allow/deny/ask) and `permissionDecisionReason`

### Key Configuration Fields

Settings structure in `.claude/settings.json`:
```json
{
  "policy": {
    "approverInstructions": "Policy text here"
  },
  "dspyApprover": {
    "model": "openrouter/google/gemini-2.5-flash-lite",
    "historyBytes": 0,
    "compiledModelPath": "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
  },
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "cc-approver hook",
        "timeout": 10
      }]
    }]
  }
}
```

### Training Data Format

JSONL format for training:
```json
{"tool_name":"Bash","tool_input_json":"{\"command\":\"rm -rf /\"}","label":"deny"}
{"tool_name":"Bash","tool_input_json":"{\"command\":\"ls -la\"}","label":"allow"}
{"tool_name":"Edit","tool_input_json":"{\"path\":\"test.py\"}","label":"allow"}
```

Required fields: `tool_name`, `tool_input_json`, `label` (allow/deny/ask)

## Critical Implementation Details

### Token Limits
- `DEFAULT_MAX_TOKENS = 1024` - Increased from 256 to handle detailed policies
- If truncation warnings appear, the policy may be too long or complex

### No Standalone Mode (Removed)
- Previously supported copying hook files to `.claude/hooks/`
- Now always uses `cc-approver hook` command to ensure latest code is used
- Removed `hook_template.py` - no longer needed

### Error Handling
- Falls back to "ask" decision if LM fails or returns invalid response
- Empty policy treated as deny-all for safety
- Validates decisions against {"allow", "deny", "ask"} set

### File Size Limitations
- Hook enforces 400-byte limit on file edits
- Use MultiEdit or multiple small edits for larger changes
- Create files incrementally when content exceeds limit

## Common Issues and Solutions

### Policy Not Being Applied
- Check settings loading order: local settings completely override global
- Use `--verbose` flag to see which settings file and policy are loaded
- Verify policy text exists in the loaded settings file

### Hook Permission Denied
- Ensure hook has execute permissions: `chmod +x .claude/hooks/cc_approver_hook.py`
- cc-approver init now automatically sets executable permissions

### Truncation Warnings
- Increase `DEFAULT_MAX_TOKENS` in `constants.py` if needed
- Simplify overly complex policies
- Consider breaking policy into clearer, shorter rules

### Policy Merging Behavior (v0.5.0+)
- Settings now properly merge: global → project → local
- Policies can be combined using merge strategies
- Use `"mergeStrategy": "replace"` to completely override global policy
- Use `"mergeStrategy": "prepend"` to give local rules higher priority
- Debug with `--verbose` to see the final merged policy

## Development Tips

### Testing Policy Changes
```python
# Use test_policy.py to test policies without hooks
python test_policy.py

# Test specific policy/tool combinations
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"},"transcript_path":""}' | \
  cc-approver hook --verbose
```

### Debugging Decision Logic
- Set `CC_APPROVER_VERBOSE=true` to see all inputs/outputs
- Check loaded policy text matches expectations
- Verify model is receiving complete policy (not truncated)

### Performance Optimization
- Keep `historyBytes: 0` unless policy requires conversation context
- Use lighter models for faster decisions (gemini-2.5-flash-lite)
- Compile models with training data for better accuracy