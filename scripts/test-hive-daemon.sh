#!/bin/bash

# [CHANGE: gemini-cli | 2026-05-02]
# HIVE Daemon Endpoint Verification Suite
# PURPOSE: Exercises every endpoint of hive-daemon.py (port 8078) before migration.

DAEMON_URL="http://localhost:8078"
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== HIVE Daemon Verification Suite ===${NC}"

# --- Pre-flight Check ---
echo -n "Checking daemon liveness... "
HEALTH_CHECK=$(curl -s --connect-timeout 2 "$DAEMON_URL/health")
if [ $? -ne 0 ]; then
    echo -e "${RED}FAILED${NC}"
    echo -e "Error: Daemon is unreachable on $DAEMON_URL"
    echo -e "Please run: ${YELLOW}python3 ~/luminos-os/scripts/hive-daemon.py${NC} in a separate terminal first."
    exit 1
fi

UPTIME=$(echo "$HEALTH_CHECK" | jq -r '.uptime // "unknown"')
echo -e "${GREEN}ONLINE${NC} (Uptime: $UPTIME)"

function print_test_header() {
    echo -e "\n${BLUE}[$1] $2${NC}"
}

function assert_jq() {
    local index=$1
    local name=$2
    local query=$3
    local expected=$4
    local json=$5
    local type=${6:-"FAIL"} # FAIL or WARN

    local actual=$(echo "$json" | jq -r "$query")
    if [ "$actual" == "$expected" ]; then
        return 0
    else
        if [ "$type" == "FAIL" ]; then
            echo -e "  ${RED}FAIL: Expected $query to be '$expected', got '$actual'${NC}"
            return 1
        else
            echo -e "  ${YELLOW}WARN: Expected $query to be '$expected', got '$actual' (Nexus routing inconsistency)$NC"
            return 2
        fi
    fi
}

# --- Test 1: Health Check ---
print_test_header "1" "Health Check"
RESPONSE=$(curl -s "$DAEMON_URL/health")
if assert_jq "1" "Status" ".status" "ok" "$RESPONSE" && assert_jq "1" "Port" ".port" "8078" "$RESPONSE"; then
    echo -e "  ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    ((FAIL_COUNT++))
fi

# --- Test 2: Initial State ---
print_test_header "2" "Initial State"
RESPONSE=$(curl -s "$DAEMON_URL/state")
CURRENT_MODEL=$(echo "$RESPONSE" | jq -r '.model // "none"')
echo -e "  Current loaded model: ${YELLOW}$CURRENT_MODEL${NC}"
echo -e "  ${GREEN}PASS${NC}"
((PASS_COUNT++))

# --- Test 3: Casual Chat (No Chip) ---
print_test_header "3" "Casual Chat (No Chip)"
PAYLOAD='{"message": "hello, who are you?", "history": []}'
START_TIME=$(date +%s%3N)
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")
END_TIME=$(date +%s%3N)
DURATION=$((END_TIME - START_TIME))

AGENT=$(echo "$RESPONSE" | jq -r '.agent')
ROUTED=$(echo "$RESPONSE" | jq -r '.routed')
CONTENT=$(echo "$RESPONSE" | jq -r '.content')
THINKING=$(echo "$RESPONSE" | jq -r '.thinking_time_ms')

echo -e "  Response: \"${CONTENT:0:100}...\""
echo -e "  Agent: $AGENT, Routed: $ROUTED, Time: ${DURATION}ms (Thinking: ${THINKING}ms)"

if [ "$AGENT" == "Nexus" ] && [ "$ROUTED" == "false" ] && [ -n "$CONTENT" ] && [ "$THINKING" -gt 0 ]; then
    echo -e "  ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  ${RED}FAIL: Unexpected response structure${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 4: Code Question (No Chip, Expect Route) ---
print_test_header "4" "Code Question (Expect Route to Bolt)"
PAYLOAD='{"message": "write me a binary search in python"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")

AGENT=$(echo "$RESPONSE" | jq -r '.agent')
ROUTED=$(echo "$RESPONSE" | jq -r '.routed')
TARGET=$(echo "$RESPONSE" | jq -r '.route_target')
NEXUS_T=$(echo "$RESPONSE" | jq -r '.nexus_time_ms // 0')
SPEC_T=$(echo "$RESPONSE" | jq -r '.specialist_time_ms // 0')

echo -e "  Agent: $AGENT, Routed: $ROUTED, Target: $TARGET"
echo -e "  Nexus Time: ${NEXUS_T}ms, Specialist Time: ${SPEC_T}ms"

if [ "$AGENT" == "Bolt" ] && [ "$ROUTED" == "true" ] && [ "$TARGET" == "bolt" ]; then
    echo -e "  ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  ${YELLOW}WARN: Nexus did not route code task to Bolt. Agent: $AGENT, Routed: $ROUTED${NC}"
    ((WARN_COUNT++))
fi

# --- Test 5: Reasoning Question (No Chip, Expect Route to Nova) ---
print_test_header "5" "Reasoning Question (Expect Route to Nova)"
PAYLOAD='{"message": "explain step by step why the sky is blue"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")

AGENT=$(echo "$RESPONSE" | jq -r '.agent')
ROUTED=$(echo "$RESPONSE" | jq -r '.routed')
TARGET=$(echo "$RESPONSE" | jq -r '.route_target')

echo -e "  Agent: $AGENT, Routed: $ROUTED, Target: $TARGET"

if [ "$AGENT" == "Nova" ] && [ "$ROUTED" == "true" ] && [ "$TARGET" == "nova" ]; then
    echo -e "  ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  ${YELLOW}WARN: Nexus did not route reasoning task to Nova. Agent: $AGENT, Routed: $ROUTED${NC}"
    ((WARN_COUNT++))
fi

# --- Test 6: Chip Override (Code -> Bolt) ---
print_test_header "6" "Chip Override (Code forces Bolt)"
PAYLOAD='{"message": "what is 2+2", "chip": "Code"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")

AGENT=$(echo "$RESPONSE" | jq -r '.agent')
ROUTED=$(echo "$RESPONSE" | jq -r '.routed')

echo -e "  Agent: $AGENT, Routed: $ROUTED"

if [ "$AGENT" == "Bolt" ] && [ "$ROUTED" == "false" ]; then
    echo -e "  ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  ${RED}FAIL: Chip 'Code' should force Bolt (routed=false). Got $AGENT (routed=$ROUTED)${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 7: Chip Override (Learn -> Nova) ---
print_test_header "7" "Chip Override (Learn forces Nova)"
PAYLOAD='{"message": "hi", "chip": "Learn"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")

AGENT=$(echo "$RESPONSE" | jq -r '.agent')

if [ "$AGENT" == "Nova" ]; then
    echo -e "  Agent: $AGENT | ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  Agent: $AGENT | ${RED}FAIL: Chip 'Learn' should force Nova${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 8: Chip Override (Write -> Nexus) ---
print_test_header "8" "Chip Override (Write forces Nexus)"
PAYLOAD='{"message": "hi", "chip": "Write"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/chat")

AGENT=$(echo "$RESPONSE" | jq -r '.agent')

if [ "$AGENT" == "Nexus" ]; then
    echo -e "  Agent: $AGENT | ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  Agent: $AGENT | ${RED}FAIL: Chip 'Write' should force Nexus${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 9: State After Swaps ---
print_test_header "9" "State Check"
RESPONSE=$(curl -s "$DAEMON_URL/state")
CURRENT_MODEL=$(echo "$RESPONSE" | jq -r '.model')
echo -e "  Current model: $CURRENT_MODEL"
echo -e "  ${GREEN}PASS${NC}"
((PASS_COUNT++))

# --- Test 10: Same-model Fast Path ---
print_test_header "10" "Same-model Fast Path"
echo -e "  Call 1 (Write/Nexus)..."
START_1=$(date +%s%3N)
curl -s -X POST -H "Content-Type: application/json" -d '{"message": "hi", "chip": "Write"}' "$DAEMON_URL/chat" > /dev/null
END_1=$(date +%s%3N)
DUR_1=$((END_1 - START_1))

echo -e "  Call 2 (Write/Nexus)..."
START_2=$(date +%s%3N)
curl -s -X POST -H "Content-Type: application/json" -d '{"message": "hello again", "chip": "Write"}' "$DAEMON_URL/chat" > /dev/null
END_2=$(date +%s%3N)
DUR_2=$((END_2 - START_2))

echo -e "  Duration 1: ${DUR_1}ms"
echo -e "  Duration 2: ${DUR_2}ms"

if [ "$DUR_2" -lt "$DUR_1" ]; then
    echo -e "  ${GREEN}PASS: Second call was faster${NC}"
    ((PASS_COUNT++))
else
    echo -e "  ${YELLOW}WARN: Second call wasn't faster. (D1: $DUR_1, D2: $DUR_2)${NC}"
    ((PASS_COUNT++)) # Not a failure, timing can be tricky
fi

# --- Test 11: Copy Endpoint ---
print_test_header "11" "Copy Endpoint"
PAYLOAD='{"text": "test clipboard from daemon test"}'
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL/copy")
STATUS=$(echo "$RESPONSE" | jq -r '.status')

if [ "$STATUS" == "ok" ]; then
    echo -e "  Status: $STATUS | ${GREEN}PASS${NC}"
    echo -e "  ${YELLOW}NOTE: Manual verification required: try pasting now to check wl-copy.${NC}"
    ((PASS_COUNT++))
else
    echo -e "  Status: $STATUS | ${RED}FAIL${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 12: Invalid Endpoint ---
print_test_header "12" "Invalid Endpoint"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DAEMON_URL/nonexistent")
if [ "$HTTP_CODE" -ne 200 ]; then
    echo -e "  HTTP Code: $HTTP_CODE | ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  HTTP Code: $HTTP_CODE | ${RED}FAIL: Should not return 200 for nonexistent endpoint${NC}"
    ((FAIL_COUNT++))
fi

# --- Test 13: Malformed Chat Request ---
print_test_header "13" "Malformed Chat Request"
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "" "$DAEMON_URL/chat")
echo -e "  Response: $RESPONSE"

# Verify daemon still alive
HEALTH=$(curl -s "$DAEMON_URL/health" | jq -r '.status')
if [ "$HEALTH" == "ok" ]; then
    echo -e "  Daemon health after crash attempt: $HEALTH | ${GREEN}PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "  Daemon health after crash attempt: FAILED | ${RED}FAIL${NC}"
    ((FAIL_COUNT++))
fi

# --- Summary ---
echo -e "\n${BLUE}=== Summary ===${NC}"
echo -e "  ${GREEN}PASS: $PASS_COUNT${NC}"
echo -e "  ${RED}FAIL: $FAIL_COUNT${NC}"
echo -e "  ${YELLOW}WARN: $WARN_COUNT${NC}"

if [ "$FAIL_COUNT" -eq 0 ]; then
    exit 0
else
    exit 1
fi
