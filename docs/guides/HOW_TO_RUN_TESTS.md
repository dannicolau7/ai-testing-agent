# 🚀 How to Run Tests Manually

## Option 1: Use the Automated Script (Easiest)

```bash
# From project root
./run_tests.sh
```

## Option 2: Run with Pytest Directly

### Run ALL tests
```bash
cd test_output
pytest test_TC*.py -v
```

### Run specific test file
```bash
cd test_output
pytest test_TC201.py -v
```

### Run tests with different verbosity levels
```bash
cd test_output

# Quiet mode
pytest test_TC*.py -q

# Normal mode
pytest test_TC*.py

# Verbose mode
pytest test_TC*.py -v

# Very verbose mode
pytest test_TC*.py -vv
```

### Run with additional options
```bash
cd test_output

# Show test duration
pytest test_TC*.py -v --durations=10

# Stop on first failure
pytest test_TC*.py -v -x

# Show local variables on failure
pytest test_TC*.py -v -l

# Run last failed tests only
pytest test_TC*.py -v --lf

# Show print statements
pytest test_TC*.py -v -s
```

## Option 3: Run with Python Directly

```bash
cd test_output

# Run pytest as Python module
python -m pytest test_TC*.py -v

# Run specific test file
python -m pytest test_TC201.py -v
```

## Option 4: Run Individual Test Classes/Functions

```bash
cd test_output

# Run specific test class
pytest test_TC001.py::TestValidLogin -v

# Run specific test function
pytest test_TC001.py::TestValidLogin::test_login_with_valid_credentials -v

# Run multiple specific tests
pytest test_TC001.py::TestValidLogin::test_login_with_valid_credentials \
       test_TC002.py::TestInvalidLogin::test_login_with_incorrect_password -v
```

## Option 5: Run from Project Root (Without cd)

```bash
# From project root directory
pytest test_output/test_TC*.py -v

# Specific file
pytest test_output/test_TC201.py -v

# Specific test
pytest test_output/test_TC001.py::TestValidLogin::test_login_with_valid_credentials -v
```

## Option 6: Run with Pattern Matching

```bash
cd test_output

# Run tests matching a pattern in name
pytest test_TC*.py -v -k "login"

# Run tests matching multiple patterns
pytest test_TC*.py -v -k "login or password"

# Run tests NOT matching a pattern
pytest test_TC*.py -v -k "not slow"
```

## Option 7: Generate HTML Report

```bash
cd test_output

# Install pytest-html if not installed
pip install pytest-html

# Run with HTML report
pytest test_TC*.py -v --html=report.html --self-contained-html
```

## Option 8: Run with Coverage Report

```bash
cd test_output

# Install pytest-cov if not installed
pip install pytest-cov

# Run with coverage
pytest test_TC*.py -v --cov=. --cov-report=html
```

## Quick Reference Table

| What You Want | Command |
|---------------|---------|
| Run all tests (easiest) | `./run_tests.sh` |
| Run all tests manually | `cd test_output && pytest test_TC*.py -v` |
| Run one test file | `cd test_output && pytest test_TC201.py -v` |
| Run specific test | `cd test_output && pytest test_TC001.py::TestValidLogin::test_login_with_valid_credentials -v` |
| Stop on first fail | `cd test_output && pytest test_TC*.py -v -x` |
| Show print statements | `cd test_output && pytest test_TC*.py -v -s` |
| Generate HTML report | `cd test_output && pytest test_TC*.py -v --html=report.html --self-contained-html` |

## Step-by-Step Example

```bash
# 1. Open terminal
# 2. Navigate to project directory
cd /Users/dann24/ai-testing-agent/files\ \(1\)

# 3. Go to test_output folder
cd test_output

# 4. Run tests
pytest test_TC*.py -v

# 5. View results in terminal
```

## Common Issues & Solutions

### Issue: "pytest: command not found"
```bash
# Solution: Install pytest
pip install pytest
```

### Issue: "No tests collected"
```bash
# Solution: Make sure you're in the right directory
cd test_output
ls test_TC*.py  # Should list test files
```

### Issue: Tests fail with import errors
```bash
# Solution: Make sure you're in the correct directory
cd test_output
pytest test_TC*.py -v
```

## Pro Tips

1. **Add aliases to your shell profile** (~/.zshrc or ~/.bashrc):
   ```bash
   alias runtests='cd /Users/dann24/ai-testing-agent/files\ \(1\) && ./run_tests.sh'
   alias pytest-all='cd test_output && pytest test_TC*.py -v'
   ```

2. **Create a Makefile** in project root:
   ```makefile
   test:
       ./run_tests.sh
   
   test-manual:
       cd test_output && pytest test_TC*.py -v
   
   test-one:
       cd test_output && pytest $(FILE) -v
   ```
   
   Then run: `make test` or `make test-one FILE=test_TC201.py`

3. **Use watch mode** (requires pytest-watch):
   ```bash
   pip install pytest-watch
   cd test_output
   ptw test_TC*.py -v  # Auto-runs tests on file changes
   ```

---

**Recommendation:** Use `./run_tests.sh` for the best experience with automatic setup and reporting!
