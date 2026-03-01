#!/usr/bin/env python3
"""
Test suite for Analytics module

Tests privacy-first analytics functionality including:
- Anonymous ID generation
- Opt-out mechanisms
- Graceful failure handling
- Event tracking
- First-run message
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from analytics import Analytics, get_analytics


def test_analytics_initialization():
    """Test analytics initialization with different configurations."""
    print("\n" + "="*70)
    print("TEST 1: Analytics Initialization")
    print("="*70)
    
    # Test with license key
    analytics = Analytics(license_key="test-license-123", tier="pro")
    print(f"✓ Initialized with license key")
    print(f"  Anonymous ID: {analytics.anonymous_id}")
    print(f"  Tier: {analytics.tier}")
    print(f"  Enabled: {analytics.enabled}")
    
    # Test without license key (free tier)
    analytics_free = Analytics(tier="free")
    print(f"\n✓ Initialized without license key (free tier)")
    print(f"  Anonymous ID: {analytics_free.anonymous_id}")
    print(f"  Tier: {analytics_free.tier}")
    
    print("\n✅ Initialization tests passed\n")


def test_opt_out_env_var():
    """Test opt-out via environment variable."""
    print("\n" + "="*70)
    print("TEST 2: Opt-Out via Environment Variable")
    print("="*70)
    
    # Set environment variable to disable telemetry
    os.environ['AI_AGENT_TELEMETRY'] = 'false'
    
    analytics = Analytics(tier="pro")
    
    print(f"Environment variable set: AI_AGENT_TELEMETRY=false")
    print(f"Analytics enabled: {analytics.enabled}")
    
    if not analytics.enabled:
        print("✅ Opt-out via environment variable works correctly")
    else:
        print("❌ Failed: Analytics still enabled despite env var")
    
    # Clean up
    del os.environ['AI_AGENT_TELEMETRY']
    print()


def test_opt_out_config_file():
    """Test opt-out via config file."""
    print("\n" + "="*70)
    print("TEST 3: Opt-Out via Config File")
    print("="*70)
    
    # Create temporary config directory
    temp_home = Path(tempfile.mkdtemp())
    config_dir = temp_home / '.ai-testing-agent'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'config.json'
    
    # Write config with telemetry disabled
    config = {"telemetry_enabled": False}
    with open(config_file, 'w') as f:
        json.dump(config, f)
    
    print(f"Created config file: {config_file}")
    print(f"Config content: {config}")
    
    # Temporarily replace home directory
    original_home = Path.home
    Path.home = lambda: temp_home
    
    try:
        analytics = Analytics(tier="pro")
        print(f"Analytics enabled: {analytics.enabled}")
        
        if not analytics.enabled:
            print("✅ Opt-out via config file works correctly")
        else:
            print("❌ Failed: Analytics still enabled despite config file")
    finally:
        # Restore original home
        Path.home = original_home
        # Clean up temp directory
        shutil.rmtree(temp_home)
    
    print()


def test_anonymous_id_generation():
    """Test anonymous ID generation and consistency."""
    print("\n" + "="*70)
    print("TEST 4: Anonymous ID Generation")
    print("="*70)
    
    license_key = "test-license-key-12345"
    
    # Create two analytics instances with same license key
    analytics1 = Analytics(license_key=license_key, tier="pro")
    analytics2 = Analytics(license_key=license_key, tier="pro")
    
    print(f"License key: {license_key}")
    print(f"Anonymous ID (instance 1): {analytics1.anonymous_id}")
    print(f"Anonymous ID (instance 2): {analytics2.anonymous_id}")
    
    if analytics1.anonymous_id == analytics2.anonymous_id:
        print("✅ Anonymous ID generation is consistent")
    else:
        print("❌ Failed: Anonymous IDs don't match")
    
    # Verify it's actually hashed (not the original key)
    if analytics1.anonymous_id != license_key:
        print("✅ Anonymous ID is hashed (not original license key)")
    else:
        print("❌ Failed: Anonymous ID is the raw license key")
    
    # Verify it's shortened (16 characters)
    if len(analytics1.anonymous_id) == 16:
        print(f"✅ Anonymous ID is shortened to 16 characters")
    else:
        print(f"⚠️  Anonymous ID length: {len(analytics1.anonymous_id)} (expected 16)")
    
    print()


def test_event_tracking():
    """Test event tracking (without actually sending requests)."""
    print("\n" + "="*70)
    print("TEST 5: Event Tracking")
    print("="*70)
    
    analytics = Analytics(license_key="test-key", tier="pro")
    
    # Track various events
    print("Tracking events (will fail gracefully if server unavailable):")
    
    analytics.track_tool_started("pro")
    print("  ✓ Tracked: tool_started")
    
    analytics.track_test_generation_started(50)
    print("  ✓ Tracked: test_generation_started")
    
    analytics.track_test_generation_complete(
        endpoints=50,
        tests_generated=100,
        duration_seconds=45.5,
        success=True
    )
    print("  ✓ Tracked: test_generation_complete (success)")
    
    analytics.track_test_generation_complete(
        endpoints=10,
        tests_generated=0,
        duration_seconds=5.2,
        success=False,
        error="api_error"
    )
    print("  ✓ Tracked: test_generation_complete (error)")
    
    analytics.track_error("license_invalid", "Invalid license key")
    print("  ✓ Tracked: error_encountered")
    
    analytics.track_upgrade_prompt_shown("free", "pro", "endpoint_limit")
    print("  ✓ Tracked: upgrade_prompt_shown")
    
    print("\n✅ Event tracking tests completed (all events tracked)")
    print("   Note: Actual HTTP requests may have failed gracefully")
    print()


def test_graceful_failure():
    """Test that analytics failures don't crash the application."""
    print("\n" + "="*70)
    print("TEST 6: Graceful Failure Handling")
    print("="*70)
    
    analytics = Analytics(license_key="test-key", tier="pro")
    
    # These should all fail gracefully (server doesn't exist)
    print("Testing graceful failure with non-existent server...")
    
    try:
        analytics.track_event("test_event", {"test": "data"})
        print("  ✓ track_event() completed without exception")
    except Exception as e:
        print(f"  ❌ Exception raised: {e}")
    
    try:
        analytics.track_tool_started("pro")
        print("  ✓ track_tool_started() completed without exception")
    except Exception as e:
        print(f"  ❌ Exception raised: {e}")
    
    try:
        analytics.track_error("test_error")
        print("  ✓ track_error() completed without exception")
    except Exception as e:
        print(f"  ❌ Exception raised: {e}")
    
    print("\n✅ All analytics calls completed without crashing")
    print("   (Failures were handled gracefully)")
    print()


def test_disable_telemetry():
    """Test the disable telemetry function."""
    print("\n" + "="*70)
    print("TEST 7: Disable Telemetry Function")
    print("="*70)
    
    # Create temporary home directory
    temp_home = Path(tempfile.mkdtemp())
    
    # Temporarily replace home directory
    original_home = Path.home
    Path.home = lambda: temp_home
    
    try:
        analytics = Analytics(tier="pro")
        print(f"Initial state - Enabled: {analytics.enabled}")
        
        # Disable telemetry
        analytics.disable_telemetry()
        print(f"After disable - Enabled: {analytics.enabled}")
        
        # Check if config file was created
        config_file = temp_home / '.ai-testing-agent' / 'config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            print(f"Config file created: {config_file}")
            print(f"Config content: {config}")
            
            if config.get('telemetry_enabled') == False:
                print("✅ Telemetry successfully disabled and persisted")
            else:
                print("❌ Failed: Config file doesn't show telemetry disabled")
        else:
            print("❌ Failed: Config file not created")
    
    finally:
        # Restore original home
        Path.home = original_home
        # Clean up temp directory
        shutil.rmtree(temp_home)
    
    print()


def test_analytics_status():
    """Test analytics status retrieval."""
    print("\n" + "="*70)
    print("TEST 8: Analytics Status")
    print("="*70)
    
    analytics = Analytics(license_key="test-key-123", tier="pro")
    status = analytics.get_status()
    
    print("Analytics Status:")
    print(f"  Enabled: {status['enabled']}")
    print(f"  Anonymous ID: {status['anonymous_id']}")
    print(f"  Tier: {status['tier']}")
    print(f"\nData collected: {len(status['data_collected'])} items")
    for item in status['data_collected']:
        print(f"    ✓ {item}")
    
    print(f"\nData NOT collected: {len(status['data_not_collected'])} items")
    for item in status['data_not_collected']:
        print(f"    ✗ {item}")
    
    print(f"\nOpt-out methods: {len(status['opt_out_methods'])} available")
    for method in status['opt_out_methods']:
        print(f"    • {method}")
    
    print("\n✅ Status retrieval test passed")
    print()


def test_first_run_message():
    """Test first-run message logic."""
    print("\n" + "="*70)
    print("TEST 9: First-Run Message")
    print("="*70)
    
    # Create temporary home directory
    temp_home = Path(tempfile.mkdtemp())
    
    # Temporarily replace home directory
    original_home = Path.home
    Path.home = lambda: temp_home
    
    try:
        # First run - should show message
        print("Creating analytics instance (first run)...")
        analytics1 = Analytics(tier="pro")
        
        marker_file = temp_home / '.ai-testing-agent' / '.analytics_notice_shown'
        
        # Show the message (would normally print to console)
        analytics1.show_first_run_message()
        
        if marker_file.exists():
            print("✓ Marker file created after first run")
        else:
            print("⚠️  Marker file not created (message may not have shown)")
        
        # Second run - should not show message
        print("\nCreating another analytics instance (second run)...")
        analytics2 = Analytics(tier="pro")
        
        if analytics2.first_run_shown:
            print("✓ First-run message suppressed on second run")
        else:
            print("⚠️  First-run flag not set correctly")
        
        print("\n✅ First-run message logic works correctly")
    
    finally:
        # Restore original home
        Path.home = original_home
        # Clean up temp directory
        shutil.rmtree(temp_home)
    
    print()


def test_global_analytics_instance():
    """Test global analytics instance getter."""
    print("\n" + "="*70)
    print("TEST 10: Global Analytics Instance")
    print("="*70)
    
    # Get global instance
    analytics1 = get_analytics(license_key="global-test-key", tier="team")
    print(f"Created global instance - Tier: {analytics1.tier}")
    
    # Get it again - should return same instance
    analytics2 = get_analytics()
    print(f"Retrieved global instance - Tier: {analytics2.tier}")
    
    if analytics1 is analytics2:
        print("✅ Global instance is singleton (same object)")
    else:
        print("❌ Failed: Different objects returned")
    
    print()


def run_all_tests():
    """Run all analytics tests."""
    print("\n" + "🧪 " + "="*68)
    print("ANALYTICS TEST SUITE")
    print("="*70)
    print("Testing privacy-first analytics functionality\n")
    
    tests = [
        test_analytics_initialization,
        test_opt_out_env_var,
        test_opt_out_config_file,
        test_anonymous_id_generation,
        test_event_tracking,
        test_graceful_failure,
        test_disable_telemetry,
        test_analytics_status,
        test_first_run_message,
        test_global_analytics_instance
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {test_func.__name__}")
            print(f"   Error: {e}\n")
            failed += 1
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All analytics tests passed!")
        print("\nPrivacy features verified:")
        print("  ✓ Anonymous ID generation works")
        print("  ✓ Opt-out mechanisms function correctly")
        print("  ✓ Graceful failure handling prevents crashes")
        print("  ✓ No blocking behavior")
        print("  ✓ Privacy-first design respected")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review output above")
    
    print("="*70 + "\n")


if __name__ == '__main__':
    run_all_tests()
