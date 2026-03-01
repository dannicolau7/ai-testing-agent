#!/bin/bash

echo "🤖 Running All Test Examples"
echo "============================"
echo ""

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo "Run: export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

export TESTING_MODE='true'

echo "1️⃣  Simple Login API..."
python cli.py run test_data/01_simple_login.txt --output test_outputs/simple_login/
echo ""

echo "2️⃣  E-commerce Login API..."
python cli.py run test_data/02_ecommerce_login.txt --output test_outputs/ecommerce/
echo ""

echo "3️⃣  Payment API..."
python cli.py run test_data/03_payment_api.txt --output test_outputs/payments/
echo ""

echo "4️⃣  User CRUD API..."
python cli.py run test_data/04_user_crud.txt --output test_outputs/users/
echo ""

echo "5️⃣  Weather API..."
python cli.py run test_data/05_weather_api.txt --output test_outputs/weather/
echo ""

echo "✅ All tests complete!"
echo ""
echo "Results:"
ls -la test_outputs/
