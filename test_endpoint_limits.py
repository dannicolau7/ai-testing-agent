"""
Test script for endpoint limit checking
Tests tier-based endpoint limits and enforcement
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_testing_agent import AITestingAgent


def test_free_tier_within_limit():
    """Test Free tier with 5 endpoints - should pass"""
    print("\n" + "="*80)
    print("TEST 1: Free Tier - 5 endpoints (SHOULD PASS)")
    print("="*80)
    
    agent = AITestingAgent()
    
    try:
        # Free tier limit is 10, so 5 should work
        agent._check_endpoint_limit(5)
        print("\n✅ TEST PASSED: 5 endpoints accepted for Free tier (limit: 10)")
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False


def test_free_tier_at_limit():
    """Test Free tier with exactly 10 endpoints - should pass"""
    print("\n" + "="*80)
    print("TEST 2: Free Tier - 10 endpoints (AT LIMIT, SHOULD PASS)")
    print("="*80)
    
    agent = AITestingAgent()
    
    try:
        # Free tier limit is 10, so 10 should work
        agent._check_endpoint_limit(10)
        print("\n✅ TEST PASSED: 10 endpoints accepted for Free tier (at limit)")
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False


def test_free_tier_exceeds_limit():
    """Test Free tier with 15 endpoints - should fail"""
    print("\n" + "="*80)
    print("TEST 3: Free Tier - 15 endpoints (SHOULD FAIL)")
    print("="*80)
    
    agent = AITestingAgent()
    
    try:
        # Free tier limit is 10, so 15 should fail
        agent._check_endpoint_limit(15)
        print("\n❌ TEST FAILED: Should have raised exception for 15 endpoints")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"\n✅ TEST PASSED: Exception raised as expected")
        print(f"\nError message:")
        print(error_msg)
        
        # Verify error message contains key information
        checks = [
            ('FREE' in error_msg, "Contains tier name (FREE)"),
            ('10 endpoints' in error_msg or 'Your Limit:   10' in error_msg, "Shows correct limit (10)"),
            ('15 endpoints' in error_msg or 'Requested:    15' in error_msg, "Shows requested count (15)"),
            ('UPGRADE TO PRO' in error_msg, "Contains upgrade message"),
            ('pricing' in error_msg.lower(), "Contains pricing link"),
        ]
        
        all_passed = True
        print("\nError message validation:")
        for check, description in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {description}")
            if not check:
                all_passed = False
        
        return all_passed


def test_pro_tier_within_limit():
    """Test Pro tier with 50 endpoints - should pass"""
    print("\n" + "="*80)
    print("TEST 4: Pro Tier - 50 endpoints (SHOULD PASS)")
    print("="*80)
    
    agent = AITestingAgent()
    agent.tier = 'pro'  # Manually set for testing
    
    try:
        # Pro tier limit is 100, so 50 should work
        agent._check_endpoint_limit(50)
        print("\n✅ TEST PASSED: 50 endpoints accepted for Pro tier (limit: 100)")
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False


def test_pro_tier_exceeds_limit():
    """Test Pro tier with 150 endpoints - should fail with Team upgrade message"""
    print("\n" + "="*80)
    print("TEST 5: Pro Tier - 150 endpoints (SHOULD FAIL)")
    print("="*80)
    
    agent = AITestingAgent()
    agent.tier = 'pro'  # Manually set for testing
    
    try:
        # Pro tier limit is 100, so 150 should fail
        agent._check_endpoint_limit(150)
        print("\n❌ TEST FAILED: Should have raised exception for 150 endpoints")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"\n✅ TEST PASSED: Exception raised as expected")
        print(f"\nError message:")
        print(error_msg)
        
        # Verify error message contains Team upgrade info
        checks = [
            ('PRO' in error_msg, "Contains tier name (PRO)"),
            ('100 endpoints' in error_msg or 'Your Limit:   100' in error_msg, "Shows correct limit (100)"),
            ('150 endpoints' in error_msg or 'Requested:    150' in error_msg, "Shows requested count (150)"),
            ('UPGRADE TO TEAM' in error_msg, "Contains Team upgrade message"),
            ('500 endpoints' in error_msg, "Mentions Team tier limit (500)"),
        ]
        
        all_passed = True
        print("\nError message validation:")
        for check, description in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {description}")
            if not check:
                all_passed = False
        
        return all_passed


def test_team_tier_exceeds_limit():
    """Test Team tier with 600 endpoints - should fail with Enterprise upgrade"""
    print("\n" + "="*80)
    print("TEST 6: Team Tier - 600 endpoints (SHOULD FAIL)")
    print("="*80)
    
    agent = AITestingAgent()
    agent.tier = 'team'  # Manually set for testing
    
    try:
        # Team tier limit is 500, so 600 should fail
        agent._check_endpoint_limit(600)
        print("\n❌ TEST FAILED: Should have raised exception for 600 endpoints")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"\n✅ TEST PASSED: Exception raised as expected")
        print(f"\nError message:")
        print(error_msg)
        
        # Verify error message contains Enterprise upgrade info
        checks = [
            ('TEAM' in error_msg, "Contains tier name (TEAM)"),
            ('500 endpoints' in error_msg or 'Your Limit:   500' in error_msg, "Shows correct limit (500)"),
            ('UPGRADE TO ENTERPRISE' in error_msg, "Contains Enterprise upgrade message"),
            ('UNLIMITED' in error_msg, "Mentions unlimited endpoints"),
        ]
        
        all_passed = True
        print("\nError message validation:")
        for check, description in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {description}")
            if not check:
                all_passed = False
        
        return all_passed


def test_enterprise_tier_unlimited():
    """Test Enterprise tier with 1000 endpoints - should pass (unlimited)"""
    print("\n" + "="*80)
    print("TEST 7: Enterprise Tier - 1000 endpoints (SHOULD PASS - UNLIMITED)")
    print("="*80)
    
    agent = AITestingAgent()
    agent.tier = 'enterprise'  # Manually set for testing
    
    try:
        # Enterprise tier has unlimited endpoints
        agent._check_endpoint_limit(1000)
        print("\n✅ TEST PASSED: 1000 endpoints accepted for Enterprise tier (unlimited)")
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False


def test_integration_with_generate_test_cases():
    """Test that generate_test_cases() calls endpoint limit check"""
    print("\n" + "="*80)
    print("TEST 8: Integration with generate_test_cases()")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Set up mock requirements
    agent.state['requirements'] = {
        'features': [
            {'name': 'Feature 1'},
            {'name': 'Feature 2'},
            {'name': 'Feature 3'}
        ]
    }
    
    try:
        # Should pass with 3 endpoints (under free tier limit of 10)
        result = agent.generate_test_cases(endpoint_count=3)
        print("\n✅ TEST PASSED: generate_test_cases() accepted 3 endpoints")
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False


def test_integration_exceeds_limit():
    """Test that generate_test_cases() rejects over-limit requests"""
    print("\n" + "="*80)
    print("TEST 9: Integration - Exceed limit in generate_test_cases()")
    print("="*80)
    
    agent = AITestingAgent()
    
    # Set up mock requirements
    agent.state['requirements'] = {
        'features': [{'name': f'Feature {i}'} for i in range(20)]
    }
    
    try:
        # Should fail with 20 endpoints (over free tier limit of 10)
        result = agent.generate_test_cases(endpoint_count=20)
        print("\n❌ TEST FAILED: Should have raised exception for 20 endpoints")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"\n✅ TEST PASSED: generate_test_cases() raised exception as expected")
        
        # Verify it's an endpoint limit error
        if 'ENDPOINT LIMIT EXCEEDED' in error_msg:
            print("✓ Correct error type (ENDPOINT LIMIT EXCEEDED)")
            return True
        else:
            print("✗ Wrong error type")
            return False


def main():
    """Run all tests"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════════╗")
    print("║              ENDPOINT LIMIT ENFORCEMENT TEST SUITE                     ║")
    print("╚════════════════════════════════════════════════════════════════════════╝")
    
    tests = [
        ("Free tier - 5 endpoints (within limit)", test_free_tier_within_limit),
        ("Free tier - 10 endpoints (at limit)", test_free_tier_at_limit),
        ("Free tier - 15 endpoints (exceeds limit)", test_free_tier_exceeds_limit),
        ("Pro tier - 50 endpoints (within limit)", test_pro_tier_within_limit),
        ("Pro tier - 150 endpoints (exceeds limit)", test_pro_tier_exceeds_limit),
        ("Team tier - 600 endpoints (exceeds limit)", test_team_tier_exceeds_limit),
        ("Enterprise tier - 1000 endpoints (unlimited)", test_enterprise_tier_unlimited),
        ("Integration with generate_test_cases()", test_integration_with_generate_test_cases),
        ("Integration exceeds limit", test_integration_exceeds_limit),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR in {test_name}: {e}")
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
        print("\n✅ Endpoint limit checking is working correctly:")
        print("   • Free tier enforces 10 endpoint limit")
        print("   • Pro tier enforces 100 endpoint limit")
        print("   • Team tier enforces 500 endpoint limit")
        print("   • Enterprise tier allows unlimited endpoints")
        print("   • Error messages are clear and helpful")
        print("   • Integration with generate_test_cases() works")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
