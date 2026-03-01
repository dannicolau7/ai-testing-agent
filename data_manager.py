#!/usr/bin/env python3
"""
Test Data Manager - Phase 2 Task D
Manages test data from multiple sources (YAML, Excel, interactive wizard)
"""

import yaml
import json
from typing import Dict, List, Any, Optional
from pathlib import Path


class DataManager:
    """
    Manages test data from various sources.
    
    Supports:
    - YAML files (test_data.yaml)
    - Excel files (test_data.xlsx)
    - Interactive wizard
    - JSON files
    """
    
    def __init__(self):
        self.data = {}
        self.warnings = []
    
    def load(self, source: str) -> Dict[str, Any]:
        """
        Load test data from source.
        
        Args:
            source: Path to file or 'wizard' for interactive mode
            
        Returns:
            Dictionary of test data
        """
        if source.lower() == 'wizard':
            return self._run_wizard()
        
        source_path = Path(source)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Test data file not found: {source}")
        
        # Detect file type and load
        if source_path.suffix in ['.yaml', '.yml']:
            return self._load_yaml(source)
        elif source_path.suffix in ['.xlsx', '.xls']:
            return self._load_excel(source)
        elif source_path.suffix == '.json':
            return self._load_json(source)
        else:
            raise ValueError(f"Unsupported file format: {source_path.suffix}")
    
    def _load_yaml(self, filepath: str) -> Dict[str, Any]:
        """Load test data from YAML file."""
        print(f"📄 Loading test data from YAML: {filepath}")
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        self.data = data
        self.warnings = self.validate(data)
        
        if self.warnings:
            print(f"⚠️  {len(self.warnings)} warning(s) found:")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        return data
    
    def _load_excel(self, filepath: str) -> Dict[str, Any]:
        """Load test data from Excel file."""
        print(f"📊 Loading test data from Excel: {filepath}")
        
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas and openpyxl required for Excel support. "
                            "Install with: pip install pandas openpyxl")
        
        # Read all sheets
        excel_file = pd.ExcelFile(filepath)
        data = {}
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            
            if sheet_name.lower() == 'users':
                data['users'] = self._parse_users_sheet(df)
            elif sheet_name.lower() == 'products':
                data['products'] = self._parse_products_sheet(df)
            elif sheet_name.lower() == 'rules':
                data['business_rules'] = self._parse_rules_sheet(df)
            elif sheet_name.lower() == 'testcases':
                data['custom_tests'] = self._parse_testcases_sheet(df)
            elif sheet_name.lower() == 'expectedresponses':
                data['expected_responses'] = self._parse_responses_sheet(df)
        
        self.data = data
        return data
    
    def _load_json(self, filepath: str) -> Dict[str, Any]:
        """Load test data from JSON file."""
        print(f"📋 Loading test data from JSON: {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.data = data
        return data
    
    def _parse_users_sheet(self, df) -> Dict:
        """Parse users sheet from Excel."""
        users = {}
        for _, row in df.iterrows():
            user_id = row.get('id') or row.get('name', f'user_{len(users)}')
            users[user_id] = {
                'email': row.get('email', ''),
                'password': row.get('password', ''),
                'role': row.get('role', 'user'),
                'status': row.get('status', 'active')
            }
        return users
    
    def _parse_products_sheet(self, df) -> Dict:
        """Parse products sheet from Excel."""
        products = {}
        for _, row in df.iterrows():
            product_id = row.get('id') or row.get('name', f'product_{len(products)}')
            products[product_id] = {
                'name': row.get('name', ''),
                'price': float(row.get('price', 0)),
                'in_stock': bool(row.get('in_stock', True)),
                'category': row.get('category', '')
            }
        return products
    
    def _parse_rules_sheet(self, df) -> Dict:
        """Parse business rules sheet from Excel."""
        rules = {}
        for _, row in df.iterrows():
            rule_name = row.get('rule_name') or row.get('name', '')
            rule_value = row.get('value')
            if rule_name:
                rules[rule_name] = rule_value
        return rules
    
    def _parse_testcases_sheet(self, df) -> List:
        """Parse test cases sheet from Excel."""
        test_cases = []
        for _, row in df.iterrows():
            test_cases.append({
                'name': row.get('test_name', ''),
                'endpoint': row.get('endpoint', ''),
                'method': row.get('method', 'GET'),
                'expected_status': int(row.get('expected_status', 200)),
                'description': row.get('description', '')
            })
        return test_cases
    
    def _parse_responses_sheet(self, df) -> Dict:
        """Parse expected responses sheet from Excel."""
        responses = {}
        for _, row in df.iterrows():
            response_name = row.get('name', f'response_{len(responses)}')
            responses[response_name] = {
                'status': int(row.get('status', 200)),
                'fields': row.get('fields', '').split(',') if row.get('fields') else []
            }
        return responses
    
    def _run_wizard(self) -> Dict[str, Any]:
        """Run interactive wizard to collect test data."""
        print("\n" + "="*60)
        print("🧙 Test Data Configuration Wizard")
        print("="*60)
        print("\nThis wizard will help you configure test data for your API.")
        print("Press Ctrl+C anytime to cancel.\n")
        
        data = {}
        
        # Environment configuration
        print("📍 Environment Configuration")
        print("-" * 40)
        data['environment'] = {
            'base_url': self._prompt("API Base URL", "http://localhost:8000"),
            'timeout': int(self._prompt("Request timeout (seconds)", "30")),
        }
        
        # Authentication configuration
        print("\n🔐 Authentication Configuration")
        print("-" * 40)
        auth_type = self._prompt_choice(
            "Authentication type",
            ["bearer", "apikey", "oauth2", "basic", "none"],
            default="bearer"
        )
        
        auth_config = {'type': auth_type}
        
        if auth_type == 'bearer':
            auth_config['login_url'] = self._prompt("Login endpoint", "/api/login")
            auth_config['credentials'] = {
                'email': self._prompt("Test email", "test@example.com"),
                'password': self._prompt("Test password", "TestPass123!", mask=True)
            }
        elif auth_type == 'apikey':
            auth_config['api_key'] = self._prompt("API Key", "your-api-key-here", mask=True)
            auth_config['header_name'] = self._prompt("Header name", "X-API-Key")
        elif auth_type == 'oauth2':
            auth_config['token_url'] = self._prompt("Token URL", "https://auth.example.com/token")
            auth_config['client_id'] = self._prompt("Client ID", "your-client-id")
            auth_config['client_secret'] = self._prompt("Client Secret", "your-secret", mask=True)
        elif auth_type == 'basic':
            auth_config['username'] = self._prompt("Username", "admin")
            auth_config['password'] = self._prompt("Password", "password", mask=True)
        
        data['auth'] = auth_config
        
        # Test users
        print("\n👥 Test Users")
        print("-" * 40)
        add_users = self._prompt_yes_no("Add test users?", default=True)
        
        if add_users:
            data['users'] = {}
            while True:
                user_name = self._prompt("User identifier (or press Enter to finish)", "")
                if not user_name:
                    break
                
                data['users'][user_name] = {
                    'email': self._prompt(f"  Email for {user_name}", f"{user_name}@test.com"),
                    'password': self._prompt(f"  Password for {user_name}", "TestPass123!", mask=True),
                    'role': self._prompt(f"  Role for {user_name}", "user")
                }
                
                print(f"  ✓ Added user: {user_name}")
        
        # Business rules
        print("\n📋 Business Rules")
        print("-" * 40)
        add_rules = self._prompt_yes_no("Add business rules?", default=True)
        
        if add_rules:
            data['business_rules'] = {}
            
            # Common rules
            data['business_rules']['max_login_attempts'] = int(
                self._prompt("Max login attempts before lockout", "5")
            )
            data['business_rules']['min_password_length'] = int(
                self._prompt("Minimum password length", "8")
            )
            data['business_rules']['token_expiry_minutes'] = int(
                self._prompt("Token expiry time (minutes)", "60")
            )
        
        # Expected responses
        print("\n✅ Expected Responses")
        print("-" * 40)
        add_responses = self._prompt_yes_no("Configure expected responses?", default=True)
        
        if add_responses:
            data['expected_responses'] = {
                'success': {
                    'status': 200,
                    'fields': ['id', 'status', 'data']
                },
                'created': {
                    'status': 201,
                    'fields': ['id', 'message']
                },
                'bad_request': {
                    'status': 400,
                    'fields': ['error', 'message']
                },
                'unauthorized': {
                    'status': 401,
                    'fields': ['error']
                },
                'not_found': {
                    'status': 404,
                    'fields': ['error', 'message']
                }
            }
        
        # Save configuration
        print("\n💾 Save Configuration")
        print("-" * 40)
        save_file = self._prompt_yes_no("Save this configuration to file?", default=True)
        
        if save_file:
            filename = self._prompt("Filename", "test_data.yaml")
            self._save_yaml(data, filename)
            print(f"✓ Saved to {filename}")
        
        print("\n" + "="*60)
        print("✅ Configuration complete!")
        print("="*60 + "\n")
        
        self.data = data
        return data
    
    def _prompt(self, question: str, default: str = "", mask: bool = False) -> str:
        """Prompt user for input."""
        if default:
            prompt = f"{question} [{default}]: "
        else:
            prompt = f"{question}: "
        
        if mask:
            import getpass
            value = getpass.getpass(prompt)
        else:
            value = input(prompt)
        
        return value.strip() or default
    
    def _prompt_choice(self, question: str, choices: List[str], default: str = "") -> str:
        """Prompt user to choose from options."""
        print(f"\n{question}:")
        for i, choice in enumerate(choices, 1):
            marker = "*" if choice == default else " "
            print(f"  {marker} {i}. {choice}")
        
        while True:
            choice_input = input(f"\nSelect (1-{len(choices)}) [{default}]: ").strip()
            
            if not choice_input and default:
                return default
            
            try:
                choice_num = int(choice_input)
                if 1 <= choice_num <= len(choices):
                    return choices[choice_num - 1]
            except ValueError:
                pass
            
            print("Invalid choice. Please try again.")
    
    def _prompt_yes_no(self, question: str, default: bool = True) -> bool:
        """Prompt user for yes/no."""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{question} [{default_str}]: ").strip().lower()
        
        if not response:
            return default
        
        return response in ['y', 'yes']
    
    def _save_yaml(self, data: Dict, filename: str):
        """Save data to YAML file."""
        with open(filename, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def validate(self, data: Dict) -> List[str]:
        """
        Validate test data and return warnings.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for required sections
        if 'auth' not in data:
            warnings.append("No authentication configuration found")
        
        if 'environment' not in data:
            warnings.append("No environment configuration found")
        
        # Validate auth config
        if 'auth' in data:
            auth = data['auth']
            if auth.get('type') == 'bearer':
                if 'credentials' not in auth:
                    warnings.append("Bearer auth requires credentials")
            elif auth.get('type') == 'apikey':
                if 'api_key' not in auth:
                    warnings.append("API key auth requires api_key field")
        
        # Check for test data
        if 'users' not in data and 'products' not in data:
            warnings.append("No test users or products defined")
        
        # Validate users
        if 'users' in data:
            for user_id, user in data['users'].items():
                if 'email' not in user:
                    warnings.append(f"User '{user_id}' missing email")
                if 'password' not in user:
                    warnings.append(f"User '{user_id}' missing password")
        
        return warnings
    
    def inject_into_tests(self, test_code: str) -> str:
        """
        Replace placeholder values in tests with real data.
        
        Args:
            test_code: Test code string with placeholders
            
        Returns:
            Test code with real data injected
        """
        if not self.data:
            return test_code
        
        # Replace common placeholders
        replacements = {}
        
        # Environment
        if 'environment' in self.data:
            env = self.data['environment']
            replacements['http://localhost:8000'] = env.get('base_url', 'http://localhost:8000')
        
        # Users
        if 'users' in self.data:
            users = self.data['users']
            if 'valid_user' in users or len(users) > 0:
                first_user = list(users.values())[0]
                replacements['test@example.com'] = first_user.get('email', 'test@example.com')
                replacements['TestPass123!'] = first_user.get('password', 'TestPass123!')
        
        # Apply replacements
        modified_code = test_code
        for placeholder, real_value in replacements.items():
            modified_code = modified_code.replace(placeholder, str(real_value))
        
        return modified_code
    
    def get_user_credentials(self, user_type: str = 'valid') -> Dict[str, str]:
        """
        Get credentials for a specific user type.
        
        Args:
            user_type: Type of user (valid, admin, locked, etc.)
            
        Returns:
            Dict with email and password
        """
        if 'users' not in self.data:
            return {'email': 'test@example.com', 'password': 'TestPass123!'}
        
        users = self.data['users']
        
        # Try to find matching user
        for user_id, user in users.items():
            if user_type in user_id.lower() or user.get('role', '').lower() == user_type:
                return {
                    'email': user.get('email', 'test@example.com'),
                    'password': user.get('password', 'TestPass123!')
                }
        
        # Return first user if no match
        if users:
            first_user = list(users.values())[0]
            return {
                'email': first_user.get('email', 'test@example.com'),
                'password': first_user.get('password', 'TestPass123!')
            }
        
        # Default fallback
        return {'email': 'test@example.com', 'password': 'TestPass123!'}
    
    def generate_conftest(self, output_path: str = "conftest.py") -> str:
        """
        Generate a conftest.py file populated with real credentials and
        configuration from the loaded test data.

        The generated conftest provides:
        - BASE_URL constant
        - api_client fixture (requests.Session)
        - auth_headers fixture (logs in and caches the token)
        - user_credentials fixture (parametrize-friendly dict of users)
        - business_rules fixture

        Args:
            output_path: Where to write the file (default: conftest.py)

        Returns:
            Path to the written conftest.py
        """
        data = self.data

        env = data.get('environment', {})
        base_url = env.get('base_url', 'http://localhost:8000')
        timeout = env.get('timeout', 30)

        auth = data.get('auth', {})
        auth_type = auth.get('type', 'bearer')
        login_url = auth.get('login_url', '/api/login')
        creds = auth.get('credentials', {})
        email = creds.get('email', 'test@example.com')
        password = creds.get('password', 'TestPass123!')
        token_field = auth.get('token_field', 'token')
        api_key = auth.get('api_key', '')
        header_name = auth.get('header_name', 'X-API-Key')
        client_id = auth.get('client_id', '')
        client_secret = auth.get('client_secret', '')
        token_url = auth.get('token_url', '')

        users = data.get('users', {})
        business_rules = data.get('business_rules', {})

        # Build user_credentials dict literal
        users_literal = '{\n'
        for uid, u in users.items():
            users_literal += (
                f'        "{uid}": {{"email": "{u.get("email", "")}", '
                f'"password": "{u.get("password", "")}", '
                f'"role": "{u.get("role", "user")}"}},\n'
            )
        users_literal += '    }'

        # Build business_rules dict literal
        rules_literal = json.dumps(business_rules, indent=8) if business_rules else '{}'

        # Build the auth_headers fixture body based on auth type
        if auth_type == 'bearer':
            auth_fixture = f'''\
@pytest.fixture(scope="session")
def auth_headers():
    """Obtain a bearer token and return auth headers (cached for the session)."""
    response = requests.post(
        f"{{BASE_URL}}{login_url}",
        json={{"email": "{email}", "password": "{password}"}},
        timeout={timeout},
    )
    response.raise_for_status()
    token = response.json()["{token_field}"]
    return {{"Authorization": f"Bearer {{token}}", "Content-Type": "application/json"}}'''

        elif auth_type == 'apikey':
            auth_fixture = f'''\
@pytest.fixture(scope="session")
def auth_headers():
    """Return API-key auth headers."""
    return {{"{header_name}": "{api_key}", "Content-Type": "application/json"}}'''

        elif auth_type == 'oauth2':
            auth_fixture = f'''\
@pytest.fixture(scope="session")
def auth_headers():
    """Obtain an OAuth2 client-credentials token."""
    response = requests.post(
        "{token_url}",
        data={{
            "grant_type": "client_credentials",
            "client_id": "{client_id}",
            "client_secret": "{client_secret}",
        }},
        timeout={timeout},
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return {{"Authorization": f"Bearer {{token}}", "Content-Type": "application/json"}}'''

        elif auth_type == 'basic':
            import base64 as _b64
            b64 = _b64.b64encode(f"{auth.get('username','admin')}:{auth.get('password','')}".encode()).decode()
            auth_fixture = f'''\
@pytest.fixture(scope="session")
def auth_headers():
    """Return HTTP Basic auth headers (pre-encoded)."""
    return {{"Authorization": "Basic {b64}", "Content-Type": "application/json"}}'''

        else:  # none
            auth_fixture = '''\
@pytest.fixture(scope="session")
def auth_headers():
    """No authentication required."""
    return {"Content-Type": "application/json"}'''

        conftest = f'''\
"""
conftest.py — generated by AI Testing Agent (Task D: DataManager)
Source: {output_path.replace("conftest.py", "test_data.yaml")}
"""
import pytest
import requests

BASE_URL = "{base_url}"


@pytest.fixture(scope="session")
def api_client():
    """Shared requests.Session for all tests."""
    session = requests.Session()
    session.headers.update({{"Content-Type": "application/json"}})
    yield session
    session.close()


{auth_fixture}


@pytest.fixture(scope="session")
def user_credentials():
    """Dict of named test users loaded from test_data.yaml."""
    return {users_literal}


@pytest.fixture(scope="session")
def business_rules():
    """Business rules loaded from test_data.yaml."""
    return {rules_literal}
'''

        Path(output_path).write_text(conftest, encoding='utf-8')
        print(f"✓ Generated conftest.py → {output_path}")
        return output_path

    def generate_example_yaml(self, filepath: str = "test_data_example.yaml"):
        """Generate example YAML file."""
        example_data = {
            'environment': {
                'base_url': 'http://localhost:8000',
                'timeout': 30
            },
            'auth': {
                'type': 'bearer',
                'login_url': '/api/login',
                'credentials': {
                    'email': 'test@example.com',
                    'password': 'TestPass123!'
                },
                'token_field': 'token'
            },
            'users': {
                'valid_user': {
                    'email': 'john.doe@test.com',
                    'password': 'SecurePass123!',
                    'user_id': 'usr_123456',
                    'role': 'customer'
                },
                'admin_user': {
                    'email': 'admin@test.com',
                    'password': 'AdminPass456!',
                    'role': 'admin'
                },
                'locked_user': {
                    'email': 'locked@test.com',
                    'password': 'LockedPass789!',
                    'status': 'locked'
                }
            },
            'products': {
                'valid_product': {
                    'id': 'prod_abc123',
                    'name': 'Test Product',
                    'price': 29.99,
                    'in_stock': True
                },
                'out_of_stock': {
                    'id': 'prod_xyz789',
                    'name': 'Unavailable Product',
                    'price': 49.99,
                    'in_stock': False
                }
            },
            'business_rules': {
                'max_login_attempts': 5,
                'min_password_length': 8,
                'token_expiry_minutes': 60,
                'max_file_size_mb': 10,
                'allowed_file_types': ['pdf', 'doc', 'docx']
            },
            'expected_responses': {
                'login_success': {
                    'status': 200,
                    'fields': ['token', 'user_id', 'email']
                },
                'login_failure': {
                    'status': 401,
                    'fields': ['error', 'message']
                },
                'account_locked': {
                    'status': 429,
                    'fields': ['error', 'retry_after']
                }
            }
        }
        
        self._save_yaml(example_data, filepath)
        print(f"✓ Generated example file: {filepath}")
        return filepath
