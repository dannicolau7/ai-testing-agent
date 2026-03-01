#!/bin/bash

# AI Testing Agent - Test Data Setup Script
# This creates all test examples and folder structure

echo "🤖 AI Testing Agent - Setting Up Test Data"
echo "==========================================="
echo ""

# Get current directory
BASE_DIR=$(pwd)
echo "📁 Base directory: $BASE_DIR"
echo ""

# Create directories
echo "📂 Creating directories..."
mkdir -p test_data
mkdir -p test_outputs
mkdir -p examples
echo "✅ Directories created"
echo ""

# Example 1: Simple Login API
echo "📝 Creating Example 1: Simple Login API..."
cat > test_data/01_simple_login.txt << 'EOF'
Simple Login API

Base URL: https://api.example.com

ENDPOINT: POST /api/login

Request Body:
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Success Response (200):
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "userId": "usr_123",
  "email": "user@example.com"
}

Error Responses:

400 Bad Request:
{
  "error": "Missing email or password"
}

401 Unauthorized:
{
  "error": "Invalid credentials"
}

Business Rules:
- Email must be valid format
- Password minimum 8 characters
- Return JWT token on success
- Lock account after 5 failed attempts

Test Scenarios:
1. Valid login → 200 with token
2. Missing email → 400
3. Missing password → 400
4. Invalid email format → 400
5. Wrong password → 401
6. 5 failed attempts → account locked
EOF
echo "✅ Created: test_data/01_simple_login.txt"

# Example 2: E-commerce API
echo "📝 Creating Example 2: E-commerce Login..."
cat > test_data/02_ecommerce_login.txt << 'EOF'
E-Commerce Authentication API

Base URL: https://api.shop.example.com

ENDPOINT: POST /api/auth/login

Request Body:
{
  "email": "customer@example.com",
  "password": "SecurePass123!"
}

Success Response (200):
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "usr_abc123",
    "email": "customer@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "role": "customer"
  },
  "expiresIn": 3600
}

Error Responses:

400 Bad Request:
{
  "error": "Missing required field: email"
}

401 Unauthorized:
{
  "error": "Invalid email or password"
}

429 Too Many Requests:
{
  "error": "Account temporarily locked",
  "retryAfter": 300
}

Business Rules:
- Email must be valid format
- Password minimum 8 characters
- Lock account after 5 failed attempts
- Token expires after 1 hour
- Must use HTTPS only

Security Requirements:
- Block SQL injection attempts
- Block XSS attempts
- Log all failed login attempts

Test Scenarios:
1. Valid credentials → 200 with token
2. Missing email → 400
3. Invalid email format → 400
4. Wrong password → 401
5. 5 failed attempts → 429
6. SQL injection attempt → 400
7. XSS attempt → 400
8. Token expiry verification
EOF
echo "✅ Created: test_data/02_ecommerce_login.txt"

# Example 3: Payment API
echo "📝 Creating Example 3: Payment Processing..."
cat > test_data/03_payment_api.txt << 'EOF'
Payment Processing API

Base URL: https://api.payments.example.com

ENDPOINT: POST /api/payments/charge
Authentication: Bearer token required

Request Body:
{
  "amount": 4999,
  "currency": "USD",
  "cardNumber": "4242424242424242",
  "cardExpiry": "12/25",
  "cvv": "123",
  "customerId": "cust_abc123"
}

Success Response (201):
{
  "id": "ch_xyz789",
  "status": "succeeded",
  "amount": 4999,
  "currency": "USD",
  "cardLast4": "4242",
  "receiptUrl": "https://receipts.example.com/ch_xyz789"
}

Error Responses:

400 Bad Request:
{
  "error": "Amount must be at least $0.50 USD"
}

402 Payment Required:
{
  "error": "Your card was declined"
}

Business Rules:
- Amount in cents (4999 = $49.99)
- Minimum amount: $0.50 USD
- Maximum amount: $999,999.99 USD
- Card number must pass Luhn algorithm
- CVV must be 3 digits (4 for Amex)

Security Requirements:
- Never log full card number
- Never return CVV in response
- PCI DSS compliant
- Encrypt card data in transit

Test Scenarios:
1. Valid payment → 201
2. Amount too small → 400
3. Card fails Luhn check → 402
4. Expired card → 402
5. Invalid CVV → 400
6. Card declined → 402
EOF
echo "✅ Created: test_data/03_payment_api.txt"

# Example 4: User CRUD
echo "📝 Creating Example 4: User Management..."
cat > test_data/04_user_crud.txt << 'EOF'
User Management REST API

Base URL: https://api.example.com
Authentication: Bearer token required

ENDPOINTS:

1. LIST USERS
GET /api/users
Query Parameters:
- page: integer (default: 1)
- limit: integer (default: 20, max: 100)

Success Response (200):
{
  "data": [
    {
      "id": "usr_001",
      "email": "john@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "role": "user"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 156
  }
}

2. GET USER
GET /api/users/{userId}

Success Response (200):
{
  "id": "usr_001",
  "email": "john@example.com",
  "firstName": "John"
}

Error (404):
{
  "error": "User not found"
}

3. CREATE USER
POST /api/users

Request Body:
{
  "email": "new@example.com",
  "firstName": "Jane",
  "password": "SecurePass123!"
}

Success Response (201):
{
  "id": "usr_002",
  "email": "new@example.com"
}

4. UPDATE USER
PUT /api/users/{userId}

Request Body:
{
  "firstName": "Jane"
}

Success Response (200)

5. DELETE USER
DELETE /api/users/{userId}

Success Response (204)

Business Rules:
- Email must be unique
- Password minimum 8 characters
- Cannot delete own account

Test Scenarios:
LIST:
- Default pagination
- Custom limit
- Max limit exceeded → 400

GET:
- Valid user → 200
- Invalid user → 404

CREATE:
- Valid data → 201
- Duplicate email → 409
- Invalid email → 400

UPDATE:
- Valid update → 200
- Non-existent user → 404

DELETE:
- Valid delete → 204
- Delete self → 403
EOF
echo "✅ Created: test_data/04_user_crud.txt"

# Example 5: Weather API
echo "📝 Creating Example 5: Weather API..."
cat > test_data/05_weather_api.txt << 'EOF'
Weather API

Base URL: https://api.weather.example.com

ENDPOINT: GET /api/weather/current
Authentication: API Key (query parameter)

Request:
GET /api/weather/current?city=San Francisco&apiKey=your-key

Query Parameters:
- city: string (required)
- units: string (optional) - "metric" or "imperial"
- apiKey: string (required)

Success Response (200):
{
  "location": {
    "city": "San Francisco",
    "country": "US",
    "coordinates": {
      "lat": 37.7749,
      "lon": -122.4194
    }
  },
  "weather": {
    "temperature": 18.5,
    "humidity": 65,
    "description": "partly cloudy"
  }
}

Error Responses:

400 Bad Request:
{
  "error": "Missing required parameter: city"
}

401 Unauthorized:
{
  "error": "Invalid or missing API key"
}

404 Not Found:
{
  "error": "City not found"
}

Business Rules:
- City name required
- Default units: metric (Celsius)
- Rate limit: 60 requests per hour

Test Scenarios:
1. Valid city → 200
2. Missing city → 400
3. Missing API key → 401
4. Invalid API key → 401
5. Non-existent city → 404
6. Metric vs Imperial units
EOF
echo "✅ Created: test_data/05_weather_api.txt"

# Create test runner script
echo ""
echo "📝 Creating test runner script..."
cat > run_single_test.sh << 'RUNNER_EOF'
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
RUNNER_EOF

chmod +x run_single_test.sh
echo "✅ Created: run_single_test.sh"

# Create test all script
echo ""
echo "📝 Creating test all script..."
cat > run_all_tests.sh << 'ALL_EOF'
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
ALL_EOF

chmod +x run_all_tests.sh
echo "✅ Created: run_all_tests.sh"

# Summary
echo ""
echo "==========================================="
echo "✅ Setup Complete!"
echo "==========================================="
echo ""
echo "Created:"
echo "  📁 test_data/ (5 example API specs)"
echo "  📁 test_outputs/ (for generated tests)"
echo "  📁 examples/ (for documentation)"
echo "  📜 run_single_test.sh (test one example)"
echo "  📜 run_all_tests.sh (test all examples)"
echo ""
echo "Test Data Files:"
ls -1 test_data/
echo ""
echo "Quick Start:"
echo "  1. Set API key:"
echo "     export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "  2. Test one example:"
echo "     ./run_single_test.sh 1"
echo ""
echo "  3. Test all examples:"
echo "     ./run_all_tests.sh"
echo ""
echo "  4. View results:"
echo "     ls test_outputs/"
echo "     cat test_outputs/simple_login/test_*.py"
echo ""
