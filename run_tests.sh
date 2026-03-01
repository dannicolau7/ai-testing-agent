#!/bin/bash
# Test Runner Script - Executes all generated tests from test_output/

echo "🧪 AI Testing Agent - Test Runner"
echo "=================================="
echo ""

# Navigate to test_output directory
cd "$(dirname "$0")/test_output" || exit 1

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "⚠️  pytest not found. Installing pytest..."
    pip install pytest pytest-html pytest-cov
    echo ""
fi

# Count test files
TEST_COUNT=$(ls test_TC*.py 2>/dev/null | wc -l | tr -d ' ')
echo "📋 Found $TEST_COUNT test files"
echo ""

# List test files
echo "📝 Test files to run:"
ls -1 test_TC*.py 2>/dev/null | sed 's/^/  ✓ /'
echo ""

# Run pytest with verbose output
echo "🚀 Running tests..."
echo "===================="
echo ""

# Try to run with HTML report if pytest-html is available
if python -c "import pytest_html" 2>/dev/null; then
    pytest test_TC*.py \
        -v \
        --tb=short \
        --color=yes \
        --html=pytest_report.html \
        --self-contained-html \
        2>&1
else
    # Run without HTML report
    pytest test_TC*.py \
        -v \
        --tb=short \
        --color=yes \
        2>&1
fi

EXIT_CODE=$?

echo ""
echo "===================="
echo "📊 Test Results"
echo "===================="

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
elif [ $EXIT_CODE -eq 5 ]; then
    echo "⚠️  No tests collected"
else
    echo "❌ Some tests failed (exit code: $EXIT_CODE)"
fi

echo ""
echo "📈 Reports generated:"
echo "  • pytest_report.html (detailed pytest report)"
echo "  • test_report.html (AI analysis report)"
echo ""
echo "💡 View reports:"
echo "  open test_output/pytest_report.html"
echo "  open test_output/test_report.html"

exit $EXIT_CODE
