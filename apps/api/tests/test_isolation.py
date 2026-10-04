"""Guards that the suite is hermetic.

The README tells a buyer the whole test suite runs with no accounts and no
network. That claim is easy to break silently: a new test that patches a
``requests.get`` call, or one run after an export of LIVE_EXTERNAL_APIS=true,
would keep passing while quietly depending on something external.

These checks fail the build in that case rather than leaving it to review.
"""

import ast
from pathlib import Path

import pytest

from app.config import settings

TESTS_DIR = Path(__file__).parent

# Modules that make outbound calls. Importing one from a test is the usual way
# a suite starts depending on the internet; the sandbox adapters below fake
# their transport, so tests should never need them directly.
NETWORK_MODULES = {"requests", "httpx", "urllib3", "aiohttp", "socket"}

AI_PROVIDER_LIBRARIES = {"anthropic", "openai", "google"}


def imported_modules(path: Path) -> set[str]:
    """Return the top-level module names imported by a Python file."""

    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_live_external_apis_is_off_during_the_suite() -> None:
    """No test may run against real advertising accounts.

    The adapters branch on this flag, so a leaked environment variable would
    turn a sandbox run into one that could spend money.
    """

    assert settings.live_external_apis is False, (
        "LIVE_EXTERNAL_APIS is enabled; the suite must run against sandbox adapters"
    )


def test_ai_provider_is_mock_or_sandbox() -> None:
    """The AI provider must not be a paid one during tests."""

    assert settings.ai_provider.lower() in {"mock", "sandbox"}, (
        f"AI_PROVIDER is {settings.ai_provider!r}; tests must not call a paid model"
    )


@pytest.mark.parametrize("path", sorted(TESTS_DIR.glob("test_*.py")), ids=lambda p: p.name)
def test_no_test_imports_a_network_client(path: Path) -> None:
    """No test file may import a library that performs real network calls."""

    imported = imported_modules(path)
    offenders = sorted(imported & NETWORK_MODULES)

    assert not offenders, f"{path.name} imports {offenders}; tests must not touch the network"


@pytest.mark.parametrize("path", sorted(TESTS_DIR.glob("test_*.py")), ids=lambda p: p.name)
def test_no_test_imports_a_paid_ai_library(path: Path) -> None:
    """No test file may import a provider SDK directly."""

    imported = imported_modules(path)
    offenders = sorted(imported & AI_PROVIDER_LIBRARIES)

    assert not offenders, f"{path.name} imports {offenders}"
