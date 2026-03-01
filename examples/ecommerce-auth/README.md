# E-Commerce Authentication System Example

This example demonstrates how to use the AI Testing Agent to generate comprehensive test suites for a complete authentication system commonly found in e-commerce applications.

## Scenario Overview

You're building an e-commerce platform that requires a robust, secure authentication system with:
- User registration with email verification
- Secure login with session management
- Two-factor authentication (2FA)
- Password reset flows
- Account security features
- Protection against common attacks (SQL injection, XSS, CSRF, brute force)

## What This Example Teaches

- **Security Testing**: How to test authentication security measures
- **Complex Workflows**: Multi-step processes like email verification and 2FA
- **Edge Cases**: Handling failures, rate limiting, concurrent operations
- **Regulatory Compliance**: GDPR, data privacy, PCI-DSS considerations
- **User Experience**: Balance between security and usability

## Requirements File Structure

The `requirements.txt` file contains 70 detailed test scenarios organized into categories:

1. **User Registration (AUTH-001 to AUTH-010)**: Account creation, validation, email verification
2. **Login (AUTH-011 to AUTH-020)**: Authentication, session management, account lockout
3. **Two-Factor Authentication (AUTH-021 to AUTH-030)**: TOTP, SMS, backup codes, recovery
4. **Password Reset (AUTH-031 to AUTH-040)**: Secure password recovery flows
5. **Session Management (AUTH-041 to AUTH-050)**: Multi-device sessions, suspicious activity detection
6. **Account Security (AUTH-051 to AUTH-060)**: Audit logs, privacy settings, account deletion
7. **Edge Cases (AUTH-061 to AUTH-070)**: Error handling, race conditions, internationalization

## How to Use This Example

### Step 1: Generate Tests

Run the AI Testing Agent with the requirements file:

```bash
python ai_testing_agent.py --requirements examples/ecommerce-auth/requirements.txt --output tests/auth/
```

Or using the CLI:

```bash
ai-testing-agent generate examples/ecommerce-auth/requirements.txt -o tests/auth/
```

### Step 2: Review Generated Tests

The AI will generate test files organized by category:
- `test_registration.py` - All registration-related tests
- `test_login.py` - Login and session tests
- `test_2fa.py` - Two-factor authentication tests
- `test_password_reset.py` - Password reset flows
- `test_session_management.py` - Session operations
- `test_account_security.py` - Security features
- `test_edge_cases.py` - Error handling and edge cases

### Step 3: Customize for Your API

Update the generated tests to match your API structure:
- Modify base URLs and endpoints
- Adjust request/response formats
- Add authentication headers
- Configure test data

### Step 4: Run Tests

```bash
pytest tests/auth/ -v
```

## Expected Test Output

The `expected_output/` directory contains examples of what the generated tests should look like. These demonstrate:

- **Proper test structure**: Setup, execution, assertion, teardown
- **Security best practices**: Secure token handling, no hardcoded secrets
- **Comprehensive assertions**: Status codes, response structure, side effects
- **Test data management**: Fixtures, factories, cleanup
- **Error handling**: Graceful failure messages

## Key Testing Patterns Demonstrated

### 1. Security Testing Pattern

```python
def test_sql_injection_in_registration(client):
    """AUTH-008: Verify SQL injection is prevented"""
    malicious_inputs = [
        "user@example.com' OR '1'='1",
        "user@example.com'; DROP TABLE users; --",
    ]
    for payload in malicious_inputs:
        response = client.post('/register', json={'email': payload})
        assert response.status_code in [400, 422]
        # Verify no data corruption
```

### 2. Rate Limiting Pattern

```python
def test_registration_rate_limiting(client):
    """AUTH-007: Verify rate limiting prevents abuse"""
    for i in range(3):
        response = client.post('/register', json={'email': f'user{i}@example.com'})
        assert response.status_code in [200, 201]
    
    # 4th attempt should fail
    response = client.post('/register', json={'email': 'user4@example.com'})
    assert response.status_code == 429
    assert 'rate limit' in response.json()['message'].lower()
```

### 3. Time-Based Testing Pattern

```python
def test_email_verification_expiration(client, freezer):
    """AUTH-005: Verify verification links expire"""
    token = generate_verification_token()
    
    # Fast-forward 25 hours
    freezer.move_to('25 hours later')
    
    response = client.get(f'/verify-email/{token}')
    assert response.status_code == 410  # Gone
    assert 'expired' in response.json()['message'].lower()
```

### 4. State Machine Testing Pattern

```python
def test_account_lockout_flow(client):
    """AUTH-014 & AUTH-015: Verify account lockout and unlock"""
    # Make 5 failed login attempts
    for i in range(5):
        response = client.post('/login', json={
            'email': 'user@example.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
    
    # 6th attempt should show locked status
    response = client.post('/login', json={
        'email': 'user@example.com',
        'password': 'correctpassword'
    })
    assert response.status_code == 423  # Locked
    
    # Verify unlock email sent
    assert len(mail_outbox) == 1
    unlock_token = extract_token_from_email(mail_outbox[0])
    
    # Unlock account
    response = client.get(f'/unlock-account/{unlock_token}')
    assert response.status_code == 200
    
    # Verify can login again
    response = client.post('/login', json={
        'email': 'user@example.com',
        'password': 'correctpassword'
    })
    assert response.status_code == 200
```

## Real-World Considerations

### 1. Test Data Management

- Use factories (e.g., `factory_boy`) for test data generation
- Clean up test data after each test
- Use unique identifiers to avoid collisions
- Consider database transactions for isolation

### 2. External Dependencies

- Mock email service in tests (e.g., `pytest-mock-email`)
- Mock SMS service for 2FA tests
- Use test Redis instance for session storage
- Freeze time for expiration testing (`freezegun`)

### 3. CI/CD Integration

- Run security tests on every commit
- Separate fast tests from slow integration tests
- Use test markers: `@pytest.mark.security`, `@pytest.mark.slow`
- Generate coverage reports

### 4. Performance Considerations

- Use database fixtures efficiently (session-scoped where possible)
- Parallelize independent tests
- Mock expensive operations (email, SMS)
- Consider load testing for rate limiting

## Security Best Practices Tested

✅ Input validation and sanitization  
✅ SQL injection prevention  
✅ XSS protection  
✅ CSRF protection  
✅ Rate limiting and DoS prevention  
✅ Secure session management  
✅ Password strength requirements  
✅ Account lockout mechanisms  
✅ Secure password reset flows  
✅ 2FA implementation  
✅ Session fixation prevention  
✅ Audit logging  

## Common Pitfalls Avoided

❌ Revealing whether email exists (AUTH-012, AUTH-013)  
❌ Weak password requirements (AUTH-003)  
❌ No rate limiting (AUTH-007, AUTH-020)  
❌ Reusable tokens (AUTH-006, AUTH-033)  
❌ Session hijacking vulnerabilities (AUTH-047, AUTH-048)  
❌ Missing 2FA recovery options (AUTH-026)  
❌ No audit trail (AUTH-052)  

## Next Steps

1. **Run the generator**: Create tests from the requirements
2. **Review and customize**: Adapt tests to your API structure
3. **Add integration tests**: Test with real database and services
4. **Set up CI/CD**: Automate test execution
5. **Monitor coverage**: Aim for >90% coverage on auth code
6. **Security audit**: Have tests reviewed by security team

## Related Examples

- **rest-api/**: See how to test RESTful API endpoints
- **payment-processing/**: Learn about testing financial transactions
- **ml-model-api/**: Understand API testing for ML services

## Additional Resources

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [NIST Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
