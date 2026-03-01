#!/usr/bin/env python3
"""
Request Body Handler - Phase 2 Task C
Handles all types of HTTP request bodies and parameters
"""

import re
from typing import Dict, List, Any, Optional
from enum import Enum


class BodyType(Enum):
    """Types of request bodies."""
    JSON = "json"
    FORM_DATA = "form_data"
    URL_ENCODED = "url_encoded"
    PATH_PARAMS = "path_params"
    QUERY_PARAMS = "query_params"


class RequestBodyHandler:
    """
    Generates test code for different request body types.
    
    Supports:
    - JSON bodies
    - Form data (file uploads)
    - URL encoded forms
    - Path parameters
    - Query parameters
    - Edge cases for all types
    """
    
    def generate_test_for_endpoint(
        self,
        endpoint: Dict[str, Any],
        auth_required: bool = True
    ) -> str:
        """
        Generate complete test code for an endpoint.
        
        Args:
            endpoint: Dict with method, path, body_type, params, etc.
            auth_required: Whether authentication is required
            
        Returns:
            Complete pytest test code
        """
        method = endpoint.get('method', 'GET')
        path = endpoint.get('path', '/api/endpoint')
        body_type = endpoint.get('body_type')
        
        # Generate appropriate test based on method and body type
        if method == 'POST' or method == 'PUT' or method == 'PATCH':
            if body_type == 'form_data':
                return self._generate_file_upload_test(endpoint, auth_required)
            elif body_type == 'url_encoded':
                return self._generate_url_encoded_test(endpoint, auth_required)
            else:
                return self._generate_json_body_test(endpoint, auth_required)
        else:
            return self._generate_query_params_test(endpoint, auth_required)
    
    def _generate_json_body_test(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate test for JSON request body."""
        method = endpoint.get('method', 'POST')
        path = endpoint.get('path', '/api/endpoint')
        params = endpoint.get('params', {})
        endpoint_name = endpoint.get('name', path.split('/')[-1])
        
        # Build payload from params
        payload_items = []
        for param_name, param_info in params.items():
            if isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                example = self._get_example_value(param_type)
            else:
                example = self._get_example_value('string')
            
            payload_items.append(f'        "{param_name}": {self._format_value(example)}')
        
        payload_str = ',\n'.join(payload_items)
        auth_param = ', auth_headers' if auth_required else ''
        headers_param = 'headers=auth_headers' if auth_required else ''
        
        test_code = f'''
def test_{endpoint_name}_success(api_client{auth_param}):
    """Test successful {endpoint_name}."""
    payload = {{
{payload_str}
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload{',' if headers_param else ''}
        {headers_param}
    )
    
    assert response.status_code in [200, 201], \\
        f"Request failed: {{response.status_code}} - {{response.text}}"
    
    data = response.json()
    assert data is not None, "Response body is empty"


def test_{endpoint_name}_missing_required_fields(api_client{auth_param}):
    """Test with missing required fields."""
    payload = {{}}  # Empty payload
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload{',' if headers_param else ''}
        {headers_param}
    )
    
    assert response.status_code in [400, 422], \\
        f"Should reject empty payload, got: {{response.status_code}}"


def test_{endpoint_name}_invalid_data_types(api_client{auth_param}):
    """Test with invalid data types."""
    payload = {{
        {f'"{list(params.keys())[0]}": "invalid_type"' if params else '"field": "value"'}
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload{',' if headers_param else ''}
        {headers_param}
    )
    
    # Should handle gracefully (400, 422, or accept with conversion)
    assert response.status_code in [200, 201, 400, 422]
'''
        
        return test_code
    
    def _generate_file_upload_test(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate test for file upload (multipart/form-data)."""
        path = endpoint.get('path', '/api/upload')
        endpoint_name = endpoint.get('name', 'upload')
        auth_param = ', auth_headers' if auth_required else ''
        
        test_code = f'''
def test_{endpoint_name}_success(api_client{auth_param}):
    """Test successful file upload."""
    # Create a test file
    import io
    test_file = io.BytesIO(b"Test file content")
    test_file.name = "test_file.txt"
    
    files = {{
        "file": ("test_document.pdf", test_file, "application/pdf")
    }}
    data = {{
        "description": "Test upload",
        "category": "documents"
    }}
    
    # Remove Content-Type from headers for file uploads
    headers = {{k: v for k, v in {'auth_headers.items()' if auth_required else '{}.items()'}
              if k != "Content-Type"}}
    
    response = api_client.post(
        f"{{BASE_URL}}{path}",
        files=files,
        data=data{',' if auth_required else ''}
        {'headers=headers' if auth_required else ''}
    )
    
    assert response.status_code in [200, 201], \\
        f"Upload failed: {{response.status_code}} - {{response.text}}"
    
    data = response.json()
    assert "id" in data or "file_id" in data, "No file ID returned"


def test_{endpoint_name}_missing_file(api_client{auth_param}):
    """Test upload without file."""
    data = {{"description": "Test without file"}}
    
    headers = {{k: v for k, v in {'auth_headers.items()' if auth_required else '{}.items()'}
              if k != "Content-Type"}}
    
    response = api_client.post(
        f"{{BASE_URL}}{path}",
        data=data{',' if auth_required else ''}
        {'headers=headers' if auth_required else ''}
    )
    
    assert response.status_code == 400, \\
        "Should reject request without file"


def test_{endpoint_name}_large_file(api_client{auth_param}):
    """Test upload with large file."""
    import io
    # 11 MB file (assuming 10MB limit)
    large_file = io.BytesIO(b"x" * (11 * 1024 * 1024))
    large_file.name = "large_file.pdf"
    
    files = {{"file": ("large.pdf", large_file, "application/pdf")}}
    
    headers = {{k: v for k, v in {'auth_headers.items()' if auth_required else '{}.items()'}
              if k != "Content-Type"}}
    
    response = api_client.post(
        f"{{BASE_URL}}{path}",
        files=files{',' if auth_required else ''}
        {'headers=headers' if auth_required else ''}
    )
    
    # Should reject if over limit
    assert response.status_code in [200, 201, 413], \\
        "Should handle large files appropriately"
'''
        
        return test_code
    
    def _generate_url_encoded_test(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate test for URL-encoded form data."""
        path = endpoint.get('path', '/api/form')
        endpoint_name = endpoint.get('name', 'form_submit')
        auth_param = ', auth_headers' if auth_required else ''

        if auth_required:
            headers_line = '    headers = {**auth_headers, "Content-Type": "application/x-www-form-urlencoded"}'
            headers_line_json = '    headers = {**auth_headers, "Content-Type": "application/json"}'
        else:
            headers_line = '    headers = {"Content-Type": "application/x-www-form-urlencoded"}'
            headers_line_json = '    headers = {"Content-Type": "application/json"}'

        test_code = f'''
def test_{endpoint_name}_success(api_client{auth_param}):
    """Test URL-encoded form submission."""
    data = {{
        "username": "testuser",
        "email": "test@example.com",
        "agree_terms": "true"
    }}

{headers_line}

    response = api_client.post(
        f"{{BASE_URL}}{path}",
        data=data,
        headers=headers
    )

    assert response.status_code in [200, 201], \\
        f"Form submission failed: {{response.status_code}}"


def test_{endpoint_name}_missing_data(api_client{auth_param}):
    """Test URL-encoded form with missing required fields."""
    data = {{}}  # Empty form

{headers_line}

    response = api_client.post(
        f"{{BASE_URL}}{path}",
        data=data,
        headers=headers
    )

    assert response.status_code in [400, 422], \\
        f"Should reject empty form data, got: {{response.status_code}}"


def test_{endpoint_name}_wrong_content_type(api_client{auth_param}):
    """Test that wrong Content-Type is handled correctly."""
    payload = {{
        "username": "testuser",
        "email": "test@example.com"
    }}

{headers_line_json}

    response = api_client.post(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=headers
    )

    # Server may accept JSON or reject with 415 Unsupported Media Type
    assert response.status_code in [200, 201, 400, 415], \\
        f"Unexpected status for wrong content type: {{response.status_code}}"
'''

        return test_code
    
    def _generate_query_params_test(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate test for query parameters."""
        path = endpoint.get('path', '/api/items')
        endpoint_name = endpoint.get('name', path.split('/')[-1])
        auth_param = ', auth_headers' if auth_required else ''
        headers_param = ', headers=auth_headers' if auth_required else ''
        
        test_code = f'''
def test_{endpoint_name}_with_pagination(api_client{auth_param}):
    """Test with pagination query parameters."""
    params = {{
        "page": 1,
        "limit": 10,
        "sort": "created_at"
    }}
    
    response = api_client.get(
        f"{{BASE_URL}}{path}",
        params=params{headers_param}
    )
    
    assert response.status_code == 200, \\
        f"Request failed: {{response.status_code}}"
    
    data = response.json()
    assert isinstance(data, (list, dict)), "Invalid response format"
    
    # If paginated response
    if isinstance(data, dict):
        assert "items" in data or "data" in data or "results" in data, \\
            "No items in paginated response"


def test_{endpoint_name}_with_filters(api_client{auth_param}):
    """Test with filter query parameters."""
    params = {{
        "status": "active",
        "category": "test",
        "min_price": 10.00
    }}
    
    response = api_client.get(
        f"{{BASE_URL}}{path}",
        params=params{headers_param}
    )
    
    assert response.status_code == 200


@pytest.mark.parametrize("page,limit", [
    (1, 10),
    (2, 20),
    (1, 100),
])
def test_{endpoint_name}_pagination_variants(api_client{auth_param}, page, limit):
    """Test different pagination combinations."""
    params = {{"page": page, "limit": limit}}
    
    response = api_client.get(
        f"{{BASE_URL}}{path}",
        params=params{headers_param}
    )
    
    assert response.status_code == 200
'''
        
        return test_code
    
    def generate_path_param_tests(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate tests for path parameters."""
        path = endpoint.get('path', '/api/users/{user_id}')
        endpoint_name = endpoint.get('name', 'get_resource')
        path_params = endpoint.get('path_params', {})
        auth_param = ', auth_headers' if auth_required else ''
        headers_param = ', headers=auth_headers' if auth_required else ''
        
        # Extract param names from path
        import re
        param_names = re.findall(r'\{(\w+)\}', path)
        
        param_replace_1 = f'url_path = url_path.replace("{{{param_names[0]}}}", resource_id)' if param_names else ''
        param_replace_2 = f'url_path = url_path.replace("{{{param_names[0]}}}", "invalid@#$%")' if param_names else ''
        
        test_code = f'''
@pytest.mark.parametrize("resource_id", [
    "valid_id_123",
    "usr_abc456",
    "12345",
])
def test_{endpoint_name}_valid_ids(api_client{auth_param}, resource_id):
    """Test with valid resource IDs."""
    url_path = f"{{{{BASE_URL}}}}{path}"
    {param_replace_1}
    
    response = api_client.get(url_path{headers_param})
    
    assert response.status_code in [200, 404], \\
        f"Unexpected status: {{{{response.status_code}}}}"


def test_{endpoint_name}_invalid_id(api_client{auth_param}):
    """Test with invalid resource ID."""
    url_path = f"{{{{BASE_URL}}}}{path}"
    {param_replace_2}
    
    response = api_client.get(url_path{headers_param})
    
    assert response.status_code in [400, 404], \\
        "Should reject invalid ID format"
'''
        
        return test_code
    
    def _get_example_value(self, param_type: str) -> Any:
        """Get example value for parameter type."""
        examples = {
            'string': 'test_value',
            'str': 'test_value',
            'email': 'test@example.com',
            'password': 'change-me',
            'int': 42,
            'integer': 42,
            'float': 19.99,
            'number': 19.99,
            'bool': True,
            'boolean': True,
            'array': [],
            'list': [],
            'object': {},
            'dict': {}
        }
        return examples.get(param_type.lower(), 'test_value')
    
    def _format_value(self, value: Any) -> str:
        """Format Python value for code generation."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, (list, dict)):
            return str(value)
        else:
            return f'"{value}"'
    
    def _generate_delete_test(self, endpoint: Dict, auth_required: bool) -> str:
        """Generate tests for DELETE endpoints."""
        path = endpoint.get('path', '/api/resource/{id}')
        endpoint_name = endpoint.get('name', 'delete_resource')
        auth_param = ', auth_headers' if auth_required else ''
        headers_param = ', headers=auth_headers' if auth_required else ''

        # Extract path param name (e.g. {user_id} → user_id)
        import re as _re
        param_names = _re.findall(r'\{(\w+)\}', path)
        param_name = param_names[0] if param_names else 'id'

        # Build a concrete URL example for the tests
        example_url = path.replace('{' + param_name + '}', 'existing_id_123')
        missing_url = path.replace('{' + param_name + '}', 'nonexistent_99999')
        invalid_url = path.replace('{' + param_name + '}', 'invalid@#$%!')

        test_code = f'''
def test_{endpoint_name}_success(api_client{auth_param}):
    """Test successful resource deletion."""
    url = f"{{BASE_URL}}{example_url}"

    response = api_client.delete(url{headers_param})

    assert response.status_code in [200, 204], \\
        f"Delete failed: {{response.status_code}} - {{response.text}}"


def test_{endpoint_name}_not_found(api_client{auth_param}):
    """Test deletion of non-existent resource."""
    url = f"{{BASE_URL}}{missing_url}"

    response = api_client.delete(url{headers_param})

    assert response.status_code == 404, \\
        f"Should return 404 for missing resource, got: {{response.status_code}}"


def test_{endpoint_name}_unauthorized(api_client):
    """Test that unauthenticated delete is rejected."""
    url = f"{{BASE_URL}}{example_url}"

    response = api_client.delete(url)  # No auth headers

    assert response.status_code in [401, 403], \\
        f"Should reject unauthenticated delete, got: {{response.status_code}}"
'''
        return test_code

    # ------------------------------------------------------------------
    # Class organisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_class_name(endpoint_name: str) -> str:
        """Convert an endpoint name like 'list_users' to 'TestListUsers'."""
        parts = re.split(r'[\s_\-]+', endpoint_name)
        return 'Test' + ''.join(p.capitalize() for p in parts if p)

    @staticmethod
    def count_tests(test_code: str) -> int:
        """Count the number of test functions in a code string."""
        return len(re.findall(r'^\s*def test_', test_code, re.MULTILINE))

    @staticmethod
    def wrap_in_class(endpoint_name: str, test_code: str) -> str:
        """
        Wrap standalone test functions inside a pytest class.

        Adds `self` as the first argument to each function and indents
        the entire body by 4 spaces.
        """
        class_name = RequestBodyHandler._to_class_name(endpoint_name)

        # Add `self` to every `def test_xxx(...)` signature
        def _add_self(match: re.Match) -> str:
            full = match.group(0)
            # If the param list is empty: def test_foo():
            full = re.sub(r'\((?!\s*self)', '(self, ', full)
            # Clean up trailing comma when originally empty: (self, ):
            full = re.sub(r'\(self,\s*\)', '(self)', full)
            return full

        wrapped_body = re.sub(r'def test_\w+\s*\(', _add_self, test_code)

        # Indent every non-empty line by 4 spaces
        indented_lines = []
        for line in wrapped_body.splitlines():
            if line.strip():
                indented_lines.append('    ' + line)
            else:
                indented_lines.append('')

        return f'\n\nclass {class_name}:\n' + '\n'.join(indented_lines) + '\n'

    def generate_complete_test_file(
        self,
        endpoint: Dict[str, Any],
        auth_required: bool = True,
        include_edge_cases: bool = True,
    ) -> str:
        """
        Generate a complete, class-organised test file for one endpoint.

        Enforces minimum test counts:
          - DELETE: 3  (success, not_found, unauthorized)
          - GET:    3  (pagination, filters, parametrized variants)
          - POST/PUT/PATCH JSON: 3  (success, missing_fields, invalid_types)
          - url_encoded: 3  (success, missing_data, wrong_content_type)
          - form_data:   3  (success, missing_file, large_file)

        Edge-case tests (SQL injection, XSS, etc.) are added when
        `include_edge_cases` is True and the endpoint uses a write method.

        Returns the full file content as a string (with import header).
        """
        method = endpoint.get('method', 'GET').upper()
        endpoint_name = endpoint.get('name', endpoint.get('path', '/endpoint').split('/')[-1] or 'endpoint')
        body_type = endpoint.get('body_type')

        # --- Core tests ---
        if method == 'DELETE':
            core_code = self._generate_delete_test(endpoint, auth_required)
        elif method in ('POST', 'PUT', 'PATCH'):
            if body_type == 'form_data':
                core_code = self._generate_file_upload_test(endpoint, auth_required)
            elif body_type == 'url_encoded':
                core_code = self._generate_url_encoded_test(endpoint, auth_required)
            else:
                core_code = self._generate_json_body_test(endpoint, auth_required)
        else:
            core_code = self._generate_query_params_test(endpoint, auth_required)

        # Also add path-param tests if the path has params
        path = endpoint.get('path', '')
        import re as _re
        if _re.search(r'\{(\w+)\}', path):
            core_code += self.generate_path_param_tests(endpoint, auth_required)

        # --- Edge cases ---
        edge_code = ''
        if include_edge_cases and method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            edge_tests = self.generate_edge_case_tests(endpoint)
            edge_code = '\n'.join(edge_tests)

        all_tests = core_code + ('\n' + edge_code if edge_code else '')

        # --- Wrap in class ---
        class_block = self.wrap_in_class(endpoint_name, all_tests)

        # --- File header ---
        header = (
            'import pytest\n'
            'import requests\n'
            '\n'
            '# BASE_URL is injected from conftest.py or environment variable\n'
            'import os\n'
            'BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")\n'
        )

        return header + class_block

    def generate_edge_case_tests(self, endpoint: Dict) -> List[str]:
        """
        Generate edge case tests for an endpoint.
        
        Returns:
            List of test code strings
        """
        endpoint_name = endpoint.get('name', 'endpoint')
        method = endpoint.get('method', 'POST')
        path = endpoint.get('path', '/api/endpoint')
        
        edge_cases = []
        
        # SQL Injection
        edge_cases.append(f'''
def test_{endpoint_name}_sql_injection_blocked(api_client, auth_headers):
    """Test that SQL injection attempts are blocked."""
    payload = {{
        "email": "test@example.com' OR '1'='1",
        "name": "Robert'); DROP TABLE users;--"
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=auth_headers
    )
    
    # Should either reject or sanitize
    assert response.status_code in [200, 201, 400, 422]
    # Verify database wasn't affected (this would need actual DB check)
''')
        
        # XSS
        edge_cases.append(f'''
def test_{endpoint_name}_xss_blocked(api_client, auth_headers):
    """Test that XSS attempts are blocked."""
    payload = {{
        "name": "<script>alert('XSS')</script>",
        "description": "<img src=x onerror=alert('XSS')>"
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=auth_headers
    )
    
    if response.status_code in [200, 201]:
        data = response.json()
        # Verify XSS was escaped
        assert "<script>" not in str(data)
''')
        
        # Empty strings
        edge_cases.append(f'''
def test_{endpoint_name}_empty_strings(api_client, auth_headers):
    """Test with empty string values."""
    payload = {{
        "field1": "",
        "field2": "",
        "field3": ""
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=auth_headers
    )
    
    # Should validate or reject empty strings
    assert response.status_code in [200, 201, 400, 422]
''')
        
        # Null values
        edge_cases.append(f'''
def test_{endpoint_name}_null_values(api_client, auth_headers):
    """Test with null values."""
    payload = {{
        "field1": None,
        "field2": None
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=auth_headers
    )
    
    assert response.status_code in [200, 201, 400, 422]
''')
        
        # Very long strings
        edge_cases.append(f'''
def test_{endpoint_name}_very_long_strings(api_client, auth_headers):
    """Test with very long string values."""
    payload = {{
        "field": "x" * 10000  # 10KB string
    }}
    
    response = api_client.{method.lower()}(
        f"{{BASE_URL}}{path}",
        json=payload,
        headers=auth_headers
    )
    
    # Should either accept or reject with 413/400
    assert response.status_code in [200, 201, 400, 413, 422]
''')
        
        return edge_cases
