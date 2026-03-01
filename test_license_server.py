#!/usr/bin/env python3
"""
Comprehensive test suite for the License Server API.

Tests all endpoints, error handling, and security features.
Uses pytest framework with fixtures and mocking.

Usage:
    pytest test_license_server.py -v
    pytest test_license_server.py -v -s  # with output
"""

import pytest
import requests
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch

# Server configuration
BASE_URL = "http://localhost:5000"
ADMIN_API_KEY = "admin-secret-key-change-in-production"


@pytest.fixture(scope="module")
def api_base():
    """Provide base URL for API."""
    return BASE_URL


@pytest.fixture
def valid_license_key():
    """Provide a valid test license key."""
    return "PRO-DEMO-TEST-KEY1"


@pytest.fixture
def admin_headers():
    """Provide admin authentication headers."""
    return {
        "X-Admin-API-Key": ADMIN_API_KEY,
        "Content-Type": "application/json"
    }


@pytest.fixture
def test_email():
    """Provide test email for license generation."""
    timestamp = int(time.time())
    return f"test_{timestamp}@example.com"


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_endpoint_exists(self, api_base):
        """Test that health endpoint is accessible."""
        response = requests.get(f"{api_base}/health")
        assert response.status_code == 200
    
    def test_health_response_format(self, api_base):
        """Test health check response format."""
        response = requests.get(f"{api_base}/health")
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert data["status"] == "ok"
    
    def test_health_check_returns_version(self, api_base):
        """Test that version is returned."""
        response = requests.get(f"{api_base}/health")
        data = response.json()
        
        assert data["version"] == "1.0.0"


class TestLicenseValidation:
    """Test license validation endpoint."""
    
    def test_validate_valid_license(self, api_base, valid_license_key):
        """Test validation of a valid license key."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": valid_license_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["tier"] == "pro"
        assert "expires" in data
        assert "email" in data
    
    def test_validate_invalid_license(self, api_base):
        """Test validation of an invalid license key."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": "INVALID-KEY-TEST-0000"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["valid"] is False
        assert "error" in data
    
    def test_validate_missing_license_key(self, api_base):
        """Test validation without license key."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert "error" in data
        assert "required" in data["error"].lower()
    
    def test_validate_malformed_license(self, api_base):
        """Test validation of malformed license key."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": "BAD-FORMAT"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["valid"] is False
        assert "format" in data["error"].lower()
    
    def test_validate_free_tier_license(self, api_base):
        """Test validation of free tier license."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": "FREE-DEMO-TEST-KEY1"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["tier"] == "free"
        assert data["monthly_runs"] == 50
        assert data["endpoints"] == 10
    
    def test_validate_team_tier_license(self, api_base):
        """Test validation of team tier license."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": "TEAM-DEMO-TEST-KEY1"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["tier"] == "team"
        assert data["endpoints"] == 500
    
    def test_validate_enterprise_tier_license(self, api_base):
        """Test validation of enterprise tier license."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": "ENT-DEMO-TEST-KEY1"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["tier"] == "enterprise"


class TestUsageTracking:
    """Test usage tracking endpoint."""
    
    def test_track_usage_success(self, api_base, valid_license_key):
        """Test successful usage tracking."""
        response = requests.post(
            f"{api_base}/v1/track-usage",
            json={
                "license_key": valid_license_key,
                "endpoints": 10,
                "cost": 0.15,
                "tests_generated": 25
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
    
    def test_track_usage_missing_license(self, api_base):
        """Test usage tracking without license key."""
        response = requests.post(
            f"{api_base}/v1/track-usage",
            json={
                "endpoints": 10,
                "cost": 0.15
            }
        )
        
        assert response.status_code == 400
    
    def test_track_usage_invalid_license(self, api_base):
        """Test usage tracking with invalid license."""
        response = requests.post(
            f"{api_base}/v1/track-usage",
            json={
                "license_key": "INVALID-KEY-0000-0000-0000",
                "endpoints": 10
            }
        )
        
        assert response.status_code == 404
    
    def test_track_usage_minimal_data(self, api_base, valid_license_key):
        """Test usage tracking with minimal data."""
        response = requests.post(
            f"{api_base}/v1/track-usage",
            json={
                "license_key": valid_license_key
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True


class TestAdminLicenseGeneration:
    """Test admin license generation endpoint."""
    
    def test_generate_license_success(self, api_base, admin_headers, test_email):
        """Test successful license generation."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "pro",
                "email": test_email,
                "duration_months": 12
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert "license_key" in data
        assert data["tier"] == "pro"
        assert data["email"] == test_email
        assert "expires" in data
        
        # Verify license key format
        license_key = data["license_key"]
        parts = license_key.split("-")
        assert len(parts) == 4
        assert parts[0] == "PRO"
    
    def test_generate_license_without_auth(self, api_base, test_email):
        """Test license generation without admin key."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            json={
                "tier": "pro",
                "email": test_email
            }
        )
        
        assert response.status_code == 401
    
    def test_generate_license_invalid_auth(self, api_base, test_email):
        """Test license generation with invalid admin key."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers={
                "X-Admin-API-Key": "wrong-key",
                "Content-Type": "application/json"
            },
            json={
                "tier": "pro",
                "email": test_email
            }
        )
        
        assert response.status_code == 403
    
    def test_generate_license_missing_email(self, api_base, admin_headers):
        """Test license generation without email."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "pro"
            }
        )
        
        assert response.status_code == 400
    
    def test_generate_license_invalid_tier(self, api_base, admin_headers, test_email):
        """Test license generation with invalid tier."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "invalid",
                "email": test_email
            }
        )
        
        assert response.status_code == 400
    
    def test_generate_free_license(self, api_base, admin_headers, test_email):
        """Test generation of free tier license."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "free",
                "email": test_email,
                "duration_months": 6
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["tier"] == "free"
        license_key = data["license_key"]
        assert license_key.startswith("FREE-")
    
    def test_generate_team_license(self, api_base, admin_headers, test_email):
        """Test generation of team tier license."""
        response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "team",
                "email": test_email
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["tier"] == "team"
        assert data["license_key"].startswith("TEAM-")


class TestAdminLicenseDeactivation:
    """Test admin license deactivation endpoint."""
    
    def test_deactivate_license_requires_auth(self, api_base):
        """Test that deactivation requires authentication."""
        response = requests.post(
            f"{api_base}/v1/deactivate-license",
            json={
                "license_key": "PRO-DEMO-TEST-KEY1"
            }
        )
        
        assert response.status_code == 401
    
    def test_deactivate_invalid_license(self, api_base, admin_headers):
        """Test deactivation of non-existent license."""
        response = requests.post(
            f"{api_base}/v1/deactivate-license",
            headers=admin_headers,
            json={
                "license_key": "INVALID-0000-0000-0000"
            }
        )
        
        assert response.status_code == 404


class TestAdminStatistics:
    """Test admin statistics endpoint."""
    
    def test_stats_requires_auth(self, api_base):
        """Test that stats endpoint requires authentication."""
        response = requests.get(f"{api_base}/v1/admin/stats")
        
        assert response.status_code == 401
    
    def test_stats_success(self, api_base, admin_headers):
        """Test successful stats retrieval."""
        response = requests.get(
            f"{api_base}/v1/admin/stats",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_licenses" in data
        assert "active_licenses" in data
        assert "licenses_by_tier" in data
        assert "total_usage_logs" in data
        
        # Verify data types
        assert isinstance(data["total_licenses"], int)
        assert isinstance(data["licenses_by_tier"], dict)
    
    def test_stats_includes_tier_breakdown(self, api_base, admin_headers):
        """Test that stats include tier breakdown."""
        response = requests.get(
            f"{api_base}/v1/admin/stats",
            headers=admin_headers
        )
        
        data = response.json()
        tier_counts = data["licenses_by_tier"]
        
        # Should have at least the demo licenses
        assert "free" in tier_counts or "pro" in tier_counts


class TestErrorHandling:
    """Test error handling across endpoints."""
    
    def test_404_for_invalid_endpoint(self, api_base):
        """Test 404 for non-existent endpoint."""
        response = requests.get(f"{api_base}/invalid-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
    
    def test_empty_request_body(self, api_base):
        """Test handling of empty request body."""
        response = requests.post(
            f"{api_base}/v1/validate-license",
            json=None
        )
        
        assert response.status_code == 400


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_license_lifecycle(self, api_base, admin_headers, test_email):
        """Test complete license lifecycle: generate, validate, track usage."""
        
        # Step 1: Generate license
        gen_response = requests.post(
            f"{api_base}/v1/generate-license",
            headers=admin_headers,
            json={
                "tier": "pro",
                "email": test_email,
                "duration_months": 12
            }
        )
        
        assert gen_response.status_code == 201
        license_key = gen_response.json()["license_key"]
        
        # Step 2: Validate license
        val_response = requests.post(
            f"{api_base}/v1/validate-license",
            json={"license_key": license_key}
        )
        
        assert val_response.status_code == 200
        assert val_response.json()["valid"] is True
        
        # Step 3: Track usage
        usage_response = requests.post(
            f"{api_base}/v1/track-usage",
            json={
                "license_key": license_key,
                "endpoints": 5,
                "cost": 0.10
            }
        )
        
        assert usage_response.status_code == 200
        assert usage_response.json()["success"] is True
        
        # Step 4: Verify in stats
        stats_response = requests.get(
            f"{api_base}/v1/admin/stats",
            headers=admin_headers
        )
        
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total_usage_logs"] > 0


def test_server_is_running():
    """Verify that the license server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200
        print(f"\n✅ License server is running at {BASE_URL}")
    except requests.exceptions.ConnectionError:
        pytest.fail(
            f"\n❌ License server is not running at {BASE_URL}\n"
            f"   Please start it with: ./run_license_server.sh\n"
            f"   Or run: python license_server.py"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
