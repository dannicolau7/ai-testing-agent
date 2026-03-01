# Data Pipeline Testing Example - ETL System

This example demonstrates comprehensive testing for ETL (Extract, Transform, Load) data pipelines.

## Scenario Overview

A complete ETL system handling data ingestion from multiple sources, complex transformations, data quality validation, and loading to various destinations with orchestration and monitoring.

## What This Example Teaches

- **Data Ingestion**: CSV, JSON, databases, APIs, cloud storage, streaming
- **Transformations**: Filtering, joins, aggregations, window functions, custom logic
- **Data Quality**: Validation rules, profiling, anomaly detection, reconciliation
- **Loading**: Database writes, upserts, slowly changing dimensions, exports
- **Orchestration**: DAG execution, scheduling, retries, checkpointing, monitoring

## Requirements Structure (75 Test Cases)

1. **Data Ingestion (ETL-001 to ETL-015)**: File formats, databases, APIs, streams
2. **Data Transformation (ETL-016 to ETL-030)**: Filters, joins, aggregations, calculations
3. **Data Quality (ETL-031 to ETL-045)**: Validation, profiling, anomaly detection, lineage
4. **Data Loading (ETL-046 to ETL-060)**: Bulk loads, upserts, SCD, exports
5. **Pipeline Orchestration (ETL-061 to ETL-075)**: DAGs, scheduling, monitoring, CI/CD

## Key Testing Patterns

### Large File Handling
```python
def test_large_file_streaming(pipeline):
    # 1GB+ file should stream without loading entirely
    job = pipeline.ingest('large_file.csv', streaming=True)
    assert job.memory_usage < 500_000_000  # <500MB
```

### Data Quality Validation
```python
def test_data_quality_validation(pipeline, dataset):
    report = pipeline.validate_quality(dataset)
    assert report.completeness_score > 95
    assert report.uniqueness_violations == 0
```

### Transformation Testing
```python
def test_transformation_pipeline(etl):
    result = (etl
        .filter(lambda row: row['amount'] > 100)
        .group_by('category')
        .aggregate({'amount': 'sum'})
        .execute())
    assert result.row_count == expected_count
```

## Best Practices Demonstrated

✅ Streaming for large datasets  
✅ Schema validation  
✅ Data quality checks  
✅ Error handling and recovery  
✅ Idempotent operations  
✅ Performance optimization  
✅ Monitoring and alerting  
✅ Data lineage tracking  

## Related Examples

- **rest-api/**: API ingestion patterns
- **payment-processing/**: Financial data validation
- **ml-model-api/**: ML feature engineering
