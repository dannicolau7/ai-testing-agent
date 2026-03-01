# License Server API

**⚠️ IMPORTANT: This is a PRIVATE server. DO NOT open source!**

Production Flask API server for validating and managing license keys for the AI Testing Agent.

## Features

- ✅ License key validation
- ✅ Usage tracking for billing
- ✅ License generation (admin only)
- ✅ Security with API key authentication
- ✅ Comprehensive logging
- ✅ CORS support
- ✅ Health check endpoint
- ✅ Admin statistics dashboard

## Quick Start

### 1. Install Dependencies

```bash
pip install -r license_server_requirements.txt
```

### 2. Configure Environment

Create a `.env` file (see `.env.example`):

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run the Server

**Development:**
```bash
python license_server.py
```

**Production (with Gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 license_server:app
```

**With Docker:**
```bash
docker build -t license-server .
docker run -p 5000:5000 --env-file .env license-server
```

## API Endpoints

### Public Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-02-17T12:00:00"
}
```

#### Validate License
```http
POST /v1/validate-license
Content-Type: application/json

{
  "license_key": "PRO-XXXX-XXXX-XXXX"
}
```

**Success Response (200):**
```json
{
  "valid": true,
  "tier": "pro",
  "expires": "2027-12-31",
  "email": "user@example.com",
  "monthly_runs": "Infinity",
  "endpoints": 100
}
```

**Error Response (404):**
```json
{
  "valid": false,
  "error": "License key not found"
}
```

#### Track Usage
```http
POST /v1/track-usage
Content-Type: application/json

{
  "license_key": "PRO-XXXX-XXXX-XXXX",
  "endpoints": 10,
  "cost": 0.15,
  "tests_generated": 25
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Usage tracked successfully"
}
```

### Admin Endpoints

All admin endpoints require the `X-Admin-API-Key` header.

#### Generate License
```http
POST /v1/generate-license
X-Admin-API-Key: your-admin-key
Content-Type: application/json

{
  "tier": "pro",
  "email": "customer@example.com",
  "duration_months": 12
}
```

**Response (201):**
```json
{
  "success": true,
  "license_key": "PRO-ABCD-EFGH-IJKL",
  "tier": "pro",
  "email": "customer@example.com",
  "expires": "2027-02-17",
  "created": "2026-02-17"
}
```

#### Deactivate License
```http
POST /v1/deactivate-license
X-Admin-API-Key: your-admin-key
Content-Type: application/json

{
  "license_key": "PRO-XXXX-XXXX-XXXX",
  "reason": "Payment failed"
}
```

#### Get Statistics
```http
GET /v1/admin/stats
X-Admin-API-Key: your-admin-key
```

**Response:**
```json
{
  "total_licenses": 15,
  "active_licenses": 12,
  "licenses_by_tier": {
    "free": 5,
    "pro": 8,
    "team": 2
  },
  "total_usage_logs": 156,
  "total_cost_tracked": 45.67,
  "total_endpoints_processed": 1234
}
```

## License Tiers

| Tier | Monthly Runs | Endpoints | Price |
|------|-------------|-----------|-------|
| Free | 50 | 10 | $0 |
| Pro | Unlimited | 100 | $29/mo |
| Team | Unlimited | 500 | $99/mo |
| Enterprise | Unlimited | Unlimited | Custom |

## Security

### Production Checklist

- [ ] Change `ADMIN_API_KEY` in environment variables
- [ ] Use HTTPS in production (configure reverse proxy)
- [ ] Enable rate limiting
- [ ] Set up database instead of in-memory storage
- [ ] Configure firewall rules
- [ ] Enable monitoring and alerts
- [ ] Set up backup system
- [ ] Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Enable audit logging
- [ ] Implement IP whitelisting for admin endpoints

### Environment Variables

Required:
- `ADMIN_API_KEY`: Admin API key for protected endpoints
- `PORT`: Server port (default: 5000)
- `DEBUG`: Debug mode (default: False)

Optional:
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis URL for caching
- `LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR)

## Testing

### Test License Keys

The server comes with pre-configured test keys:

```
FREE-DEMO-TEST-KEY1  (Free tier)
PRO-DEMO-TEST-KEY1   (Pro tier)
TEAM-DEMO-TEST-KEY1  (Team tier)
ENT-DEMO-TEST-KEY1   (Enterprise tier)
```

### Test with cURL

**Validate License:**
```bash
curl -X POST http://localhost:5000/v1/validate-license \
  -H "Content-Type: application/json" \
  -d '{"license_key":"PRO-DEMO-TEST-KEY1"}'
```

**Generate License (Admin):**
```bash
curl -X POST http://localhost:5000/v1/generate-license \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: admin-secret-key-change-in-production" \
  -d '{"tier":"pro","email":"test@example.com","duration_months":12}'
```

**Get Stats (Admin):**
```bash
curl -X GET http://localhost:5000/v1/admin/stats \
  -H "X-Admin-API-Key: admin-secret-key-change-in-production"
```

## Deployment

### Production with Gunicorn

```bash
gunicorn -w 4 \
  -b 0.0.0.0:5000 \
  --access-logfile /var/log/gunicorn/access.log \
  --error-logfile /var/log/gunicorn/error.log \
  --log-level info \
  license_server:app
```

### systemd Service

Create `/etc/systemd/system/license-server.service`:

```ini
[Unit]
Description=License Server API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/license-server
Environment="PATH=/opt/license-server/venv/bin"
EnvironmentFile=/opt/license-server/.env
ExecStart=/opt/license-server/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 license_server:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable license-server
sudo systemctl start license-server
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring

### Logs

Logs are written to:
- `license_server.log` (file)
- stdout (console)

### Health Check

Use `/health` endpoint for monitoring:

```bash
curl http://localhost:5000/health
```

### Metrics (Optional)

Add Prometheus metrics:

```python
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

## Database Migration

To migrate from in-memory to PostgreSQL:

1. Install psycopg2: `pip install psycopg2-binary`
2. Create database schema
3. Update LICENSES dict to use database queries
4. Implement connection pooling

Example schema:

```sql
CREATE TABLE licenses (
    license_key VARCHAR(50) PRIMARY KEY,
    tier VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL,
    expires DATE NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE usage_logs (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(50) REFERENCES licenses(license_key),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    endpoints INTEGER,
    cost DECIMAL(10,4),
    tests_generated INTEGER
);
```

## Support

For issues or questions:
- Internal documentation: [link]
- Contact: admin@yourdomain.com

## License

**PROPRIETARY - DO NOT DISTRIBUTE**

This is proprietary software. All rights reserved.
