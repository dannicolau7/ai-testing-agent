#!/usr/bin/env python3
"""
Test script for license validation system
Tests different scenarios: no license, fake license, environment variable
"""

import os
import sys
from ai_testing_agent import AITestingAgent


def test_no_license():
    """Test 1: No license key provided - should default to 'free'"""
    print("\n" + "="*70)
    print("TEST 1: No License Key (Should be FREE tier)")
    print("="*70)
    
    agent = AITestingAgent()
    
    assert agent.tier == 'free', f"Expected 'free', got '{agent.tier}'"
    assert agent.limits['free']['endpoints'] == 10
    assert agent.limits['free']['monthly_runs'] == 50
    
    print("✅ TEST 1 PASSED: No license defaults to FREE tier")
    return True


def test_fake_license():
    """Test 2: Fake license key - should default to 'free' with warning"""
    print("\n" + "="*70)
    print("TEST 2: Fake License Key (Should be FREE tier with warning)")
    print("="*70)
    
    agent = AITestingAgent(license_key="FAKE-LICENSE-KEY-12345")
    
    assert agent.tier == 'free', f"Expected 'free', got '{agent.tier}'"
    
    print("✅ TEST 2 PASSED: Invalid license defaults to FREE tier with warning")
    return True


def test_env_variable():
    """Test 3: License from environment variable"""
    print("\n" + "="*70)
    print("TEST 3: License from Environment Variable")
    print("="*70)
    
    # Set environment variable
    os.environ['AI_AGENT_LICENSE_KEY'] = 'ENV-LICENSE-KEY-67890'
    
    agent = AITestingAgent()
    
    assert agent.license_key == 'ENV-LICENSE-KEY-67890'
    assert agent.tier == 'free'  # Will still be free since it's fake
    
    # Clean up
    del os.environ['AI_AGENT_LICENSE_KEY']
    
    print("✅ TEST 3 PASSED: Environment variable support works")
    return True


def test_tier_limits():
    """Test 4: Verify tier limits are correctly configured"""
    print("\n" + "="*70)
    print("TEST 4: Verify Tier Limits Configuration")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Check all tiers exist
    assert 'free' in agent.limits
    assert 'pro' in agent.limits
    assert 'team' in agent.limits
    assert 'enterprise' in agent.limits
    
    # Check free tier limits
    assert agent.limits['free']['endpoints'] == 10
    assert agent.limits['free']['monthly_runs'] == 50
    
    # Check pro tier limits
    assert agent.limits['pro']['endpoints'] == 100
    assert agent.limits['pro']['monthly_runs'] == float('inf')
    
    # Check team tier limits
    assert agent.limits['team']['endpoints'] == 500
    assert agent.limits['team']['monthly_runs'] == float('inf')
    
    # Check enterprise tier limits
    assert agent.limits['enterprise']['endpoints'] == float('inf')
    assert agent.limits['enterprise']['monthly_runs'] == float('inf')
    
    print("✅ TEST 4 PASSED: All tier limits correctly configured")
    return True


def test_state_tracking():
    """Test 5: Verify state tracks tier and usage"""
    print("\n" + "="*70)
    print("TEST 5: Verify State Tracking")
    print("="*70)
    
    agent = AITestingAgent()
    
    # Check state includes tier information
    assert 'tier' in agent.state
    assert agent.state['tier'] == 'free'
    
    # Check usage tracking exists
    assert 'usage' in agent.state
    assert 'runs_this_month' in agent.state['usage']
    assert 'endpoints_tested' in agent.state['usage']
    
    print("✅ TEST 5 PASSED: State correctly tracks tier and usage")
    return True


def main():
    """Run all tests"""
    print("\n" + "🧪 "*35)
    print("TESTING LICENSE VALIDATION SYSTEM")
    print("🧪 "*35)
    
    tests = [
        test_no_license,
        test_fake_license,
        test_env_variable,
        test_tier_limits,
        test_state_tracking
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ TEST ERROR: {e}")
            failed += 1
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! License system is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
