#!/usr/bin/env python3
"""
Authentication Handler - Phase 2 Task B
Comprehensive auth handler supporting all major authentication types
"""

from typing import Dict, Optional, Tuple
from enum import Enum


class AuthType(Enum):
    """Supported authentication types."""
    BEARER = "bearer"
    API_KEY = "apikey"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    NONE = "none"


class AuthHandler:
    """
    Handles generation of authentication code for different auth types.
    
    Supports:
    - Bearer Token (most common)
    - API Key
    - OAuth 2.0
    - Basic Auth
    - No Auth (public endpoints)
    """
    
    def __init__(self, auth_config: Optional[Dict] = None):
        """
        Initialize auth handler.
        
        Args:
            auth_config: Authentication configuration dict
                Example for Bearer:
                {
                    'type': 'bearer',
                    'login_url': '/api/login',
                    'credentials': {
                        'email': 'test@example.com',
                        'password': 'TestPass123!'
                    },
                    'token_field': 'token'
                }
        """
        self.auth_config = auth_config or {'type': 'bearer'}
        self.auth_type = AuthType(self.auth_config.get('type', 'bearer'))
    
    def generate_conftest_fixtures(self) -> str:
        """
        Generate pytest fixtures for conftest.py based on auth type.
        
        Returns:
            String containing fixture code
        """
        fixtures = {
            AuthType.BEARER: self._generate_bearer_fixtures(),
            AuthType.API_KEY: self._generate_apikey_fixtures(),
            AuthType.OAUTH2: self._generate_oauth2_fixtures(),
            AuthType.BASIC: self._generate_basic_fixtures(),
            AuthType.NONE: self._generate_none_fixtures()
        }
        
        return fixtures.get(self.auth_type, fixtures[AuthType.BEARER])
    
    def generate_env_variables(self) -> Dict[str, str]:
        """
        Generate environment variables needed for this auth type.
        
        Returns:
            Dict of {variable_name: default_value}
        """
        env_vars = {
            AuthType.BEARER: {
                'BASE_URL': 'http://localhost:8000',
                'TEST_EMAIL': 'test@example.com',
                'TEST_PASSWORD': 'your-password-here'
            },
            AuthType.API_KEY: {
                'BASE_URL': 'http://localhost:8000',
                'API_KEY': 'your-api-key-here'
            },
            AuthType.OAUTH2: {
                'BASE_URL': 'http://localhost:8000',
                'OAUTH_TOKEN_URL': 'https://auth.example.com/oauth/token',
                'OAUTH_CLIENT_ID': 'your-client-id',
                'OAUTH_CLIENT_SECRET': 'your-client-secret'
            },
            AuthType.BASIC: {
                'BASE_URL': 'http://localhost:8000',
                'API_USERNAME': 'your-username',
                'API_PASSWORD': 'your-password'
            },
            AuthType.NONE: {
                'BASE_URL': 'http://localhost:8000'
            }
        }
        
        return env_vars.get(self.auth_type, env_vars[AuthType.BEARER])
    
    def generate_test_usage(self) -> str:
        """
        Generate example test code showing how to use auth.
        
        Returns:
            String containing example test code
        """
        usage_examples = {
            AuthType.BEARER: '''
def test_example_with_bearer_auth(api_client, auth_headers):
    """Example test using Bearer token authentication."""
    response = api_client.get(
        f"{BASE_URL}/api/protected-endpoint",
        headers=auth_headers
    )
    assert response.status_code == 200
''',
            AuthType.API_KEY: '''
def test_example_with_api_key(api_client, auth_headers):
    """Example test using API Key authentication."""
    response = api_client.get(
        f"{BASE_URL}/api/protected-endpoint",
        headers=auth_headers
    )
    assert response.status_code == 200
''',
            AuthType.OAUTH2: '''
def test_example_with_oauth2(api_client, auth_headers):
    """Example test using OAuth 2.0 authentication."""
    response = api_client.get(
        f"{BASE_URL}/api/protected-endpoint",
        headers=auth_headers
    )
    assert response.status_code == 200
''',
            AuthType.BASIC: '''
def test_example_with_basic_auth(api_client, basic_auth):
    """Example test using Basic authentication."""
    response = api_client.get(
        f"{BASE_URL}/api/protected-endpoint",
        auth=basic_auth
    )
    assert response.status_code == 200
''',
            AuthType.NONE: '''
def test_example_no_auth(api_client):
    """Example test for public endpoint (no auth)."""
    response = api_client.get(
        f"{BASE_URL}/api/public-endpoint"
    )
    assert response.status_code == 200
'''
        }
        
        return usage_examples.get(self.auth_type, usage_examples[AuthType.BEARER])
    
    def _generate_bearer_fixtures(self) -> str:
        """Generate Bearer token authentication fixtures."""
        login_url = self.auth_config.get('login_url', '/api/login')
        token_field = self.auth_config.get('token_field', 'token')
        
        return f'''
@pytest.fixture(scope="session")
def auth_token(api_client):
    """
    Get authentication token by logging in.
    
    This fixture is session-scoped, so login happens once per test session.
    The token is reused across all tests.
    """
    login_response = api_client.post(
        f"{{BASE_URL}}{login_url}",
        json={{
            "email": os.getenv("TEST_EMAIL"),
            "password": os.getenv("TEST_PASSWORD")
        }}
    )
    
    # Verify login succeeded
    assert login_response.status_code == 200, \\
        f"Login failed: {{login_response.status_code}} - {{login_response.text}}"
    
    # Extract token from response
    response_data = login_response.json()
    assert "{token_field}" in response_data, \\
        f"Token field '{token_field}' not found in login response"
    
    return response_data["{token_field}"]


@pytest.fixture
def auth_headers(auth_token):
    """
    Headers with Bearer token authentication.
    
    Use this fixture in tests that need authentication:
    def test_something(api_client, auth_headers):
        response = api_client.get(url, headers=auth_headers)
    """
    return {{
        "Authorization": f"Bearer {{auth_token}}",
        "Content-Type": "application/json"
    }}


@pytest.fixture
def auth_headers_no_content_type(auth_token):
    """
    Auth headers without Content-Type (useful for file uploads).
    """
    return {{
        "Authorization": f"Bearer {{auth_token}}"
    }}
'''
    
    def _generate_apikey_fixtures(self) -> str:
        """Generate API Key authentication fixtures."""
        header_name = self.auth_config.get('header_name', 'X-API-Key')
        
        return f'''
@pytest.fixture
def auth_headers():
    """
    Headers with API Key authentication.
    
    The API key is read from the API_KEY environment variable.
    Make sure to set this in your .env file.
    """
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        pytest.fail("API_KEY environment variable is not set")
    
    return {{
        "{header_name}": api_key,
        "Content-Type": "application/json"
    }}


@pytest.fixture
def api_key():
    """
    Raw API key for tests that need it directly.
    """
    return os.getenv("API_KEY")
'''
    
    def _generate_oauth2_fixtures(self) -> str:
        """Generate OAuth 2.0 authentication fixtures."""
        grant_type = self.auth_config.get('grant_type', 'client_credentials')
        
        return f'''
@pytest.fixture(scope="session")
def oauth_token():
    """
    Get OAuth 2.0 access token.
    
    This fixture handles the OAuth 2.0 client credentials flow.
    The token is cached for the entire test session.
    """
    import requests
    
    token_url = os.getenv("OAUTH_TOKEN_URL")
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    
    # Verify all required config is present
    if not all([token_url, client_id, client_secret]):
        pytest.fail("OAuth credentials not configured in environment variables")
    
    # Request access token
    response = requests.post(
        token_url,
        data={{
            "grant_type": "{grant_type}",
            "client_id": client_id,
            "client_secret": client_secret
        }},
        headers={{"Content-Type": "application/x-www-form-urlencoded"}}
    )
    
    assert response.status_code == 200, \\
        f"OAuth token request failed: {{response.status_code}} - {{response.text}}"
    
    token_data = response.json()
    assert "access_token" in token_data, \\
        "access_token not found in OAuth response"
    
    return token_data["access_token"]


@pytest.fixture
def auth_headers(oauth_token):
    """
    Headers with OAuth 2.0 Bearer token.
    
    The OAuth token is automatically obtained and refreshed as needed.
    """
    return {{
        "Authorization": f"Bearer {{oauth_token}}",
        "Content-Type": "application/json"
    }}
'''
    
    def _generate_basic_fixtures(self) -> str:
        """Generate Basic authentication fixtures."""
        return '''
@pytest.fixture
def basic_auth():
    """
    Basic authentication credentials tuple.
    
    Returns (username, password) tuple that can be passed to requests.
    
    Usage:
        response = api_client.get(url, auth=basic_auth)
    """
    username = os.getenv("API_USERNAME")
    password = os.getenv("API_PASSWORD")
    
    if not username or not password:
        pytest.fail("API_USERNAME or API_PASSWORD environment variable not set")
    
    return (username, password)


@pytest.fixture
def auth_headers():
    """
    Headers for Basic auth (if needed for some reason).
    
    Note: Usually you use the basic_auth fixture with the auth parameter,
    not with headers. But this is here if you need it.
    """
    import base64
    
    username = os.getenv("API_USERNAME")
    password = os.getenv("API_PASSWORD")
    
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json"
    }
'''
    
    def _generate_none_fixtures(self) -> str:
        """Generate fixtures for no authentication."""
        return '''
@pytest.fixture
def auth_headers():
    """
    Empty auth headers for public endpoints.
    
    This API doesn't require authentication, but we provide
    this fixture for consistency with authenticated endpoints.
    """
    return {
        "Content-Type": "application/json"
    }


# No authentication required for this API
# Tests can be written without auth concerns:
# def test_public_endpoint(api_client):
#     response = api_client.get(f"{BASE_URL}/api/public")
#     assert response.status_code == 200
'''

    def detect_auth_type_from_code(self, code: str) -> AuthType:
        """
        Auto-detect authentication type from API code.
        
        Args:
            code: Source code of API (Python/Node.js/etc)
            
        Returns:
            Detected AuthType
        """
        code_lower = code.lower()
        
        # Check for OAuth patterns
        if any(pattern in code_lower for pattern in [
            'oauth', 'client_credentials', 'authorization_code'
        ]):
            return AuthType.OAUTH2
        
        # Check for Bearer token patterns
        if any(pattern in code_lower for pattern in [
            'bearer', 'jwt', 'token'
        ]):
            return AuthType.BEARER
        
        # Check for API key patterns
        if any(pattern in code_lower for pattern in [
            'x-api-key', 'apikey', 'api_key'
        ]):
            return AuthType.API_KEY
        
        # Check for Basic auth patterns
        if any(pattern in code_lower for pattern in [
            'basic auth', 'basicauth', 'http basic'
        ]):
            return AuthType.BASIC
        
        # Default to Bearer (most common)
        return AuthType.BEARER
    
    def get_auth_description(self) -> str:
        """
        Get human-readable description of the auth type.
        
        Returns:
            Description string
        """
        descriptions = {
            AuthType.BEARER: "Bearer Token Authentication (login to get token)",
            AuthType.API_KEY: "API Key Authentication (static key in header)",
            AuthType.OAUTH2: "OAuth 2.0 Authentication (client credentials flow)",
            AuthType.BASIC: "Basic Authentication (username and password)",
            AuthType.NONE: "No Authentication (public API)"
        }
        
        return descriptions.get(self.auth_type, "Unknown authentication type")
