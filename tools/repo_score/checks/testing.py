"""Testing category: is the codebase actually exercised by automated tests?"""

from __future__ import annotations

from ..config import MIN_TEST_RATIO_PASS, MIN_TEST_RATIO_WARN
from ..models import CheckResult, Status
from ..repo import RepoContext, is_test_path

PY_TEST_MARKERS = ("def test_", "class Test")
TS_TEST_MARKERS = ("it(", "test(", "describe(", "expect(")


def _test_function_count(text: str) -> int:
    return sum(text.count(marker) for marker in PY_TEST_MARKERS) + sum(text.count(marker) for marker in TS_TEST_MARKERS)


def _framework_detected(context: RepoContext) -> str | None:
    if any(context.exists(name) for name in ("pytest.ini", "conftest.py", "tox.ini")):
        return "pytest"
    for _, relative in context.iter_paths({"json"}):
        if not relative.endswith("package.json"):
            continue
        content = context.read(relative)
        if '"vitest"' in content:
            return "vitest"
        if '"jest"' in content:
            return "jest"
    return None


def run(context: RepoContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    sources = context.source_files()
    tests = context.test_files()

    if not tests:
        return [
            CheckResult(
                name="tests_present",
                status=Status.FAIL,
                message="No test files found in the repository",
                weight=3.0,
            )
        ]

    results.append(
        CheckResult(
            name="tests_present",
            status=Status.PASS,
            message=f"{len(tests)} test file(s) detected",
            weight=1.0,
        )
    )

    ratio = len(tests) / max(len(sources), 1)
    if ratio >= MIN_TEST_RATIO_PASS:
        status, message = Status.PASS, f"Test-to-source ratio {ratio:.2f} (>= {MIN_TEST_RATIO_PASS})"
    elif ratio >= MIN_TEST_RATIO_WARN:
        status, message = Status.WARN, f"Test-to-source ratio {ratio:.2f} is below {MIN_TEST_RATIO_PASS}"
    else:
        status, message = Status.FAIL, f"Test-to-source ratio {ratio:.2f} is below {MIN_TEST_RATIO_WARN}"
    results.append(CheckResult(name="test_to_source_ratio", status=status, message=message, weight=2.0))

    framework = _framework_detected(context)
    results.append(
        CheckResult(
            name="test_framework_configured",
            status=Status.PASS if framework else Status.FAIL,
            message=f"Test runner configured: {framework}" if framework else "No pytest or vitest/jest configuration found",
            weight=1.5,
        )
    )

    total_assertions = sum(_test_function_count(source.text) for source in tests)
    if total_assertions >= len(tests):
        status = Status.PASS
        message = f"{total_assertions} test cases across {len(tests)} files"
    else:
        status = Status.WARN
        message = f"Only {total_assertions} test cases across {len(tests)} files; suites may be shallow"
    results.append(CheckResult(name="test_case_count", status=status, message=message, weight=1.5))

    untested = [source.relative for source in sources if not _is_test_path(source.relative) and not _has_sibling_test(source.relative, tests)]
    if untested:
        results.append(
            CheckResult(
                name="source_coverage",
                status=Status.WARN,
                message=f"{len(untested)} source file(s) have no matching test file",
                weight=1.0,
            )
        )
    else:
        results.append(CheckResult(name="source_coverage", status=Status.PASS, message="Every source file has a matching test file", weight=1.0))

    return results


def _is_test_path(relative: str) -> bool:
    return is_test_path(relative)


def _has_sibling_test(relative: str, tests: list) -> bool:
    """True when a test file targets the given source module's basename."""

    stem = relative.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return any(is_test_path(test.relative) and stem in test.relative for test in tests)