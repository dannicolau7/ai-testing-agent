# Docker Deployment Guide

Guide for running AI Testing Agent with Docker.

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Prerequisites](#-prerequisites)
- [Configuration](#-configuration)
- [Development Setup](#-development-setup)
- [Production Deployment](#-production-deployment)
- [Common Commands](#-common-commands)
- [Troubleshooting](#-troubleshooting)

---

## Quick Start

```bash
# Build the image
docker build -t ai-testing-agent .

# Run with example requirements
docker run --rm \
  -v $(pwd)/test_output:/app/test_output \
  ai-testing-agent \
  python cli.py run example_requirements.txt

# View generated tests
ls -la test_output/
```

Or with docker-compose:

```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

docker-compose up -d
docker-compose ps
docker-compose logs -f
```

---

## 📦 Prerequisites

### Required

- **Docker** 20.10 or higher
- **Docker Compose** 2.0 or higher

### Optional

- **Anthropic API Key** - For real Claude AI generation (mock is used otherwise)

### Installation

**macOS:**
```bash
brew install docker docker-compose
```

**Linux:**
```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**Windows:**
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop)

---

## ⚙️ Configuration

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example file
cp .env.example .env
```

**Edit `.env`:**
```env
# AI Testing Agent Configuration
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

### 2. Volumes

The Docker setup creates persistent volumes for:

- **test_output/** - Generated test files
- **ai-agent-data** - Usage tracking data

### 3. Networks

Services communicate through:
- **ai-agent-network** (production)
- **ai-agent-dev-network** (development)

---

## 🛠️ Development Setup

### Start Development Environment

```bash
# Start with live code reload
docker-compose -f docker-compose.dev.yml up

# Or in detached mode
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### Run Commands Interactively

```bash
# Open shell in agent container
docker-compose -f docker-compose.dev.yml exec ai-testing-agent bash

# Inside container:
python cli.py usage
python cli.py run requirements.txt
```

### Run Tests

```bash
# Run all tests
docker-compose -f docker-compose.dev.yml exec ai-testing-agent pytest tests/ -v

# Run specific test
docker-compose -f docker-compose.dev.yml exec ai-testing-agent pytest tests/test_agent.py -v

# With coverage
docker-compose -f docker-compose.dev.yml exec ai-testing-agent pytest tests/ --cov
```

### Code Formatting

```bash
# Format code
docker-compose -f docker-compose.dev.yml exec ai-testing-agent black .

# Check linting
docker-compose -f docker-compose.dev.yml exec ai-testing-agent flake8 .
```

---

## 🚀 Production Deployment

### Build Images

```bash
# Build all images
docker-compose build

# Build specific service
docker-compose build ai-testing-agent

# Build with no cache
docker-compose build --no-cache
```

### Start Services

```bash
# Start all services in background
docker-compose up -d

# View status
docker-compose ps
```

### Verify Deployment

```bash
# Check health status
docker-compose ps

# View agent logs
docker-compose logs ai-testing-agent

# Follow logs
docker-compose logs -f
```

### Scale Services (if needed)

```bash
# Run multiple agent instances
docker-compose up -d --scale ai-testing-agent=3

# Check instances
docker-compose ps
```

---

## 💻 Common Commands

### Image Management

```bash
# List images
docker images | grep ai-testing

# Remove images
docker rmi ai-testing-agent:latest

# Prune unused images
docker image prune -a
```

### Container Management

```bash
# List containers
docker-compose ps

# Start services
docker-compose start

# Stop services
docker-compose stop

# Restart services
docker-compose restart

# Remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v
```

### Logs and Debugging

```bash
# View logs
docker-compose logs

# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Container logs
docker logs ai-testing-agent
```

### Running the Agent

```bash
# Run with example requirements
docker-compose run --rm ai-testing-agent \
  python cli.py run example_requirements.txt

# Run with your requirements
docker-compose run --rm \
  -v $(pwd)/my_requirements.txt:/app/requirements.txt \
  ai-testing-agent \
  python cli.py run /app/requirements.txt

# Check usage
docker-compose run --rm ai-testing-agent python cli.py usage

# Generate report
docker-compose run --rm ai-testing-agent \
  python cli.py report requirements.txt --format html
```

### Volume Management

```bash
# List volumes
docker volume ls | grep ai-testing

# Inspect volume
docker volume inspect ai-agent-data

# Remove volumes
docker volume rm ai-agent-data

# Backup volume data
docker run --rm \
  -v ai-agent-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/ai-agent-backup.tar.gz -C /data .

# Restore volume data
docker run --rm \
  -v ai-agent-data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/ai-agent-backup.tar.gz -C /data
```

---

## 🔧 Advanced Configuration

### Custom Dockerfile

Create `Dockerfile.custom`:

```dockerfile
FROM ai-testing-agent:latest

# Add custom dependencies
RUN pip install your-package

# Add custom scripts
COPY custom_script.py /app/

# Custom entrypoint
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
```

Build:
```bash
docker build -f Dockerfile.custom -t ai-testing-agent:custom .
```

### Environment-Specific Compose Files

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Health Checks

```bash
# Check agent health
docker inspect --format='{{.State.Health.Status}}' ai-testing-agent
```

---

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs ai-testing-agent

# Inspect container
docker inspect ai-testing-agent

# Check resource usage
docker stats

# Verify environment variables
docker-compose config
```

### Permission Issues

```bash
# Fix volume permissions
docker-compose run --rm --user root ai-testing-agent \
  chown -R $(id -u):$(id -g) /app/test_output

# Or on host
sudo chown -R $USER:$USER test_output/
```

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "5001:5000"
```

### Out of Memory

```bash
# Increase Docker memory limit
# Docker Desktop → Preferences → Resources → Memory

# Or limit container memory
docker-compose run --rm -m 512m ai-testing-agent python cli.py run requirements.txt
```

### Network Issues

```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d

# Check network
docker network inspect ai-agent-network

# Test connectivity between containers
docker-compose exec ai-testing-agent ping ai-testing-agent
```

### Clean Start

```bash
# Stop everything
docker-compose down -v

# Remove all images
docker rmi $(docker images 'ai-testing*' -q)

# Prune system
docker system prune -a

# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 Monitoring

### Container Stats

```bash
# Real-time stats
docker stats

# Specific container
docker stats ai-testing-agent

# Custom format
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### Logs Aggregation

```bash
# Export logs
docker-compose logs > ai-testing-logs.txt

# Send to logging service (example)
docker-compose logs | logstash -f logstash.conf
```

---

## 🔒 Security Best Practices

1. **Never commit `.env` files**
2. **Change default API keys**
3. **Use secrets for production**
4. **Run containers as non-root** (where possible)
5. **Keep images updated**
6. **Scan for vulnerabilities**

```bash
# Scan image for vulnerabilities
docker scan ai-testing-agent:latest
```

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [AI Testing Agent Documentation](README.md)

---

## 💬 Get Help

**Issues with Docker setup?**
- [Open a GitHub Issue](https://github.com/dannicolau7/ai-testing-agent/issues)

---

<div align="center">

**Made with ❤️ and 🐳**

[⬅️ Back to README](README.md)

</div>
