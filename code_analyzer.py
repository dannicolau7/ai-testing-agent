#!/usr/bin/env python3
"""
API Code Analyzer - Phase 2 Task E
Analyzes API code from various frameworks to extract endpoints
"""

import re
import ast
from typing import Dict, List, Any, Optional
from enum import Enum


class Framework(Enum):
    """Supported frameworks."""
    FASTAPI = "fastapi"
    FLASK = "flask"
    EXPRESS = "express"
    OPENAPI = "openapi"
    PLAIN_TEXT = "plain_text"


class CodeAnalyzer:
    """
    Analyzes API code and extracts endpoint information.
    
    Supports:
    - Python FastAPI
    - Python Flask
    - Node.js Express
    - OpenAPI/Swagger YAML
    - Plain English descriptions (via AI)
    """
    
    def analyze(self, source: str, framework: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Analyze source code and extract endpoints.
        
        Args:
            source: API source code or specification
            framework: Force specific framework (auto-detect if None)
            
        Returns:
            List of endpoint dictionaries
        """
        if framework:
            detected_framework = Framework(framework.lower())
        else:
            detected_framework = self._detect_framework(source)
        
        print(f"🔍 Detected framework: {detected_framework.value}")
        
        if detected_framework == Framework.FASTAPI:
            return self._parse_fastapi(source)
        elif detected_framework == Framework.FLASK:
            return self._parse_flask(source)
        elif detected_framework == Framework.EXPRESS:
            return self._parse_express(source)
        elif detected_framework == Framework.OPENAPI:
            return self._parse_openapi(source)
        else:
            return self._analyze_plain_text(source)
    
    def _detect_framework(self, source: str) -> Framework:
        """Auto-detect framework from source code."""
        source_lower = source.lower()
        
        # Check for FastAPI
        if 'fastapi' in source_lower or '@app.post' in source_lower or '@app.get' in source_lower:
            if 'from fastapi' in source_lower or 'import fastapi' in source_lower:
                return Framework.FASTAPI
        
        # Check for Flask
        if 'flask' in source_lower or '@app.route' in source_lower:
            if 'from flask' in source_lower or 'import flask' in source_lower:
                return Framework.FLASK
        
        # Check for Express
        if 'express' in source_lower or 'app.get(' in source_lower or 'app.post(' in source_lower:
            if 'require(' in source_lower or 'import' in source_lower:
                return Framework.EXPRESS
        
        # Check for OpenAPI/Swagger
        if 'openapi:' in source_lower or 'swagger:' in source_lower:
            if 'paths:' in source_lower:
                return Framework.OPENAPI
        
        # Default to plain text
        return Framework.PLAIN_TEXT
    
    def _parse_fastapi(self, source: str) -> List[Dict[str, Any]]:
        """Parse FastAPI code to extract endpoints."""
        endpoints = []
        
        try:
            tree = ast.parse(source)
        except SyntaxError:
            print("⚠️  Failed to parse Python code, falling back to regex")
            return self._parse_fastapi_regex(source)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for route decorators (handles both def and async def)
                for decorator in node.decorator_list:
                    endpoint_info = self._extract_fastapi_decorator(decorator, node)
                    if endpoint_info:
                        endpoints.append(endpoint_info)
        
        return endpoints
    
    def _extract_fastapi_decorator(self, decorator: ast.AST, func_node: Any) -> Optional[Dict]:
        """Extract endpoint info from FastAPI decorator."""
        if not isinstance(decorator, ast.Call):
            return None
        
        # Get decorator name (e.g., app.post, app.get)
        decorator_name = self._get_decorator_name(decorator)
        
        if not any(method in decorator_name.lower() for method in ['get', 'post', 'put', 'delete', 'patch']):
            return None
        
        # Extract HTTP method
        method = None
        for m in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            if m.lower() in decorator_name.lower():
                method = m
                break
        
        # Extract path
        path = None
        if decorator.args:
            path_arg = decorator.args[0]
            if isinstance(path_arg, ast.Constant):
                path = path_arg.value
        
        # Extract parameters from function signature
        params = {}
        for arg in func_node.args.args:
            if arg.arg not in ['self', 'request', 'db', 'session']:
                param_type = 'string'
                if arg.annotation:
                    param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else 'string'
                params[arg.arg] = {'type': param_type, 'required': True}
        
        # Extract docstring
        docstring = ast.get_docstring(func_node) or ''

        resolved_path = path or f'/api/{func_node.name}'
        resolved_method = method or 'GET'

        # Merge path params into params dict
        path_params = self._extract_path_params(resolved_path)
        params.update(path_params)

        # Reconstruct function source for auth / body-type detection
        try:
            func_src = ast.unparse(func_node) if hasattr(ast, 'unparse') else ''
        except Exception:
            func_src = ''

        return {
            'method': resolved_method,
            'path': resolved_path,
            'name': func_node.name,
            'description': docstring.split('\n')[0] if docstring else f"{func_node.name} endpoint",
            'params': params,
            'body_type': self._infer_body_type(resolved_method, resolved_path, func_src),
            'auth_required': self._detect_auth(func_src),
            'framework': 'fastapi',
        }
    
    def _parse_fastapi_regex(self, source: str) -> List[Dict[str, Any]]:
        """Fallback regex parsing for FastAPI."""
        endpoints = []
        
        # Pattern: @app.post("/api/login")
        pattern = r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']\s*\)'
        matches = re.finditer(pattern, source, re.IGNORECASE)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Try to find function name
            func_match = re.search(r'def\s+(\w+)\s*\(', source[match.end():match.end()+200])
            func_name = func_match.group(1) if func_match else path.split('/')[-1]
            
            context = source[match.start():match.end() + 400]
            path_params = self._extract_path_params(path)
            endpoints.append({
                'method': method,
                'path': path,
                'name': func_name,
                'description': f"{func_name} endpoint",
                'params': path_params,
                'body_type': self._infer_body_type(method, path, context),
                'auth_required': self._detect_auth(context),
                'framework': 'fastapi',
            })
        
        return endpoints
    
    def _parse_flask(self, source: str) -> List[Dict[str, Any]]:
        """Parse Flask code to extract endpoints."""
        endpoints = []
        
        # Pattern: @app.route('/api/login', methods=['POST'])
        pattern = r"@app\.route\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*methods\s*=\s*\[([^\]]+)\])?\s*\)"
        matches = re.finditer(pattern, source)
        
        for match in matches:
            path = match.group(1)
            methods_str = match.group(2)
            
            # Parse methods
            methods = ['GET']  # Default
            if methods_str:
                methods = [m.strip().strip("'\"") for m in methods_str.split(',')]
            
            # Find function name
            func_match = re.search(r'def\s+(\w+)\s*\(', source[match.end():match.end()+200])
            func_name = func_match.group(1) if func_match else path.split('/')[-1]
            
            context = source[max(0, match.start() - 100):match.end() + 400]
            auth_required = self._detect_auth(context)
            path_params = self._extract_path_params(path)

            for method in methods:
                m = method.upper()
                endpoints.append({
                    'method': m,
                    'path': path,
                    'name': f"{func_name}_{method.lower()}" if len(methods) > 1 else func_name,
                    'description': f"{func_name} endpoint",
                    'params': dict(path_params),
                    'body_type': self._infer_body_type(m, path, context),
                    'auth_required': auth_required,
                    'framework': 'flask',
                })
        
        return endpoints
    
    def _parse_express(self, source: str) -> List[Dict[str, Any]]:
        """Parse Express.js code to extract endpoints."""
        endpoints = []
        
        # Pattern: app.post('/api/login', async (req, res) =>
        pattern = r"app\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]\s*"
        matches = re.finditer(pattern, source)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Check for auth middleware
            auth_required = any(auth in source[match.start():match.start()+200] 
                              for auth in ['authenticateToken', 'requireAuth', 'isAuthenticated'])
            
            # Extract req.body parameters
            params = {}
            body_match = re.search(r'(?:const|let|var)\s*\{([^}]+)\}\s*=\s*req\.body', 
                                 source[match.end():match.end()+300])
            if body_match:
                param_names = [p.strip() for p in body_match.group(1).split(',')]
                params = {name: {'type': 'any', 'required': True} for name in param_names}
            
            context = source[match.start():match.end() + 400]
            path_params = self._extract_path_params(path)
            params.update(path_params)
            endpoints.append({
                'method': method,
                'path': path,
                'name': path.split('/')[-1] or 'root',
                'description': f"{method} {path}",
                'params': params,
                'body_type': self._infer_body_type(method, path, context),
                'auth_required': auth_required,
                'framework': 'express',
            })
        
        return endpoints
    
    def _parse_openapi(self, source: str) -> List[Dict[str, Any]]:
        """Parse OpenAPI/Swagger YAML to extract endpoints."""
        endpoints = []
        
        try:
            import yaml
            spec = yaml.safe_load(source)
        except:
            print("⚠️  Failed to parse YAML, using regex fallback")
            return self._parse_openapi_regex(source)
        
        if 'paths' not in spec:
            return endpoints
        
        for path, path_item in spec['paths'].items():
            for method, operation in path_item.items():
                if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                    continue
                
                params = {}
                
                # Extract parameters
                if 'requestBody' in operation:
                    content = operation['requestBody'].get('content', {})
                    if 'application/json' in content:
                        schema = content['application/json'].get('schema', {})
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        
                        for param_name, param_schema in properties.items():
                            params[param_name] = {
                                'type': param_schema.get('type', 'string'),
                                'required': param_name in required
                            }
                
                m = method.upper()
                path_params = self._extract_path_params(path)
                params.update(path_params)
                security = operation.get('security') or spec.get('security')
                endpoints.append({
                    'method': m,
                    'path': path,
                    'name': operation.get('operationId', path.split('/')[-1]),
                    'description': operation.get('summary') or operation.get('description', ''),
                    'params': params,
                    'body_type': self._infer_body_type(m, path),
                    'auth_required': bool(security),
                    'framework': 'openapi',
                })
        
        return endpoints
    
    def _parse_openapi_regex(self, source: str) -> List[Dict[str, Any]]:
        """Fallback regex parsing for OpenAPI."""
        endpoints = []
        
        # Simple pattern for paths
        path_pattern = r'/[a-zA-Z0-9/_{}]+'
        paths = re.findall(path_pattern, source)
        
        for path in paths:
            # Check methods near this path
            path_pos = source.find(path)
            context = source[path_pos:path_pos+500]
            
            for method in ['get', 'post', 'put', 'delete', 'patch']:
                if f'{method}:' in context.lower():
                    endpoints.append({
                        'method': method.upper(),
                        'path': path,
                        'name': path.split('/')[-1] or 'root',
                        'description': f"{method.upper()} {path}",
                        'params': {},
                        'framework': 'openapi'
                    })
        
        return endpoints
    
    def _analyze_plain_text(self, source: str) -> List[Dict[str, Any]]:
        """Analyze plain English description of API."""
        endpoints = []
        
        # Look for common patterns
        # "POST /api/login" or "login endpoint" etc
        
        # Pattern 1: HTTP method + path
        pattern1 = r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)'
        matches1 = re.finditer(pattern1, source, re.IGNORECASE)
        
        for match in matches1:
            method = match.group(1).upper()
            path = match.group(2)
            
            endpoints.append({
                'method': method,
                'path': path,
                'name': path.split('/')[-1] or 'endpoint',
                'description': self._extract_description_near(source, match.start()),
                'params': self._extract_params_from_text(source, match.start()),
                'framework': 'plain_text'
            })
        
        # Pattern 2: "login endpoint", "user registration", etc
        if not endpoints:
            pattern2 = r'(\w+)\s+(?:endpoint|API|route)'
            matches2 = re.finditer(pattern2, source, re.IGNORECASE)
            
            for match in matches2:
                endpoint_name = match.group(1).lower()
                method = 'POST' if any(word in endpoint_name for word in ['create', 'login', 'register', 'add']) else 'GET'
                
                endpoints.append({
                    'method': method,
                    'path': f'/api/{endpoint_name}',
                    'name': endpoint_name,
                    'description': self._extract_description_near(source, match.start()),
                    'params': self._extract_params_from_text(source, match.start()),
                    'framework': 'plain_text'
                })
        
        return endpoints
    
    def _extract_description_near(self, text: str, pos: int, window: int = 200) -> str:
        """Extract description near a position."""
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        context = text[start:end]
        
        # Get first sentence
        sentences = re.split(r'[.!?]\s+', context)
        return sentences[0] if sentences else context[:100]
    
    def _extract_params_from_text(self, text: str, pos: int, window: int = 300) -> Dict:
        """Extract parameters from text description."""
        params = {}
        
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        context = text[start:end]
        
        # Look for "email", "password", etc
        common_params = ['email', 'password', 'username', 'name', 'id', 'token']
        
        for param in common_params:
            if param in context.lower():
                params[param] = {'type': 'string', 'required': True}
        
        return params
    
    def _get_decorator_name(self, decorator: ast.Call) -> str:
        """Get decorator name from AST node."""
        if isinstance(decorator.func, ast.Attribute):
            return f"{decorator.func.value.id}.{decorator.func.attr}"
        elif isinstance(decorator.func, ast.Name):
            return decorator.func.id
        return ""
    
    # ──────────────────────────────────────────────────────────────────
    # Helpers used by all parsers
    # ──────────────────────────────────────────────────────────────────

    def _infer_body_type(self, method: str, path: str, context: str = '') -> str:
        """
        Infer the request body type for an endpoint.

        Rules (in priority order):
        1. File-upload signals in context → form_data
        2. URL-encoded signals in context → url_encoded
        3. Path contains {param} → path_params (for GET/DELETE only)
        4. POST/PUT/PATCH with no upload signals → json
        5. GET/DELETE → query_params
        """
        context_lower = context.lower()

        if any(sig in context_lower for sig in ['uploadfile', 'file =', 'multipart', 'form-data', 'spooledtemporaryfile']):
            return 'form_data'

        if any(sig in context_lower for sig in ['form(', 'form_data', 'urlencoded', 'x-www-form']):
            return 'url_encoded'

        if method.upper() in ('POST', 'PUT', 'PATCH'):
            return 'json'

        return 'query_params'

    def _extract_path_params(self, path: str) -> Dict[str, Any]:
        """Extract {param} tokens from a URL path into a params dict."""
        param_names = re.findall(r'\{(\w+)\}', path)
        return {name: {'type': 'string', 'required': True, 'location': 'path'}
                for name in param_names}

    def _detect_auth(self, context: str) -> bool:
        """Return True if the context suggests authentication is required."""
        auth_signals = [
            'authenticate', 'requireauth', 'isauthorized', 'isauthenticated',
            'login_required', 'current_user', 'get_current_user',
            'depends(', 'oauth2_scheme', 'bearer', 'verify_token',
        ]
        context_lower = context.lower()
        return any(sig in context_lower for sig in auth_signals)

    # ──────────────────────────────────────────────────────────────────

    def generate_summary(self, endpoints: List[Dict]) -> str:
        """Generate summary of analyzed endpoints."""
        if not endpoints:
            return "No endpoints found"
        
        summary = f"\n📊 Analysis Summary\n"
        summary += f"{'='*50}\n"
        summary += f"Total endpoints: {len(endpoints)}\n"
        
        # Group by method
        methods = {}
        for endpoint in endpoints:
            method = endpoint['method']
            methods[method] = methods.get(method, 0) + 1
        
        summary += f"\nBy HTTP method:\n"
        for method, count in sorted(methods.items()):
            summary += f"  {method}: {count}\n"
        
        summary += f"\nEndpoints:\n"
        for i, endpoint in enumerate(endpoints, 1):
            summary += f"  {i}. {endpoint['method']} {endpoint['path']}\n"
            if endpoint.get('description'):
                summary += f"     {endpoint['description']}\n"
        
        return summary
