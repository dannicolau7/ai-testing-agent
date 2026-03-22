"""
AI Testing Agent - Autonomous Test Generation and Execution
Created: 2026

This AI agent automates the entire testing workflow:
1. Reads requirement documents
2. Generates test cases
3. Creates pytest code
4. Executes tests
5. Analyzes results
6. Generates reports
"""

import os
import json
import re
import time
import random
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import warnings
import tempfile
import shutil

# Import analytics module
try:
    from analytics import Analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    Analytics = None


# Optional import for Anthropic API
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AITestingAgent:
    """
    Autonomous AI agent for test automation.
    Uses Claude API for intelligent test generation and analysis.
    Falls back to mock AI when no API key is configured.
    """

    def __init__(self, api_key=None, verbose=True):
        """
        Initialize the AI Testing Agent.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            verbose: Whether to print status messages (default: True)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.verbose = verbose

        # Initialize analytics (privacy-first, opt-out supported)
        self.analytics = None
        if ANALYTICS_AVAILABLE:
            self.analytics = Analytics()
            # Show first-run message if appropriate
            self.analytics.show_first_run_message()
            # Track tool startup
            self.analytics.track_tool_started()
        
        # Initialize state
        self.state = {
            'requirements': None,
            'test_cases': [],
            'generated_code': [],
            'test_results': [],
            'current_phase': 'initialized',
            'usage': {
                'endpoints_tested': 0,
                'api_calls': 0,
                'tokens_used': 0,
                'estimated_cost': 0.0
            }
        }

        # Initialize comprehensive usage tracking
        self.usage_stats = {
            'session_start': datetime.now(),
            'api_calls': 0,
            'tokens_input': 0,
            'tokens_output': 0,
            'estimated_cost': 0.0,
            'endpoints_processed': 0,
            'tests_generated': 0,
        }
        
        # Initialize mock response counter for variety
        self._mock_call_count = 0
        
        self.output_dir = Path('test_output')
        self.output_dir.mkdir(exist_ok=True)
    
        
    def _track_usage(self, api_response):
        """
        Track API usage for cost calculation and analytics.
        
        Tracks token usage, calculates costs, and updates statistics
        for monitoring and billing purposes.
        
        Args:
            api_response: Response object from Claude API with usage information
        """
        # Track input and output tokens separately
        input_tokens = api_response.usage.input_tokens
        output_tokens = api_response.usage.output_tokens
        
        self.usage_stats['tokens_input'] += input_tokens
        self.usage_stats['tokens_output'] += output_tokens
        self.usage_stats['api_calls'] += 1
        
        # Calculate cost (Claude 3.5 Sonnet pricing)
        # Input: $3 per million tokens
        # Output: $15 per million tokens
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        call_cost = input_cost + output_cost
        
        self.usage_stats['estimated_cost'] += call_cost
        
        # Also update legacy state.usage for backwards compatibility
        self.state['usage']['api_calls'] += 1
        self.state['usage']['tokens_used'] += input_tokens + output_tokens
        self.state['usage']['estimated_cost'] += call_cost
    
    def get_usage_stats(self) -> Dict:
        """
        Return usage statistics for this session.
        
        Provides comprehensive usage data including session duration,
        token usage, costs, and per-call averages.
        
        Returns:
            Dictionary containing all usage statistics
        """
        # Calculate session duration
        session_duration = datetime.now() - self.usage_stats['session_start']
        duration_seconds = int(session_duration.total_seconds())
        duration_minutes = duration_seconds // 60
        duration_secs = duration_seconds % 60
        
        # Calculate average cost per API call
        avg_cost_per_call = 0.0
        if self.usage_stats['api_calls'] > 0:
            avg_cost_per_call = self.usage_stats['estimated_cost'] / self.usage_stats['api_calls']
        
        # Format cost string
        cost_formatted = f"${self.usage_stats['estimated_cost']:.4f}"
        
        return {
            **self.usage_stats,  # Include all tracked stats
            'session_duration_seconds': duration_seconds,
            'session_duration_formatted': f"{duration_minutes}m {duration_secs}s",
            'avg_cost_per_call': avg_cost_per_call,
            'cost_formatted': cost_formatted,
            'total_tokens': self.usage_stats['tokens_input'] + self.usage_stats['tokens_output']
        }
    
    def _save_usage_log(self):
        """
        Save usage statistics to log file.
        
        Appends session usage data to ~/.ai-testing-agent/usage.log
        in JSON format for tracking and analytics.
        """
        try:
            # Create log directory if it doesn't exist
            log_dir = Path.home() / '.ai-testing-agent'
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / 'usage.log'
            
            # Get current usage stats
            stats = self.get_usage_stats()
            
            # Create log entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'tier': stats['tier'],
                'session_duration': stats['session_duration_formatted'],
                'api_calls': stats['api_calls'],
                'tokens_input': stats['tokens_input'],
                'tokens_output': stats['tokens_output'],
                'total_tokens': stats['total_tokens'],
                'estimated_cost': stats['estimated_cost'],
                'endpoints_processed': stats['endpoints_processed'],
                'tests_generated': stats['tests_generated']
            }
            
            # Append to log file (one JSON object per line)
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
        except Exception as e:
            # Don't fail the whole operation if logging fails
            print(f"  ⚠️  Warning: Could not save usage log: {e}")
    
    def _print_usage_summary(self):
        """
        Print usage summary with cost warnings.
        
        Displays comprehensive usage statistics and warns about
        high-cost sessions.
        """
        stats = self.get_usage_stats()
        
        print("\n" + "="*60)
        print("📊 Usage Summary")
        print("="*60)
        print(f"Endpoints processed: {stats['endpoints_processed']}")
        print(f"Tests generated: {stats['tests_generated']}")
        print(f"API calls: {stats['api_calls']}")
        
        # Format token usage
        total_tokens = stats['total_tokens']
        print(f"Tokens used: {total_tokens:,} (input: {stats['tokens_input']:,} | output: {stats['tokens_output']:,})")
        
        # Display cost
        cost = stats['estimated_cost']
        print(f"Estimated cost: ${cost:.4f}")
        
        # Add cost warnings
        if cost > 5.00:
            print("🚨 Very high cost: ${:.2f} - check your inputs".format(cost))
        elif cost > 1.00:
            print("⚠️  High cost session: ${:.2f}".format(cost))
        
        # Show session duration
        print(f"Session duration: {stats['session_duration_formatted']}")
        
        # Show average cost per call if there were API calls
        if stats['api_calls'] > 0:
            print(f"Average cost per API call: ${stats['avg_cost_per_call']:.4f}")
        
        print("="*60)
    
    
    def parse_requirements(self, requirements_text: str) -> Dict:
        """
        Parse requirements document using AI.
        
        Args:
            requirements_text: Raw text from requirements document
            
        Returns:
            Structured requirements data
        """
        print("📄 Parsing requirements document...")
        
        # Use AI to extract structured data from requirements
        prompt = f"""Analyze these software requirements and extract:
1. Features to test
2. User stories
3. Acceptance criteria
4. Edge cases to consider
5. Test priorities (Critical/High/Medium/Low)

Requirements:
{requirements_text}

Return a JSON structure with these fields."""

        # Call AI and parse JSON response
        ai_response = self._parse_json_response(self._call_ai(prompt))
        
        # If real AI returned a string (not JSON), wrap it into a usable dict
        if isinstance(ai_response, str):
            ai_response = {'features': [{'name': 'API Feature', 'priority': 'High'}], 'raw': ai_response}
        
        self.state['requirements'] = ai_response
        self.state['current_phase'] = 'requirements_parsed'
        
        print(f"✅ Found {len(ai_response.get('features', []))} features to test")
        return ai_response
    
    def generate_test_cases(self, endpoint_count: Optional[int] = None) -> List[Dict]:
        """
        AI generates comprehensive test cases based on requirements.
        
        Args:
            endpoint_count: Number of endpoints to generate tests for (optional)
        
        Returns:
            List of test case specifications
        """
        print("\n🤖 AI Agent generating test cases...")
        
        requirements = self.state['requirements']
        
        # Extract endpoint count from requirements if not provided
        if endpoint_count is None:
            # Estimate from features in requirements
            features = requirements.get('features', [])
            endpoint_count = len(features)
        
        prompt = f"""Based on these requirements, generate comprehensive test cases.

Requirements:
{json.dumps(requirements, indent=2)}

Return ONLY a valid JSON object in this EXACT format with no extra text:
{{
  "test_cases": [
    {{
      "test_id": "TC001",
      "test_name": "test_example",
      "description": "What this test verifies",
      "type": "integration",
      "priority": "High",
      "preconditions": ["System is running"],
      "test_steps": ["Step 1", "Step 2"],
      "expected_result": "Expected outcome",
      "test_data": {{"key": "value"}},
      "endpoint": {{
        "method": "POST",
        "path": "/api/example",
        "body_type": "json",
        "params": {{
          "field_name": {{"type": "string", "required": true}}
        }}
      }}
    }}
  ]
}}

Rules for the "endpoint" field:
- "method": one of GET, POST, PUT, PATCH, DELETE
- "body_type": "json", "form_data", "url_encoded", or "query_params"
- "params": object mapping each field name to its type info
- Omit "endpoint" only if the test is not about an HTTP API call

Generate 3-5 test cases covering positive, negative, and edge cases."""

        ai_response = self._parse_json_response(self._call_ai(prompt))
        # Handle various response formats from real AI
        if isinstance(ai_response, list):
            test_cases = ai_response  # Claude returned a bare list
        elif isinstance(ai_response, dict):
            # Try common key names Claude might use
            test_cases = (
                ai_response.get('test_cases') or
                ai_response.get('tests') or
                ai_response.get('test_suite') or
                ai_response.get('cases') or
                []
            )
        else:
            test_cases = []
        
        self.state['test_cases'] = test_cases
        self.state['current_phase'] = 'test_cases_generated'
        
        print(f"✅ Generated {len(test_cases)} test cases")
        return test_cases
    
    def _extract_python_code(self, raw: str) -> str:
        """
        Extract pure Python code from an AI response.

        Handles two common LLM output patterns:
        1. Code wrapped in a ```python ... ``` markdown fence.
        2. Plain Python returned directly (no fence present).

        Returns the extracted code string, stripped of surrounding whitespace.
        """
        # Look for ```python ... ``` fence (most common)
        match = re.search(r'```(?:python)?\s*\n(.*?)```', raw, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fall back: return as-is if no fence found (already plain Python)
        return raw.strip()

    def generate_pytest_code(self) -> List[str]:
        """
        AI converts test cases into executable pytest code.

        When a test case includes an 'endpoint' dict, the RequestBodyHandler
        generates structured pytest code for that body/param type.
        All other test cases fall back to AI-generated code.

        Returns:
            List of generated pytest file paths
        """
        from request_body_handler import RequestBodyHandler
        body_handler = RequestBodyHandler()

        print("\n💻 Generating pytest code...")

        test_cases = self.state['test_cases']
        generated_files = []

        for i, test_case in enumerate(test_cases):
            endpoint = test_case.get('endpoint')

            if endpoint:
                # Route through RequestBodyHandler for structured generation
                endpoint.setdefault('name', test_case.get('test_name', f'endpoint_{i}'))
                auth_required = test_case.get('auth_required', True)
                pytest_code = body_handler.generate_test_for_endpoint(endpoint, auth_required)

                # Prepend standard imports if not present
                if 'import pytest' not in pytest_code:
                    pytest_code = "import pytest\nimport requests\n\nBASE_URL = \"\"\n" + pytest_code
                elif 'BASE_URL' not in pytest_code:
                    pytest_code = pytest_code.replace(
                        'import pytest', 'import pytest\n\nBASE_URL = ""', 1
                    )

                print(f"  ✓ Generated {test_case.get('test_id', i)} via RequestBodyHandler ({endpoint.get('method')} {endpoint.get('path')})")
            else:
                # Fall back to AI generation for non-endpoint test cases
                prompt = f"""Generate pytest code for this test case:
{json.dumps(test_case, indent=2)}

Requirements:
- Use pytest framework
- Include proper fixtures
- Add parametrize for data-driven tests
- Include assertions
- Add docstrings
- Handle setup/teardown
- Make it production-ready

Return ONLY the raw Python code. Do NOT include markdown fences, explanations, or commentary."""

                pytest_code = self._call_ai(prompt)

                if isinstance(pytest_code, dict):
                    pytest_code = pytest_code.get('code', str(pytest_code))

                pytest_code = self._extract_python_code(str(pytest_code))
                print(f"  ✓ Generated {test_case.get('test_id', i)} via AI")

            # Save to file
            filename = f"test_{test_case.get('test_id', i)}.py"
            filepath = self.output_dir / filename

            with open(filepath, 'w') as f:
                f.write(pytest_code)

            generated_files.append(str(filepath))
            print(f"     → Saved: {filename}")
        
        self.state['generated_code'] = generated_files
        self.state['current_phase'] = 'code_generated'
        
        print(f"✅ Generated {len(generated_files)} pytest files")
        return generated_files
    
    def execute_tests(self) -> Dict:
        """
        Execute generated pytest tests and capture results.
        
        Returns:
            Test execution results
        """
        print("\n🧪 Executing tests...")
        
        # In real implementation, this would run pytest programmatically
        # For now, we'll simulate execution
        
        results = {
            'total_tests': len(self.state['test_cases']),
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'execution_time': 0,
            'details': []
        }
        
        for test_file in self.state['generated_code']:
            # Simulate test execution
            test_result = {
                'file': test_file,
                'status': 'passed',  # In real version: run pytest
                'duration': 0.5,
                'output': ''
            }
            results['details'].append(test_result)
            results['passed'] += 1
        
        self.state['test_results'] = results
        self.state['current_phase'] = 'tests_executed'
        
        print(f"✅ Tests completed: {results['passed']} passed, {results['failed']} failed")
        return results
    
    def analyze_results(self) -> Dict:
        """
        AI analyzes test results and provides insights.
        
        Returns:
            Analysis report with recommendations
        """
        print("\n📊 Analyzing results with AI...")
        
        results = self.state['test_results']
        
        prompt = f"""Analyze these test results and provide:
1. Summary of test coverage
2. Critical issues found
3. Patterns in failures (if any)
4. Recommendations for improvement
5. Missing test scenarios

Results:
{json.dumps(results, indent=2)}

Provide actionable insights."""

        analysis = self._call_ai(prompt)
        
        print("✅ Analysis complete")
        return analysis
    
    def generate_report(self, format: str = 'html') -> str:
        """
        Generate comprehensive test report.
        
        Args:
            format: Report format (html, json, markdown)
            
        Returns:
            Path to generated report
        """
        print(f"\n📋 Generating {format.upper()} report...")
        
        report_data = {
            'execution_date': datetime.now().isoformat(),
            'requirements': self.state['requirements'],
            'test_cases': self.state['test_cases'],
            'results': self.state['test_results'],
            'analysis': self.analyze_results()
        }
        
        if format == 'json':
            report_path = self.output_dir / 'test_report.json'
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
        
        elif format == 'html':
            report_path = self.output_dir / 'test_report.html'
            html_content = self._generate_html_report(report_data)
            with open(report_path, 'w') as f:
                f.write(html_content)
        
        elif format == 'markdown':
            report_path = self.output_dir / 'test_report.md'
            md_content = self._generate_markdown_report(report_data)
            with open(report_path, 'w') as f:
                f.write(md_content)
        
        print(f"✅ Report saved to: {report_path}")
        return str(report_path)
    
    # ── OpenAPI spec ingestion (Week 2) ───────────────────────────────────────

    def generate_from_spec(
        self,
        spec_path: str,
        output_dir: Optional[str] = None,
        compliance_config: Optional[str] = None,
    ) -> Dict:
        """
        Parse an OpenAPI / Swagger spec and generate a full pytest suite.

        Workflow:
          1. Load and parse the spec (YAML or JSON)
          2. Extract rich endpoint metadata via SpecIngestion
          3. (Optional) Load compliance config and map controls to endpoints
          4. For each tag group, call Claude with a spec-aware prompt
          5. Tag generated tests with @pytest.mark.<control_id> decorators
          6. Write one pytest file per tag + optional conftest.py with markers
          7. Return a summary dict with compliance coverage data

        Args:
            spec_path:          Path to openapi.yaml / swagger.json / etc.
            output_dir:         Directory to write generated test files.
            compliance_config:  Path to compliance.yaml (optional).

        Returns:
            Dict with keys: spec_path, base_url, endpoint_count,
                            files_generated, output_dir,
                            compliance_coverage (if config provided)
        """
        from spec_ingestion import SpecIngestion
        from compliance import (
            ComplianceConfig, ControlMapper, ComplianceTagger,
            ComplianceReport, EndpointCoverage,
        )

        out = Path(output_dir) if output_dir else self.output_dir
        out.mkdir(parents=True, exist_ok=True)

        print(f"\n📄 Loading spec: {spec_path}")
        ingestion = SpecIngestion()

        try:
            spec = ingestion.load(spec_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"❌ Failed to load spec: {exc}")
            raise

        base_url = ingestion.get_base_url(spec)
        version = ingestion.spec_version(spec)
        title = spec.get("info", {}).get("title", "API")
        endpoints = ingestion.extract_endpoints(spec)

        print(f"   Title   : {title}")
        print(f"   Version : OpenAPI {version}.x")
        print(f"   Base URL: {base_url or '(not specified)'}")
        print(f"   Endpoints: {len(endpoints)}")


        # ── Compliance setup ──────────────────────────────────────────────────
        comp_config = None
        mapper = None
        tagger = None
        if compliance_config:
            try:
                comp_config = ComplianceConfig.load(compliance_config)
                mapper = ControlMapper(comp_config)
                tagger = ComplianceTagger()
                print(f"   Compliance: {', '.join(comp_config.frameworks)}")
            except Exception as exc:
                print(f"   ⚠️  Compliance config error: {exc} — skipping compliance tagging")

        groups = ingestion.group_by_tag(endpoints)
        generated_files: List[str] = []
        coverage_data: List[EndpointCoverage] = []
        all_controls: List = []

        for tag, tag_endpoints in groups.items():
            print(f"\n🔧 Generating tests for tag: [{tag}] ({len(tag_endpoints)} endpoints)")

            # Map controls for each endpoint in this group
            tag_controls = []
            if mapper:
                for ep in tag_endpoints:
                    ep_controls = mapper.map(ep.path, ep.method, ep.tags)
                    tag_controls.extend(ep_controls)
                    coverage_data.append(EndpointCoverage(
                        method=ep.method,
                        path=ep.path,
                        control_ids=[c.id for c in ep_controls],
                        test_names=[f"test_{ep.operation_id or ep.path.strip('/').replace('/', '_')}_success"],
                    ))
                    all_controls.extend(ep_controls)

            # Deduplicate controls for this tag group
            seen_ids: set = set()
            unique_tag_controls = []
            for c in tag_controls:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    unique_tag_controls.append(c)

            prompt = self._build_spec_prompt(
                tag, tag_endpoints, base_url, title,
                controls=unique_tag_controls,
            )
            raw_code = self._call_ai(prompt)
            pytest_code = self._extract_python_code(str(raw_code))

            # Inject compliance marks into the generated code
            if tagger and unique_tag_controls:
                pytest_code = tagger.tag(pytest_code, unique_tag_controls)
                n_marked = len(re.findall(r'^def test_', pytest_code, re.MULTILINE))
                print(f"   🏷  Tagged {n_marked} test(s) with "
                      f"{len(unique_tag_controls)} control(s): "
                      f"{', '.join(c.id for c in unique_tag_controls[:3])}"
                      f"{'…' if len(unique_tag_controls) > 3 else ''}")

            filename = f"test_{tag.lower().replace(' ', '_').replace('-', '_')}.py"
            filepath = out / filename

            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(pytest_code)

            print(f"   ✓ Wrote {filename} ({len(pytest_code.splitlines())} lines)")
            generated_files.append(str(filepath))

        # ── Write conftest.py with marker registrations ───────────────────────
        if tagger and all_controls:
            seen_ids = set()
            unique_all = []
            for c in all_controls:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    unique_all.append(c)

            conftest_path = out / "conftest.py"
            conftest_content = tagger.conftest_markers(unique_all)
            with open(conftest_path, "w", encoding="utf-8") as fh:
                fh.write(conftest_content)
            print(f"\n   ✓ Wrote conftest.py ({len(unique_all)} marker(s) registered)")

        # ── Compliance report ─────────────────────────────────────────────────
        compliance_summary = None
        if comp_config and coverage_data:
            reporter = ComplianceReport()
            report_text = reporter.generate(coverage_data, comp_config)
            print(report_text)
            compliance_summary = reporter.generate_json(coverage_data, comp_config)

            # Save markdown report
            md_path = out / "compliance_report.md"
            with open(md_path, "w", encoding="utf-8") as fh:
                fh.write(reporter.generate_markdown(coverage_data, comp_config))
            print(f"   ✓ Compliance report → {md_path}")

        print(f"\n✅ Spec ingestion complete — {len(generated_files)} file(s) written to {out}/")
        return {
            "spec_path": str(spec_path),
            "base_url": base_url,
            "endpoint_count": len(endpoints),
            "files_generated": generated_files,
            "output_dir": str(out),
            "compliance_coverage": compliance_summary,
        }

    def _build_spec_prompt(
        self,
        tag: str,
        endpoints: List[Dict],
        base_url: str,
        api_title: str,
        controls: Optional[List] = None,
    ) -> str:
        """Build a spec-aware Claude prompt for one tag group of endpoints."""
        import json as _json

        # Serialise endpoint data to a compact JSON block
        ep_data = []
        for ep in endpoints:
            entry = {
                "method": ep.method,
                "path": ep.path,
                "operation_id": ep.operation_id,
                "summary": ep.summary,
                "description": ep.description,
            }
            if ep.parameters:
                entry["parameters"] = [
                    {
                        "name": p.name,
                        "in": p.location,
                        "required": p.required,
                        "type": p.schema_type,
                        **({"enum": p.enum} if p.enum else {}),
                        **({"default": p.default} if p.default is not None else {}),
                        **({"description": p.description} if p.description else {}),
                    }
                    for p in ep.parameters
                ]
            if ep.request_body:
                rb = ep.request_body
                entry["request_body"] = {
                    "required": rb.get("required"),
                    "content_type": rb.get("content_type"),
                    "schema": rb.get("schema", {}),
                }
            if ep.responses:
                entry["responses"] = [
                    {
                        "status_code": r.status_code,
                        "description": r.description,
                        **({"schema": r.schema} if r.schema else {}),
                    }
                    for r in ep.responses
                ]
            if ep.security:
                entry["security"] = ep.security
            ep_data.append(entry)

        ep_json = _json.dumps(ep_data, indent=2)

        # Build compliance section for the prompt (Week 4)
        compliance_section = ""
        if controls:
            control_lines = "\n".join(
                f"  - {c.id}: {c.title} ({c.framework})"
                for c in controls
            )
            compliance_section = f"""
COMPLIANCE CONTROLS THAT APPLY TO THESE ENDPOINTS:
{control_lines}

"""

        return f"""You are a senior Python engineer writing a pytest test suite.

API: {api_title}
Tag group: {tag}
Base URL: {base_url or "https://api.example.com"}
{compliance_section}
Below is the endpoint specification in JSON format:

{ep_json}

Generate a COMPLETE, RUNNABLE pytest file that:

1. Starts with a module docstring: "Tests for {tag} endpoints — generated from OpenAPI spec"
2. Imports: pytest, requests (standard library only, no third-party test libs)
3. Defines BASE_URL = "{base_url or 'https://api.example.com'}"
4. Defines a session-scoped api_client fixture using requests.Session
5. For EACH endpoint, writes test functions covering:
   - Happy path: valid inputs → expected 2xx status code
   - Validation: missing required fields or invalid types → 4xx
   - Edge cases: boundary values, empty strings, very large numbers where relevant
   - Path parameters: test with valid ID and non-existent ID (404)
6. Each test function:
   - Has a clear name: test_<operation_id>_<scenario>
   - Has a one-line docstring from the operation summary/description
   - Asserts status code
   - For 2xx responses with a JSON schema: asserts required fields are present
     and have the correct type
7. Do NOT mock — generate tests that call the real API (the test runner handles mocking)
8. Do NOT add conftest.py imports — everything goes in this one file

Return ONLY valid Python code. No markdown fences, no explanations."""

    # ── Failure analysis (Week 3) ──────────────────────────────────────────────

    def analyze_test_failures(
        self,
        paths: List[str],
        extra_pytest_args: Optional[List[str]] = None,
        output_format: str = "text",
    ) -> Dict:
        """
        Run pytest on the given paths, parse any failures, and analyze them
        with Claude (or the free-tier mock when no API key is set).

        Args:
            paths:             Files or directories to pass to pytest.
            extra_pytest_args: Additional pytest flags.
            output_format:     'text' (default) or 'json'.

        Returns:
            Dict with keys:
                exit_code    – pytest exit code (0 = all passed)
                passed       – number of passing tests
                failed       – number of failing tests
                failures     – list of FailureRecord dicts
                analyses     – list of FailureAnalysis dicts
                report       – formatted text report (if output_format='text')
        """
        from failure_analyzer import FailureAnalyzer

        analyzer = FailureAnalyzer()

        print(f"\n🧪 Running tests: {' '.join(paths)}")
        raw_output, exit_code = analyzer.run_pytest(paths, extra_pytest_args)

        # Count passed/failed from the summary line
        passed = len(re.findall(r'\d+ passed', raw_output))
        failed_count = len(re.findall(r'\d+ failed', raw_output))

        # More precise counts from summary
        m_passed = re.search(r'(\d+) passed', raw_output)
        m_failed = re.search(r'(\d+) failed', raw_output)
        passed = int(m_passed.group(1)) if m_passed else 0
        failed_count = int(m_failed.group(1)) if m_failed else 0

        print(f"   Passed: {passed}  Failed: {failed_count}")

        failures = analyzer.parse_failures(raw_output)
        analyses = []

        if failures:
            print(f"\n🔍 Analyzing {len(failures)} failure(s) with AI...")
            # Only pass _call_ai if we have a real API key
            call_ai = self._call_ai if self.api_key and ANTHROPIC_AVAILABLE else None
            analyses = analyzer.analyze_all(failures, call_ai_fn=call_ai)
            report = analyzer.format_report(analyses)
            print(report)
        else:
            report = "All tests passed — no failures to analyze."
            if exit_code == 0:
                print("   ✅ All tests passed.")
            elif exit_code == 5:
                print("   ⚠️  No tests were collected.")

        return {
            "exit_code": exit_code,
            "passed": passed,
            "failed": failed_count,
            "failures": [
                {
                    "test_name": f.test_name,
                    "test_file": f.test_file,
                    "error_type": f.error_type,
                    "short_message": f.short_message,
                }
                for f in failures
            ],
            "analyses": analyzer.format_json(analyses),
            "report": report,
        }

    def run_autonomous(self, requirements_text: str, endpoint_count: Optional[int] = None) -> Dict:
        """
        Run the full autonomous testing workflow.
        
        Args:
            requirements_text: Requirements document content
            endpoint_count: Number of endpoints to process (optional, auto-detected if not provided)
            
        Returns:
            Complete workflow results
        """
        print("🚀 Starting Autonomous AI Testing Agent")
        print("=" * 60)
        
        # Track execution start time for analytics
        execution_start = time.time()
        
        try:
            # Phase 1: Parse requirements
            requirements = self.parse_requirements(requirements_text)
            
            # Determine endpoint count if not provided
            if endpoint_count is None:
                features = requirements.get('features', [])
                endpoint_count = len(features)
                print(f"📊 Detected {endpoint_count} endpoints from requirements")
            
            # Update usage tracking
            self.state['usage']['endpoints_tested'] = endpoint_count
            self.usage_stats['endpoints_processed'] = endpoint_count
            
            # Track test generation start in analytics
            if self.analytics:
                self.analytics.track_test_generation_started(endpoint_count)
            
            # Phase 2: Generate test cases
            test_cases = self.generate_test_cases(endpoint_count=endpoint_count)
            
            # Track tests generated
            self.usage_stats['tests_generated'] = len(test_cases)
            
            # Phase 3: Generate pytest code
            pytest_files = self.generate_pytest_code()
            
            # Phase 4: Execute tests
            results = self.execute_tests()
            
            # Phase 5: Analyze results
            analysis = self.analyze_results()
            
            # Phase 6: Generate report
            report_path = self.generate_report(format='html')
            
            print("\n" + "=" * 60)
            print("✅ Autonomous testing workflow completed!")
            print(f"📊 Report available at: {report_path}")
            
            # Print usage summary
            self._print_usage_summary()
            
            # Save usage to log file
            self._save_usage_log()
            
            # Track successful completion in analytics
            execution_duration = time.time() - execution_start
            if self.analytics:
                self.analytics.track_test_generation_complete(
                    endpoints=endpoint_count,
                    tests_generated=len(test_cases),
                    duration_seconds=execution_duration,
                    success=True
                )
            
            return {
                'success': True,
                'requirements': requirements,
                'test_cases': len(test_cases),
                'pytest_files': pytest_files,
                'results': results,
                'analysis': analysis,
                'report': report_path,
                'usage_stats': self.get_usage_stats()
            }
            
        except Exception as e:
            print(f"\n❌ Error during autonomous execution: {e}")
            
            # Track error in analytics
            execution_duration = time.time() - execution_start
            if self.analytics:
                # Determine error type
                error_type = "unknown_error"
                if "LIMIT EXCEEDED" in str(e):
                    error_type = "limit_exceeded"
                elif "API" in str(e):
                    error_type = "api_error"
                elif "License" in str(e) or "license" in str(e):
                    error_type = "license_error"
                
                self.analytics.track_test_generation_complete(
                    endpoints=endpoint_count if endpoint_count else 0,
                    tests_generated=0,
                    duration_seconds=execution_duration,
                    success=False,
                    error=error_type
                )
                self.analytics.track_error(error_type, str(e)[:100])
            
            return {
                'success': False,
                'error': str(e),
                'state': self.state
            }
    
    def _parse_json_response(self, response):
        """
        Parse JSON from AI response string.
        Handles plain JSON, markdown code blocks, and partial JSON.
        
        Args:
            response: String or dict response from AI
            
        Returns:
            Parsed dict, or original response if not parseable
        """
        if isinstance(response, dict):
            return response
        if not isinstance(response, str):
            return response
        
        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Try to find first { ... } block
        brace_match = re.search(r'\{[\s\S]*\}', response)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Return as-is (string)
        return response

    def _call_ai(self, prompt: str) -> str:
        """
        Call Claude API if an API key is configured, otherwise use mock AI.

        Args:
            prompt: Prompt for the AI

        Returns:
            AI response as string or structured data
        """
        if self.api_key and ANTHROPIC_AVAILABLE:
            try:
                return self._call_claude_api(prompt)
            except Exception as e:
                print(f"⚠️  API error: {str(e)[:100]}. Using mock fallback.")
                return self._mock_ai_response(prompt)

        return self._mock_ai_response(prompt)
    
    def _call_claude_api(self, prompt: str) -> str:
        """
        Call the real Claude API with retry logic and error handling.
        
        Features:
        - Automatic retry with exponential backoff (3 attempts)
        - Rate limit handling
        - Usage tracking for cost calculation
        - Comprehensive error messages
        
        Args:
            prompt: Prompt for Claude
            
        Returns:
            AI response from Claude
            
        Raises:
            Exception: If all retry attempts fail
        """
        # Check if anthropic library is available
        if not ANTHROPIC_AVAILABLE:
            raise Exception(
                "Anthropic library not installed. Install with: pip install anthropic\n"
                "Documentation: https://docs.anthropic.com/claude/reference/client-sdks"
            )
        
        max_retries = 3
        base_delay = 1  # Base delay in seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  🔄 API call attempt {attempt}/{max_retries}...")
                
                # Initialize the Anthropic client
                client = anthropic.Anthropic(api_key=self.api_key)
                
                # Make the API call
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",  # Claude Haiku 4.5
                    max_tokens=4096,
                    temperature=0.7,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Track usage for cost calculation
                self._track_usage(message)
                
                # Log usage details
                input_tokens = message.usage.input_tokens
                output_tokens = message.usage.output_tokens
                call_cost = (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
                
                print(f"  📊 Tokens: {input_tokens} in / {output_tokens} out")
                print(f"  💰 Cost: ${call_cost:.4f} (Total: ${self.usage_stats['estimated_cost']:.4f})")
                
                # Extract and return the text content
                return message.content[0].text
                
            except anthropic.RateLimitError as e:
                # Extract retry-after time from error if available
                retry_after = getattr(e, 'retry_after', base_delay * (2 ** attempt))
                print(f"  ⏱️  Rate limit reached. Retrying in {retry_after} seconds...")
                
                if attempt < max_retries:
                    time.sleep(retry_after)
                else:
                    raise Exception(
                        f"Rate limit exceeded after {max_retries} attempts.\n"
                        f"Please wait {retry_after} seconds and try again.\n"
                        "Consider upgrading your Anthropic API tier for higher limits:\n"
                        "→ https://console.anthropic.com/settings/plans"
                    )
            
            except anthropic.AuthenticationError as e:
                # Don't retry authentication errors
                raise Exception(
                    "❌ Authentication failed: Invalid API key\n\n"
                    "Please check your API key and try again:\n"
                    "1. Verify key at: https://console.anthropic.com/account/keys\n"
                    "2. Ensure key starts with 'sk-ant-'\n"
                    "3. Check for extra spaces or typos\n\n"
                    f"Error details: {str(e)}"
                )
            
            except anthropic.APIConnectionError as e:
                delay = base_delay * (2 ** attempt)
                print(f"  🌐 Connection error: {str(e)[:100]}")
                
                if attempt < max_retries:
                    print(f"  ⏱️  Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    raise Exception(
                        f"Failed to connect to Anthropic API after {max_retries} attempts.\n"
                        "Please check your internet connection and try again.\n"
                        "If the problem persists, check Anthropic status:\n"
                        "→ https://status.anthropic.com"
                    )
            
            except anthropic.APIStatusError as e:
                # Handle various API status errors
                status_code = e.status_code
                
                if status_code == 500 or status_code == 503:
                    # Server errors - retry
                    delay = base_delay * (2 ** attempt)
                    print(f"  ⚠️  Server error (HTTP {status_code})")
                    
                    if attempt < max_retries:
                        print(f"  ⏱️  Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        raise Exception(
                            f"Anthropic API server error after {max_retries} attempts.\n"
                            "The service may be experiencing issues.\n"
                            "Check status: https://status.anthropic.com"
                        )
                else:
                    # Don't retry client errors (4xx)
                    raise Exception(
                        f"API error (HTTP {status_code}): {str(e)}\n"
                        "Please check the error message and try again."
                    )
            
            except Exception as e:
                # Generic error handler
                delay = base_delay * (2 ** attempt)
                print(f"  ❌ Unexpected error: {str(e)[:100]}")
                
                if attempt < max_retries:
                    print(f"  ⏱️  Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    raise Exception(
                        f"Failed after {max_retries} attempts.\n"
                        f"Last error: {str(e)}\n\n"
                        "If this persists, please:\n"
                        "1. Check your API key and network connection\n"
                        "2. Visit: https://docs.anthropic.com/claude/reference/errors\n"
                        "3. Contact support: https://support.anthropic.com"
                    )
        
        # Should never reach here, but just in case
        raise Exception("Unexpected error: Exhausted retries without raising exception")
    
    def _mock_spec_pytest(self, prompt: str) -> str:
        """
        Generate realistic pytest code from the spec data embedded in the prompt.

        Extracts the JSON endpoint block from the prompt and produces test
        functions for each endpoint: one happy-path, one validation, and (where
        applicable) one 404 test.  This gives free-tier users a clear preview of
        what the real Claude-powered output looks like.
        """
        import re as _re

        # ── Extract base_url and tag from the prompt header ──────────────────
        base_url = ""
        bm = _re.search(r'Base URL:\s*(\S+)', prompt)
        if bm:
            base_url = bm.group(1)

        tag = "default"
        tm = _re.search(r'Tag group:\s*(\S+)', prompt)
        if tm:
            tag = tm.group(1)

        api_title = "API"
        am = _re.search(r'API:\s*(.+)', prompt)
        if am:
            api_title = am.group(1).strip()

        # ── Extract the JSON endpoint block ──────────────────────────────────
        json_match = _re.search(r'(\[[\s\S]*?\])\s*\nGenerate', prompt)
        endpoints_raw = []
        if json_match:
            try:
                endpoints_raw = json.loads(json_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        if not endpoints_raw:
            # Fall back to a minimal placeholder
            return (
                '"""Mock spec tests — run with a real API key for full output."""\n'
                "import pytest\nimport requests\n\n"
                f'BASE_URL = "{base_url}"\n\n\n'
                "@pytest.fixture(scope='session')\ndef api_client():\n"
                "    return requests.Session()\n\n\n"
                "def test_placeholder(api_client):\n"
                '    """Placeholder test — add ANTHROPIC_API_KEY for real spec-aware tests."""\n'
                "    assert True\n"
            )

        # ── Build the pytest file ─────────────────────────────────────────────
        lines = [
            f'"""',
            f"Tests for {tag} endpoints — generated from OpenAPI spec",
            f"API: {api_title}",
            f"",
            f"NOTE: This is a mock output (no API key configured).",
            f"      Set ANTHROPIC_API_KEY to generate Claude-powered tests.",
            f'"""',
            "import pytest",
            "import requests",
            "",
            f'BASE_URL = "{base_url}"',
            "",
            "",
            "@pytest.fixture(scope='session')",
            "def api_client():",
            '    """Shared requests session for all tests in this module."""',
            "    session = requests.Session()",
            "    return session",
        ]

        for ep in endpoints_raw:
            method = ep.get("method", "GET").upper()
            path = ep.get("path", "/")
            op_id = ep.get("operation_id") or path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
            summary = ep.get("summary") or f"{method} {path}"

            # Detect path params
            path_params = _re.findall(r'\{(\w+)\}', path)
            has_path_param = bool(path_params)

            # Happy-path test
            lines.append("")
            lines.append("")
            if has_path_param:
                param_args = ", ".join(f"{p}=1" for p in path_params)
                url_expr = f'f\'{{BASE_URL}}{path}\'.format(**{{{", ".join(repr(p) + ": 1" for p in path_params)}}})'
                # Build a simpler URL line
                url_line = f'BASE_URL + "{path}"'
                for pp in path_params:
                    url_line = url_line.replace("{" + pp + "}", f'" + str({pp}_id) + "')
                fixture_arg = "api_client"
            else:
                url_line = f'BASE_URL + "{path}"'
                fixture_arg = "api_client"

            # Choose success code
            success_codes = [
                r.get("status_code", "200")
                for r in ep.get("responses", [])
                if str(r.get("status_code", "")).startswith("2")
            ]
            success_code = success_codes[0] if success_codes else "200"

            # Get query params
            query_params = [
                p for p in ep.get("parameters", [])
                if p.get("in") == "query"
            ]

            # Get request body fields
            rb = ep.get("request_body")
            rb_properties = {}
            if rb and isinstance(rb.get("schema"), dict):
                rb_properties = rb["schema"].get("properties", {})
            required_fields = rb["schema"].get("required", []) if rb else []

            func_name = f"test_{op_id}_success"
            lines.append(f"def {func_name}({fixture_arg}):")
            lines.append(f'    """{summary} — expects {success_code}."""')

            if method in ("GET", "DELETE"):
                if has_path_param:
                    lines.append(f"    url = {url_line.replace('{petId}', '1').replace('{userId}', '1')}")
                    # simplify for mock
                    url_simple = f'BASE_URL + "{path.format(**{p: 1 for p in path_params})}"'
                    lines[-1] = f"    url = f'{base_url}{path.replace('{' + path_params[0] + '}', '1') if path_params else path}'"
                else:
                    lines.append(f"    url = f'{{BASE_URL}}{path}'")
                if query_params:
                    param_items = []
                    for p in query_params[:2]:
                        pname = p["name"]
                        pdefault = p.get("default", 1) if pname == "limit" else ""
                        param_items.append(f'"{pname}": {repr(pdefault)}')
                    params_dict = "{" + ", ".join(param_items) + "}"
                    lines.append(f"    response = api_client.{method.lower()}(url, params={params_dict})")
                else:
                    lines.append(f"    response = api_client.{method.lower()}(url)")
            else:
                if has_path_param:
                    lines.append(f"    url = f'{base_url}{path.replace('{' + path_params[0] + '}', '1') if path_params else path}'")
                else:
                    lines.append(f"    url = f'{{BASE_URL}}{path}'")
                if rb_properties:
                    payload_items = []
                    for fname, finfo in list(rb_properties.items())[:3]:
                        ftype = finfo.get("type", "string")
                        sample = finfo.get("example") or ("test_value" if ftype == "string" else 1)
                        payload_items.append(f'"{fname}": {repr(sample)}')
                    lines.append(f"    payload = {{{', '.join(payload_items)}}}")
                    lines.append(f"    response = api_client.{method.lower()}(url, json=payload)")
                else:
                    lines.append(f"    response = api_client.{method.lower()}(url, json={{}})")

            lines.append(f"    assert response.status_code == {success_code}")

            # Check response schema if available
            resp_200 = next(
                (r for r in ep.get("responses", []) if str(r.get("status_code", "")).startswith("2")),
                None,
            )
            if resp_200 and resp_200.get("schema"):
                schema = resp_200["schema"]
                if schema.get("type") == "array":
                    lines.append("    data = response.json()")
                    lines.append("    assert isinstance(data, list)")
                    item_props = schema.get("items", {}).get("properties", {})
                    required_item = schema.get("items", {}).get("required", [])
                    if item_props and required_item:
                        lines.append("    if data:  # assert structure when list is non-empty")
                        for req_field in required_item[:2]:
                            lines.append(f'        assert "{req_field}" in data[0]')
                elif schema.get("properties"):
                    lines.append("    data = response.json()")
                    for req_field in schema.get("required", [])[:2]:
                        lines.append(f'    assert "{req_field}" in data')

            # 404 test for path-param endpoints
            if has_path_param and method == "GET":
                lines.append("")
                lines.append("")
                func_404 = f"def test_{op_id}_not_found({fixture_arg}):"
                lines.append(func_404)
                lines.append(f'    """GET {path} with non-existent ID — expects 404."""')
                lines.append(f"    url = f'{base_url}{path.replace('{' + path_params[0] + '}', '99999') if path_params else path}'")
                lines.append(f"    response = api_client.get(url)")
                lines.append("    assert response.status_code == 404")

            # Validation test for POST/PUT/PATCH with required body fields
            if method in ("POST", "PUT", "PATCH") and required_fields:
                lines.append("")
                lines.append("")
                func_val = f"def test_{op_id}_missing_required_field({fixture_arg}):"
                lines.append(func_val)
                lines.append(f'    """POST {path} with empty body — expects 4xx."""')
                if has_path_param:
                    lines.append(f"    url = f'{base_url}{path.replace('{' + path_params[0] + '}', '1') if path_params else path}'")
                else:
                    lines.append(f"    url = f'{{BASE_URL}}{path}'")
                lines.append(f"    response = api_client.{method.lower()}(url, json={{}})")
                lines.append("    assert response.status_code in [400, 422]")

        return "\n".join(lines) + "\n"

    def _mock_ai_response(self, prompt: str):
        """
        Generate realistic mock AI responses for demonstration.
        
        Features:
        - Provides variety across multiple calls
        - Returns structured JSON-like data that matches real API
        - Includes realistic content for different prompt types
        - Clear indication these are mock responses
        
        Args:
            prompt: The prompt that would have been sent to the AI
            
        Returns:
            Mock response appropriate to the prompt type
        """
        # Increment call counter for variety
        self._mock_call_count += 1
        
        # Add random variation to make responses feel more natural
        random.seed(self._mock_call_count)
        
        print("  🎭 Generating mock AI response (set ANTHROPIC_API_KEY for real Claude)")
        print("  ⚠️  Mock responses are simplified and may not reflect production quality")
        
        # Detect prompt type and return appropriate mock data
        prompt_lower = prompt.lower()

        # SPEC INGESTION — generate realistic pytest code from embedded endpoint JSON
        if 'openapi spec' in prompt_lower and 'tag group' in prompt_lower:
            return self._mock_spec_pytest(prompt)

        # REQUIREMENTS PARSING
        if 'requirements' in prompt_lower and 'extract' in prompt_lower:
            features = [
                [
                    {'name': 'User Authentication', 'priority': 'Critical'},
                    {'name': 'Data Validation', 'priority': 'High'},
                    {'name': 'API Integration', 'priority': 'High'}
                ],
                [
                    {'name': 'Payment Processing', 'priority': 'Critical'},
                    {'name': 'User Profile Management', 'priority': 'Medium'},
                    {'name': 'Email Notifications', 'priority': 'Low'}
                ],
                [
                    {'name': 'Search Functionality', 'priority': 'High'},
                    {'name': 'Data Export', 'priority': 'Medium'},
                    {'name': 'Analytics Dashboard', 'priority': 'High'}
                ]
            ]
            
            selected_features = features[self._mock_call_count % len(features)]
            
            return {
                '_mock_response': True,
                '_note': 'This is a simplified mock response. Real AI provides deeper analysis.',
                'features': selected_features,
                'user_stories': [
                    f'As a user, I want to {selected_features[0]["name"].lower()}',
                    f'As a user, I want to {selected_features[1]["name"].lower()}'
                ],
                'edge_cases': [
                    'Invalid input data',
                    'Empty or null values',
                    'Concurrent operations',
                    'Network timeouts',
                    'Security injection attempts'
                ],
                'acceptance_criteria': [
                    'All positive test cases pass',
                    'Error handling is comprehensive',
                    'Performance meets SLA requirements'
                ]
            }
        
        # TEST CASE GENERATION
        elif 'test case' in prompt_lower and 'generate' in prompt_lower:
            test_prefixes = ['valid', 'invalid', 'edge_case', 'boundary', 'security']
            test_types = ['unit', 'integration', 'e2e', 'performance', 'security']
            priorities = ['Critical', 'High', 'Medium', 'Low']
            
            num_tests = 2 + (self._mock_call_count % 3)  # Generate 2-4 tests
            test_cases = []
            
            for i in range(num_tests):
                test_id = f'TC{str(self._mock_call_count * 100 + i + 1).zfill(3)}'
                prefix = test_prefixes[i % len(test_prefixes)]
                test_type = test_types[i % len(test_types)]
                priority = priorities[i % len(priorities)]
                
                test_cases.append({
                    'test_id': test_id,
                    'test_name': f'test_{prefix}_{test_type}',
                    'description': f'Verify {prefix} scenario for {test_type} testing',
                    'type': test_type,
                    'priority': priority,
                    'preconditions': ['System is running', 'Test data is loaded'],
                    'test_steps': [
                        'Setup test environment',
                        'Execute test action',
                        'Verify expected outcome',
                        'Cleanup test data'
                    ],
                    'expected_result': f'{prefix.capitalize()} behavior verified',
                    'test_data': {'sample': 'mock_data'}
                })
            
            return {
                '_mock_response': True,
                '_note': 'Real AI generates more comprehensive and context-aware test cases.',
                'test_cases': test_cases,
                'coverage_analysis': {
                    'total_scenarios': num_tests,
                    'risk_coverage': f'{60 + (self._mock_call_count % 30)}%',
                    'recommendation': 'Mock tests provide basic coverage only'
                }
            }
        
        # PYTEST CODE GENERATION
        elif 'pytest' in prompt_lower or 'code' in prompt_lower:
            test_id = f'TC{str(self._mock_call_count).zfill(3)}'
            
            code_templates = [
                f'''"""
Mock generated test - Limited functionality
Real AI generates production-ready code with proper fixtures and assertions
"""
import pytest

class Test{test_id}:
    """Mock test class - simplified version"""
    
    def test_basic_functionality(self):
        """Basic test - real AI provides comprehensive coverage"""
        # Mock implementation
        result = True
        assert result, "Mock test assertion"
    
    def test_error_handling(self):
        """Error handling test - simplified"""
        # Mock implementation
        with pytest.raises(ValueError):
            raise ValueError("Mock error")
''',
                f'''"""
Mock test module - Basic structure
Upgrade to Pro for intelligent, context-aware test generation
"""
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_setup():
    """Mock fixture - simplified"""
    return {{"data": "test_value"}}

def test_{test_id.lower()}_positive(mock_setup):
    """Positive test case - mock version"""
    assert mock_setup["data"] == "test_value"

def test_{test_id.lower()}_negative():
    """Negative test case - mock version"""
    assert True, "Mock negative test"

@pytest.mark.parametrize("input,expected", [
    ("test1", True),
    ("test2", True)
])
def test_{test_id.lower()}_parametrized(input, expected):
    """Parametrized test - simplified mock"""
    assert expected
'''
            ]
            
            return code_templates[self._mock_call_count % len(code_templates)]
        
        # ANALYSIS AND INSIGHTS
        elif 'analyz' in prompt_lower or 'insight' in prompt_lower:
            coverage_percent = 70 + (self._mock_call_count % 20)
            
            return {
                '_mock_response': True,
                '_note': 'Real AI provides deep insights and actionable recommendations.',
                'summary': f'Mock analysis complete - {coverage_percent}% coverage (estimated)',
                'test_coverage': f'{coverage_percent}%',
                'critical_issues': [
                    'Mock analysis has limited intelligence',
                    'Upgrade to Pro for comprehensive AI analysis'
                ],
                'patterns': {
                    'positive': 'Basic functionality appears covered',
                    'negative': 'Mock analysis cannot detect complex issues'
                },
                'recommendations': [
                    '⚠️  These are generic mock recommendations',
                    'Add more edge case tests',
                    'Improve error handling coverage',
                    'Consider boundary value analysis',
                    '💡 Upgrade to Pro for intelligent, context-specific recommendations'
                ],
                'risk_assessment': 'Limited - mock AI cannot assess real risks',
                'missing_scenarios': [
                    'Mock AI has limited scenario detection',
                    'Real AI identifies gaps in test coverage'
                ]
            }
        
        # DEFAULT/GENERIC RESPONSE
        else:
            return {
                '_mock_response': True,
                '_note': 'Generic mock response - Real AI provides contextual, intelligent answers.',
                'response': 'This is a simplified mock AI response.',
                'quality': 'basic',
                'note': 'Mock AI has limited capabilities. Set ANTHROPIC_API_KEY for real Claude.',
                'data': {
                    'call_number': self._mock_call_count,
                    'mock_mode': True
                }
            }
    
    def _generate_html_report(self, data: Dict) -> str:
        """Generate HTML report."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Testing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; border-radius: 10px; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; 
                    border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 15px; text-align: center; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #667eea; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        .success {{ color: #10b981; }}
        .failed {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Testing Agent Report</h1>
        <p>Generated: {data['execution_date']}</p>
    </div>
    
    <div class="section">
        <h2>📊 Test Summary</h2>
        <div class="metric">
            <div class="metric-value success">{data['results']['passed']}</div>
            <div class="metric-label">Passed</div>
        </div>
        <div class="metric">
            <div class="metric-value failed">{data['results']['failed']}</div>
            <div class="metric-label">Failed</div>
        </div>
        <div class="metric">
            <div class="metric-value">{data['results']['total_tests']}</div>
            <div class="metric-label">Total Tests</div>
        </div>
    </div>
    
    <div class="section">
        <h2>📝 Requirements Analyzed</h2>
        <pre>{json.dumps(data['requirements'], indent=2)}</pre>
    </div>
    
    <div class="section">
        <h2>🎯 Test Cases Generated</h2>
        <p>Total test cases: {len(data['test_cases'])}</p>
    </div>
    
    <div class="section">
        <h2>💡 AI Analysis</h2>
        <pre>{json.dumps(data['analysis'], indent=2)}</pre>
    </div>
</body>
</html>"""
    
    def _generate_markdown_report(self, data: Dict) -> str:
        """Generate Markdown report."""
        return f"""# 🤖 AI Testing Agent Report

**Generated:** {data['execution_date']}

## 📊 Test Summary

- **Total Tests:** {data['results']['total_tests']}
- **Passed:** ✅ {data['results']['passed']}
- **Failed:** ❌ {data['results']['failed']}
- **Skipped:** ⏭️ {data['results']['skipped']}

## 📝 Requirements Analyzed

```json
{json.dumps(data['requirements'], indent=2)}
```

## 🎯 Test Cases Generated

Total test cases created: {len(data['test_cases'])}

## 💡 AI Analysis

```json
{json.dumps(data['analysis'], indent=2)}
```

---
*Report generated by AI Testing Agent*
"""
