# Quick Start - Testing Guide

## Setup (First Time Only)

```bash
# 1. Navigate to project root
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor

# 2. Install test dependencies
pip install -r requirements.txt

# This installs:
# - pytest (test framework)
# - pytest-cov (coverage reports)
# - pytest-asyncio (async test support)
# - pytest-mock (mocking utilities)
```

## Running Tests

### Option 1: Run from Project Root
```bash
# Navigate to project root
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor

# Run all tests
python -m pytest .venv/app/tests -v

# With coverage
python -m pytest .venv/app/tests --cov=.venv/app --cov-report=html
```

### Option 2: Run from App Directory
```bash
# Navigate to app directory
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\.venv\app

# Run all tests
pytest tests/ -v

# With coverage
pytest --cov=. --cov-report=html tests/
```

### Option 3: Using Custom Runner
```bash
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\.venv\app
python run_tests.py --verbose --coverage
```

## Quick Validation

Before running tests, check if everything is set up:

```bash
# Check if pytest is installed
pytest --version

# Check if tests can be discovered
pytest --collect-only

# Run a single test to verify
pytest tests/test_api_datasources.py::TestDataSourcesAPI::test_healthcheck -v
```

## Test Suite Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_api_datasources.py        # API: Datasource management (8 tests)
├── test_api_analyze.py            # API: Query analysis (15+ tests)
├── test_ui.py                     # UI: Page rendering (12 tests)
├── test_e2e_workflows.py          # E2E: User workflows (7 tests)
└── test_utils.py                  # Unit: Utilities (15 tests)
```

## Expected Output

### Successful Test Run
```
============================= test session starts =============================
platform win32 -- Python 3.13.x, pytest-8.x.x
collected 57 items

tests/test_api_datasources.py::TestDataSourcesAPI::test_healthcheck PASSED [ 1%]
tests/test_api_datasources.py::TestDataSourcesAPI::test_root_endpoint PASSED [ 3%]
...
tests/test_utils.py::TestConfigValidation::test_settings_env_variable PASSED [100%]

======================== 57 passed in 2.54s ===============================
```

### With Coverage
```
Name                              Stmts   Miss  Cover
-----------------------------------------------------
app/main.py                         20      2    90%
app/routers/analyze.py              80      5    94%
app/routers/datasources.py          15      0   100%
app/routers/ui.py                  250     15    94%
...
-----------------------------------------------------
TOTAL                              672     39    94%
```

## Common Commands

```bash
# Run specific test file
pytest tests/test_api_datasources.py

# Run specific test
pytest tests/test_api_datasources.py::TestDataSourcesAPI::test_register_datasource_success

# Run tests matching pattern
pytest -k "datasource"

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Verbose output
pytest -vv

# Generate HTML coverage report
pytest --cov=. --cov-report=html
# Then open htmlcov/index.html in browser
```

## Troubleshooting

### Issue: "pytest: command not found"
**Solution:**
```bash
pip install pytest
# or
python -m pytest
```

### Issue: "ModuleNotFoundError: No module named 'app'"
**Solution:**
```bash
# Make sure you're running from the correct directory
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\.venv\app
pytest tests/

# Or use absolute imports
python -m pytest .venv/app/tests -v
```

### Issue: "No tests collected"
**Solution:**
```bash
# Check test discovery
pytest --collect-only

# Ensure test files start with "test_"
ls tests/test_*.py
```

### Issue: "Fixture 'client' not found"
**Solution:**
```bash
# Ensure conftest.py exists in tests directory
ls tests/conftest.py

# Run from correct directory
cd .venv/app
pytest tests/
```

## What Tests Cover

### ✅ API Endpoints
- Datasource registration and listing
- Query analysis (EXPLAIN, top queries, locks, stats)
- Index and rewrite recommendations
- Hypothetical index testing
- AI-powered suggestions

### ✅ UI Pages
- Home page with features
- Datasource management
- Query analyzer with selector
- Performance dashboard
- EXPLAIN query interface
- Recommendations page

### ✅ Workflows
- New user onboarding
- Query optimization cycle
- AI recommendations flow
- Multiple datasource management
- Error handling scenarios

### ✅ Utilities
- SQL parsing and predicate mining
- Query plan comparison
- Configuration validation

## Test Data

All tests use mock data - **no real database required**!

- Mock PostgreSQL agent
- Sample datasource configurations
- Sample SQL queries
- Mock execution plans and statistics

## Next Steps

1. **Run validation**: `python validate_setup.py`
2. **Run all tests**: `pytest -v`
3. **Check coverage**: `pytest --cov=. --cov-report=html`
4. **Review report**: Open `htmlcov/index.html`

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Run Tests
  run: |
    pip install -r requirements.txt
    cd .venv/app
    pytest --cov=. --cov-report=xml
```

## Documentation

- **TESTING.md** - Complete testing guide (detailed)
- **TEST_SUMMARY.md** - Test suite summary (overview)
- **tests/README.md** - Test directory README
- **QUICKSTART_TESTING.md** - This file (quick reference)

---

**Ready to test?** Run: `pytest -v`