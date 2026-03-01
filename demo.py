#!/usr/bin/env python3
"""
Demo of AI Testing Agent
This script demonstrates the autonomous testing capabilities
"""

import sys
from ai_testing_agent import AITestingAgent


def main():
    """Run demo of AI Testing Agent."""
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║        AI TESTING AGENT - AUTONOMOUS TEST AUTOMATION         ║
║                      Demo Version 1.0                        ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Read example requirements
    with open('example_requirements.txt', 'r') as f:
        requirements_text = f.read()
    
    print("📚 Loaded example requirements:")
    print("   - E-Commerce User Authentication System")
    print("   - 7 sections with detailed specifications")
    print(f"   - {len(requirements_text.split())} words of requirements\n")
    
    # Initialize AI agent
    print("🤖 Initializing AI Testing Agent...")
    agent = AITestingAgent()
    print("   ✓ Agent initialized")
    print("   ✓ Using mock AI (set ANTHROPIC_API_KEY for real AI)\n")
    
    # Run autonomous workflow
    print("🚀 Starting autonomous testing workflow...\n")
    
    result = agent.run_autonomous(requirements_text)
    
    if result['success']:
        print("\n" + "="*60)
        print("📊 WORKFLOW SUMMARY")
        print("="*60)
        print(f"✅ Status: SUCCESS")
        print(f"📝 Test Cases Generated: {result['test_cases']}")
        print(f"💻 Pytest Files Created: {len(result['pytest_files'])}")
        print(f"✅ Tests Passed: {result['results']['passed']}")
        print(f"❌ Tests Failed: {result['results']['failed']}")
        print(f"📋 Report Location: {result['report']}")
        print("="*60)
        
        print("\n💡 NEXT STEPS:")
        print("1. Check the 'test_output' directory for generated files")
        print("2. Open test_report.html in your browser")
        print("3. Review generated pytest files")
        print("4. Run: pytest test_output/ (to execute tests)")
        print("\n📚 To use with real AI:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("   python demo.py")
        
    else:
        print(f"\n❌ Workflow failed: {result['error']}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
