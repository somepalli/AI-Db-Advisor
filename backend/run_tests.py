#!/usr/bin/env python
"""
Test runner script for AI DB Advisor

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --verbose    # Run with verbose output
    python run_tests.py --coverage   # Run with coverage report
    python run_tests.py --ui         # Run only UI tests
    python run_tests.py --e2e        # Run only E2E tests
"""

import sys
import subprocess
from pathlib import Path


def main():
    """Run pytest with appropriate arguments"""
    args = sys.argv[1:]

    # Base pytest command
    cmd = ["pytest"]

    # Parse custom arguments
    if "--verbose" in args:
        cmd.append("-v")
        args.remove("--verbose")
    else:
        cmd.append("-v")  # Always verbose by default

    if "--coverage" in args:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
        args.remove("--coverage")

    if "--ui" in args:
        cmd.extend(["-m", "ui"])
        args.remove("--ui")

    if "--e2e" in args:
        cmd.extend(["-m", "e2e"])
        args.remove("--e2e")

    if "--integration" in args:
        cmd.extend(["-m", "integration"])
        args.remove("--integration")

    if "--quick" in args:
        cmd.extend(["-m", "not slow"])
        args.remove("--quick")

    # Add any remaining arguments
    cmd.extend(args)

    # Add test directory if no specific path provided
    if not any(arg.startswith("tests/") for arg in cmd):
        cmd.append("tests/")

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    # Run pytest
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()