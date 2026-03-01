# 📊 How to See Extra Information About Test Runs

## 🎯 Quick Options

### 1. View the AI-Generated HTML Report (Already Created!)
```bash
# This report was automatically created when you ran the tests
open test_output/test_report.html
```

**What's inside:**
- Test summary and statistics
- AI analysis and insights
- Coverage analysis
- Risk assessment
- Recommendations
- Edge case detection

---

## 🔍 Get More Details When Running Tests

### Option 1: Very Verbose Output
```bash
cd test_output

# Double verbose (-vv) - Shows more detail
pytest test_TC*.py -vv

# Triple verbose (-vvv) - Shows EVERYTHING
pytest test_TC*.py -vvv
```

### Option 2: Show Print Statements
```bash
cd test_output

# Shows all print() statements in your tests
pytest test_TC*.py -v -s
```

### Option 3: Show Test Duration
```bash
cd test_output

# Shows how long each test took
pytest test_TC*.py -v --durations=10

# Show ALL test durations
pytest test_TC*.py -v --durations=0
```

### Option 4: Show Local Variables on Failures
```bash
cd test_output

# If any test fails, shows all variable values
pytest test_TC*.py -v -l
```

### Option 5: Show Full Traceback
```bash
cd test_output

# Short traceback (default)
pytest test_TC*.py -v --tb=short

# Long traceback (more detail)
pytest test_TC*.py -v --tb=long

# No traceback
pytest test_TC*.py -v --tb=no

# Line-only traceback
pytest test_TC*.py -v --tb=line
```

---

## 📈 Generate Detailed HTML Reports

### Option 1: Generate Pytest HTML Report
```bash
cd test_output

# Install pytest-html if needed
pip install pytest-html

# Generate HTML report
pytest test_TC*.py -v --html=detailed_report.html --self-contained-html

# Open the report
open detailed_report.html
```

### Option 2: Generate Coverage Report
```bash
cd test_output

# Install pytest-cov if needed
pip install pytest-cov

# Generate coverage report
pytest test_TC*.py -v --cov=. --cov-report=html

# Open the coverage report
open htmlcov/index.html
```

### Option 3: Generate JUnit XML Report (for CI/CD)
```bash
cd test_output

# Generate XML report
pytest test_TC*.py -v --junitxml=junit_report.xml

# View with text editor
cat junit_report.xml
```

---

## 🎨 Combine Multiple Options

### Super Detailed Run
```bash
cd test_output

pytest test_TC*.py \
    -vv \
    -s \
    --durations=10 \
    -l \
    --tb=long \
    --html=full_report.html \
    --self-contained-html
```

### Quick Summary with Key Info
```bash
cd test_output

pytest test_TC*.py -v --durations=5 --tb=short
```

---

## 📋 View Different Reports

### Report 1: AI Test Report (Already Exists!)
```bash
# View the AI-generated analysis
open test_output/test_report.html
```

**Contains:**
- Test summary
- Requirements analysis
- Test coverage percentage
- AI recommendations
- Risk assessment
- Missing scenarios

### Report 2: Check Test Files Directly
```bash
# See what tests exist
ls -lh test_output/test_TC*.py

# View a specific test file
cat test_output/test_TC001.py

# Or open in editor
nano test_output/test_TC001.py
```

### Report 3: Pytest Cache Info
```bash
cd test_output

# Show last failed tests
pytest --lf -v

# Show last run stats
pytest --cache-show
```

---

## 🔬 Detailed Test Information Examples

### Example 1: See Everything
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output
pytest test_TC*.py -vvv -s --durations=0
```

Output includes:
- Exact test being run
- All print statements
- Variable values
- Test duration
- Full stack traces
- Setup/teardown info

### Example 2: Failure Analysis
```bash
cd test_output
pytest test_TC*.py -vv -l --tb=long
```

Output includes:
- Detailed failure messages
- Local variable values
- Full traceback
- Line numbers

### Example 3: Performance Analysis
```bash
cd test_output
pytest test_TC*.py -v --durations=10 --durations-min=0.01
```

Output includes:
- Slowest 10 tests
- Time taken for each
- Performance insights

---

## 📊 All Reports in One Command

```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output

# Generate multiple reports at once
pytest test_TC*.py \
    -vv \
    -s \
    --durations=10 \
    --tb=long \
    --html=pytest_report.html \
    --self-contained-html \
    --junitxml=junit.xml \
    | tee test_run.log

# Now you have:
# 1. pytest_report.html - Visual HTML report
# 2. junit.xml - XML for CI/CD
# 3. test_run.log - Terminal output saved to file
```

---

## 🎯 Quick Reference Table

| What You Want to See | Command |
|---------------------|---------|
| AI analysis | `open test_output/test_report.html` |
| Very detailed output | `cd test_output && pytest test_TC*.py -vvv` |
| Print statements | `cd test_output && pytest test_TC*.py -v -s` |
| Test durations | `cd test_output && pytest test_TC*.py -v --durations=10` |
| HTML report | `cd test_output && pytest test_TC*.py -v --html=report.html --self-contained-html && open report.html` |
| Coverage report | `cd test_output && pytest test_TC*.py -v --cov=. --cov-report=html && open htmlcov/index.html` |
| Full traceback | `cd test_output && pytest test_TC*.py -v --tb=long` |
| Local variables | `cd test_output && pytest test_TC*.py -v -l` |

---

## 💡 Pro Tip: Create Aliases

Add these to your `~/.zshrc` or `~/.bashrc`:

```bash
# Quick test commands
alias test-detail='cd test_output && pytest test_TC*.py -vvv -s --durations=10'
alias test-report='cd test_output && pytest test_TC*.py -v --html=report.html --self-contained-html && open report.html'
alias test-quick='cd test_output && pytest test_TC*.py -v'
alias view-ai-report='open test_output/test_report.html'
```

Then just type:
```bash
test-detail    # Super detailed run
test-report    # Generate and open HTML report
view-ai-report # View AI analysis
```

---

## 🎬 Step-by-Step: View ALL Information

```bash
# 1. Navigate to test directory
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output

# 2. Run with maximum detail
pytest test_TC*.py -vvv -s --durations=0 --tb=long -l

# 3. Generate HTML report
pytest test_TC*.py -v --html=detailed_report.html --self-contained-html

# 4. Open HTML report
open detailed_report.html

# 5. Also view the AI analysis
open test_report.html
```

Now you have ALL the information! 🎉
