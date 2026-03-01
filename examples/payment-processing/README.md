# Payment Processing API Testing Example

This example demonstrates comprehensive testing for payment processing systems including credit cards, subscriptions, refunds, and compliance.

## Scenario Overview

A complete payment processing API with Stripe/PayPal integration, subscription management, fraud detection, PCI-DSS compliance, and regulatory reporting.

## What This Example Teaches

- **Financial Transactions**: Payments, refunds, authorizations, captures
- **Security & Compliance**: PCI-DSS, 3D Secure, fraud detection, data protection
- **Subscriptions**: Recurring billing, trial periods, prorations, cancellations
- **Integration Testing**: Third-party APIs (Stripe, PayPal, Apple Pay)
- **Regulatory Requirements**: Audit trails, reporting, GDPR, data retention

## Requirements Structure (70 Test Cases)

1. **Payment Creation & Processing (PAY-001 to PAY-020)**: Card payments, tokenization, 3DS, authorization
2. **Refunds (PAY-021 to PAY-030)**: Full/partial refunds, disputes, webhooks
3. **Subscriptions (PAY-031 to PAY-045)**: Recurring billing, trials, prorations, cancellations
4. **Compliance & Security (PAY-046 to PAY-060)**: PCI-DSS, fraud detection, audit logging
5. **Integration & Webhooks (PAY-061 to PAY-070)**: Stripe, PayPal, Apple/Google Pay, invoicing

## Key Testing Patterns

### Idempotency Testing
```python
def test_idempotency_prevents_duplicate_charges(client):
    idempotency_key = str(uuid.uuid4())
    # First request
    response1 = client.post('/payments', json=payment_data,
        headers={'Idempotency-Key': idempotency_key})
    # Duplicate request
    response2 = client.post('/payments', json=payment_data,
        headers={'Idempotency-Key': idempotency_key})
    assert response1.json()['id'] == response2.json()['id']
```

### Webhook Verification
```python
def test_webhook_signature_verification(client):
    payload = json.dumps(webhook_data)
    signature = compute_signature(payload, secret_key)
    response = client.post('/webhooks/stripe',
        data=payload,
        headers={'Stripe-Signature': signature})
    assert response.status_code == 200
```

### Subscription State Testing
```python
def test_subscription_lifecycle(client):
    # Create -> Trial -> Active -> Cancelled
    subscription = create_subscription(trial=True)
    assert subscription['status'] == 'trialing'
    # Fast-forward past trial
    advance_time(days=14)
    assert get_subscription()['status'] == 'active'
```

## Security & Compliance

✅ PCI-DSS Level 1 compliance  
✅ Never store full card numbers  
✅ 3D Secure 2 authentication  
✅ Fraud detection and prevention  
✅ Audit logging for all operations  
✅ Data encryption (transit & rest)  
✅ GDPR compliance  
✅ Regulatory reporting  

## Related Examples

- **ecommerce-auth/**: User authentication flows
- **rest-api/**: RESTful API testing patterns
- **data-pipeline/**: Processing large transaction volumes
