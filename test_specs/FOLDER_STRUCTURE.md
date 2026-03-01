# 📂 Folder Structure - Where Everything Is Located

## 📍 Generated Test Code Location

**All generated test code is in:** `/test_output/`

```
test_output/
├── test_TC201.py         ← Generated Stripe test #1 (1.1 KB)
├── test_TC202.py         ← Generated Stripe test #2 (1.5 KB)
├── test_TC203.py         ← Generated Stripe test #3 (1.9 KB)
├── test_TC204.py         ← Generated Stripe test #4 (1.1 KB)
├── test_report.html      ← Test report with analytics
└── __pycache__/          ← Python cache files
```

## 🗂️ Complete Project Structure

```
ai-testing-agent/files (1)/
│
├── test_specs/                    ← INPUT: Test specifications
│   ├── test_stripe_api_keys.txt  ← Your API specification
│   ├── run_stripe_test.sh        ← Automation script
│   ├── README.md                 ← Documentation
│   └── FOLDER_STRUCTURE.md       ← This file
│
├── test_output/                   ← OUTPUT: Generated tests
│   ├── test_TC201.py             ← ✨ NEW: Stripe tests
│   ├── test_TC202.py             ← ✨ NEW: Stripe tests
│   ├── test_TC203.py             ← ✨ NEW: Stripe tests
│   ├── test_TC204.py             ← ✨ NEW: Stripe tests
│   └── test_report.html          ← ✨ NEW: HTML report
│
├── cli.py                         ← Main CLI tool
├── ai_testing_agent.py           ← Core engine
└── ...other project files

```

## 🎯 Quick Access Commands

### View Generated Test Code
```bash
# Navigate to test output folder
cd test_output

# List all generated test files
ls -lh test_TC*.py

# View specific test file
cat test_TC201.py
# or
code test_TC201.py  # Open in VS Code
```

### Open in VS Code
```bash
# Open entire test_output folder
code test_output/

# Open specific test file
code test_output/test_TC201.py
```

### View Test Report
```bash
# macOS
open test_output/test_report.html

# Linux
xdg-open test_output/test_report.html

# Windows
start test_output/test_report.html
```

## 🔄 Workflow

1. **Input** → Create spec in `test_specs/`
2. **Process** → Run `python cli.py run test_specs/your_file.txt`
3. **Output** → Find generated tests in `test_output/`

---

📌 **Remember:** All generated Python test files are always saved in `test_output/`
