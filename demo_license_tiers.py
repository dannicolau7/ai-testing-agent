#!/usr/bin/env python3
"""
Demo script showing different license tiers
"""

from ai_testing_agent import AITestingAgent

print("\n" + "🎯"*30)
print("DEMO: LICENSE TIER SYSTEM")
print("🎯"*30)

# Demo 1: Free Tier (No License)
print("\n\n📱 DEMO 1: FREE TIER")
print("=" * 70)
agent_free = AITestingAgent()

# Demo 2: With License Key (will attempt validation)
print("\n\n💎 DEMO 2: ATTEMPTING LICENSE VALIDATION")
print("=" * 70)
print("Note: This will show connection warning since validation server")
print("      doesn't exist yet. In production, valid keys would activate")
print("      Pro/Team/Enterprise tiers.\n")
agent_pro = AITestingAgent(license_key="PRO-LICENSE-KEY-EXAMPLE")

print("\n\n✅ DEMO COMPLETE!")
print("\n📚 Key Features Implemented:")
print("   ✓ Tier-based licensing (Free, Pro, Team, Enterprise)")
print("   ✓ License validation via API")
print("   ✓ Environment variable support (AI_AGENT_LICENSE_KEY)")
print("   ✓ Graceful fallback to free tier on errors")
print("   ✓ Comprehensive error handling")
print("   ✓ Usage tracking in state")
print("   ✓ Beautiful tier information display")
