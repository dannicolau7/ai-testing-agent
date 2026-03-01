# RESTful API Testing Example - Task Management API

This example demonstrates comprehensive testing of a RESTful API following REST principles and best practices.

## Scenario Overview

A task management API with full CRUD operations, filtering, sorting, relationships, and advanced features like caching, rate limiting, and webhooks.

## What This Example Teaches

- **REST Principles**: Proper HTTP methods, status codes, and resource naming
- **API Design Patterns**: Pagination, filtering, sorting, bulk operations
- **Performance**: Caching strategies, response optimization
- **Standards Compliance**: CORS, ETags, compression, versioning
- **Advanced Features**: Real-time updates, batch requests, GraphQL alternative

## Requirements Structure (85 Test Cases)

1. **CRUD Operations (API-001 to API-015)**: Basic create, read, update, delete
2. **Advanced Filtering & Sorting (API-016 to API-025)**: Complex queries, statistics, exports
3. **Relationships & Nested Resources (API-026 to API-035)**: Comments, attachments, history
4. **API Conventions (API-036 to API-045)**: Headers, timestamps, versioning, HATEOAS
5. **Error Handling (API-046 to API-055)**: Consistent error format, all HTTP error codes
6. **Authentication & Authorization (API-056 to API-065)**: JWT, OAuth2, scopes, API keys
7. **Performance & Caching (API-066 to API-075)**: Response times, caching strategies
8. **Edge Cases (API-076 to API-085)**: Unicode, timezones, concurrency, health checks

## How to Use

```bash
# Generate tests
ai-testing-agent generate examples/rest-api/requirements.txt -o tests/api/

# Run tests
pytest tests/api/ -v --cov
```

## Key Testing Patterns

### Testing HTTP Methods
```python
def test_create_task(client, auth_headers):
    response = client.post('/api/tasks', 
        json={'title': 'Test Task', 'description': 'Test'},
        headers=auth_headers)
    assert response.status_code == 201
    assert 'id' in response.json()
```

### Testing Pagination
```python
def test_pagination(client, auth_headers):
    response = client.get('/api/tasks?page=2&limit=10', headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert 'page' in data
    assert len(data['tasks']) <= 10
```

### Testing Filters
```python
def test_filter_by_status(client, auth_headers):
    response = client.get('/api/tasks?status=completed', headers=auth_headers)
    assert response.status_code == 200
    for task in response.json()['tasks']:
        assert task['status'] == 'completed'
```

## Best Practices Demonstrated

✅ RESTful URL design  
✅ Proper HTTP status codes  
✅ Request/response validation  
✅ Error handling consistency  
✅ Authentication & authorization  
✅ Rate limiting  
✅ Caching strategies  
✅ API versioning  
✅ Documentation (OpenAPI/Swagger)  

## Related Examples

- **ecommerce-auth/**: Authentication patterns
- **payment-processing/**: Financial transaction testing
- **ml-model-api/**: ML service API testing
