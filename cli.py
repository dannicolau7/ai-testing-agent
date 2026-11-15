#!/usr/bin/env python3
"""
AI Testing Agent CLI
Command-line interface for the AI Testing Agent

Usage:
    python cli.py tier
    python cli.py analyze requirements.txt
    python cli.py generate requirements.txt --format html
    python cli.py run requirements.txt --api-key YOUR_KEY
"""

import argparse
import json
import re
import sys
import os
from pathlib import Path
from ai_testing_agent import AITestingAgent

# Import analytics for status command
try:
    from analytics import show_analytics_status, disable_telemetry as disable_analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

# Rich console (used by request command)
try:
    from rich.console import Console as _RichConsole
    console = _RichConsole()
except ImportError:
    console = None

# Version information
__version__ = "1.0.0"


def read_requirements_file(filepath: str) -> str:
    """Read requirements from file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: File '{filepath}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)


def cmd_usage(args):
    """Display current session usage statistics."""
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'

    agent = AITestingAgent(api_key=args.api_key)
    stats = agent.get_usage_stats()

    print("\n" + "="*70)
    print("📊 Session Usage Statistics")
    print("="*70)
    print(f"API calls:          {stats['api_calls']}")
    print(f"Tokens (in/out):    {stats['tokens_input']:,} / {stats['tokens_output']:,}")
    print(f"Total tokens:       {stats['total_tokens']:,}")
    print(f"Estimated cost:     {stats['cost_formatted']}")
    print(f"Endpoints processed:{stats['endpoints_processed']}")
    print(f"Tests generated:    {stats['tests_generated']}")
    print(f"Session duration:   {stats['session_duration_formatted']}")
    print("="*70 + "\n")


def cmd_analytics_status(args):
    """Display analytics configuration and status."""
    if not ANALYTICS_AVAILABLE:
        print("\n❌ Analytics module not available")
        print("   Make sure analytics.py is in the same directory\n")
        return

    from analytics import Analytics
    analytics = Analytics()
    status = analytics.get_status()

    print("\n" + "="*70)
    print("📊 Analytics Status")
    print("="*70)
    print(f"Status: {'✅ Enabled' if status['enabled'] else '❌ Disabled'}")
    print(f"Anonymous ID: {status['anonymous_id']}")

    print("\n📦 What we collect:")
    for item in status['data_collected']:
        print(f"  ✓ {item}")

    print("\n🔒 What we DON'T collect:")
    for item in status['data_not_collected']:
        print(f"  ✗ {item}")

    print("\n⚙️  Opt-out methods:")
    for method in status['opt_out_methods']:
        print(f"  • {method}")

    print("="*70 + "\n")


def cmd_analytics_disable(args):
    """Disable analytics/telemetry."""
    if not ANALYTICS_AVAILABLE:
        print("\n❌ Analytics module not available")
        return
    
    print("\n🔧 Disabling telemetry...")
    disable_analytics()
    print("\n✅ Telemetry has been disabled")
    print("   Analytics will not be collected in future sessions")
    print("   To re-enable, remove or edit: ~/.ai-testing-agent/config.json\n")




def cmd_analyze(args):
    """Analyze requirements and generate test cases."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    print("🔍 Analyzing requirements...")
    
    requirements_text = read_requirements_file(args.requirements)
    agent = AITestingAgent(api_key=args.api_key)
    
    # Parse requirements
    requirements = agent.parse_requirements(requirements_text)
    
    # Generate test cases
    test_cases = agent.generate_test_cases()
    
    print(f"\n✅ Analysis complete!")
    print(f"   Features found: {len(requirements.get('features', []))}")
    print(f"   Test cases generated: {len(test_cases)}")


def cmd_generate(args):
    """Generate pytest code from requirements."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    print("💻 Generating pytest code...")
    
    requirements_text = read_requirements_file(args.requirements)
    agent = AITestingAgent(api_key=args.api_key)
    
    # Parse and generate
    agent.parse_requirements(requirements_text)
    agent.generate_test_cases()
    pytest_files = agent.generate_pytest_code()
    
    print(f"\n✅ Generated {len(pytest_files)} pytest files")
    for file in pytest_files:
        print(f"   📄 {file}")


def _is_spec_file(path: str) -> bool:
    """
    Return True when the file looks like an OpenAPI / Swagger spec.

    Detects by file extension first, then by peeking at the first few
    hundred bytes for 'openapi:' or 'swagger:' keys.
    """
    p = Path(path)
    if p.suffix.lower() in (".yaml", ".yml", ".json") and p.exists():
        try:
            sample = p.read_text(encoding="utf-8", errors="ignore")[:500].lower()
            return "openapi:" in sample or "swagger:" in sample
        except OSError:
            pass
    return False


def cmd_run(args):
    """Run full autonomous testing workflow."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'

    input_path = args.requirements
    agent = AITestingAgent(api_key=args.api_key)

    # ── OpenAPI / Swagger spec path ──────────────────────────────────────────
    force_spec = getattr(args, "spec", False)
    if force_spec or _is_spec_file(input_path):
        print(f"📄 OpenAPI spec detected — using spec ingestion mode")
        output_dir = getattr(args, "output", "./test_output")
        compliance_path = getattr(args, "compliance", None)
        result = agent.generate_from_spec(
            input_path,
            output_dir=output_dir,
            compliance_config=compliance_path,
        )
        print(f"\n✅ Generated {result['endpoint_count']} endpoint(s)")
        print(f"   Files   : {len(result['files_generated'])}")
        for f in result['files_generated']:
            print(f"            {f}")

        # --analyze: run the generated tests and diagnose failures
        if getattr(args, "analyze", False) and result["files_generated"]:
            agent.analyze_test_failures(result["files_generated"])
        return

    # ── Plain requirements / doc path ────────────────────────────────────────
    print("🚀 Running autonomous AI testing workflow...")

    requirements_text = read_requirements_file(input_path)

    # Run autonomous workflow
    result = agent.run_autonomous(requirements_text)
    
    if result['success']:
        print(f"\n✅ Workflow completed successfully!")
        print(f"   Test cases: {result['test_cases']}")
        print(f"   Tests passed: {result['results']['passed']}")
        print(f"   Report: {result['report']}")
        
        # Phase 2 Task A: Generate complete project structure
        if hasattr(args, 'output') and args.output:
            from project_generator import ProjectGenerator
            
            print(f"\n🏗️  Generating complete test project...")
            generator = ProjectGenerator(output_dir=args.output)
            
            # Create test files dict (using result data)
            test_files = {}
            if 'pytest_files' in result:
                for filename in result['pytest_files']:
                    # Read generated test file
                    filepath = Path(filename)
                    if filepath.exists():
                        test_files[filepath.name] = filepath.read_text()
            
            # If no test files found, create sample from test output
            if not test_files:
                # Use existing test_TC*.py files as templates
                test_output_dir = Path("./test_output")
                if test_output_dir.exists():
                    for test_file in test_output_dir.glob("test_TC*.py"):
                        test_files[test_file.name] = test_file.read_text()
            
            # Generate complete project
            generator.generate_complete_project(
                test_files=test_files,
                base_url="http://localhost:8000",
                auth_type="bearer"
            )
    else:
        print(f"\n❌ Workflow failed: {result['error']}")


def cmd_failures(args):
    """Run pytest on existing test files and AI-analyze any failures."""
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'

    agent = AITestingAgent(api_key=args.api_key)
    result = agent.analyze_test_failures(list(args.paths))

    if getattr(args, 'json_output', False):
        import json
        print(json.dumps({
            "exit_code": result["exit_code"],
            "passed": result["passed"],
            "failed": result["failed"],
            "analyses": result["analyses"],
        }, indent=2))
    else:
        # report was already printed inside analyze_test_failures
        exit_code = result["exit_code"]
        if exit_code not in (0, 5):
            sys.exit(exit_code)


def cmd_compliance_report(args):
    """Generate a compliance coverage report from a test output directory."""
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'

    try:
        from compliance import ComplianceConfig, ControlMapper, ComplianceReport, EndpointCoverage
    except ImportError:
        print("❌ compliance.py not found — run from the project root.")
        sys.exit(1)

    # Load config
    try:
        config = ComplianceConfig.load(args.compliance)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ Could not load compliance config: {exc}")
        sys.exit(1)

    # Scan test directory for .py files and extract marked test names + paths
    test_dir = Path(args.test_dir)
    if not test_dir.exists():
        print(f"❌ Directory not found: {test_dir}")
        sys.exit(1)

    mapper = ControlMapper(config)
    coverage: list[EndpointCoverage] = []

    for py_file in sorted(test_dir.glob("test_*.py")):
        source = py_file.read_text()
        # Extract decorated function names grouped by endpoint path heuristic
        # (best-effort: use the filename stem as a tag proxy)
        tag = py_file.stem.replace("test_", "")
        # Find all test function names in the file
        test_names = [
            line.strip().split("def ")[1].split("(")[0]
            for line in source.splitlines()
            if line.strip().startswith("def test_")
        ]
        if not test_names:
            continue
        # Map controls by tag keyword
        controls = mapper.map(f"/{tag}", "GET", tags=[tag])
        control_ids = [c.id for c in controls]
        cov = EndpointCoverage(
            method="*",
            path=f"/{tag}",
            control_ids=control_ids,
            test_names=test_names,
        )
        coverage.append(cov)

    reporter = ComplianceReport()

    if args.format == 'markdown':
        report_text = reporter.generate_markdown(coverage, config)
    elif args.format == 'json':
        import json
        report_text = json.dumps(reporter.generate_json(coverage, config), indent=2)
    else:
        report_text = reporter.generate(coverage, config)

    if args.out:
        Path(args.out).write_text(report_text)
        print(f"✅ Compliance report written to {args.out}")
    else:
        print(report_text)


# ──────────────────────────────────────────────────────────────────────────────
# Request command (Postman replacement)
# ──────────────────────────────────────────────────────────────────────────────

def add_request_command(subparsers):
    """Register the 'request' sub-command with its full argument set."""
    request_parser = subparsers.add_parser(
        'request',
        help='Send an HTTP request (Postman replacement)',
        description=(
            'Send HTTP requests from the command line and optionally capture them\n'
            'as runnable pytest test files.\n\n'
            'Examples:\n'
            '  python cli.py request GET /api/users\n'
            '  python cli.py request POST /api/login \\\n'
            '    --body \'{"email":"test@test.com","password":"pass"}\'\n'
            '  python cli.py request GET /api/profile --auth bearer --token eyJ...\n'
            '  python cli.py request POST /api/login \\\n'
            '    --body \'{"email":"test@test.com","password":"pass"}\' \\\n'
            '    --save-as-test --test-name login_test'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    request_parser.add_argument(
        'method',
        choices=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
        nargs='?',
        help='HTTP method (not required in --interactive mode)',
    )

    request_parser.add_argument(
        'path',
        nargs='?',
        help='API path, e.g. /api/login (not required in --interactive mode)',
    )

    request_parser.add_argument(
        '--base-url',
        help='Base URL override (default: env_manager → BASE_URL env var → http://localhost:8000)',
        default=None,
    )

    request_parser.add_argument(
        '--body',
        help='Request body as a JSON string, e.g. \'{"key":"value"}\'',
        default=None,
    )

    request_parser.add_argument(
        '--headers',
        help='Extra headers as a JSON string, e.g. \'{"X-Custom":"value"}\'',
        default=None,
    )

    request_parser.add_argument(
        '--params',
        help='Query-string parameters as a JSON string, e.g. \'{"page":"1"}\'',
        default=None,
    )

    request_parser.add_argument(
        '--auth',
        choices=['bearer', 'apikey', 'basic', 'none'],
        help='Authentication type (default: none)',
        default='none',
    )

    request_parser.add_argument(
        '--token',
        help=(
            'Token / API key to use with --auth.\n'
            '  bearer : JWT or opaque token\n'
            '  apikey : raw key value\n'
            '  basic  : "username:password" (colon-separated)'
        ),
        default=None,
    )

    request_parser.add_argument(
        '--timeout',
        help='Request timeout in seconds (default: 30)',
        type=int,
        default=30,
    )

    request_parser.add_argument(
        '--save-as-test',
        action='store_true',
        help='Save this request/response as a pytest test file',
    )

    request_parser.add_argument(
        '--test-name',
        help='Function name for the saved test (default: manual_request)',
        default='manual_request',
    )

    request_parser.add_argument(
        '--output',
        help='Directory to save generated test file (default: ./test_output)',
        default='./test_output',
    )

    request_parser.add_argument(
        '--env',
        help='Named environment to load base URL from (default: dev)',
        default='dev',
    )

    request_parser.add_argument(
        '--show-request',
        action='store_true',
        help='Print the full request panel before sending',
    )

    request_parser.add_argument(
        '--curl',
        action='store_true',
        help='Print the equivalent curl command and exit',
    )

    request_parser.add_argument(
        '--repeat',
        help='Send N times and show latency stats (benchmark mode)',
        type=int,
        default=None,
        metavar='N',
    )

    request_parser.add_argument(
        '--retry',
        help='Retry up to N times on network errors or 5xx responses',
        type=int,
        default=0,
        metavar='N',
    )

    request_parser.add_argument(
        '--save-to-collection',
        help='Save this request to a collection with the given name',
        default=None,
        metavar='NAME',
    )

    request_parser.add_argument(
        '--collection-file',
        help='Path to collection JSON file (default: ./requests_collection.json)',
        default='./requests_collection.json',
    )

    request_parser.add_argument(
        '--interactive',
        action='store_true',
        help='Launch interactive REPL request builder (ignores method/path args)',
    )

    request_parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze the response and print assertion suggestions after sending',
    )

    request_parser.set_defaults(func=handle_request_command)


def handle_request_command(args):
    """Handle the 'request' sub-command end-to-end."""
    try:
        from rich.console import Console as _C
        _console = _C()
    except ImportError:
        class _FallbackConsole:
            def print(self, msg, **_):
                import re as _re
                print(_re.sub(r'\[/?[^\]]+\]', '', str(msg)))
        _console = _FallbackConsole()

    try:
        from request_runner import RequestRunner
    except ImportError:
        _console.print("[red]❌ request_runner.py not found.[/red]")
        return

    # --interactive: enter REPL mode and return immediately
    if getattr(args, 'interactive', False):
        runner = RequestRunner(base_url=getattr(args, 'base_url', None), env=getattr(args, 'env', 'dev'))
        runner.interactive_mode(output_path=getattr(args, 'output', './test_output'))
        return

    # method and path are required for non-interactive mode
    if not args.method or not args.path:
        _console.print("[red]❌ method and path are required. Use --interactive for REPL mode.[/red]")
        _console.print("   Example: python cli.py request GET /api/users")
        _console.print("   REPL:    python cli.py request --interactive")
        return

    # Parse JSON args
    body = None
    if args.body:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError as exc:
            _console.print(f"[red]❌ Invalid JSON in --body: {exc}[/red]")
            return

    headers = None
    if args.headers:
        try:
            headers = json.loads(args.headers)
        except json.JSONDecodeError as exc:
            _console.print(f"[red]❌ Invalid JSON in --headers: {exc}[/red]")
            return

    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as exc:
            _console.print(f"[red]❌ Invalid JSON in --params: {exc}[/red]")
            return

    auth = None
    if args.auth != 'none':
        auth = {'type': args.auth, 'token': args.token}

    runner = RequestRunner(base_url=args.base_url, env=args.env)

    # Correct URL for display
    _display_url = (
        args.path
        if args.path.startswith("http://") or args.path.startswith("https://")
        else f"{runner.base_url}{args.path if args.path.startswith('/') else '/' + args.path}"
    )

    # --curl: print curl command and exit
    if args.curl:
        curl_cmd = runner.to_curl(
            method=args.method, path=args.path,
            headers=headers, body=body, params=params, auth=auth,
        )
        _console.print("\n[yellow]curl command:[/yellow]")
        _console.print(curl_cmd)
        _console.print()
        return

    # --show-request: display request panel before sending
    if args.show_request:
        runner.display_request(
            method=args.method, path=args.path,
            headers=headers, body=body, params=params, auth=auth,
        )

    _console.print(f"\n[cyan]→ {args.method}  {_display_url}[/cyan]")
    if auth:
        _console.print(f"[dim]  Auth: {args.auth}[/dim]")
    if body:
        _console.print(f"[dim]  Body: {str(body)[:120]}[/dim]")

    # --repeat: benchmark mode
    if args.repeat:
        runner.run_benchmark(
            method=args.method, path=args.path, n=args.repeat,
            headers=headers, body=body, params=params, auth=auth,
            timeout=args.timeout,
        )
        return

    # Send (with optional retry)
    try:
        if args.retry > 0:
            response = runner.retry_send(
                method=args.method, path=args.path,
                headers=headers, body=body, params=params, auth=auth,
                timeout=args.timeout, retries=args.retry,
            )
        else:
            response = runner.send(
                method=args.method, path=args.path,
                headers=headers, body=body, params=params, auth=auth,
                timeout=args.timeout,
            )
    except Exception:
        return

    runner.display_response(response)

    # --analyze: run pattern-based response analysis
    if getattr(args, 'analyze', False):
        runner.analyze_response(response, method=args.method, path=args.path)

    # --save-as-test
    if args.save_as_test:
        runner.save_as_test(
            response=response, test_name=args.test_name,
            output_path=args.output, method=args.method, path=args.path,
            body=body, headers=headers, params=params,
        )

    # --save-to-collection
    if args.save_to_collection:
        runner.save_collection(
            name=args.save_to_collection,
            method=args.method, path=args.path,
            headers=headers, body=body, params=params, auth=auth,
            collection_file=args.collection_file,
        )

def cmd_report(args):
    """Generate report from existing test results."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    print(f"📋 Generating {args.format} report...")
    
    requirements_text = read_requirements_file(args.requirements)
    agent = AITestingAgent(api_key=args.api_key)
    
    # Run workflow and generate report
    agent.run_autonomous(requirements_text)
    report_path = agent.generate_report(format=args.format)
    
    print(f"\n✅ Report generated: {report_path}")


def cmd_env(args):
    """Handle the 'env' sub-command for environment management."""
    from env_manager import EnvManager
    mgr = EnvManager()

    action = args.env_action

    if action == 'list':
        envs = mgr.list_envs()
        if not envs:
            print("No environments found. Create one with: python cli.py env create <name> <url>")
        else:
            active = mgr.get_active_env()
            active_name = active.get('name', '').lower() if active else ''
            print("\nAvailable environments:")
            for name in sorted(envs):
                marker = " ← active" if name.lower() == active_name else ""
                print(f"  {name}{marker}")
            print()

    elif action == 'create':
        variables = {}
        if getattr(args, 'vars', None):
            try:
                variables = json.loads(args.vars)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in --vars: {e}")
                return
        mgr.create_env(args.name, args.url, variables)

    elif action == 'use':
        mgr.use_env(args.name)

    elif action == 'show':
        mgr.show_env(getattr(args, 'name', None))

    elif action == 'set':
        mgr.set_variable(args.key, args.value, env_name=getattr(args, 'name', None))

    elif action == 'delete':
        mgr.delete_env(args.name, force=getattr(args, 'force', False))

    elif action == 'export':
        mgr.export_env(args.name, args.output)

    elif action == 'import':
        mgr.import_env(args.file, name=getattr(args, 'name', None))

    elif action == 'init':
        mgr.create_default_envs()
        print("\n✅ Default environments created. Switch with: python cli.py env use dev")

    else:
        print("Usage: python cli.py env <list|create|use|show|set|delete|export|import|init>")


def cmd_test_data(args):
    """Handle the 'test-data' sub-command."""
    from data_manager import DataManager
    dm = DataManager()

    if args.td_action == 'example':
        filepath = getattr(args, 'output', 'test_data_example.yaml')
        dm.generate_example_yaml(filepath)
        print(f"\n✅ Example test data written to: {filepath}")
        print("   Edit it with your real credentials, then run:")
        print(f"   python cli.py test-data validate {filepath}")

    elif args.td_action == 'validate':
        data = dm.load(args.file)
        warnings_list = dm.validate(data)
        if warnings_list:
            print(f"\n⚠️  {len(warnings_list)} warning(s):")
            for w in warnings_list:
                print(f"   - {w}")
        else:
            print(f"\n✅ {args.file} is valid — no warnings found")
        print(f"   Sections: {', '.join(data.keys())}")

    elif args.td_action == 'init':
        data = dm.load('wizard')
        # Optionally generate conftest after wizard
        gen = input("\nGenerate conftest.py from this data? [Y/n]: ").strip().lower()
        if gen in ('', 'y', 'yes'):
            out_dir = input("Output directory [.]: ").strip() or '.'
            conftest_path = f"{out_dir}/conftest.py"
            dm.generate_conftest(conftest_path)

    else:
        print("Usage: python cli.py test-data <init|example|validate>")


def add_collection_command(subparsers):
    """Register the 'collection' sub-command."""
    col_parser = subparsers.add_parser(
        'collection',
        help='Manage saved request collections (like Postman collections)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'Save, list, and replay named HTTP requests.\n\n'
            'Examples:\n'
            '  python cli.py request GET /api/users --save-to-collection get_users\n'
            '  python cli.py collection list\n'
            '  python cli.py collection run get_users\n'
        ),
    )
    col_sub = col_parser.add_subparsers(dest='col_action', help='Action')

    list_p = col_sub.add_parser('list', help='List all saved requests')
    list_p.add_argument('--collection-file', default='./requests_collection.json')

    run_p = col_sub.add_parser('run', help='Replay a saved request')
    run_p.add_argument('name', help='Name of the saved request')
    run_p.add_argument('--collection-file', default='./requests_collection.json')
    run_p.add_argument('--timeout', type=int, default=30)
    run_p.add_argument('--save-as-test', action='store_true')
    run_p.add_argument('--test-name', default=None)
    run_p.add_argument('--output', default='./test_output')

    col_parser.set_defaults(func=handle_collection_command)


def handle_collection_command(args):
    """Handle the 'collection' sub-command."""
    try:
        from rich.console import Console as _C
        _console = _C()
    except ImportError:
        class _FallbackConsole:
            def print(self, msg, **_):
                import re as _re
                print(_re.sub(r'\[/?[^\]]+\]', '', str(msg)))
        _console = _FallbackConsole()

    try:
        from request_runner import RequestRunner
    except ImportError:
        _console.print("[red]❌ request_runner.py not found.[/red]")
        return

    runner = RequestRunner()
    col_action = getattr(args, 'col_action', None)

    if col_action == 'list' or col_action is None:
        runner.list_collection(collection_file=args.collection_file)

    elif col_action == 'run':
        response = runner.run_collection_request(
            name=args.name,
            collection_file=args.collection_file,
            timeout=args.timeout,
        )
        if response is not None:
            runner.display_response(response)
            if args.save_as_test:
                test_name = args.test_name or args.name.replace('-', '_').replace(' ', '_')
                runner.save_as_test(
                    response=response,
                    test_name=test_name,
                    output_path=args.output,
                )
    else:
        _console.print(f"[red]Unknown collection action: {col_action}[/red]")


def cmd_chains(args):
    """Detect and generate multi-endpoint chain tests from an OpenAPI spec."""
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'

    from pathlib import Path
    from spec_ingestion import SpecIngestion
    from chain_detector import ChainDetector
    from chain_test_generator import ChainTestGenerator

    spec_path = args.spec
    if not Path(spec_path).exists():
        print(f"❌ Error: File '{spec_path}' not found")
        sys.exit(1)

    ingestion = SpecIngestion()
    try:
        spec = ingestion.load(spec_path)
    except Exception as exc:
        print(f"❌ Failed to load spec: {exc}")
        sys.exit(1)

    base_url = ingestion.get_base_url(spec)
    title = spec.get('info', {}).get('title', 'API')
    endpoints = ingestion.extract_endpoints(spec)

    print(f"\n📄 {title}")
    print(f"   {len(endpoints)} endpoints | Base URL: {base_url or '(not specified)'}")

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)

    if not chains:
        print("\n⚠️  No chains detected.")
        print("   Chains require response schemas with id or token fields.")
        print("   Ensure your spec includes $ref schemas with properties.")
        return

    print(f"\n🔗 {len(chains)} chain(s) detected:\n")
    for chain in chains:
        print(f"  [{chain.chain_type.upper()}] {chain.name}")
        print(f"   {chain.description}")
        for i, step in enumerate(chain.steps, 1):
            captures = ''
            if step.captures:
                captures = '  (captures: ' + ', '.join(
                    f'{k} → {v}' for k, v in step.captures.items()
                ) + ')'
            print(f"     {i}. {step.endpoint.method} {step.endpoint.path}{captures}")
        print()

    if getattr(args, 'list', False):
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = ChainTestGenerator()
    code = generator.generate_chain_file(chains, base_url=base_url, spec_title=title)

    output_file = output_dir / 'test_chains.py'
    output_file.write_text(code, encoding='utf-8')

    print(f"✅ Written → {output_file}")
    print(f"   Run with: pytest {output_file} -v")


def cmd_trace(args):
    """Requirement traceability: which requirement does each test check?"""
    import traceability

    try:
        text = Path(args.requirements).read_text(encoding='utf-8')
    except OSError as exc:
        print(f"❌ Cannot read requirements file: {exc}")
        sys.exit(2)
    requirements = traceability.extract_requirements(text)
    if not requirements:
        print("❌ No requirement ids found. A requirement line starts with an id such as REQ-12 or US-7.")
        sys.exit(2)
    report = traceability.build_report(requirements, traceability.scan_tests(args.tests))
    markdown = traceability.render_markdown(report)
    if args.output:
        Path(args.output).write_text(markdown, encoding='utf-8')
        print(f"Report → {args.output}")
    else:
        print(markdown)
    sys.exit(0 if report.ok else 1)


def cmd_validate(args):
    """Test validation: does each test fail when the response is wrong?"""
    import validation

    result = validation.validate_tests(args.tests, timeout=args.timeout)
    markdown = validation.render_markdown(result)
    if args.output:
        Path(args.output).write_text(markdown, encoding='utf-8')
        print(f"Report → {args.output}")
    else:
        print(markdown)
    sys.exit(2 if result.problem else (0 if result.ok else 1))


def cmd_analyze_code(args):
    """
    Analyze API source code and generate pytest tests directly.

    Pipeline:
        source file → CodeAnalyzer → endpoints → RequestBodyHandler → test files
    """
    from pathlib import Path
    from code_analyzer import CodeAnalyzer
    from request_body_handler import RequestBodyHandler

    source_path = Path(args.api)
    if not source_path.exists():
        print(f"❌ Error: File '{args.api}' not found")
        sys.exit(1)

    source = source_path.read_text(encoding='utf-8')
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🔍 Analyzing: {source_path.name}")

    analyzer = CodeAnalyzer()
    endpoints = analyzer.analyze(source, framework=getattr(args, 'framework', None))

    if not endpoints:
        print("⚠️  No endpoints found. Check that the file contains API route definitions.")
        sys.exit(1)

    print(analyzer.generate_summary(endpoints))
    print(f"\n💻 Generating pytest files in: {output_dir}/")

    body_handler = RequestBodyHandler()
    generated = []

    for ep in endpoints:
        # generate_complete_test_file: class-organised, min test counts, edge cases included
        test_code = body_handler.generate_complete_test_file(
            ep,
            auth_required=ep.get('auth_required', False),
            include_edge_cases=ep.get('method', 'GET') in ('POST', 'PUT', 'PATCH', 'DELETE'),
        )

        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', ep.get('name', 'endpoint'))
        filename = f"test_{safe_name}.py"
        filepath = output_dir / filename
        filepath.write_text(test_code, encoding='utf-8')
        generated.append(filename)
        test_count = body_handler.count_tests(test_code)
        print(f"  ✓ {ep['method']:6s} {ep['path']:30s} → {filename} ({test_count} tests)")

    print(f"\n✅ Generated {len(generated)} test file(s)")

    # Optional: inject real test data and generate conftest.py
    if getattr(args, 'test_data', None):
        from data_manager import DataManager
        dm = DataManager()
        try:
            dm.load(args.test_data)
        except Exception as exc:
            print(f"⚠️  Could not load test data: {exc}")
        else:
            print(f"\n💉 Injecting data from: {args.test_data}")
            for fname in generated:
                fpath = output_dir / fname
                original = fpath.read_text(encoding='utf-8')
                injected = dm.inject_into_tests(original)
                fpath.write_text(injected, encoding='utf-8')
                if injected != original:
                    print(f"   ✓ Injected → {fname}")

            conftest_path = output_dir / 'conftest.py'
            dm.generate_conftest(str(conftest_path))

    print(f"\n   Run them with:  pytest {output_dir}/ -v")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='AI Testing Agent - Autonomous pytest generation powered by Claude',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze requirements
  python cli.py analyze requirements.txt

  # Generate pytest code
  python cli.py generate requirements.txt

  # Run full autonomous workflow
  python cli.py run requirements.txt --api-key YOUR_KEY

  # Parse an OpenAPI spec
  python cli.py run openapi.yaml

  # Run with compliance tagging
  python cli.py run openapi.yaml --compliance compliance.yaml

  # Generate HTML report
  python cli.py report requirements.txt --format html
        """
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'AI Testing Agent v{__version__}'
    )
    
    parser.add_argument(
        '--api-key',
        help='Anthropic API key (or set ANTHROPIC_API_KEY env var)',
        default=None
    )

    parser.add_argument(
        '--no-telemetry',
        action='store_true',
        help='Disable anonymous usage analytics for this session',
        default=False
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Analytics status command
    analytics_status_parser = subparsers.add_parser(
        'analytics',
        help='Show analytics status and privacy information'
    )
    
    # Analytics disable command
    analytics_disable_parser = subparsers.add_parser(
        'analytics-disable',
        help='Permanently disable analytics/telemetry'
    )
    
    # Usage command
    subparsers.add_parser(
        'usage',
        help='Display session usage statistics'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze requirements and generate test cases'
    )
    analyze_parser.add_argument(
        'requirements',
        help='Path to requirements file (supports .txt, .md, .pdf, .docx)'
    )
    
    # Generate command
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate pytest code from requirements'
    )
    generate_parser.add_argument(
        'requirements',
        help='Path to requirements file (supports .txt, .md, .pdf, .docx)'
    )
    
    # Run command
    run_parser = subparsers.add_parser(
        'run',
        help='Run full autonomous testing workflow'
    )
    run_parser.add_argument(
        'requirements',
        help=(
            'Path to requirements file (.txt, .md, .pdf, .docx) '
            'or an OpenAPI/Swagger spec (.yaml, .yml, .json)'
        )
    )
    run_parser.add_argument(
        '--output',
        help='Directory to save generated tests (default: ./test_output)',
        default='./test_output'
    )
    run_parser.add_argument(
        '--spec',
        action='store_true',
        help='Force OpenAPI spec ingestion mode (auto-detected by default)'
    )
    run_parser.add_argument(
        '--analyze',
        action='store_true',
        help='After generating tests, run them and AI-analyze any failures'
    )
    run_parser.add_argument(
        '--compliance',
        metavar='COMPLIANCE_YAML',
        help='Path to compliance.yaml — injects HIPAA/NIST/ISO marks into generated tests'
    )

    # Compliance report command
    compliance_report_parser = subparsers.add_parser(
        'compliance-report',
        help='Generate a compliance coverage report from existing test output'
    )
    compliance_report_parser.add_argument(
        'test_dir',
        help='Directory containing generated test files (e.g. test_output/)'
    )
    compliance_report_parser.add_argument(
        '--compliance',
        metavar='COMPLIANCE_YAML',
        required=True,
        help='Path to compliance.yaml defining frameworks and custom mappings'
    )
    compliance_report_parser.add_argument(
        '--format',
        choices=['text', 'markdown', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    compliance_report_parser.add_argument(
        '--out',
        metavar='FILE',
        help='Write report to FILE instead of stdout'
    )

    # Failures command (standalone analysis of existing test files)
    failures_parser = subparsers.add_parser(
        'failures',
        help='Run pytest on existing test files and AI-analyze any failures'
    )
    failures_parser.add_argument(
        'paths',
        nargs='+',
        help='Test files or directories to run (e.g. test_output/test_pets.py)'
    )
    failures_parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Output analysis as JSON instead of human-readable text'
    )

    # Report command
    report_parser = subparsers.add_parser(
        'report',
        help='Generate test report'
    )
    report_parser.add_argument(
        'requirements',
        help='Path to requirements file'
    )
    report_parser.add_argument(
        '--format',
        choices=['html', 'json', 'markdown'],
        default='html',
        help='Report format (default: html)'
    )

    # Env command (Task G: environment management)
    env_parser = subparsers.add_parser(
        'env',
        help='Manage environments (dev / staging / prod)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'Create and switch between named environments.\n\n'
            'Examples:\n'
            '  python cli.py env init                            # create dev/staging/prod defaults\n'
            '  python cli.py env list                            # list all environments\n'
            '  python cli.py env create staging https://staging.api.com\n'
            '  python cli.py env use staging                     # switch active environment\n'
            '  python cli.py env show                            # show active environment\n'
            '  python cli.py env set API_KEY abc123              # set a variable\n'
            '  python cli.py env export dev dev_env.yaml\n'
            '  python cli.py env import dev_env.yaml'
        ),
    )
    env_sub = env_parser.add_subparsers(dest='env_action', help='Action')

    env_sub.add_parser('list', help='List all environments')
    env_sub.add_parser('init', help='Create default dev/staging/prod environments')
    env_sub.add_parser('show', help='Show the active environment')

    _e_create = env_sub.add_parser('create', help='Create a new environment')
    _e_create.add_argument('name', help='Environment name (e.g. staging)')
    _e_create.add_argument('url', help='Base URL (e.g. https://staging.api.com)')
    _e_create.add_argument('--vars', help='Additional variables as JSON string', default=None)

    _e_use = env_sub.add_parser('use', help='Switch active environment')
    _e_use.add_argument('name', help='Environment name')

    _e_set = env_sub.add_parser('set', help='Set a variable in the active environment')
    _e_set.add_argument('key', help='Variable name')
    _e_set.add_argument('value', help='Variable value')
    _e_set.add_argument('--env', dest='name', help='Target environment (default: active)', default=None)

    _e_del = env_sub.add_parser('delete', help='Delete an environment')
    _e_del.add_argument('name', help='Environment name')
    _e_del.add_argument('--force', action='store_true', help='Skip confirmation prompt')

    _e_exp = env_sub.add_parser('export', help='Export environment to YAML/JSON')
    _e_exp.add_argument('name', help='Environment name')
    _e_exp.add_argument('output', help='Output file path (.yaml or .json)')

    _e_imp = env_sub.add_parser('import', help='Import environment from file')
    _e_imp.add_argument('file', help='Input file path')
    _e_imp.add_argument('--name', help='Override environment name', default=None)

    env_parser.set_defaults(func=cmd_env)

    # Test-data command (Task D: manage test data files)
    td_parser = subparsers.add_parser(
        'test-data',
        help='Manage test data (YAML/Excel/JSON) for generated tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'Create, validate, and apply test data files.\n\n'
            'Examples:\n'
            '  python cli.py test-data example                   # create example YAML\n'
            '  python cli.py test-data validate test_data.yaml   # validate a file\n'
            '  python cli.py test-data init                      # interactive wizard'
        ),
    )
    td_sub = td_parser.add_subparsers(dest='td_action', help='Action')

    # test-data example
    td_example = td_sub.add_parser('example', help='Generate an example test_data.yaml')
    td_example.add_argument('--output', default='test_data_example.yaml',
                            help='Output filename (default: test_data_example.yaml)')

    # test-data validate
    td_validate = td_sub.add_parser('validate', help='Validate a test data file')
    td_validate.add_argument('file', help='Path to test data file (YAML/JSON)')

    # test-data init
    td_sub.add_parser('init', help='Run the interactive wizard to create test_data.yaml')

    td_parser.set_defaults(func=cmd_test_data)

    # Chains command — multi-endpoint chain test generation
    chains_parser = subparsers.add_parser(
        'chains',
        help='Detect and generate multi-endpoint integration chain tests from an OpenAPI spec',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'Analyze endpoint dependencies and generate integration tests that\n'
            'chain multiple API calls, threading captured values between steps.\n\n'
            'Examples:\n'
            '  python cli.py chains openapi.yaml\n'
            '  python cli.py chains openapi.yaml --output ./test_output\n'
            '  python cli.py chains openapi.yaml --list\n'
        ),
    )
    chains_parser.add_argument(
        'spec',
        help='Path to OpenAPI/Swagger spec (.yaml, .yml, .json)'
    )
    chains_parser.add_argument(
        '--output',
        help='Directory to write test_chains.py (default: ./test_output)',
        default='./test_output'
    )
    chains_parser.add_argument(
        '--list',
        action='store_true',
        help='Print detected chains without generating test files'
    )

    # Analyze-code command (Task E: generate tests directly from API source)
    analyze_code_parser = subparsers.add_parser(
        'analyze-code',
        help='Generate tests directly from API source code (FastAPI, Flask, Express, OpenAPI)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'Analyze API source code and generate runnable pytest files.\n\n'
            'Examples:\n'
            '  python cli.py analyze-code myapi.py\n'
            '  python cli.py analyze-code myapi.py --output ./tests\n'
            '  python cli.py analyze-code openapi.yaml --framework openapi\n'
            '  python cli.py analyze-code routes.js --framework express'
        ),
    )
    analyze_code_parser.add_argument(
        'api',
        help='Path to API source file (.py, .js, .yaml, .yml, .json, .txt)'
    )
    analyze_code_parser.add_argument(
        '--output',
        help='Directory to save generated tests (default: ./test_output)',
        default='./test_output'
    )
    analyze_code_parser.add_argument(
        '--framework',
        choices=['fastapi', 'flask', 'express', 'openapi', 'plain_text'],
        help='Force a specific framework (default: auto-detect)',
        default=None
    )
    analyze_code_parser.add_argument(
        '--test-data',
        help='Path to test_data.yaml (injects real credentials/BASE_URL + generates conftest.py)',
        default=None,
        dest='test_data'
    )

    # Traceability (roadmap stage 2)
    trace_parser = subparsers.add_parser(
        'trace',
        help='Show which requirement each test checks, and which requirements have no test'
    )
    trace_parser.add_argument('requirements', help='Requirements document with ids such as REQ-12')
    trace_parser.add_argument('tests', nargs='+', help='Test files or directories')
    trace_parser.add_argument('--output', '-o', help='Write the Markdown report to this file')

    # Validation (roadmap stage 3)
    validate_parser = subparsers.add_parser(
        'validate',
        help='Check that each passing test fails when the HTTP response is wrong'
    )
    validate_parser.add_argument('tests', nargs='+', help='Test files or directories')
    validate_parser.add_argument('--output', '-o', help='Write the Markdown report to this file')
    validate_parser.add_argument('--timeout', type=int, default=300, help='Seconds per pytest run')

    # Request command (Postman replacement)
    add_request_command(subparsers)

    # Collection command
    add_collection_command(subparsers)

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate command
    if args.command == 'analytics':
        cmd_analytics_status(args)
    elif args.command == 'analytics-disable':
        cmd_analytics_disable(args)
    elif args.command == 'usage':
        cmd_usage(args)
    elif args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'run':
        cmd_run(args)
    elif args.command == 'failures':
        cmd_failures(args)
    elif args.command == 'compliance-report':
        cmd_compliance_report(args)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'request':
        handle_request_command(args)
    elif args.command == 'collection':
        handle_collection_command(args)
    elif args.command == 'chains':
        cmd_chains(args)
    elif args.command == 'analyze-code':
        cmd_analyze_code(args)
    elif args.command == 'trace':
        cmd_trace(args)
    elif args.command == 'validate':
        cmd_validate(args)
    elif args.command == 'test-data':
        cmd_test_data(args)
    elif args.command == 'env':
        cmd_env(args)


if __name__ == '__main__':
    main()
