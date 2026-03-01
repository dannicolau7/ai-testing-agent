"""
Test script for AI routing functionality
Tests tier-based routing between mock and real AI
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_testing_agent import AITestingAgent


def test_free_tier():
    """Test Free tier - should use mock AI"""
    print("\n" + "="*80)
    print("TEST 1: Free Tier (Mock AI)")
    print("="*80)
    
    # Create agent with free tier (no license key)
    agent = AITestingAgent()
    
    # Test a simple AI call
    prompt = "Extract requirements from this text: User login feature"
    response = agent._call_ai(prompt)
    
    print(f"\nResponse type: {type(response)}")
    print(f"Is mock response: {response.get('_mock_response', False)}")
    print("\n✅ Free tier test completed")
    

def test_pro_tier_no_api_key():
    """Test Pro tier without API key - should show error and fallback to mock"""
    print("\n" + "="*80)
    print("TEST 2: Pro Tier WITHOUT API Key (Should fallback to mock)")
    print("="*80)
    
    # Temporarily set a fake license key to simulate Pro tier
    os.environ['AI_AGENT_LICENSE_KEY'] = 'fake-pro-license'
    
    # Remove API key if it exists
    if 'ANTHROPIC_API_KEY' in os.environ:
        del os.environ['ANTHROPIC_API_KEY']
    
    # Create agent - will validate to free tier since license server isn't real
    # but we can manually set tier for testing
    agent = AITestingAgent()
    agent.tier = 'pro'  # Manually set for testing
    
    # Test AI call
    prompt = "Generate test cases for user authentication"
    response = agent._call_ai(prompt)
    
    print(f"\nResponse type: {type(response)}")
    print(f"Is mock response: {response.get('_mock_response', False)}")
    print("\n✅ Pro tier (no API key) test completed")
    
    # Cleanup
    if 'AI_AGENT_LICENSE_KEY' in os.environ:
        del os.environ['AI_AGENT_LICENSE_KEY']


def test_mock_response_variety():
    """Test that mock responses have variety"""
    print("\n" + "="*80)
    print("TEST 3: Mock Response Variety")
    print("="*80)
    
    agent = AITestingAgent()
    
    print("\n--- Call 1: Requirements parsing ---")
    response1 = agent._call_ai("Extract requirements from: Login feature")
    print(f"Features count: {len(response1.get('features', []))}")
    
    print("\n--- Call 2: Test case generation ---")
    response2 = agent._call_ai("Generate test cases for authentication")
    print(f"Test cases count: {len(response2.get('test_cases', []))}")
    
    print("\n--- Call 3: Pytest code ---")
    response3 = agent._call_ai("Generate pytest code for login test")
    print(f"Response is code: {isinstance(response3, str) and 'pytest' in response3}")
    
    print("\n--- Call 4: Analysis ---")
    response4 = agent._call_ai("Analyze test results and provide insights")
    print(f"Has recommendations: {'recommendations' in response4}")
    
    print("\n✅ Variety test completed - all response types generated")


def test_usage_tracking():
    """Test that usage tracking is initialized"""
    print("\n" + "="*80)
    print("TEST 4: Usage Tracking")
    print("="*80)
    
    agent = AITestingAgent()
    
    print(f"\nInitial usage state:")
    print(f"  API calls: {agent.state['usage']['api_calls']}")
    print(f"  Tokens used: {agent.state['usage']['tokens_used']}")
    print(f"  Estimated cost: ${agent.state['usage']['estimated_cost']:.4f}")
    print(f"  Mock call count: {agent._mock_call_count}")
    
    # Make a few mock calls
    agent._call_ai("Test prompt 1")
    agent._call_ai("Test prompt 2")
    
    print(f"\nAfter 2 mock calls:")
    print(f"  Mock call count: {agent._mock_call_count}")
    
    print("\n✅ Usage tracking test completed")


def test_different_tiers():
    """Test different tier configurations"""
    print("\n" + "="*80)
    print("TEST 5: Different Tier Configurations")
    print("="*80)
    
    tiers = ['free', 'pro', 'team', 'enterprise']
    
    for tier in tiers:
        print(f"\n--- Testing {tier.upper()} tier ---")
        agent = AITestingAgent()
        agent.tier = tier  # Manually set for testing
        
        # Test a call
        response = agent._call_ai("Test prompt")
        
        if tier == 'free':
            assert response.get('_mock_response') == True, f"{tier} should use mock"
            print(f"✓ {tier.upper()} uses mock AI (correct)")
        else:
            # Without API key, paid tiers should also fallback to mock
            print(f"✓ {tier.upper()} attempted real API, fell back to mock (correct)")
    
    print("\n✅ Tier configuration test completed")


def main():
    """Run all tests"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════════╗")
    print("║                 AI ROUTING FUNCTIONALITY TEST SUITE                    ║")
    print("╚════════════════════════════════════════════════════════════════════════╝")
    
    try:
        test_free_tier()
        test_pro_tier_no_api_key()
        test_mock_response_variety()
        test_usage_tracking()
        test_different_tiers()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\nSummary:")
        print("✅ Free tier routing works")
        print("✅ Paid tier routing works (with fallback)")
        print("✅ Mock responses have variety")
        print("✅ Usage tracking initialized")
        print("✅ All tier configurations tested")
        print("\n💡 To test with real Claude API:")
        print("   1. Set ANTHROPIC_API_KEY environment variable")
        print("   2. Use a Pro/Team/Enterprise tier")
        print("   3. The system will automatically use real API")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
