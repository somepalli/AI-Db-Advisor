"""
Test Real MCP Integration - End-to-End Test
"""
import requests
import json
import time
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

BASE_URL = "http://localhost:8000"
MCP_BRIDGE_URL = "http://localhost:3000"

print("\n" + "="*80)
print("TESTING REAL MCP INTEGRATION")
print("="*80)

# Step 1: Check MCP Bridge
print("\n1. Checking MCP Bridge Health...")
try:
    response = requests.get(f"{MCP_BRIDGE_URL}/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ MCP Bridge is running: {data}")
    else:
        print(f"   ❌ MCP Bridge returned {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ MCP Bridge not accessible: {e}")
    print("   Please start: python mcp_http_bridge.py")
    sys.exit(1)

# Step 2: Check MCP Tools
print("\n2. Checking MCP Tools...")
try:
    response = requests.get(f"{MCP_BRIDGE_URL}/tools", timeout=5)
    if response.status_code == 200:
        data = response.json()
        tools = data.get("tools", [])
        print(f"   ✅ Found {len(tools)} MCP tools:")
        for tool in tools:
            print(f"      - {tool.get('name')}: {tool.get('description')}")
    else:
        print(f"   ⚠️  MCP Tools returned {response.status_code}")
except Exception as e:
    print(f"   ❌ Failed to get MCP tools: {e}")

# Step 3: Check Main App
print("\n3. Checking Main App...")
try:
    response = requests.get(f"{BASE_URL}/healthz", timeout=5)
    if response.status_code == 200:
        print(f"   ✅ Main app is running")
    else:
        print(f"   ❌ Main app returned {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Main app not accessible: {e}")
    print("   Please start: python run.py")
    sys.exit(1)

# Step 4: Check MCP Health through App
print("\n4. Checking MCP Integration Status...")
try:
    response = requests.get(f"{BASE_URL}/mcp/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ MCP Status: {json.dumps(data, indent=6)}")

        if not data.get("mcp_enabled"):
            print("\n   ⚠️  MCP is not enabled!")
            print("   Check .env file: MCP_ENABLED=true")
    else:
        print(f"   ⚠️  MCP health check returned {response.status_code}")
except Exception as e:
    print(f"   ❌ Failed to check MCP status: {e}")

# Step 5: Register a test datasource
print("\n5. Registering Test Datasource...")
ds_payload = {
    "id": "test-postgres-mcp",
    "engine": "postgres",
    "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
}

try:
    response = requests.post(f"{BASE_URL}/datasources", json=ds_payload, timeout=10)
    if response.status_code in [200, 201]:
        print(f"   ✅ Datasource registered: test-postgres-mcp")
    else:
        print(f"   ⚠️  Datasource registration: {response.status_code} - {response.text}")
except Exception as e:
    print(f"   ⚠️  Datasource registration failed: {e}")

# Step 6: Test MCP Suggestions via AI Chat
print("\n6. Testing MCP Suggestions via AI Chat...")
chat_payload = {
    "ds_id": "test-postgres-mcp",
    "message": "Optimize query performance",
    "current_sql": "SELECT * FROM students WHERE enrollment_year = 2020 ORDER BY student_id",
    "save_to_history": False
}

try:
    print("   Sending request to AI Chat endpoint...")
    response = requests.post(f"{BASE_URL}/ai-chat/chat", json=chat_payload, timeout=30)

    if response.status_code == 200:
        data = response.json()
        suggestions = data.get("suggestions", [])

        print(f"\n   ✅ Received {len(suggestions)} suggestions")

        # Count MCP suggestions
        mcp_suggestions = [s for s in suggestions if s.get("is_mcp")]
        ai_suggestions = [s for s in suggestions if not s.get("is_mcp")]

        print(f"      - MCP Suggestions: {len(mcp_suggestions)}")
        print(f"      - AI Suggestions: {len(ai_suggestions)}")

        if mcp_suggestions:
            print("\n   📋 MCP Suggestions:")
            for i, sug in enumerate(mcp_suggestions, 1):
                print(f"\n      {i}. {sug.get('summary')}")
                print(f"         Type: {sug.get('type')}")
                print(f"         Risk: {sug.get('risk')}")
                if sug.get('sql'):
                    print(f"         SQL: {sug.get('sql')[:100]}...")
                print(f"         Status: {sug.get('status')}")
        else:
            print("\n   ⚠️  No MCP suggestions received (may be using demo mode)")

        print(f"\n   Full response saved to: mcp_test_response.json")
        with open("mcp_test_response.json", "w") as f:
            json.dump(data, f, indent=2)

    else:
        print(f"   ❌ AI Chat failed: {response.status_code}")
        print(f"   Response: {response.text}")

except Exception as e:
    print(f"   ❌ AI Chat request failed: {e}")
    import traceback
    traceback.print_exc()

# Step 7: Test Direct MCP Request
print("\n7. Testing Direct MCP Request...")
mcp_request = {
    "query": "SELECT * FROM students WHERE enrollment_year = 2020",
    "optimization_type": "performance",
    "max_suggestions": 3
}

try:
    response = requests.post(
        f"{BASE_URL}/mcp/test-postgres-mcp/request-suggestions",
        json=mcp_request,
        timeout=30
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ MCP Direct Request successful")
        print(f"      Suggestions: {data.get('count')}")
        print(f"      Note: {data.get('note')}")
    else:
        print(f"   ⚠️  MCP Direct Request: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

except Exception as e:
    print(f"   ⚠️  MCP Direct Request failed: {e}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
print("\n✅ Summary:")
print("   - MCP Bridge: Running")
print("   - Main App: Running")
print("   - MCP Integration: Check results above")
print("\nCheck mcp_test_response.json for full AI Chat response")
print("="*80 + "\n")
