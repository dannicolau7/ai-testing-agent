# 🚀 PHASE 2 - Advanced Integration Tasks
## What to Build AFTER Completing the 18 Core Tasks

---

## 📋 OVERVIEW

This document contains everything discussed for Phase 2.
Complete ALL 18 tasks in CLINE_TASKS.md FIRST, then come back here.

**Goal of Phase 2:**
Transform the basic test generator into a complete
API testing platform that REPLACES Postman.

---

## 🎯 THE BIG PICTURE

### What You're Building:

```
INPUT (any of these):
├── Your API code (Python, Node, Java)
├── Plain English description
├── OpenAPI/Swagger YAML
├── Database schema
└── Existing Postman collection

AI PROCESSES EVERYTHING
         ↓
OUTPUT (all of this):
├── Complete test suite (pytest)
├── conftest.py (auth + fixtures)
├── test_data/ (realistic data)
├── pytest.ini (configuration)
├── .env (environment variables)
├── CI/CD pipeline (GitHub Actions)
└── Saved to CUSTOMER'S project!

CUSTOMER RUNS INDEPENDENTLY:
pytest tests/   ← FREE forever, no AI needed!
```

---

## 🔑 PHASE 2 TASK LIST

### Task A: Test Output Goes to Customer's Project

**Paste into Cline:**

```
CRITICAL FEATURE: Save generated tests to customer's project directory.

Current problem:
- Tests save to: ./test_output/ (inside our tool)
- Customer can't easily use them

Required solution:
- Add --output flag to CLI
- Save ALL generated files to their project

IMPLEMENT:

1. Add --output argument to CLI:
   parser.add_argument(
       '--output',
       help='Directory to save generated tests',
       default='./test_output'
   )

2. Generated file structure in their project:
   
   {output_dir}/
   ├── tests/
   │   ├── conftest.py
   │   ├── test_{endpoint_name}.py  (one per endpoint)
   │   └── test_data/
   │       ├── valid_users.json
   │       └── test_payloads.json
   ├── pytest.ini
   ├── requirements-test.txt
   ├── .env.example
   └── .github/
       └── workflows/
           └── api_tests.yml

3. Generate conftest.py with:
   - Base URL fixture from .env
   - Auth token fixture (auto-login)
   - Reusable request headers
   - Setup and teardown
   - Environment variable loading

4. Generate pytest.ini:
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = -v --tb=short

5. Generate requirements-test.txt:
   pytest==7.4.0
   pytest-html==4.1.0
   requests==2.31.0
   python-dotenv==1.0.0
   faker==20.0.0

6. Generate .env.example:
   BASE_URL=http://localhost:8000
   TEST_EMAIL=test@example.com
   TEST_PASSWORD=your-password-here
   API_KEY=your-api-key-here

7. Generate GitHub Actions CI/CD:
   .github/workflows/api_tests.yml
   - Runs on push to main
   - Runs every night at 2 AM
   - Uploads HTML report as artifact
   - Sends Slack notification on failure

USAGE:
python cli.py run api_docs.txt --output /Users/john/my-project/

RESULT:
Customer goes to their project and runs:
cd /Users/john/my-project/
pip install -r requirements-test.txt
cp .env.example .env
# Edit .env with real values
pytest tests/ -v
# Tests run completely independently!
```

---

### Task B: Complete Authentication Handler

**Paste into Cline:**

```
Create comprehensive auth handler that supports ALL auth types.

CREATE FILE: auth_handler.py

SUPPORT THESE AUTH TYPES:

1. BEARER TOKEN (most common):
   Config:
   auth:
     type: bearer
     login_url: /api/login
     credentials:
       email: test@example.com
       password: TestPass123!
     token_field: token  # field name in response

   Generated conftest.py:
   @pytest.fixture(scope="session")
   def auth_token(api_client):
       response = api_client.post(
           f"{BASE_URL}/api/login",
           json={
               "email": os.getenv("TEST_EMAIL"),
               "password": os.getenv("TEST_PASSWORD")
           }
       )
       assert response.status_code == 200
       return response.json()["token"]

   @pytest.fixture
   def auth_headers(auth_token):
       return {"Authorization": f"Bearer {auth_token}"}

2. API KEY:
   Config:
   auth:
     type: apikey
     header_name: X-API-Key
     key: your-api-key

   Generated:
   @pytest.fixture
   def auth_headers():
       return {"X-API-Key": os.getenv("API_KEY")}

3. OAUTH 2.0:
   Config:
   auth:
     type: oauth2
     token_url: https://auth.example.com/token
     client_id: your-client-id
     client_secret: your-client-secret
     grant_type: client_credentials

   Generated:
   @pytest.fixture(scope="session")
   def oauth_token():
       response = requests.post(
           os.getenv("OAUTH_TOKEN_URL"),
           data={
               "grant_type": "client_credentials",
               "client_id": os.getenv("OAUTH_CLIENT_ID"),
               "client_secret": os.getenv("OAUTH_CLIENT_SECRET")
           }
       )
       return response.json()["access_token"]

4. BASIC AUTH:
   Config:
   auth:
     type: basic
     username: admin
     password: password

   Generated:
   @pytest.fixture
   def basic_auth():
       return (os.getenv("API_USERNAME"), os.getenv("API_PASSWORD"))

5. NO AUTH (public endpoints):
   Config:
   auth:
     type: none

   Generated:
   # No auth fixture needed
   # Tests make direct requests

IMPORTANT:
- ALL credentials come from .env file
- NEVER hardcode in test files
- Auto-detect auth type from API code if possible
- Support per-endpoint auth override
```

---

### Task C: Complete Request Body Handler

**Paste into Cline:**

```
Handle ALL types of request bodies in generated tests.

IMPLEMENT IN: test_generator.py

SUPPORT THESE BODY TYPES:

1. JSON BODY (most common):
   
   From API code or description:
   POST /api/login
   body: {"email": string, "password": string}
   
   Generated test:
   def test_login(api_client, auth_headers):
       payload = {
           "email": "test@example.com",
           "password": "TestPass123!"
       }
       response = api_client.post(
           f"{BASE_URL}/api/login",
           json=payload
       )
       assert response.status_code == 200

2. FORM DATA (file uploads):
   
   From API code:
   POST /api/upload
   body: form-data (file + description)
   
   Generated test:
   def test_file_upload(api_client, auth_headers):
       with open("tests/test_data/sample.pdf", "rb") as f:
           files = {"file": ("test.pdf", f, "application/pdf")}
           data = {"description": "Test upload"}
           headers = {k:v for k,v in auth_headers.items()
                     if k != "Content-Type"}
           response = api_client.post(
               f"{BASE_URL}/api/upload",
               files=files,
               data=data,
               headers=headers
           )
       assert response.status_code == 201

3. URL ENCODED:
   
   Generated test:
   def test_form_submit(api_client):
       data = {"username": "test", "password": "pass"}
       response = api_client.post(
           f"{BASE_URL}/api/token",
           data=data,
           headers={"Content-Type": "application/x-www-form-urlencoded"}
       )
       assert response.status_code == 200

4. PATH PARAMETERS:
   
   From: GET /api/users/{user_id}/orders/{order_id}
   
   Generated test:
   @pytest.mark.parametrize("user_id,order_id", [
       ("usr_123", "ord_456"),
       ("usr_789", "ord_012"),
   ])
   def test_get_user_order(api_client, auth_headers, user_id, order_id):
       response = api_client.get(
           f"{BASE_URL}/api/users/{user_id}/orders/{order_id}",
           headers=auth_headers
       )
       assert response.status_code in [200, 404]

5. QUERY PARAMETERS:
   
   From: GET /api/users?page=1&limit=10&sort=name
   
   Generated test:
   def test_list_users_paginated(api_client, auth_headers):
       params = {"page": 1, "limit": 10, "sort": "name"}
       response = api_client.get(
           f"{BASE_URL}/api/users",
           params=params,
           headers=auth_headers
       )
       assert response.status_code == 200
       data = response.json()
       assert len(data["items"]) <= 10

ALSO GENERATE EDGE CASE TESTS FOR EACH:
- Missing required fields
- Wrong data types
- Values exceeding limits
- Empty strings
- Null values
- SQL injection attempts
- XSS attempts
```

---

### Task D: Test Data Management System

**Paste into Cline:**

```
Create complete test data management system.

CREATE FILE: data_manager.py

PURPOSE: Let dev/QA provide their own test data
that gets used in generated tests.

SUPPORT THESE INPUT FORMATS:

1. YAML FILE (test_data.yaml):

environment:
  base_url: https://api.example.com

auth:
  type: bearer
  login_url: /api/login
  credentials:
    email: testuser@company.com
    password: TestPass123!

users:
  valid_user:
    email: john@test.com
    password: ValidPass123!
    user_id: "usr_123456"
    role: customer
  admin_user:
    email: admin@test.com
    password: AdminPass456!
    role: admin
  locked_user:
    email: locked@test.com
    status: locked

products:
  valid_product:
    id: "prod_abc123"
    price: 29.99
    in_stock: true
  out_of_stock:
    id: "prod_xyz789"
    in_stock: false

business_rules:
  max_login_attempts: 5
  min_password_length: 8
  token_expiry_minutes: 60
  max_file_size_mb: 10

expected_responses:
  login_success:
    status: 200
    fields: [token, user_id, email]
  login_failure:
    status: 401
    fields: [error]
  account_locked:
    status: 429
    fields: [error, retry_after]

2. EXCEL FILE (test_data.xlsx):
   Sheet: Users → user test data
   Sheet: Products → product test data
   Sheet: Rules → business rules
   Sheet: TestCases → custom test cases
   Sheet: ExpectedResponses → what to expect

3. SETUP WIZARD (interactive):
   Run: ai-test init
   
   Asks questions:
   - What is your API base URL?
   - What auth type does it use?
   - Do you have test credentials?
   - Any business rules to test?
   - What response codes do you expect?
   
   Saves to: .ai-test/test_data.yaml

IMPLEMENT:

class DataManager:
    def load(self, source: str) -> dict:
        """Load test data from file or wizard"""
        if source.endswith('.yaml'):
            return self._load_yaml(source)
        elif source.endswith('.xlsx'):
            return self._load_excel(source)
        else:
            return self._run_wizard()
    
    def validate(self, data: dict) -> list:
        """Validate data and return list of warnings"""
        warnings = []
        if not data.get('auth'):
            warnings.append("No auth configured")
        if not data.get('users'):
            warnings.append("No test users provided")
        return warnings
    
    def inject_into_tests(self, test_code: str, data: dict) -> str:
        """Replace placeholders in tests with real data"""
        # Replace placeholder values with real ones
        # test@example.com → john@test.com (from YAML)
        # ValidPass123! → their real password
        return test_code

USAGE:
python cli.py generate \
  --api api.py \
  --data test_data.yaml \
  --output ./tests/

Tests use THEIR real data!
No more placeholder values!
Tests actually WORK when run!
```

---

### Task E: API Code Analyzer

**Paste into Cline:**

```
Create API code analyzer that reads code and extracts endpoints.

CREATE FILE: code_analyzer.py

SUPPORT THESE FRAMEWORKS:

1. PYTHON FASTAPI:
   Input code:
   @app.post("/api/login")
   async def login(
       email: str,
       password: str,
       db: Session = Depends(get_db)
   ):
       """Login user and return JWT token"""
   
   Extract:
   {
     "method": "POST",
     "path": "/api/login",
     "name": "login",
     "description": "Login user and return JWT token",
     "body_params": {
       "email": {"type": "str", "required": true},
       "password": {"type": "str", "required": true}
     },
     "auth_required": false
   }

2. PYTHON FLASK:
   Input:
   @app.route('/api/users/<int:user_id>', methods=['GET'])
   @login_required
   def get_user(user_id):
       """Get user by ID"""
   
   Extract:
   {
     "method": "GET",
     "path": "/api/users/{user_id}",
     "path_params": {"user_id": "int"},
     "auth_required": true
   }

3. NODE.JS EXPRESS:
   Input:
   app.post('/api/payments', authenticateToken, async (req, res) => {
     const { amount, cardNumber } = req.body;
   
   Extract:
   {
     "method": "POST",
     "path": "/api/payments",
     "auth_required": true,
     "body_params": {"amount": "any", "cardNumber": "any"}
   }

4. PLAIN ENGLISH:
   Input:
   "Login API that accepts email and password,
   returns JWT token, locks after 5 failed attempts"
   
   Use AI to extract:
   {
     "method": "POST",
     "path": "/api/login",
     "body_params": {
       "email": {"type": "string", "format": "email"},
       "password": {"type": "string", "min_length": 8}
     },
     "business_rules": {
       "max_attempts": 5,
       "response": "JWT token"
     }
   }

5. OPENAPI/SWAGGER YAML:
   Input:
   paths:
     /api/login:
       post:
         requestBody:
           content:
             application/json:
               schema:
                 properties:
                   email:
                     type: string
   
   Direct parsing - most structured!

IMPLEMENTATION:
class CodeAnalyzer:
    def analyze(self, source: str) -> List[Dict]:
        """Analyze source and return list of endpoints"""
        
        if self._is_fastapi(source):
            return self._parse_fastapi(source)
        elif self._is_flask(source):
            return self._parse_flask(source)
        elif self._is_express(source):
            return self._parse_express(source)
        elif self._is_openapi(source):
            return self._parse_openapi(source)
        else:
            return self._analyze_with_ai(source)

OUTPUT: List of endpoint dicts
used by test_generator.py to create tests
```

---

### Task F: Request Runner (Postman Replacement)

**Paste into Cline:**

```
Create interactive request runner that replaces Postman.

CREATE FILE: request_runner.py

PURPOSE: Send HTTP requests from command line
and optionally save them as automated tests.

USAGE:

# Send a request (like Postman!)
ai-test request POST https://api.example.com/api/login \
  --body '{"email":"test@test.com","password":"pass"}' \
  --auth bearer

# With environment
ai-test request GET /api/users \
  --env dev \
  --auth bearer \
  --save-as-test  # Saves this as a test file!

# Interactive mode (like Postman GUI but in terminal)
ai-test request --interactive

INTERACTIVE MODE:
┌─────────────────────────────────────────────┐
│  🤖 Request Runner                          │
│─────────────────────────────────────────────│
│  Method:  POST                              │
│  URL:     /api/login                        │
│  Auth:    Bearer Token (auto-login)         │
│                                             │
│  Body:                                      │
│  {                                          │
│    "email": "test@test.com",                │
│    "password": "TestPass123!"               │
│  }                                          │
│                                             │
│  [Send] [Save as Test] [Add to Collection]  │
│                                             │
│  Response: 200 OK (234ms)                   │
│  {                                          │
│    "token": "eyJ...",                       │
│    "user_id": "123"                         │
│  }                                          │
│                                             │
│  AI Analysis:                               │
│  ✅ Response looks correct                  │
│  ⚠️  No token expiry returned              │
│  💡 Add refresh_token to response          │
└─────────────────────────────────────────────┘

IMPLEMENT:
class RequestRunner:
    def send(
        self,
        method: str,
        url: str,
        headers: dict = None,
        body: dict = None,
        auth: dict = None,
        params: dict = None
    ) -> Response:
        """Send HTTP request"""
    
    def save_as_test(
        self,
        response: Response,
        test_name: str,
        output_path: str
    ):
        """Convert this request/response into a pytest test"""
    
    def analyze_response(self, response: Response) -> dict:
        """Use AI to analyze response and suggest improvements"""

WHEN SAVING AS TEST:
Generate complete pytest test from the request:

def test_{name}(api_client, auth_headers):
    """Auto-generated from request on {date}"""
    response = api_client.post(
        f"{BASE_URL}/api/login",
        json={
            "email": "test@test.com",
            "password": "TestPass123!"
        },
        headers=auth_headers
    )
    # Assertions based on actual response received
    assert response.status_code == 200
    assert "token" in response.json()
    assert "user_id" in response.json()
```

---

### Task G: Environment Manager

**Paste into Cline:**

```
Create environment manager for dev/staging/prod configurations.

CREATE FILE: env_manager.py

PURPOSE: Manage different environments like Postman does.

FILE STRUCTURE:
.ai-test/
├── environments/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
└── active_env.txt

dev.yaml:
name: Development
base_url: http://localhost:8000
variables:
  TEST_EMAIL: dev_user@test.com
  TEST_PASSWORD: DevPass123!
  API_KEY: dev-api-key-123

staging.yaml:
name: Staging
base_url: https://staging.api.com
variables:
  TEST_EMAIL: stage_user@test.com
  TEST_PASSWORD: StagePass456!
  API_KEY: staging-api-key-456

prod.yaml:
name: Production (READ-ONLY!)
base_url: https://api.com
variables:
  TEST_EMAIL: prod_readonly@test.com
read_only: true  # Only safe GET tests!
warning: "Running tests in production!"

COMMANDS:
# Switch environment
ai-test env use dev
ai-test env use staging

# List environments
ai-test env list
Output:
  * dev (active)
    staging
    prod (read-only)

# Set variable in current env
ai-test env set BASE_URL http://localhost:9000

# Show current environment
ai-test env show
Output:
  Active: Development
  Base URL: http://localhost:8000
  Variables: 3 configured

INTEGRATION:
- When running tests: use active environment
- pytest conftest.py reads from active env
- .env file updated automatically
- Never run destructive tests in prod!

SAFETY:
- Warn when switching to prod
- Require --force flag for prod tests
- Only allow GET requests in prod by default
- Log all prod test runs
```

---

### Task H: Complete Test Suite Quality

**Paste into Cline:**

```
Ensure ALL generated tests are high quality and actually work.

UPDATE: test_generator.py

QUALITY REQUIREMENTS:

1. EVERY test must be immediately runnable:
   - No undefined variables
   - No missing imports
   - No undefined fixtures
   - All dependencies in requirements-test.txt

2. TESTS MUST BE ORGANIZED:
   
   class TestLoginSuccess:
       """Happy path - should work"""
       
       def test_valid_credentials_returns_200(self):...
       def test_response_has_token(self):...
       def test_response_has_user_id(self):...
   
   class TestLoginFailure:
       """These should fail gracefully"""
       
       def test_wrong_password_returns_401(self):...
       def test_nonexistent_user_returns_401(self):...
       def test_missing_email_returns_400(self):...
       def test_missing_password_returns_400(self):...
   
   class TestLoginEdgeCases:
       """Boundary conditions"""
       
       def test_empty_email_string(self):...
       def test_email_max_length(self):...
       def test_password_minimum_length(self):...
       def test_special_characters_in_password(self):...
       def test_unicode_email(self):...
   
   class TestLoginSecurity:
       """Security focused"""
       
       def test_sql_injection_blocked(self):...
       def test_xss_in_email_blocked(self):...
       def test_account_lockout_enforced(self):...
       def test_response_hides_password(self):...
       def test_https_required(self):...
   
   class TestLoginParametrized:
       """Data-driven tests"""
       
       @pytest.mark.parametrize("email,password,expected", [
           ("valid@test.com", "ValidPass!", 200),
           ("wrong@test.com", "WrongPass!", 401),
           ("", "SomePass!", 400),
       ])
       def test_multiple_scenarios(self):...

3. REALISTIC TEST DATA:
   NOT: email = "test@test.com"
   YES: email = "john.doe@company.com"
   
   NOT: password = "password123"
   YES: password = "SecureP@ss2024!"
   
   NOT: user_id = "123"
   YES: user_id = "usr_a1b2c3d4"

4. CLEAR COMMENTS:
   def test_account_lockout_enforced(self, api_client):
       """
       Business Rule: Account must lock after 5 failed login attempts.
       After lockout, even correct password should return 429.
       Ref: Security Requirements v2.1, Section 3.4
       """

5. ASSERTIONS MUST BE MEANINGFUL:
   NOT: assert response.status_code == 200
   YES:
   assert response.status_code == 200, \
       f"Login failed. Got {response.status_code}: {response.text}"
   assert "token" in response.json(), \
       "Token missing from login response"
   assert len(response.json()["token"]) > 20, \
       "Token seems too short to be valid JWT"

MINIMUM TEST COUNT PER ENDPOINT:
- Simple GET: 5 tests
- POST with body: 15 tests
- Auth endpoint: 25 tests
- Payment endpoint: 30+ tests
```

---

## 📋 INTEGRATION ORDER

**Complete these AFTER the 18 core tasks:**

```
Week 3: Core Integration
├── Task A: Output to customer's project ← MOST IMPORTANT
├── Task B: Auth handler (all types)
├── Task C: Request body handler
└── Task D: Test data management

Week 4: Advanced Features
├── Task E: API code analyzer
├── Task F: Request runner (Postman replacement!)
├── Task G: Environment manager
└── Task H: Test quality improvements

Week 5: Testing & Polish
├── Test with 10+ real API documents
├── Fix all issues found
├── Get 5 beta users to test
├── Fix beta feedback
└── Decide: ready for launch?
```

---

## 🎯 TESTING CHECKLIST

**Before considering Phase 2 complete,
test with ALL of these documents:**

```
Test 1: Simple login API (text description)
ai-test generate --api "login endpoint with email/password" \
  --output ./test_projects/test1/

Test 2: REST CRUD API (Python FastAPI code)
ai-test generate --api examples/fastapi_users.py \
  --output ./test_projects/test2/

Test 3: Payment API (complex, high security)
ai-test generate --api examples/payment_api.py \
  --data examples/payment_test_data.yaml \
  --output ./test_projects/test3/

Test 4: With OAuth auth
ai-test generate --api examples/oauth_api.py \
  --output ./test_projects/test4/

Test 5: With file uploads
ai-test generate --api examples/upload_api.py \
  --output ./test_projects/test5/

For EACH test, verify:
□ All generated files exist
□ pytest runs without errors
□ Tests actually test the right things
□ Auth works correctly
□ Test data is realistic
□ CI/CD file is valid YAML
□ .env.example has all variables
□ README explains how to run
```

---

## 💰 WHEN TO ADD PAID FEATURES

**Only add paid tiers AFTER:**

```
□ Phase 2 complete
□ Tested with 10+ real APIs
□ 5+ beta users satisfied
□ Tests are high quality
□ Tool is stable (no crashes)
□ You would personally pay for it
□ At least one person said "I need this!"
```

**Then add (from CLINE_TASKS.md):**
- License validation
- Usage limits
- Pro/Team/Enterprise tiers
- Payment processing

---

## 🏆 THE GOAL

```
BEFORE YOUR TOOL:
Developer writes API
→ Opens Postman (30 min setup)
→ Creates collection manually (2 hours)
→ Tests manually (1 hour)
→ Writes tests manually (4 hours)
→ Sets up CI/CD manually (2 hours)
Total: ~9 hours per API feature

AFTER YOUR TOOL:
Developer writes API
→ Runs: ai-test generate --api api.py --output ./tests/
→ 3 minutes later: complete test suite ready
→ pytest tests/ ← works immediately!
→ CI/CD runs automatically
Total: ~5 minutes per API feature

TIME SAVED: 8+ hours per feature
VALUE: Priceless for development teams

THIS is why people will pay $29-99/month!
```

---

*Complete 18 tasks from CLINE_TASKS.md first*
*Then return here for Phase 2*
*Document version: 1.0*
*Created: February 2026*
