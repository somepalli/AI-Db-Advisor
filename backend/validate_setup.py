#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validation script to check if the test environment is properly configured

Run this before running tests to ensure everything is set up correctly.
"""

import sys
import io
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_python_version():
    """Check Python version is 3.10+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        return False, f"Python 3.10+ required, found {version.major}.{version.minor}"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"


def check_dependencies():
    """Check if required packages are installed"""
    required = [
        "fastapi",
        "pytest",
        "pytest_cov",
        "httpx",
        "pydantic",
        "fastui",
    ]

    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, "All required packages installed"


def check_directory_structure():
    """Check if directory structure is correct"""
    required_dirs = [
        Path("tests"),
        Path("app"),
        Path("routers"),
        Path("services"),
        Path("utils"),
    ]

    missing = []
    for dir_path in required_dirs:
        if not dir_path.exists():
            missing.append(str(dir_path))

    if missing:
        return False, f"Missing directories: {', '.join(missing)}"
    return True, "Directory structure correct"


def check_test_files():
    """Check if test files exist"""
    required_files = [
        Path("tests/__init__.py"),
        Path("tests/conftest.py"),
        Path("tests/test_api_datasources.py"),
        Path("tests/test_api_analyze.py"),
        Path("tests/test_ui.py"),
        Path("tests/test_e2e_workflows.py"),
        Path("tests/test_utils.py"),
    ]

    missing = []
    for file_path in required_files:
        if not file_path.exists():
            missing.append(str(file_path))

    if missing:
        return False, f"Missing test files: {', '.join(missing)}"
    return True, f"All {len(required_files)} test files present"


def check_pytest_config():
    """Check if pytest configuration exists"""
    config_files = [Path("pytest.ini"), Path("pyproject.toml"), Path("setup.cfg")]

    found = None
    for config in config_files:
        if config.exists():
            found = config
            break

    if not found:
        return False, "No pytest configuration found"
    return True, f"Configuration found: {found}"


def check_app_imports():
    """Check if app modules can be imported"""
    try:
        from app.main import app
        from app.config import settings
        from app.deps import resolve_agent

        return True, "App modules can be imported"
    except ImportError as e:
        return False, f"Import error: {e}"


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("AI DB Advisor - Test Environment Validation")
    print("=" * 60)
    print()

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Directory Structure", check_directory_structure),
        ("Test Files", check_test_files),
        ("Pytest Config", check_pytest_config),
        ("App Imports", check_app_imports),
    ]

    results = []
    all_passed = True

    for name, check_func in checks:
        try:
            passed, message = check_func()
            status = "✓ PASS" if passed else "✗ FAIL"
            results.append((name, status, message))

            if not passed:
                all_passed = False
        except Exception as e:
            results.append((name, "✗ ERROR", str(e)))
            all_passed = False

    # Print results
    max_name_len = max(len(name) for name, _, _ in results)
    for name, status, message in results:
        padding = " " * (max_name_len - len(name))
        print(f"{name}{padding} ... {status}")
        if not status.startswith("✓"):
            print(f"  {message}")

    print()
    print("=" * 60)

    if all_passed:
        print("✓ All checks passed! You're ready to run tests.")
        print()
        print("Run tests with:")
        print("  pytest")
        print("  pytest -v")
        print("  pytest --cov=app --cov-report=html")
        print()
        sys.exit(0)
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print()
        print("Quick fixes:")
        print("  pip install -r requirements.txt")
        print("  cd app  # Make sure you're in the app directory")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()