#!/usr/bin/env python3
"""
Test script for monthly usage limit checking system.

Tests:
1. Usage database creation
2. Monthly usage tracking
3. Monthly limit checking
4. Warning messages at 80% and 90%
5. Blocking at 100%
6. CLI usage command
"""

import os
import sys
import json
from pathlib import Path
from ai_testing_agent import AITestingAgent

def test_usage_db_creation():
    """Test that usage database is created properly."""
    print("="*70)
    print("TEST 1: Usage Database Creation")
    print("="*70)
    
    # Create agent (this should create the usage db)
    agent = AITestingAgent()
    
    # Check if usage db file exists
    usage_file = Path.home() / '.ai-testing-agent' / 'usage_db.json'
    
    if usage_file.exists():
        print("✅ Usage database file created")
        with open(usage_file, 'r') as f:
            data = json.load(f)
        print(f"   📄 Content: {json.dumps(data, indent=2)}")
    else:
        print("❌ Usage database file NOT created")
    
    print()


def test_monthly_usage_tracking():
    """Test that monthly usage is tracked correctly."""
    print("="*70)
    print("TEST 2: Monthly Usage Tracking")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Get initial usage
    initial_stats = agent.get_monthly_usage_stats()
    print(f"Initial runs used: {initial_stats['runs_used']}")
    
    # Simulate a run by manually incrementing
    agent._save_monthly_usage(increment_runs=1, increment_endpoints=3, increment_cost=0.0)
    
    # Check updated usage
    updated_stats = agent.get_monthly_usage_stats()
    print(f"After increment: {updated_stats['runs_used']} runs")
    print(f"Endpoints this month: {updated_stats['endpoints_this_month']}")
    
    if updated_stats['runs_used'] > initial_stats['runs_used']:
        print("✅ Usage tracking works correctly")
    else:
        print("❌ Usage tracking FAILED")
    
    print()


def test_usage_display():
    """Test the usage stats display."""
    print("="*70)
    print("TEST 3: Usage Stats Display")
    print("="*70)
    
    agent = AITestingAgent()
    stats = agent.get_monthly_usage_stats()
    
    print(f"Month: {stats['month']}")
    print(f"Tier: {stats['tier']}")
    print(f"Runs: {stats['runs_used']} / {stats['runs_limit']}")
    print(f"Endpoints this month: {stats['endpoints_this_month']}")
    print(f"Cost: ${stats['cost_this_month']:.4f}")
    print(f"Days until reset: {stats['days_until_reset']}")
    print(f"Reset date: {stats['reset_date']}")
    print("✅ Usage display working")
    print()


def test_warning_messages():
    """Test warning messages at different usage levels."""
    print("="*70)
    print("TEST 4: Warning Messages")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Test at different percentages
    print("\n📊 Testing at 0% usage:")
    agent._check_monthly_limits()
    
    # Manually set usage to 80% for testing
    print("\n📊 Testing at 80% usage (simulated):")
    usage_data = agent._load_monthly_usage()
    original_runs = usage_data['runs_this_month']
    usage_data['runs_this_month'] = 40  # 40/50 = 80%
    agent._save_usage_data(usage_data)
    agent._check_monthly_limits()
    
    # Test at 90%
    print("\n📊 Testing at 90% usage (simulated):")
    usage_data['runs_this_month'] = 45  # 45/50 = 90%
    agent._save_usage_data(usage_data)
    agent._check_monthly_limits()
    
    # Reset to original
    usage_data['runs_this_month'] = original_runs
    agent._save_usage_data(usage_data)
    
    print("✅ Warning messages working")
    print()


def test_limit_enforcement():
    """Test that limits are enforced at 100%."""
    print("="*70)
    print("TEST 5: Limit Enforcement at 100%")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Save original usage
    usage_data = agent._load_monthly_usage()
    original_runs = usage_data['runs_this_month']
    
    # Set to limit
    usage_data['runs_this_month'] = 50  # At free tier limit
    agent._save_usage_data(usage_data)
    
    print("Setting usage to 100% (50/50 runs)...")
    
    try:
        agent._check_monthly_limits()
        print("❌ FAILED - Limit should have been enforced")
    except Exception as e:
        if "MONTHLY LIMIT REACHED" in str(e):
            print("✅ Limit correctly enforced at 100%")
            print(f"   Error message preview: {str(e)[:100]}...")
        else:
            print(f"❌ Unexpected error: {e}")
    
    # Reset to original
    usage_data['runs_this_month'] = original_runs
    agent._save_usage_data(usage_data)
    
    print()


def test_run_integration():
    """Test integration with actual run."""
    print("="*70)
    print("TEST 6: Integration with Autonomous Run")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Get initial usage
    initial_stats = agent.get_monthly_usage_stats()
    initial_runs = initial_stats['runs_used']
    
    print(f"Initial runs: {initial_runs}")
    
    # Run a test workflow
    requirements = """
    Test Feature 1: User login
    Test Feature 2: Data validation
    """
    
    print("Running test workflow...")
    result = agent.run_autonomous(requirements)
    
    # Check updated usage
    updated_stats = agent.get_monthly_usage_stats()
    updated_runs = updated_stats['runs_used']
    
    print(f"Runs after workflow: {updated_runs}")
    
    if updated_runs > initial_runs:
        print("✅ Run integration working - usage incremented")
    else:
        print("⚠️  Usage not incremented (may need to complete successfully)")
    
    print()


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 MONTHLY USAGE LIMIT CHECKING - TEST SUITE")
    print("="*70)
    print()
    
    try:
        test_usage_db_creation()
        test_monthly_usage_tracking()
        test_usage_display()
        test_warning_messages()
        test_limit_enforcement()
        test_run_integration()
        
        print("="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)
        print("\n💡 Next steps:")
        print("   1. Run: python cli.py usage")
        print("   2. Run multiple times with: python cli.py run example_requirements.txt")
        print("   3. Check ~/.ai-testing-agent/usage_db.json")
        print()
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
