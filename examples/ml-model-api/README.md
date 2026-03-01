# ML Model API Testing Example

This example demonstrates comprehensive testing for machine learning model APIs including predictions, model management, performance, and security.

## Scenario Overview

A production ML API serving predictions with features like model versioning, A/B testing, explainability, monitoring, and performance optimization.

## What This Example Teaches

- **ML Predictions**: Single, batch, real-time, with various input types
- **Model Management**: Versioning, deployment, monitoring, retraining
- **Data Validation**: Input validation, preprocessing, feature engineering
- **Performance**: Low latency, high throughput, GPU acceleration, caching
- **Security**: Authentication, rate limiting, adversarial detection, compliance

## Requirements Structure (75 Test Cases)

1. **Model Prediction (ML-001 to ML-020)**: Single/batch, validation, preprocessing, explainability
2. **Model Management (ML-021 to ML-035)**: Versioning, A/B testing, monitoring, drift detection
3. **Data Validation (ML-036 to ML-045)**: Schema, ranges, normalization, outliers
4. **Performance & Scalability (ML-046 to ML-060)**: Latency, throughput, GPU, auto-scaling
5. **Security & Compliance (ML-061 to ML-075)**: Auth, audit trails, GDPR, bias monitoring

## Key Testing Patterns

### Latency Testing
```python
def test_prediction_latency(client, sample_input):
    import time
    start = time.time()
    response = client.post('/predict', json=sample_input)
    latency = time.time() - start
    
    assert response.status_code == 200
    assert latency < 0.1  # <100ms
```

### Feature Drift Detection
```python
def test_feature_drift_detection(client, drift_data):
    response = client.post('/predict', json=drift_data)
    
    assert response.status_code == 200
    assert 'drift_warning' in response.json()
    assert response.json()['confidence'] < 0.5  # Low confidence on drift
```

### Model Explainability
```python
def test_prediction_explanation(client):
    response = client.post('/predict', json={
        'features': [1.0, 2.0, 3.0],
        'explain': True
    })
    
    assert 'prediction' in response.json()
    assert 'feature_importance' in response.json()
    assert len(response.json()['feature_importance']) == 3
```

## Best Practices Demonstrated

✅ Input validation and preprocessing  
✅ Low latency predictions (<100ms)  
✅ Model versioning and A/B testing  
✅ Monitoring and drift detection  
✅ Explainability (SHAP, LIME)  
✅ Security and rate limiting  
✅ Performance optimization (GPU, caching)  
✅ Fairness and bias monitoring  

## Related Examples

- **rest-api/**: API design patterns
- **data-pipeline/**: Feature engineering pipelines
- **payment-processing/**: Fraud detection use case
