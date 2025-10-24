"""
Test script for Google MCP API integration
"""
import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'app'))

from services.mcp_client import MCPClient, initialize_mcp_client
from config import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_integration():
    """Test MCP API integration"""

    print("\n" + "="*80)
    print("TESTING GOOGLE MCP API INTEGRATION")
    print("="*80)

    # Check configuration
    print(f"\n1. Configuration Check:")
    print(f"   - MCP Enabled: {settings.MCP_ENABLED}")
    print(f"   - MCP Endpoint: {settings.MCP_ENDPOINT}")
    print(f"   - API Key: {settings.MCP_API_KEY[:15]}..." if settings.MCP_API_KEY else "   - API Key: NOT SET")

    if not settings.MCP_ENABLED:
        print("\n❌ ERROR: MCP is not enabled in configuration")
        print("   Set MCP_ENABLED=true in .env file")
        return False

    if not settings.MCP_API_KEY:
        print("\n❌ ERROR: MCP API Key is not configured")
        print("   Set MCP_API_KEY in .env file")
        return False

    # Initialize MCP client
    print(f"\n2. Initializing MCP Client...")
    try:
        mcp_client = MCPClient(
            mcp_endpoint=settings.MCP_ENDPOINT,
            api_key=settings.MCP_API_KEY,
            timeout=settings.MCP_TIMEOUT
        )
        print("   ✅ MCP Client initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize MCP Client: {e}")
        return False

    # Validate credentials
    print(f"\n3. Validating API Credentials...")
    try:
        is_valid = await mcp_client.validate_credentials()
        if is_valid:
            print("   ✅ API credentials are VALID")
        else:
            print("   ❌ API credentials are INVALID")
            return False
    except Exception as e:
        print(f"   ❌ Credential validation failed: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        return False

    # Discover tools
    print(f"\n4. Discovering Available MCP Tools...")
    try:
        tools = await mcp_client.discover_tools()
        print(f"   ✅ Found {len(tools)} MCP tools")

        if tools:
            print("\n   Available Tools:")
            for i, tool in enumerate(tools[:5], 1):  # Show first 5
                print(f"      {i}. {tool.get('name', 'Unknown')} - {tool.get('description', 'No description')[:60]}...")
        else:
            print("   ⚠️  No tools found (this might be normal if the API has no tools configured)")
    except Exception as e:
        print(f"   ❌ Tool discovery failed: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        return False

    # Close client
    await mcp_client.close()

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - MCP Integration is working!")
    print("="*80 + "\n")

    return True


if __name__ == "__main__":
    print("Starting MCP Integration Test...")

    try:
        success = asyncio.run(test_mcp_integration())

        if success:
            print("✅ Test completed successfully")
            sys.exit(0)
        else:
            print("❌ Test failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
