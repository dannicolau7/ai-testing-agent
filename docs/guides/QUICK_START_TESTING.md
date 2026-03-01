# ⚡ Quick Start - Run Tests in 30 Seconds

## 🎯 The Simplest Way (RECOMMENDED)

Just run this ONE command from your terminal:

```bash
./run_tests.sh
```

That's it! The script handles everything automatically.

---

## 🔧 If You Get Errors, Follow These Steps:

### Step 1: Make sure you're in the right directory
```bash
# First, navigate to the project folder
cd /Users/dann24/ai-testing-agent/files\ \(1\)

# Verify you're in the right place (you should see run_tests.sh)
ls run_tests.sh
```

### Step 2: Run the automated test script
```bash
./run_tests.sh
```

---

## 📝 Manual Method (If Script Doesn't Work)

### Option A: From project root
```bash
# 1. Make sure you're in project root
cd /Users/dann24/ai-testing-agent/files\ \(1\)

# 2. Navigate to test_output
cd test_output

# 3. Run pytest
pytest test_TC*.py -v
```

### Option B: All in one command
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output && pytest test_TC*.py -v
```

---

## 🚨 Common Error: "file or directory not found: pytest"

This happens when you type the command incorrectly. Here's what's WRONG vs RIGHT:

### ❌ WRONG
```bash
pytest pytest test_TC*.py   # Don't type pytest twice!
pytest                       # This looks for a file named "pytest"
```

### ✅ RIGHT
```bash
# First go to the test_output directory
cd test_output

# Then run pytest with the test files
pytest test_TC*.py -v
```

Or all in one line:
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output && pytest test_TC*.py -v
```

---

## 🆘 Troubleshooting

### Problem: "pytest: command not found"
**Solution:** Install pytest first
```bash
pip install pytest
```

### Problem: "ERROR: file or directory not found: pytest"
**Solution:** You're typing the command wrong. Use this instead:
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output
pytest test_TC*.py -v
```

### Problem: "No tests collected"
**Solution:** You're not in the right directory
```bash
# Go to test_output folder first
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output

# List test files (should show test_TC*.py files)
ls test_TC*.py

# Now run tests
pytest test_TC*.py -v
```

---

## 📋 Copy-Paste Commands (100% Working)

### Command 1: Easiest (Automated)
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\) && ./run_tests.sh
```

### Command 2: Manual Method
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output && pytest test_TC*.py -v
```

### Command 3: Run One File Only
```bash
cd /Users/dann24/ai-testing-agent/files\ \(1\)/test_output && pytest test_TC201.py -v
```

---

## ✅ What Success Looks Like

When tests run successfully, you'll see:
```
=================================================================== test session starts ===================================================================
platform darwin -- Python 3.12.7, pytest-7.4.3, pluggy-1.0.0
collecting ... collected 19 items

test_TC001.py::TestValidLogin::test_login_with_valid_credentials PASSED    [  5%]
test_TC001.py::TestValidLogin::test_login_returns_jwt_token PASSED         [ 10%]
...
=================================================================== 19 passed in 0.25s ====================================================================
```

---

## 💡 Pro Tip

**Save yourself time - just use the automated script:**
```bash
./run_tests.sh
```

It's already configured to work perfectly!
