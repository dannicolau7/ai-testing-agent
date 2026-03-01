# Dockerfile for AI Testing Agent
# Production-ready containerization

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ai_testing_agent.py .
COPY cli.py .

# Copy example requirements (optional)
COPY example_requirements.txt .

# Create output directory
RUN mkdir -p /app/test_output

# Create usage tracking directory
RUN mkdir -p /root/.ai-testing-agent

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set labels
LABEL maintainer="AI Testing Agent Team <support@yourdomain.com>" \
      version="1.0.0" \
      description="Autonomous test generation using Claude AI"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import ai_testing_agent; print('OK')" || exit 1

# Default command shows help
CMD ["python", "cli.py", "--help"]
