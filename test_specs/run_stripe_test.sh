#!/bin/bash
# Automation script to run Stripe API tests

echo "🚀 Starting Stripe API Test Generation..."
echo "=========================================="

# Navigate to project directory
cd "$(dirname "$0")/.." || exit 1

# Check if test spec file exists
if [ ! -f "test_specs/test_stripe_api_keys.txt" ]; then
    echo "❌ Error: test_stripe_api_keys.txt not found!"
    exit 1
fi

# Run the AI testing agent
echo "📝 Analyzing Stripe API specification..."
python cli.py run test_specs/test_stripe_api_keys.txt

# Check if tests were generated
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test generation completed successfully!"
    echo ""
    echo "📊 Generated files:"
    ls -lh test_output/test_TC*.py 2>/dev/null | tail -4
    echo ""
    echo "📈 View the test report at: test_output/test_report.html"
    echo ""
    echo "💡 To run the generated tests:"
    echo "   cd test_output && pytest test_TC*.py -v"
else
    echo "❌ Test generation failed!"
    exit 1
fi
