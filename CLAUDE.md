# cc_approver Project Notes

## Project Overview
cc_approver is a DSPy-only permission hook and optimizer for Claude Code's PreToolUse functionality.
It provides intelligent tool permission management using machine learning without heuristics.

## Key Architecture Decisions

### 1. Pure DSPy Implementation
- Uses DSPy Signatures and Modules exclusively
- No hardcoded heuristics or rule-based logic
- Relies on LM (Language Model) for decision making
- Supports MIPROv2 and GEPA optimizers for training

### 2. Settings Integration
- Integrates with Claude's native settings system
- Settings stored in .claude/settings.json (local or global)
- Policy text in policy.approverInstructions
- DSPy config in dspyApprover object
- Supports project-level and global settings with proper precedence

### 3. Hook System
- PreToolUse hook intercepts tool calls
- Standalone mode: copies physical hook file to .claude/hooks/
- Command mode: uses cc-approver hook command
- Supports custom matchers (regex) for tool filtering
- Configurable timeout for hook execution

## Technical Implementation Details

### Module Structure
- **constants.py**: Centralized configuration constants
- **validators.py**: Input validation and normalization functions
- **models.py**: Pydantic data models for type safety
- **approver.py**: Core DSPy Signature/Module for decisions
- **settings.py**: Settings management (read/write Claude config)
- **optimizer.py**: Training logic with MIPROv2/GEPA
- **cli.py**: Command-line interface and entry points
- **hook.py**: Hook execution logic
- **hook_template.py**: Standalone hook (self-contained)
- **tui.py**: Terminal UI using questionary

### Testing Strategy
- Comprehensive pytest test suite
- Unit tests for each module
- Mocking DSPy LM to avoid API calls during tests
- Fixtures for common test data (settings, payloads)
- Test coverage for edge cases and error handling

## Lessons Learned

### File Size Limitations
- Write operations limited to 400 bytes by hook
- Must split large edits into smaller chunks
- Create files incrementally when content exceeds limit

### DSPy Best Practices
- Configure LM globally with dspy.configure()
- Use Signatures for clear input/output contracts
- Modules wrap Predict for reusable components
- Compiled models can be saved/loaded as JSON

## Architecture Improvements (v0.4.0)

### Extracted Constants
- All magic values moved to constants.py
- Improves maintainability and consistency

### Added Validation Layer
- validators.py provides input normalization
- Ensures data consistency across modules

### Type Safety with Pydantic
- models.py defines data structures
- Automatic validation and serialization

## Usage Commands

### Installation
```bash
poetry install
# or: pip install -e .
```

### Initialize (TUI)
```bash
cc-approver  # Opens interactive menu
```

### Initialize (CLI)
```bash
cc-approver init --scope project --standalone
```

### Optimize/Train
```bash
cc-approver optimize --scope project \
  --train data.jsonl --optimizer mipro --auto light
```

### Run Tests
```bash
pytest
pytest --cov=cc_approver  # With coverage
pytest -m "not slow"      # Skip slow tests
```

## Important Notes

- History is disabled by default (historyBytes: 0)
- Falls back to "ask" if LM fails or returns invalid decision
- Settings precedence: local > project > global
- JSONL training data requires "label" field with allow/deny/ask
- Use OPENROUTER_API_KEY or other LiteLLM-supported env vars