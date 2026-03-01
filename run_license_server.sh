#!/bin/bash
"""
Start the License Server for development/testing.

Usage:
    ./run_license_server.sh
    
To stop:
    pkill -f license_server.py
    # or press Ctrl+C
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   License Server - Starting...${NC}"
echo -e "${BLUE}================================================================${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is not installed${NC}"
    exit 1
fi

# Check if license_server.py exists
if [ ! -f "license_server.py" ]; then
    echo -e "${RED}❌ Error: license_server.py not found${NC}"
    echo -e "${YELLOW}   Make sure you're in the correct directory${NC}"
    exit 1
fi

# Check if Flask is installed
if ! python3 -c "import flask" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Flask not installed. Installing dependencies...${NC}"
    pip install -r license_server_requirements.txt
fi

# Set environment variables for development
export ADMIN_API_KEY="admin-secret-key-change-in-production"
export PORT=5000
export DEBUG=True
export LOG_LEVEL=INFO

echo -e "${GREEN}✅ Environment configured:${NC}"
echo -e "   Port: ${PORT}"
echo -e "   Debug: ${DEBUG}"
echo -e "   Admin API Key: ${ADMIN_API_KEY:0:20}..."

# Check if port is already in use
if lsof -Pi :${PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port ${PORT} is already in use${NC}"
    echo -e "${YELLOW}   Stopping existing process...${NC}"
    pkill -f "license_server.py" 2>/dev/null
    sleep 2
fi

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}🚀 Starting License Server...${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""
echo -e "${GREEN}Server URL:${NC}       http://localhost:${PORT}"
echo -e "${GREEN}Health Check:${NC}     http://localhost:${PORT}/health"
echo -e "${GREEN}API Docs:${NC}         See LICENSE_SERVER_README.md"
echo ""
echo -e "${YELLOW}📝 Test Commands:${NC}"
echo -e "   # Health check"
echo -e "   curl http://localhost:${PORT}/health"
echo ""
echo -e "   # Validate license"
echo -e "   curl -X POST http://localhost:${PORT}/v1/validate-license \\"
echo -e "     -H 'Content-Type: application/json' \\"
echo -e "     -d '{\"license_key\":\"PRO-DEMO-TEST-KEY1\"}'"
echo ""
echo -e "   # Run tests"
echo -e "   pytest test_license_server.py -v"
echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Start the server
python3 license_server.py
