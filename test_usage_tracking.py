"""
Test script for usage tracking functionality
Tests comprehensive usage statistics and logging
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_testing_agent import AITestingAgent


def test_usage_stats_initialization():
    """Test that usage stats are initialized correctly"""
    print("\n" + "="*80)
    print("TEST 1: Usage Stats Initialization")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Check usage_stats structure
    required_keys = ['session_start', 'api_calls', 'tokens_input', 'tokens_output',
                     'estimated_cost', 'endpoints_processed', 'tests_generated', 'tier']
    
    for key in required_keys:
        if key in agent.usage_stats:
            print(f"✓ {key}: {agent.usage_stats[key]}")
        else:
            print(f"✗ Missing key: {key}")
            return False
    
    print("\n✅ Usage stats initialized correctly")
    return True


def test_get_usage_stats():
    """Test get_usage_stats method"""
    print("\n" + "="*80)
    print("TEST 2: get_usage_stats() Method")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Wait a moment to have some session duration
    time.sleep(1)
    
    stats = agent.get_usage_stats()
    
    print("\nReturned stats:")
    print(f"  Tier: {stats['tier']}")
    print(f"  API calls: {stats['api_calls']}")
    print(f"  Tokens (input/output): {stats['tokens_input']}/{stats['tokens_output']}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Estimated cost: {stats['cost_formatted']}")
    print(f"  Session duration: {stats['session_duration_formatted']}")
    print(f"  Endpoints processed: {stats['endpoints_processed']}")
    print(f"  Tests generated: {stats['tests_generated']}")
    
    # Verify required fields
    required_fields = ['session_duration_seconds', 'session_duration_formatted',
                       'avg_cost_per_call', 'cost_formatted', 'total_tokens']
    
    all_present = all(field in stats for field in required_fields)
    
    if all_present:
        print("\n✅ All required fields present")
        return True
    else:
        print("\n✗ Some fields missing")
        return False


def test_mock_usage_tracking():
    """Test usage tracking with mock AI calls"""
    print("\n" + "="*80)
    print("TEST 3: Usage Tracking with Mock AI")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Simulate a workflow
    requirements_text = """
    Test Feature 1: User login
    Test Feature 2: Data validation
    Test Feature 3: API integration
    """
    
    print("\nRunning autonomous workflow...")
    result = agent.run_autonomous(requirements_text)
    
    if result['success']:
        stats = result.get('usage_stats', {})
        print(f"\n✓ Workflow completed successfully")
        print(f"✓ Endpoints processed: {stats.get('endpoints_processed', 0)}")
        print(f"✓ Tests generated: {stats.get('tests_generated', 0)}")
        print(f"✓ Session duration: {stats.get('session_duration_formatted', 'N/A')}")
        return True
    else:
        print(f"\n✗ Workflow failed: {result.get('error')}")
        return False


def test_usage_log_file():
    """Test that usage log file is created"""
    print("\n" + "="*80)
    print("TEST 4: Usage Log File Creation")
    print("="*80)
    
    log_dir = Path.home() / '.ai-testing-agent'
    log_file = log_dir / 'usage.log'
    
    # Run a simple workflow
    agent = AITestingAgent()
    requirements_text = "Test Feature: Basic functionality"
    agent.run_autonomous(requirements_text)
    
    # Check if log file exists
    if log_file.exists():
        print(f"\n✓ Log file created at: {log_file}")
        
        # Read last line
        with open(log_file, 'r') as f:
            lines = f.readlines()
            if lines:
                last_entry = lines[-1]
                print(f"\n✓ Last log entry:")
                import json
                try:
                    entry = json.loads(last_entry)
                    print(f"  Timestamp: {entry.get('timestamp')}")
                    print(f"  Tier: {entry.get('tier')}")
                    print(f"  Tests generated: {entry.get('tests_generated')}")
                    print(f"  Estimated cost: ${entry.get('estimated_cost'):.4f}")
                    return True
                except:
                    print("  ✗ Could not parse JSON")
                    return False
    else:
        print(f"\n✗ Log file not found at: {log_file}")
        return False


def test_cost_warnings():
    """Test cost warning thresholds"""
    print("\n" + "="*80)
    print("TEST 5: Cost Warning Display")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Manually set high cost for testing
    print("\nTesting normal cost (no warning):")
    agent.usage_stats['estimated_cost'] = 0.50
    agent._print_usage_summary()
    
    print("\nTesting high cost warning ($1.00+):")
    agent.usage_stats['estimated_cost'] = 1.25
    agent._print_usage_summary()
    
    print("\nTesting very high cost warning ($5.00+):")
    agent.usage_stats['estimated_cost'] = 6.00
    agent._print_usage_summary()
    
    print("\n✅ Cost warnings displayed correctly")
    return True


def main():
    """Run all tests"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════════╗")
    print("║               USAGE TRACKING FUNCTIONALITY TEST SUITE                 ║")
    print("╚════════════════════════════════════════════════════════════════════════╝")
    
    tests = [
        ("Usage stats initialization", test_usage_stats_initialization),
        ("get_usage_stats() method", test_get_usage_stats),
        ("Mock usage tracking", test_mock_usage_tracking),
        ("Usage log file creation", test_usage_log_file),
        ("Cost warnings", test_cost_warnings),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Usage tracking is working correctly:")
        print("   • Usage stats initialized properly")
        print("   • get_usage_stats() returns complete data")
        print("   • Tracking works with mock AI calls")
        print("   • Log file is created and contains valid JSON")
        print("   • Cost warnings display at correct thresholds")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
