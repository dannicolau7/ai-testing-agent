#!/usr/bin/env python3
"""
License Server API - Flask Backend
IMPORTANT: This file should NOT be open sourced!

This server handles:
- License key validation
- Usage tracking for billing
- License generation (admin only)
- Security and authentication

DO NOT commit this file to public repositories!
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import secrets
import string
import logging
import os
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for web requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('license_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Admin API key (load from environment in production)
ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'admin-secret-key-change-in-production')

# Version
VERSION = "1.0.0"

# In-memory license database
# In production, this should be replaced with a real database (PostgreSQL, MongoDB, etc.)
LICENSES = {
    'FREE-DEMO-TEST-KEY1': {
        'tier': 'free',
        'email': 'demo@example.com',
        'expires': '2099-12-31',
        'active': True,
        'created': '2026-01-01',
        'monthly_runs': 50,
        'endpoints': 10
    },
    'PRO-DEMO-TEST-KEY1': {
        'tier': 'pro',
        'email': 'demo@example.com',
        'expires': '2027-12-31',
        'active': True,
        'created': '2026-01-01',
        'monthly_runs': float('inf'),
        'endpoints': 100
    },
    'TEAM-DEMO-TEST-KEY1': {
        'tier': 'team',
        'email': 'demo@example.com',
        'expires': '2027-12-31',
        'active': True,
        'created': '2026-01-01',
        'monthly_runs': float('inf'),
        'endpoints': 500
    },
    'ENT-DEMO-TEST-KEY1': {
        'tier': 'enterprise',
        'email': 'demo@example.com',
        'expires': '2027-12-31',
        'active': True,
        'created': '2026-01-01',
        'monthly_runs': float('inf'),
        'endpoints': float('inf')
    }
}

# Usage tracking (in-memory, replace with database in production)
USAGE_LOGS = []


def require_admin_key(f):
    """Decorator to require admin API key for protected endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-Admin-API-Key')
        
        if not api_key:
            logger.warning(f"Admin endpoint accessed without API key: {request.endpoint}")
            return jsonify({'error': 'Admin API key required'}), 401
        
        if api_key != ADMIN_API_KEY:
            logger.warning(f"Admin endpoint accessed with invalid API key: {request.endpoint}")
            return jsonify({'error': 'Invalid admin API key'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def validate_license_format(license_key: str) -> bool:
    """
    Validate license key format: TIER-XXXX-XXXX-XXXX
    
    Args:
        license_key: License key string
        
    Returns:
        True if format is valid, False otherwise
    """
    if not license_key or not isinstance(license_key, str):
        return False
    
    parts = license_key.split('-')
    
    # Should have 4 parts
    if len(parts) != 4:
        return False
    
    # First part should be a valid tier
    valid_tiers = ['FREE', 'PRO', 'TEAM', 'ENT', 'ENTERPRISE']
    if parts[0].upper() not in valid_tiers:
        return False
    
    # Other parts should be alphanumeric
    for part in parts[1:]:
        if not part.isalnum() or len(part) < 4:
            return False
    
    return True


def generate_license_key(tier: str) -> str:
    """
    Generate a new license key with format: TIER-XXXX-XXXX-XXXX
    
    Args:
        tier: License tier (free, pro, team, enterprise)
        
    Returns:
        Generated license key string
    """
    # Map tier to prefix
    tier_prefixes = {
        'free': 'FREE',
        'pro': 'PRO',
        'team': 'TEAM',
        'enterprise': 'ENT'
    }
    
    prefix = tier_prefixes.get(tier.lower(), 'FREE')
    
    # Generate 3 random segments
    chars = string.ascii_uppercase + string.digits
    segments = []
    for _ in range(3):
        segment = ''.join(secrets.choice(chars) for _ in range(4))
        segments.append(segment)
    
    return f"{prefix}-{'-'.join(segments)}"


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON with status and version
    """
    return jsonify({
        'status': 'ok',
        'version': VERSION,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/v1/validate-license', methods=['POST'])
def validate_license():
    """
    Validate a license key.
    
    Request body:
        {
            "license_key": "PRO-XXXX-XXXX-XXXX"
        }
    
    Returns:
        200: License is valid
        400: Bad request (missing or invalid data)
        403: License expired or deactivated
        404: License not found
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("License validation called without data")
            return jsonify({'error': 'Request body required'}), 400
        
        license_key = data.get('license_key')
        
        if not license_key:
            logger.warning("License validation called without license key")
            return jsonify({'error': 'License key required'}), 400
        
        # Validate format
        if not validate_license_format(license_key):
            logger.warning(f"Invalid license format: {license_key[:10]}...")
            return jsonify({
                'valid': False,
                'error': 'Invalid license key format'
            }), 400
        
        # Look up license
        license_info = LICENSES.get(license_key)
        
        if not license_info:
            logger.info(f"License not found: {license_key[:10]}...")
            return jsonify({
                'valid': False,
                'error': 'License key not found'
            }), 404
        
        # Check if active
        if not license_info.get('active', False):
            logger.info(f"Deactivated license attempted: {license_key[:10]}...")
            return jsonify({
                'valid': False,
                'error': 'License has been deactivated'
            }), 403
        
        # Check expiration
        expires_str = license_info.get('expires')
        if expires_str:
            try:
                expires = datetime.strptime(expires_str, '%Y-%m-%d')
                if datetime.now() > expires:
                    logger.info(f"Expired license attempted: {license_key[:10]}...")
                    return jsonify({
                        'valid': False,
                        'error': 'License has expired'
                    }), 403
            except ValueError:
                logger.error(f"Invalid expiration date format: {expires_str}")
                return jsonify({
                    'valid': False,
                    'error': 'Invalid license data'
                }), 500
        
        # License is valid
        logger.info(f"License validated successfully: {license_info['tier']} - {license_info['email']}")
        
        return jsonify({
            'valid': True,
            'tier': license_info['tier'],
            'expires': license_info['expires'],
            'email': license_info.get('email'),
            'monthly_runs': license_info.get('monthly_runs', 50),
            'endpoints': license_info.get('endpoints', 10)
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating license: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/v1/track-usage', methods=['POST'])
def track_usage():
    """
    Track usage for billing and analytics.
    
    Request body:
        {
            "license_key": "PRO-XXXX-XXXX-XXXX",
            "endpoints": 10,
            "cost": 0.15,
            "tests_generated": 25
        }
    
    Returns:
        200: Usage tracked successfully
        400: Bad request
        404: License not found
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        license_key = data.get('license_key')
        endpoints = data.get('endpoints', 0)
        cost = data.get('cost', 0.0)
        tests_generated = data.get('tests_generated', 0)
        
        if not license_key:
            return jsonify({'error': 'License key required'}), 400
        
        # Verify license exists
        if license_key not in LICENSES:
            return jsonify({'error': 'License not found'}), 404
        
        # Create usage log entry
        usage_entry = {
            'timestamp': datetime.now().isoformat(),
            'license_key': license_key[:10] + '...',  # Don't log full key
            'tier': LICENSES[license_key]['tier'],
            'email': LICENSES[license_key].get('email'),
            'endpoints': endpoints,
            'cost': cost,
            'tests_generated': tests_generated
        }
        
        USAGE_LOGS.append(usage_entry)
        
        logger.info(f"Usage tracked: {LICENSES[license_key]['tier']} - {endpoints} endpoints, ${cost:.4f}")
        
        return jsonify({
            'success': True,
            'message': 'Usage tracked successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error tracking usage: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/v1/generate-license', methods=['POST'])
@require_admin_key
def generate_license():
    """
    Generate a new license key (admin only).
    
    Request headers:
        X-Admin-API-Key: <admin_api_key>
    
    Request body:
        {
            "tier": "pro",
            "email": "user@example.com",
            "duration_months": 12
        }
    
    Returns:
        201: License created successfully
        400: Bad request
        401: Unauthorized
        403: Forbidden
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        tier = data.get('tier', 'free').lower()
        email = data.get('email')
        duration_months = data.get('duration_months', 12)
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # Validate tier
        valid_tiers = ['free', 'pro', 'team', 'enterprise']
        if tier not in valid_tiers:
            return jsonify({'error': f'Invalid tier. Must be one of: {", ".join(valid_tiers)}'}), 400
        
        # Generate license key
        license_key = generate_license_key(tier)
        
        # Calculate expiration
        expires = datetime.now() + timedelta(days=duration_months * 30)
        
        # Define tier limits
        tier_limits = {
            'free': {'monthly_runs': 50, 'endpoints': 10},
            'pro': {'monthly_runs': float('inf'), 'endpoints': 100},
            'team': {'monthly_runs': float('inf'), 'endpoints': 500},
            'enterprise': {'monthly_runs': float('inf'), 'endpoints': float('inf')}
        }
        
        # Create license entry
        license_info = {
            'tier': tier,
            'email': email,
            'expires': expires.strftime('%Y-%m-%d'),
            'active': True,
            'created': datetime.now().strftime('%Y-%m-%d'),
            'monthly_runs': tier_limits[tier]['monthly_runs'],
            'endpoints': tier_limits[tier]['endpoints']
        }
        
        # Store license
        LICENSES[license_key] = license_info
        
        logger.info(f"License generated: {tier.upper()} for {email} - {license_key[:10]}...")
        
        return jsonify({
            'success': True,
            'license_key': license_key,
            'tier': tier,
            'email': email,
            'expires': license_info['expires'],
            'created': license_info['created']
        }), 201
        
    except Exception as e:
        logger.error(f"Error generating license: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/v1/deactivate-license', methods=['POST'])
@require_admin_key
def deactivate_license():
    """
    Deactivate a license key (admin only).
    
    Request headers:
        X-Admin-API-Key: <admin_api_key>
    
    Request body:
        {
            "license_key": "PRO-XXXX-XXXX-XXXX",
            "reason": "Payment failed"
        }
    
    Returns:
        200: License deactivated
        400: Bad request
        404: License not found
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        license_key = data.get('license_key')
        reason = data.get('reason', 'No reason provided')
        
        if not license_key:
            return jsonify({'error': 'License key required'}), 400
        
        if license_key not in LICENSES:
            return jsonify({'error': 'License not found'}), 404
        
        # Deactivate license
        LICENSES[license_key]['active'] = False
        LICENSES[license_key]['deactivated_at'] = datetime.now().isoformat()
        LICENSES[license_key]['deactivation_reason'] = reason
        
        logger.info(f"License deactivated: {license_key[:10]}... - Reason: {reason}")
        
        return jsonify({
            'success': True,
            'message': 'License deactivated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deactivating license: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/v1/admin/stats', methods=['GET'])
@require_admin_key
def admin_stats():
    """
    Get server statistics (admin only).
    
    Returns:
        200: Statistics
        401: Unauthorized
    """
    try:
        # Count licenses by tier
        tier_counts = {}
        active_count = 0
        
        for license_key, info in LICENSES.items():
            tier = info['tier']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            if info.get('active', False):
                active_count += 1
        
        # Calculate total usage
        total_cost = sum(log.get('cost', 0) for log in USAGE_LOGS)
        total_endpoints = sum(log.get('endpoints', 0) for log in USAGE_LOGS)
        
        return jsonify({
            'total_licenses': len(LICENSES),
            'active_licenses': active_count,
            'licenses_by_tier': tier_counts,
            'total_usage_logs': len(USAGE_LOGS),
            'total_cost_tracked': round(total_cost, 2),
            'total_endpoints_processed': total_endpoints
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # In production, use a production WSGI server like gunicorn
    # gunicorn -w 4 -b 0.0.0.0:5000 license_server:app
    
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting License Server v{VERSION} on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
