"""
Test script to identify correct Google API endpoint
"""
import httpx
import asyncio
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

API_KEY = "AIzaSyD6VA6doaEnnG8MCQJrGL8Brxtvwu6LZLU"

# Possible Google API endpoints
ENDPOINTS_TO_TEST = [
    # MCP endpoints
    ("MCP v1", "https://mcp.googleapis.com/v1/tools"),
    ("MCP v1 models", "https://mcp.googleapis.com/v1/models"),

    # Gemini endpoints
    ("Gemini v1", "https://generativelanguage.googleapis.com/v1/models"),
    ("Gemini v1beta", "https://generativelanguage.googleapis.com/v1beta/models"),

    # Generic Google API
    ("Generic discovery", "https://www.googleapis.com/discovery/v1/apis"),
]


async def test_endpoint(name: str, url: str, api_key: str):
    """Test a specific endpoint"""
    print(f"\nTesting: {name}")
    print(f"  URL: {url}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"key": api_key})

            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                try:
                    data = response.json()
                    print(f"  Response keys: {list(data.keys())}")
                    return True
                except:
                    print(f"  Response (text): {response.text[:200]}...")
                    return True
            elif response.status_code == 404:
                print(f"  ❌ Not Found (404)")
            elif response.status_code == 401 or response.status_code == 403:
                print(f"  ⚠️  Authentication/Permission Error ({response.status_code})")
                print(f"  Response: {response.text[:200]}")
            else:
                print(f"  ⚠️  Unexpected status: {response.status_code}")
                print(f"  Response: {response.text[:200]}")

            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def main():
    print("="*80)
    print("TESTING GOOGLE API ENDPOINTS")
    print("="*80)
    print(f"\nAPI Key: {API_KEY[:15]}...")

    successful_endpoints = []

    for name, url in ENDPOINTS_TO_TEST:
        success = await test_endpoint(name, url, API_KEY)
        if success:
            successful_endpoints.append((name, url))

    print("\n" + "="*80)
    if successful_endpoints:
        print(f"✅ Found {len(successful_endpoints)} working endpoint(s):")
        for name, url in successful_endpoints:
            print(f"   - {name}: {url}")
    else:
        print("❌ No working endpoints found")
        print("\nPossible reasons:")
        print("  1. API key might be invalid or expired")
        print("  2. API key might be for a different Google service")
        print("  3. API key might not have the required permissions")
        print("  4. The endpoint URLs might be incorrect")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
