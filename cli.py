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
    """Display current monthly usage statistics."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    # Create agent to get usage info
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
    # Get monthly usage stats
    stats = agent.get_monthly_usage_stats()
    
    print("\n" + "="*70)
    print("📊 Monthly Usage Statistics")
    print("="*70)
    
    print(f"\nCurrent Month: {stats['month']}")
    print(f"Tier: {stats['tier'].upper()}")
    
    print(f"\n🔄 Test Runs:")
    print(f"   Used:      {stats['runs_used']} / {stats['runs_limit']}")
    if stats['runs_percent'] > 0:
        print(f"   Usage:     {stats['runs_percent']:.1f}%")
        # Add warning if approaching limit
        if stats['runs_percent'] >= 80:
            if stats['runs_percent'] >= 90:
                print(f"   Status:    🚨 CRITICAL - {100 - stats['runs_percent']:.1f}% remaining")
            else:
                print(f"   Status:    ⚠️  WARNING - {100 - stats['runs_percent']:.1f}% remaining")
        else:
            print(f"   Status:    ✅ OK")
    
    print(f"\n🔌 Endpoints:")
    print(f"   This Month: {stats['endpoints_this_month']}")
    print(f"   Per Run:    {stats['endpoint_limit']}")
    
    print(f"\n💰 Cost This Month:")
    print(f"   ${stats['cost_this_month']:.4f}")
    
    print(f"\n📅 Quota Reset:")
    print(f"   Days:       {stats['days_until_reset']} days")
    print(f"   Date:       {stats['reset_date']}")
    
    # Show upgrade message if on free tier with high usage
    if stats['tier'] == 'free' and stats['runs_percent'] >= 70:
        print("\n" + "💡 " + "="*66)
        print("Running low on quota? Upgrade to PRO for:")
        print("  • UNLIMITED test runs (never run out!)")
        print("  • 10x more endpoints per run")
        print("  • Real Claude AI")
        print("  • Coming soon")
        print("\n  Visit: https://yourdomain.com/pricing")
    
    print("="*70 + "\n")


def cmd_analytics_status(args):
    """Display analytics configuration and status."""
    if not ANALYTICS_AVAILABLE:
        print("\n❌ Analytics module not available")
        print("   Make sure analytics.py is in the same directory\n")
        return
    
    # Import and initialize analytics for display
    from analytics import Analytics
    analytics = Analytics(
        license_key=args.license_key or os.getenv('AI_AGENT_LICENSE_KEY'),
        tier='free'  # Default tier for status display
    )
    
    # Show status
    status = analytics.get_status()
    
    print("\n" + "="*70)
    print("📊 Analytics Status")
    print("="*70)
    print(f"Status: {'✅ Enabled' if status['enabled'] else '❌ Disabled'}")
    print(f"Anonymous ID: {status['anonymous_id']}")
    print(f"Tier: {status['tier']}")
    
    print("\n📦 What we collect:")
    for item in status['data_collected']:
        print(f"  ✓ {item}")
    
    print("\n🔒 What we DON'T collect:")
    for item in status['data_not_collected']:
        print(f"  ✗ {item}")
    
    print("\n⚙️  Opt-out methods:")
    for method in status['opt_out_methods']:
        print(f"  • {method}")
    
    print(f"\n📚 Privacy Policy: {status['privacy_policy']}")
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


def cmd_tier(args):
    """Display current tier information."""
    # Create agent to get tier info (with telemetry disabled if flag is set)
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
    tier = agent.tier
    limits = agent.limits[tier]
    
    # Tier emoji mapping
    tier_emoji = {
        'free': '🆓',
        'pro': '✨',
        'team': '👥',
        'enterprise': '🏢'
    }
    
    # License status
    license_status = "✅ Activated" if args.license_key or os.getenv('AI_AGENT_LICENSE_KEY') else "❌ Not activated"
    
    print("\n" + "="*70)
    print("🎯 AI Testing Agent - Tier Information")
    print("="*70)
    
    print(f"\nCurrent Tier: {tier_emoji.get(tier, '📦')} {tier.upper()}")
    print(f"License: {license_status}")
    
    # Format limits
    endpoint_limit = "Unlimited" if limits['endpoints'] == float('inf') else str(limits['endpoints'])
    runs_limit = "Unlimited" if limits['monthly_runs'] == float('inf') else str(limits['monthly_runs'])
    
    print(f"\nFeatures Available:")
    if tier == 'free':
        print("  ✓ Mock AI test generation")
        print("  ✓ Up to 10 API endpoints")
        print("  ✓ Basic pytest code generation")
        print("  ✓ HTML/JSON/Markdown reports")
        print("  ✓ PDF/Word document support")
    elif tier == 'pro':
        print("  ✓ Real Claude AI (advanced intelligence)")
        print("  ✓ Up to 100 API endpoints")
        print("  ✓ Production-quality test generation")
        print("  ✓ Advanced test strategies")
        print("  ✓ Unlimited monthly runs")
        print("  ✓ Priority email support")
    elif tier == 'team':
        print("  ✓ All Pro features")
        print("  ✓ Up to 500 API endpoints")
        print("  ✓ Team collaboration tools")
        print("  ✓ Shared test libraries")
        print("  ✓ Role-based access control")
        print("  ✓ Team management dashboard")
    elif tier == 'enterprise':
        print("  ✓ Unlimited everything")
        print("  ✓ Unlimited API endpoints")
        print("  ✓ Dedicated support team")
        print("  ✓ Custom integrations")
        print("  ✓ SLA guarantees")
        print("  ✓ On-premise deployment option")
    
    print(f"\nLimits:")
    print(f"  • Endpoints per run: {endpoint_limit}")
    print(f"  • Monthly runs: {runs_limit}")
    print(f"  • AI quality: {'Real Claude AI' if tier != 'free' else 'Mock (basic)'}")
    
    # Show upgrade information if not on highest tier
    if tier == 'free':
        print("\n" + "💡 " + "="*66)
        print("Upgrade to PRO for:")
        print("  • Real Claude AI (much smarter!)")
        print("  • 100 endpoints per run (10x more)")
        print("  • Unlimited monthly runs")
        print("  • Advanced test strategies")
        print("  • Priority email support")
        print("  • Coming soon")
    elif tier == 'pro':
        print("\n" + "💡 " + "="*66)
        print("Upgrade to TEAM for:")
        print("  • 500 endpoints per run (5x more)")
        print("  • Team collaboration features")
        print("  • Shared test libraries")
        print("  • Team management dashboard")
        print("  • Coming soon")
    elif tier == 'team':
        print("\n" + "💡 " + "="*66)
        print("Upgrade to ENTERPRISE for:")
        print("  • Unlimited endpoints")
        print("  • Dedicated support team")
        print("  • Custom integrations")
        print("  • SLA guarantees")
        print("  • Contact sales for pricing")
    
    print("\n📚 Visit: https://yourdomain.com/pricing")
    print("="*70 + "\n")


def cmd_analyze(args):
    """Analyze requirements and generate test cases."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    print("🔍 Analyzing requirements...")
    
    requirements_text = read_requirements_file(args.requirements)
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
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
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
    # Parse and generate
    agent.parse_requirements(requirements_text)
    agent.generate_test_cases()
    pytest_files = agent.generate_pytest_code()
    
    print(f"\n✅ Generated {len(pytest_files)} pytest files")
    for file in pytest_files:
        print(f"   📄 {file}")


def cmd_run(args):
    """Run full autonomous testing workflow."""
    # Disable telemetry if flag is set
    if args.no_telemetry:
        os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    print("🚀 Running autonomous AI testing workflow...")
    
    requirements_text = read_requirements_file(args.requirements)
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
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
    agent = AITestingAgent(api_key=args.api_key, license_key=args.license_key)
    
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
        description='AI Testing Agent - Autonomous test automation with tier-based licensing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check your tier and features
  python cli.py tier
  
  # Analyze requirements (Free tier: mock AI, up to 10 endpoints)
  python cli.py analyze requirements.txt
  
  # Generate pytest code (Pro tier recommended for best results)
  python cli.py generate requirements.txt --license-key YOUR_LICENSE
  
  # Run full autonomous workflow (requires API key for paid tiers)
  python cli.py run requirements.txt --api-key YOUR_KEY --license-key YOUR_LICENSE
  
  # Generate HTML report
  python cli.py report requirements.txt --format html

Tier Information:
  Free tier    : Mock AI, 10 endpoints, 50 runs/month
  Pro tier     : Real AI, 100 endpoints, unlimited runs ($29/mo)
  Team tier    : 500 endpoints, team features ($99/mo)
  Enterprise   : Unlimited everything (contact sales)
  
Visit https://yourdomain.com/pricing for more information.
        """
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'AI Testing Agent v{__version__}'
    )
    
    parser.add_argument(
        '--api-key',
        help='Anthropic API key for paid tiers (or set ANTHROPIC_API_KEY env var)',
        default=None
    )
    
    parser.add_argument(
        '--license-key',
        help='License key for paid tiers (or set AI_AGENT_LICENSE_KEY env var)',
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
    usage_parser = subparsers.add_parser(
        'usage',
        help='Display monthly usage statistics and quota information'
    )
    
    # Tier command
    tier_parser = subparsers.add_parser(
        'tier',
        help='Display current tier information and features'
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze requirements and generate test cases (Free tier: up to 10 endpoints)'
    )
    analyze_parser.add_argument(
        'requirements',
        help='Path to requirements file (supports .txt, .md, .pdf, .docx)'
    )
    
    # Generate command
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate pytest code from requirements (Pro tier recommended)'
    )
    generate_parser.add_argument(
        'requirements',
        help='Path to requirements file (supports .txt, .md, .pdf, .docx)'
    )
    
    # Run command
    run_parser = subparsers.add_parser(
        'run',
        help='Run full autonomous testing workflow (checks tier limits)'
    )
    run_parser.add_argument(
        'requirements',
        help='Path to requirements file (supports .txt, .md, .pdf, .docx)'
    )
    run_parser.add_argument(
        '--output',
        help='Directory to save generated tests (default: ./test_output)',
        default='./test_output'
    )
    
    # Report command
    report_parser = subparsers.add_parser(
        'report',
        help='Generate test report (all tiers)'
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
    elif args.command == 'tier':
        cmd_tier(args)
    elif args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'run':
        cmd_run(args)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'request':
        handle_request_command(args)
    elif args.command == 'collection':
        handle_collection_command(args)
    elif args.command == 'analyze-code':
        cmd_analyze_code(args)
    elif args.command == 'test-data':
        cmd_test_data(args)
    elif args.command == 'env':
        cmd_env(args)


if __name__ == '__main__':
    main()
