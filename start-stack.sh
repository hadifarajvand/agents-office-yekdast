#!/bin/bash

# Agent Office - Complete Stack Startup Script
# Launches backend and frontend with proper logging

set -e

PROJECT_DIR="D:/Projects/agent-office-yekdast"
BACKEND_DIR="$PROJECT_DIR"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Agent Office - Complete Stack Startup              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup on exit
cleanup() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║              Stopping all services...                      ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  pkill -f "python.*backend.main" 2>/dev/null || true
  pkill -f "npm start" 2>/dev/null || true
  sleep 1
  echo "✅ Services stopped"
}

trap cleanup EXIT

# Check if ports are available
check_port() {
  local port=$1
  if netstat -tuln 2>/dev/null | grep -q ":$port "; then
    echo -e "${YELLOW}⚠️  Port $port may already be in use${NC}"
  fi
}

echo -e "${BLUE}1. Checking ports...${NC}"
check_port 8000
check_port 4520
echo "✅ Port check complete"
echo ""

# Start Backend
echo -e "${BLUE}2. Starting Backend...${NC}"
cd "$BACKEND_DIR"
export USE_PYTHON_BACKEND=true
export PYTHON_BACKEND_URL=http://localhost:8000
export ANTHROPIC_BASE_URL=http://127.0.0.1:20128/v1
export ANTHROPIC_AUTH_TOKEN=sk-d88b5ef429e08f78-wah1ts-45f9884f

python -m backend.main > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   Logs: /tmp/backend.log"
sleep 3

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null; then
  echo -e "${GREEN}✅ Backend is running${NC}"
else
  echo -e "${YELLOW}⚠️  Backend failed to start. Check /tmp/backend.log${NC}"
  cat /tmp/backend.log
  exit 1
fi

# Wait for backend to be ready
echo -e "${BLUE}3. Waiting for backend to be ready...${NC}"
for i in {1..30}; do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${YELLOW}⚠️  Backend not responding. Check logs at /tmp/backend.log${NC}"
  fi
  echo "   Attempt $i/30..."
  sleep 1
done
echo ""

# Start Frontend
echo -e "${BLUE}4. Starting Frontend...${NC}"
cd "$FRONTEND_DIR"
export USE_PYTHON_BACKEND=true
export PYTHON_BACKEND_URL=http://localhost:8000

npm start > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo "   Logs: /tmp/frontend.log"
sleep 4

# Check if frontend is running
if ps -p $FRONTEND_PID > /dev/null; then
  echo -e "${GREEN}✅ Frontend is running${NC}"
else
  echo -e "${YELLOW}⚠️  Frontend failed to start. Check /tmp/frontend.log${NC}"
  cat /tmp/frontend.log
  exit 1
fi

# Wait for frontend to be ready
echo -e "${BLUE}5. Waiting for frontend to be ready...${NC}"
for i in {1..30}; do
  if curl -s http://localhost:4520 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is ready${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${YELLOW}⚠️  Frontend not responding. Check logs at /tmp/frontend.log${NC}"
  fi
  echo "   Attempt $i/30..."
  sleep 1
done
echo ""

# Display endpoints
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Agent Office Stack Ready! 🚀                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✅ ALL SERVICES RUNNING${NC}"
echo ""
echo "📍 Access Points:"
echo -e "   Frontend (UI):      ${BLUE}http://localhost:4520${NC}"
echo -e "   Backend (API):      ${BLUE}http://localhost:8000${NC}"
echo -e "   API Docs:           ${BLUE}http://localhost:8000/docs${NC}"
echo -e "   Health Check:       ${BLUE}http://localhost:8000/api/health${NC}"
echo -e "   Real-time Events:   ${BLUE}http://localhost:8000/api/events${NC}"
echo -e "   Metrics:            ${BLUE}http://localhost:8000/api/metrics${NC}"
echo ""
echo "📋 Logs:"
echo "   Backend:  tail -f /tmp/backend.log"
echo "   Frontend: tail -f /tmp/frontend.log"
echo ""
echo "🧪 Test Steps:"
echo "   1. Open http://localhost:4520 in browser"
echo "   2. Create a task using the UI"
echo "   3. Watch it appear in real-time (no 6-second delay!)"
echo "   4. Check backend health: curl http://localhost:8000/api/metrics | jq ."
echo ""
echo "⏹️  To stop: Press Ctrl+C"
echo ""

# Keep script running
wait $BACKEND_PID $FRONTEND_PID
