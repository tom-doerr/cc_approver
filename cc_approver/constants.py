"""Constants for cc_approver package."""

# Model Configuration Constants
DEFAULT_TEMPERATURE = 0.0
REFLECTION_TEMPERATURE = 1.0
DEFAULT_MAX_TOKENS = 1024
REFLECTION_MAX_TOKENS = 4096
DEFAULT_MODEL = "openrouter/google/gemini-2.5-flash-lite"

# Hook Configuration Constants
DEFAULT_MATCHER = "Bash|Edit|Write"
DEFAULT_TIMEOUT = 60
MAX_REASON_LENGTH = 500
DEFAULT_HISTORY_BYTES = 0

# Decision Constants
VALID_DECISIONS = {"allow", "deny", "ask"}
DEFAULT_DECISION = "ask"

# Path Constants
DEFAULT_COMPILED_PATH = "$CLAUDE_PROJECT_DIR/.claude/models/approver.compiled.json"
HOOK_EVENT_NAME = "PreToolUse"

# Training Constants
VALIDATION_SPLIT_RATIO = 0.2
RANDOM_SEED = 7

# Gemini Model Choices
GEMINI_CHOICES = [
    "openrouter/google/gemini-2.5-flash-lite",
    "openrouter/google/gemini-2.5-flash",
    "openrouter/google/gemini-2.5-pro",
]

# Default Policy Text
DEFAULT_POLICY = "Deny destructive ops; ask on ambiguous; allow read-only or tests."