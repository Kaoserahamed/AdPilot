"""Weights and thresholds for the repository quality scorer.

Every number the scorer uses lives here so the model can be re-tuned without
reading check implementations. Weights are fractions of the whole score and
must sum to 1.0; `validate_config` enforces that.

The rubric is an original construction based on widely used repository-health
signals (test coverage, module size, import cycles, lint/CI wiring, secret
hygiene). It is not a reproduction of any third party's proprietary criteria.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Category weights -------------------------------------------------------

WEIGHT_TESTING = 0.25
WEIGHT_ARCHITECTURE = 0.20
WEIGHT_CLEANLINESS = 0.20
WEIGHT_DOCUMENTATION = 0.15
WEIGHT_CI = 0.10
WEIGHT_HYGIENE = 0.10

# --- Testing ----------------------------------------------------------------

MIN_TEST_RATIO_PASS = 0.50
MIN_TEST_RATIO_WARN = 0.25

# --- Architecture -----------------------------------------------------------

MAX_MODULE_LINES_PASS = 400
MAX_MODULE_LINES_WARN = 800
MAX_FUNCTION_LINES_WARN = 60
MAX_FUNCTION_LINES_FAIL = 120

# --- Code cleanliness -------------------------------------------------------

MAX_LINE_LENGTH_PASS = 120
MAX_LINE_LENGTH_WARN = 160
# Entry points legitimately print to stdout; that is their contract, not debris.
DEBUG_OUTPUT_EXEMPT = ("cli.py", "__main__.py", "scripts/")

# Inline marker that exempts a specific line from secret detection, for test
# fixtures that must contain realistic-looking fake credentials.
SECRET_SUPPRESSION_MARKER = "repo-score: allow-secret"

MAX_DEBUG_MARKERS_WARN = 5
MAX_DEBUG_MARKERS_FAIL = 20
MAX_STRIPPED_BLANK_RATIO = 0.5

# --- Documentation ----------------------------------------------------------

MIN_README_CHARS = 500
MIN_DOCSTRING_RATIO_PASS = 0.30
MIN_DOCSTRING_RATIO_WARN = 0.10

# --- Repository hygiene -----------------------------------------------------

REQUIRED_IGNORE_PATTERNS = (
    "node_modules/",
    ".env",
    "__pycache__/",
    ".venv/",
)

COMMIT_SUBJECT_PATTERN = r"^(feat|fix|test|docs|refactor|perf|build|ci|chore|security|style|revert)(\(.+\))?!?: .+"

SECRET_PATTERNS = (
    "-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "AKIA[0-9A-Z]{16}",
    r"sk-[A-Za-z0-9]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    "AIza[0-9A-Za-z_-]{35}",
)

SECRET_VALUE_PATTERN = r"(?i)(api[_-]?key|secret|password|token|client[_-]?secret)\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"

CONVENTIONAL_COMMIT_SAMPLE = 15

CATEGORY_WEIGHTS: dict[str, float] = {
    "testing": WEIGHT_TESTING,
    "architecture": WEIGHT_ARCHITECTURE,
    "cleanliness": WEIGHT_CLEANLINESS,
    "documentation": WEIGHT_DOCUMENTATION,
    "ci": WEIGHT_CI,
    "hygiene": WEIGHT_HYGIENE,
}


@dataclass(frozen=True)
class Config:
    """Immutable bundle of scorer settings (the defaults unless overridden)."""

    root_override: str | None = None


def validate_config(weights: dict[str, float] | None = None) -> None:
    """Raise if category weights are missing or do not sum to 1.0."""

    active = CATEGORY_WEIGHTS if weights is None else weights
    if not active:
        raise ValueError("At least one category weight is required")
    if any(weight <= 0 for weight in active.values()):
        raise ValueError(f"Category weights must be positive, got {active}")
    total = round(sum(active.values()), 6)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Category weights must sum to 1.0, got {total}")
