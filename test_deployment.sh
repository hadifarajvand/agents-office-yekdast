#!/bin/bash
# Comprehensive deployment test script
# Run after: python -m backend.main (in another terminal)

set -e

echo "=========================================="
echo "AGENTS OFFICE DEPLOYMENT TEST"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4

    echo -n "Testing $name... "

    if [ -z "$data" ]; then
        response=$(curl -s -X $method "$BASE_URL$endpoint")
    else
        response=$(curl -s -X $method "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    if echo "$response" | grep -q "error" && [ "$method" = "POST" ]; then
        echo -e "${RED}FAILED${NC}"
        echo "Response: $response"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    elif [ -z "$response" ]; then
        echo -e "${RED}NO RESPONSE${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    else
        echo -e "${GREEN}OK${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi
}

echo "Phase 1: Health & Status"
echo "=========================="
test_endpoint "Health Check" "GET" "/api/health"
echo ""

echo "Phase 2: Agent & Brain APIs"
echo "============================"
test_endpoint "List Agents" "GET" "/api/agents"
test_endpoint "List Brain Notes" "GET" "/api/brain/notes"
echo ""

echo "Phase 3: Task Creation"
echo "======================"
test_endpoint "Create Task (Marketing)" "POST" "/api/tasks" \
    '{"department":"marketing","text":"Test campaign brief","model":"sonnet","effort":"low"}'

# Extract task ID from response for further testing
TASK_ID=$(curl -s -X POST "$BASE_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"department":"marketing","text":"Test task","model":"sonnet","effort":"low"}' \
    | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 | head -1)

if [ ! -z "$TASK_ID" ]; then
    echo -e "${GREEN}Got task ID: $TASK_ID${NC}"
    test_endpoint "Get Task Status" "GET" "/api/tasks/$TASK_ID"
    test_endpoint "Approve Task" "POST" "/api/tasks/$TASK_ID/approve"
else
    echo -e "${YELLOW}Could not create task for testing${NC}"
fi

echo ""
echo "=========================================="
echo "UNIT TESTS"
echo "=========================================="
echo ""

# Run pytest
if command -v pytest &> /dev/null; then
    echo "Running pytest backend/tests/..."
    pytest backend/tests/ -v --tb=short
else
    echo -e "${YELLOW}pytest not found${NC}"
    echo "Install with: pip install pytest pytest-asyncio"
fi

echo ""
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo -e "API Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "API Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
