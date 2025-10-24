# AI DB Advisor - Test Suite

Comprehensive test suite for the AI Database Performance Advisor application.

## Test Structure

```
tests/
├── __init__.py                 # Tests package
├── conftest.py                 # Shared fixtures and configuration
├── test_api_datasources.py     # Datasource management API tests
├── test_api_analyze.py         # Query analysis API tests
├── test_ui.py                  # FastUI page integration tests
├── test_e2e_workflows.py       # End-to-end workflow tests
├── test_utils.py               # Utility function unit tests
└── README.md                   # This file
```

## Running Tests

### Run All Tests
```bash
# From the app directory
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=app --cov-report=html
```

### Run Specific Test Files
```bash
# Datasource API tests
pytest tests/test_api_datasources.py

# Analyze API tests
pytest tests/test_api_analyze.py

# UI tests
pytest tests/test_ui.py

# E2E workflow tests
pytest tests/test_e2e_workflows.py

# Utility tests
pytest tests/test_utils.py
```

### Run Specific Test Classes or Functions
```bash
# Run a specific test class
pytest tests/test_api_datasources.py::TestDataSourcesAPI

# Run a specific test function
pytest tests/test_api_datasources.py::TestDataSourcesAPI::test_register_datasource_success

# Run tests matching a pattern
pytest -k "test_register"
```

### Run Tests by Marker
```bash
# Run only UI tests
pytest -m ui

# Run only integration tests
pytest -m integration

# Run only e2e tests
pytest -m e2e
```

## Test Coverage

### API Tests (test_api_datasources.py)
- ✅ Healthcheck endpoint
- ✅ Root endpoint
- ✅ List datasources (empty and populated)
- ✅ Register datasource (success, duplicate, missing fields)
- ✅ Multiple datasource registration
- ✅ Different engine name variations

### API Tests (test_api_analyze.py)
- ✅ Get database schema
- ✅ Get top queries (default and custom limits)
- ✅ EXPLAIN query (with and without ANALYZE)
- ✅ Get database locks
- ✅ Get database statistics
- ✅ Index advisor recommendations
- ✅ Query rewrite recommendations
- ✅ Hypothetical index creation
- ✅ AI-powered recommendations
- ✅ AI EXPLAIN interpretation
- ✅ Non-existent datasource handling

### UI Tests (test_ui.py)
- ✅ HTML shell serving
- ✅ Home page rendering
- ✅ Datasources page (empty and populated)
- ✅ Analyze page (with and without datasources)
- ✅ Dashboard page with statistics
- ✅ EXPLAIN query page
- ✅ Recommendations page (rule-based and AI)
- ✅ Navigation buttons presence
- ✅ Invalid datasource handling

### E2E Workflow Tests (test_e2e_workflows.py)
- ✅ Complete new user workflow
- ✅ UI navigation workflow
- ✅ AI recommendations workflow
- ✅ Multiple datasources workflow
- ✅ Query optimization cycle
- ✅ Error handling workflow
- ✅ Performance monitoring workflow

### Utility Tests (test_utils.py)
- ✅ SQL predicate mining (WHERE, ORDER BY, GROUP BY)
- ✅ Column projection
- ✅ Query plan comparison
- ✅ Configuration validation

## Test Fixtures

### Available Fixtures (conftest.py)

- **client**: FastAPI test client with clean state
- **mock_postgres_agent**: Mock PostgreSQL agent for testing without database
- **sample_datasource**: Sample datasource configuration
- **sample_sql**: Collection of sample SQL queries
- **mock_llm_client**: Mock LLM client for AI testing

## Test Data

### Mock Data Provided

**Database Schema:**
- `public.users` table (id, name, email, created_at)
- `public.orders` table (id, user_id, amount, status)

**Sample Queries:**
- Simple SELECT with WHERE
- Complex JOIN with GROUP BY
- Query with OFFSET pagination
- SELECT * query

**Mock Statistics:**
- Database size: 1GB
- Active backends: 5
- Lock information
- Top queries with execution stats

## Writing New Tests

### Test File Template
```python
import pytest
from fastapi import status
from unittest.mock import patch

class TestYourFeature:
    """Test suite for your feature"""

    def test_your_functionality(self, client):
        """Test description"""
        response = client.get("/your-endpoint")
        assert response.status_code == status.HTTP_200_OK
```

### Using Mocks
```python
@patch('app.deps.get_agent_for')
def test_with_mock_agent(self, mock_get_agent, client, mock_postgres_agent):
    mock_get_agent.return_value = mock_postgres_agent
    # Your test code here
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Clean State**: Use fixtures to ensure clean state before each test
3. **Descriptive Names**: Test names should clearly describe what is being tested
4. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
5. **Mock External Dependencies**: Use mocks for database and LLM interactions
6. **Test Edge Cases**: Include tests for error conditions and boundary cases

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Common Issues

**Import Errors:**
- Ensure you're running pytest from the `app` directory
- Check that `__init__.py` files exist in test directories

**Fixture Not Found:**
- Verify fixtures are defined in `conftest.py`
- Check fixture scope (function, class, module, session)

**Mock Not Working:**
- Ensure you're patching the correct import path
- Use `patch` decorator or context manager correctly

## Additional Tools

### Recommended Packages
```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

### Coverage Report
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View report
# Open htmlcov/index.html in browser
```

### Test Performance
```bash
# Show slowest tests
pytest --durations=10

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```