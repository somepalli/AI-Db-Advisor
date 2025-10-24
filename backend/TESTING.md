# Testing Guide for AI DB Advisor

Complete guide for testing the AI Database Performance Advisor application.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
cd app
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test suite
pytest tests/test_api_datasources.py
```

## Test Organization

### Test Files

| File | Purpose | Test Count |
|------|---------|------------|
| `test_api_datasources.py` | Datasource management API | 8+ tests |
| `test_api_analyze.py` | Query analysis endpoints | 15+ tests |
| `test_ui.py` | FastUI page rendering | 12+ tests |
| `test_e2e_workflows.py` | End-to-end workflows | 7+ tests |
| `test_utils.py` | Utility functions | 15+ tests |

### Test Categories

**Unit Tests** - Individual function testing
- SQL parsing utilities
- Query plan comparison
- Configuration validation

**Integration Tests** - API endpoint testing
- Datasource registration
- Query analysis
- Recommendations generation

**UI Tests** - FastUI page testing
- Page rendering
- Component presence
- Navigation flow

**E2E Tests** - Complete workflow testing
- User journeys
- Multi-step operations
- Error scenarios

## Running Tests

### Basic Commands

```bash
# All tests with verbose output
pytest -v

# Specific test file
pytest tests/test_api_datasources.py

# Specific test class
pytest tests/test_api_datasources.py::TestDataSourcesAPI

# Specific test function
pytest tests/test_api_datasources.py::TestDataSourcesAPI::test_register_datasource_success

# Tests matching pattern
pytest -k "datasource"
```

### Advanced Options

```bash
# Run with coverage report
pytest --cov=app --cov-report=html --cov-report=term-missing

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run last failed tests
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto

# Show slowest tests
pytest --durations=10

# Quiet mode (less verbose)
pytest -q
```

### Custom Test Runner

```bash
# Using the custom runner script
python run_tests.py                  # Run all tests
python run_tests.py --coverage       # With coverage
python run_tests.py --ui             # Only UI tests
python run_tests.py --e2e            # Only E2E tests
python run_tests.py --quick          # Skip slow tests
```

## Test Coverage Report

### Functional Coverage

#### Datasource Management
- ✅ Register new datasource
- ✅ List all datasources
- ✅ Duplicate ID prevention
- ✅ Validation of required fields
- ✅ Multiple datasource support
- ✅ Engine name variations (postgres/postgresql/pg)

#### Query Analysis
- ✅ Database schema retrieval
- ✅ Top queries by execution time
- ✅ EXPLAIN plan generation
- ✅ EXPLAIN ANALYZE support
- ✅ Database locks monitoring
- ✅ Statistics collection
- ✅ Custom query limits

#### Recommendations
- ✅ Index recommendations
- ✅ Query rewrite suggestions
- ✅ Hypothetical index testing
- ✅ Plan comparison
- ✅ AI-powered suggestions
- ✅ AI EXPLAIN interpretation

#### UI Pages
- ✅ Home page with features
- ✅ Datasource management page
- ✅ Analyzer page with selector
- ✅ Performance dashboard
- ✅ EXPLAIN query interface
- ✅ Recommendations page
- ✅ Navigation between pages

#### Error Handling
- ✅ Non-existent datasource
- ✅ Invalid SQL queries
- ✅ Missing required fields
- ✅ Duplicate registrations
- ✅ Database connection errors
- ✅ LLM unavailability

### Code Coverage Target

- **Target**: 80%+ coverage
- **Current**: Run `pytest --cov=app` to check
- **Critical paths**: 100% coverage for API endpoints

## Test Data & Fixtures

### Mock Data Available

```python
# Sample datasource
{
    "id": "test-pg",
    "engine": "postgres",
    "dsn": "postgresql://user:pass@localhost:5432/testdb"
}

# Sample SQL queries
{
    "simple": "SELECT * FROM users WHERE email = 'test@example.com'",
    "complex": "SELECT u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o...",
    "with_offset": "SELECT * FROM users ORDER BY id OFFSET 1000 LIMIT 10",
    "select_star": "SELECT * FROM users"
}

# Mock database schema
{
    "tables": {
        "public.users": [
            {"column": "id", "type": "integer", "nullable": "NO"},
            {"column": "name", "type": "varchar", "nullable": "YES"},
            ...
        ]
    }
}
```

### Using Fixtures

```python
def test_with_datasource(client, sample_datasource):
    """Use pre-configured test datasource"""
    client.post("/datasources", json=sample_datasource)
    # Test code here

@patch('app.deps.get_agent_for')
def test_with_mock_agent(mock_get_agent, mock_postgres_agent):
    """Use mock PostgreSQL agent"""
    mock_get_agent.return_value = mock_postgres_agent
    # No real database needed
```

## API Testing Examples

### Test Datasource Registration

```python
def test_register_datasource(client):
    payload = {
        "id": "my-db",
        "engine": "postgres",
        "dsn": "postgresql://localhost/mydb"
    }
    response = client.post("/datasources", json=payload)
    assert response.status_code == 201
    assert response.json()["id"] == "my-db"
```

### Test Query Analysis

```python
@patch('app.deps.get_agent_for')
def test_explain_query(mock_get_agent, client, mock_postgres_agent):
    mock_get_agent.return_value = mock_postgres_agent

    payload = {"sql": "SELECT * FROM users", "analyze": False}
    response = client.post("/analyze/test-pg/explain", json=payload)

    assert response.status_code == 200
    assert "plan" in response.json()
```

### Test UI Pages

```python
def test_home_page(client):
    response = client.get("/ui/pages/home")
    assert response.status_code == 200

    data = response.json()
    assert data[0]["type"] == "Page"
    assert data[0]["title"] == "AI DB Advisor"
```

## E2E Workflow Testing

### Complete User Journey

```python
def test_complete_workflow(client, sample_datasource, mock_postgres_agent):
    """Test from registration to recommendations"""

    # 1. Register datasource
    client.post("/datasources", json=sample_datasource)

    # 2. Get schema
    schema = client.get(f"/analyze/{ds_id}/schema").json()
    assert "tables" in schema

    # 3. Run EXPLAIN
    payload = {"sql": "SELECT * FROM users", "analyze": False}
    plan = client.post(f"/analyze/{ds_id}/explain", json=payload).json()
    assert "plan" in plan

    # 4. Get recommendations
    recs = client.post(f"/analyze/{ds_id}/advise/index", json=payload).json()
    assert isinstance(recs, list)
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests with coverage
        run: |
          cd app
          pytest --cov=app --cov-report=xml --cov-report=term

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./app/coverage.xml
          fail_ci_if_error: true
```

## Troubleshooting

### Common Issues

**ImportError: No module named 'app'**
```bash
# Solution: Run pytest from the app directory
cd app
pytest
```

**Fixture 'mock_postgres_agent' not found**
```bash
# Solution: Ensure conftest.py is in tests/ directory
ls tests/conftest.py
```

**Tests fail with database connection error**
```bash
# Solution: Tests use mocks, ensure patches are applied
# Check @patch decorators are correct
```

**Coverage report not generated**
```bash
# Solution: Install pytest-cov
pip install pytest-cov

# Run with coverage flags
pytest --cov=app --cov-report=html
```

### Debug Failed Tests

```bash
# Show full error traceback
pytest --tb=long

# Drop into debugger on failure
pytest --pdb

# Show print statements
pytest -s

# Verbose output with local variables
pytest -vv -l
```

## Best Practices

### Writing Tests

1. **Use descriptive names**
   ```python
   def test_register_datasource_with_invalid_dsn_returns_400():
       # Clear what is being tested
   ```

2. **Follow AAA pattern** (Arrange, Act, Assert)
   ```python
   def test_example():
       # Arrange
       payload = {"id": "test"}

       # Act
       response = client.post("/endpoint", json=payload)

       # Assert
       assert response.status_code == 200
   ```

3. **One assertion per test** (when possible)
   ```python
   def test_response_status():
       assert response.status_code == 200

   def test_response_content():
       assert "key" in response.json()
   ```

4. **Use fixtures for setup**
   ```python
   @pytest.fixture
   def prepared_database(client):
       # Setup code
       yield client
       # Teardown code
   ```

5. **Mock external dependencies**
   ```python
   @patch('app.services.ai_client.LLMClient')
   def test_ai_feature(mock_llm):
       # Test without actual LLM calls
   ```

### Performance

- Keep tests fast (<1s each)
- Use mocks instead of real databases
- Parallelize with pytest-xdist
- Skip slow tests in development

### Maintenance

- Update tests when API changes
- Keep test data realistic
- Document complex test scenarios
- Review coverage reports regularly

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

## Support

For issues or questions about testing:
1. Check this documentation
2. Review test examples in `tests/` directory
3. Check pytest output for error messages
4. Review CI/CD logs if applicable