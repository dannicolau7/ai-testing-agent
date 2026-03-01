#!/bin/bash

# Run a single test example

if [ -z "$1" ]; then
    echo "Usage: ./run_single_test.sh <number>"
    echo ""
    echo "Available tests:"
    echo "  1 - Simple Login"
    echo "  2 - E-commerce Login"
    echo "  3 - Payment API"
    echo "  4 - User CRUD"
    echo "  5 - Weather API"
    exit 1
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo "Run: export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

export TESTING_MODE='true'

case $1 in
    1)
        echo "🧪 Testing: Simple Login API"
        python cli.py run test_data/01_simple_login.txt --output test_outputs/simple_login/
        ;;
    2)
        echo "🧪 Testing: E-commerce Login API"
        python cli.py run test_data/02_ecommerce_login.txt --output test_outputs/ecommerce/
        ;;
    3)
        echo "🧪 Testing: Payment API"
        python cli.py run test_data/03_payment_api.txt --output test_outputs/payments/
        ;;
    4)
        echo "🧪 Testing: User CRUD API"
        python cli.py run test_data/04_user_crud.txt --output test_outputs/users/
        ;;
    5)
        echo "🧪 Testing: Weather API"
        python cli.py run test_data/05_weather_api.txt --output test_outputs/weather/
        ;;
    *)
        echo "❌ Invalid test number. Use 1-5"
        exit 1
        ;;
esac

echo ""
echo "✅ Test complete! Check: test_outputs/"
