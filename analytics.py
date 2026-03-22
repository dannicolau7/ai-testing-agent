"""
Privacy-First Analytics for AI Testing Agent

This module tracks anonymous product usage to help improve the tool.
NO personal data or code is collected - only usage statistics.

Privacy guarantees:
- Anonymous user IDs only (machine-based hash)
- No requirements content sent
- No code or test data transmitted
- Opt-out support via multiple methods
- All requests are non-blocking
- Graceful failure on network errors
"""

import os
import json
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
import warnings

# Optional import for HTTP requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    warnings.warn("requests library not available - analytics disabled")


class Analytics:
    """
    Privacy-first analytics tracker.
    
    Tracks anonymous usage statistics to improve the product without
    compromising user privacy. All tracking can be disabled via opt-out.
    """
    
    # Timeout for analytics requests (never block user operations)
    REQUEST_TIMEOUT = 2  # seconds

    def __init__(self, license_key: Optional[str] = None, tier: Optional[str] = None):
        """
        Initialize analytics tracker.

        Args:
            license_key: Accepted for backward compatibility, not used
            tier: Accepted for backward compatibility, not used
        """
        self.license_key = license_key
        self.tier = tier
        self.enabled = self._check_enabled()
        self.anonymous_id = self._generate_anonymous_id()
        
        # Track if first run message has been shown
        self.first_run_shown = self._check_first_run()
    
    def _check_enabled(self) -> bool:
        """
        Check if telemetry is enabled.
        
        Checks multiple opt-out mechanisms:
        1. Environment variable: AI_AGENT_TELEMETRY
        2. Config file: ~/.ai-testing-agent/config.json
        3. requests library availability
        
        Returns:
            True if enabled, False if opted out
        """
        # Check environment variable
        env_telemetry = os.getenv('AI_AGENT_TELEMETRY', 'true').lower()
        if env_telemetry in ['false', '0', 'no', 'off', 'disabled']:
            return False
        
        # Check config file
        try:
            config_dir = Path.home() / '.ai-testing-agent'
            config_file = config_dir / 'config.json'
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    telemetry_enabled = config.get('telemetry_enabled', True)
                    
                    # Handle various false values
                    if isinstance(telemetry_enabled, bool):
                        if not telemetry_enabled:
                            return False
                    elif isinstance(telemetry_enabled, str):
                        if telemetry_enabled.lower() in ['false', '0', 'no', 'off', 'disabled']:
                            return False
        except Exception:
            # If config read fails, default to enabled
            pass
        
        # Check if requests library is available
        if not REQUESTS_AVAILABLE:
            return False
        
        # Default: enabled
        return True
    
    def _generate_anonymous_id(self) -> str:
        """
        Generate anonymous machine-based user ID.

        Uses SHA256 hashing of machine hostname. Cannot be reversed.

        Returns:
            16-character hashed anonymous ID
        """
        try:
            import platform
            import socket

            machine_data = f"{platform.node()}-{socket.gethostname()}"
            return hashlib.sha256(machine_data.encode()).hexdigest()[:16]
        except Exception:
            return "anonymous-user"
    
    def _check_first_run(self) -> bool:
        """
        Check if this is the first run (to show privacy notice).
        
        Returns:
            True if message has been shown before, False if first run
        """
        try:
            config_dir = Path.home() / '.ai-testing-agent'
            marker_file = config_dir / '.analytics_notice_shown'
            
            return marker_file.exists()
        except Exception:
            # If we can't check, assume it's been shown to avoid spam
            return True
    
    def _mark_first_run_complete(self):
        """Mark that the first-run message has been shown."""
        try:
            config_dir = Path.home() / '.ai-testing-agent'
            config_dir.mkdir(exist_ok=True)
            
            marker_file = config_dir / '.analytics_notice_shown'
            marker_file.touch()
        except Exception:
            # Fail silently - this is not critical
            pass
    
    def show_first_run_message(self):
        """
        Show first-run privacy notice to user.
        
        Only shown once, on first use of the tool.
        """
        if self.first_run_shown:
            return
        
        if not self.enabled:
            # If already opted out, don't show message
            self._mark_first_run_complete()
            return
        
        print("\n" + "="*70)
        print("📊 Anonymous Usage Analytics")
        print("="*70)
        print("""
Anonymous usage analytics are enabled to help improve the tool.

What we collect:
  ✓ Tool usage events (started, completed, errors)
  ✓ Performance metrics (duration, endpoints, tests generated)
  ✓ Success/failure status

What we DON'T collect:
  ✗ NO personal data or identifiable information
  ✗ NO requirements content or business logic
  ✗ NO generated code or test data
  ✗ NO IP addresses

Your privacy is important. All data is anonymous.

Opt out using any of these methods:
  • Environment variable: export AI_AGENT_TELEMETRY=false
  • Config file: echo '{"telemetry_enabled": false}' > ~/.ai-testing-agent/config.json
  • CLI flag: --no-telemetry
""")
        print("="*70 + "\n")
        
        self._mark_first_run_complete()
    
    def track_event(
        self,
        event: str,
        properties: Optional[Dict[str, Any]] = None,
        blocking: bool = False
    ):
        """
        Track an analytics event.
        
        This method is non-blocking by default and will never cause the
        application to fail or hang. All errors are caught and logged silently.
        
        Args:
            event: Event name (e.g., "test_generation_complete")
            properties: Event properties (e.g., tier, endpoints, duration)
            blocking: If True, wait for request to complete (default: False)
        """
        # Skip if telemetry is disabled
        if not self.enabled:
            return
        
        # Skip if requests library not available
        if not REQUESTS_AVAILABLE:
            return
        
        # Prepare payload
        payload = {
            "event": event,
            "properties": properties or {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "anonymous_id": self.anonymous_id
        }

        # Send analytics in background thread (non-blocking)
        if blocking:
            self._send_analytics(payload)
        else:
            thread = threading.Thread(
                target=self._send_analytics,
                args=(payload,),
                daemon=True  # Don't prevent program exit
            )
            thread.start()
    
    def _send_analytics(self, payload: Dict[str, Any]):
        """
        Send analytics payload to server. Fails silently on any error.

        Args:
            payload: Analytics payload to send
        """
        pass  # Analytics endpoint not configured
    
    def track_tool_started(self, tier: Optional[str] = None):
        """Track when the tool starts."""
        self.track_event("tool_started")
    
    def track_test_generation_started(self, endpoint_count: int):
        """Track when test generation begins."""
        self.track_event(
            "test_generation_started",
            {"endpoints": endpoint_count}
        )
    
    def track_test_generation_complete(
        self,
        endpoints: int,
        tests_generated: int,
        duration_seconds: float,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Track completion of test generation.
        
        Args:
            endpoints: Number of endpoints processed
            tests_generated: Number of tests generated
            duration_seconds: Execution time in seconds
            success: Whether generation succeeded
            error: Error type if failed (e.g., "api_error", "limit_exceeded")
        """
        properties = {
            "endpoints": endpoints,
            "tests_generated": tests_generated,
            "duration_seconds": round(duration_seconds, 2),
            "success": success
        }
        
        if error:
            properties["error"] = error
        
        self.track_event("test_generation_complete", properties)
    
    def track_error(self, error_type: str, error_message: str = ""):
        """
        Track errors encountered. Only error type is sent, not the message.

        Args:
            error_type: Type of error (e.g., "api_timeout", "api_error")
            error_message: Ignored — not transmitted
        """
        self.track_event(
            "error_encountered",
            {"error_type": error_type}
        )

    def track_upgrade_prompt_shown(self, from_tier: str, to_tier: str, reason: str):
        """Accepted for backward compatibility. No-op."""
        pass
    
    def disable_telemetry(self):
        """
        Disable telemetry for this session and persist to config.
        """
        self.enabled = False
        
        try:
            config_dir = Path.home() / '.ai-testing-agent'
            config_dir.mkdir(exist_ok=True)
            
            config_file = config_dir / 'config.json'
            
            # Load existing config if present
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Update telemetry setting
            config['telemetry_enabled'] = False
            
            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Telemetry disabled successfully")
            print("   Config saved to: ~/.ai-testing-agent/config.json")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not save telemetry preference: {e}")
            print("   Use: export AI_AGENT_TELEMETRY=false")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current analytics status.
        
        Returns:
            Dictionary with analytics configuration
        """
        return {
            "enabled": self.enabled,
            "anonymous_id": self.anonymous_id if self.enabled else "disabled",
            "tier": self.tier,
            "opt_out_methods": [
                "Environment: export AI_AGENT_TELEMETRY=false",
                "Config file: ~/.ai-testing-agent/config.json",
                "CLI flag: --no-telemetry"
            ],
            "data_collected": [
                "Usage events (started, completed, errors)",
                "Performance metrics (duration, counts)",
                "Success/failure status"
            ],
            "data_not_collected": [
                "Personal data",
                "Requirements content",
                "Generated code",
                "Test data",
                "IP addresses"
            ]
        }


# Global analytics instance (lazy initialization)
_analytics_instance: Optional[Analytics] = None


def get_analytics(license_key: Optional[str] = None, tier: str = 'free') -> Analytics:
    """
    Get or create global analytics instance.
    
    Args:
        license_key: License key for anonymous ID generation
        tier: Current tier
        
    Returns:
        Analytics instance
    """
    global _analytics_instance
    
    if _analytics_instance is None:
        _analytics_instance = Analytics(license_key=license_key, tier=tier)
    
    return _analytics_instance


def track_event(event: str, properties: Optional[Dict[str, Any]] = None):
    """
    Convenience function to track an event.
    
    Args:
        event: Event name
        properties: Event properties
    """
    if _analytics_instance:
        _analytics_instance.track_event(event, properties)


def disable_telemetry():
    """Convenience function to disable telemetry."""
    if _analytics_instance:
        _analytics_instance.disable_telemetry()


def show_analytics_status():
    """Show current analytics status and configuration."""
    if _analytics_instance:
        status = _analytics_instance.get_status()
        
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
    else:
        print("Analytics not initialized")
