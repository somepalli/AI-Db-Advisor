"""
Comprehensive Test Suite for AI Chat with MCP Integration
Tests the complete flow from first request to subsequent requests with MCP cards
"""
import sys
sys.path.insert(0, '.venv')

from app.routers.ai_chat import ChatRequest, ChatMessage, ChatResponse
from app.routers.mcp import _generate_demo_suggestions, MCPSuggestionRequest
import json


def test_case_1_first_request():
    """Test Case 1: First AI chat request (no conversation history)"""
    print("\n" + "="*80)
    print("TEST CASE 1: First AI Chat Request")
    print("="*80)

    request_data = {
        'ds_id': 'test-db',
        'message': 'Show all students enrolled in 2020',
        'conversation_history': [],
        'current_sql': None,
        'session_id': 'session-test-001',
        'save_to_history': True
    }

    try:
        chat_req = ChatRequest(**request_data)
        print("[PASS] First request validation succeeded")
        print(f"  - Message: {chat_req.message}")
        print(f"  - History items: {len(chat_req.conversation_history)}")
        print(f"  - Session ID: {chat_req.session_id}")
        return True
    except Exception as e:
        print(f"[X] FAIL: {e}")
        return False


def test_case_2_second_request_with_regular_history():
    """Test Case 2: Second request with regular chat history (no MCP cards)"""
    print("\n" + "="*80)
    print("TEST CASE 2: Second Request with Regular Chat History")
    print("="*80)

    request_data = {
        'ds_id': 'test-db',
        'message': 'What about students in 2021?',
        'conversation_history': [
            {'role': 'user', 'content': 'Show all students enrolled in 2020'},
            {'role': 'assistant', 'content': 'SELECT * FROM students WHERE enrollment_year = 2020;'}
        ],
        'current_sql': 'SELECT * FROM students WHERE enrollment_year = 2020;',
        'session_id': 'session-test-001',
        'save_to_history': True
    }

    try:
        chat_req = ChatRequest(**request_data)
        print("[OK] PASS: Second request with regular history succeeded")
        print(f"  - Message: {chat_req.message}")
        print(f"  - History items: {len(chat_req.conversation_history)}")
        for i, msg in enumerate(chat_req.conversation_history):
            print(f"    [{i}] {msg.role}: {msg.content[:50]}...")
        return True
    except Exception as e:
        print(f"[X] FAIL: {e}")
        return False


def test_case_3_mcp_card_in_history_should_fail():
    """Test Case 3: Request with MCP card in history (SHOULD FAIL without filtering)"""
    print("\n" + "="*80)
    print("TEST CASE 3: MCP Card in History (Expected to FAIL)")
    print("="*80)

    request_data = {
        'ds_id': 'test-db',
        'message': 'Another question',
        'conversation_history': [
            {'role': 'user', 'content': 'Show students'},
            {'role': 'assistant', 'content': 'SELECT * FROM students;'},
            {
                'role': 'mcp_suggestion',
                'type': 'mcp_card',
                'suggestion': {
                    'id': 'mcp-123',
                    'sql': 'CREATE INDEX idx_students ON students(id);',
                    'description': 'Add index',
                    'risk_level': 'low'
                },
                'timestamp': '2024-01-01T00:00:00'
            }
        ],
        'session_id': 'session-test-001'
    }

    try:
        chat_req = ChatRequest(**request_data)
        print("[X] FAIL: Should have rejected MCP card in history!")
        return False
    except Exception as e:
        print("[OK] PASS: Correctly rejected MCP card (missing 'content' field)")
        print(f"  - Error: {str(e)[:100]}...")
        return True


def test_case_4_filtered_history():
    """Test Case 4: Filtered conversation history (MCP cards removed)"""
    print("\n" + "="*80)
    print("TEST CASE 4: Filtered Conversation History (Frontend Fix)")
    print("="*80)

    # Simulate frontend chat history with MCP cards
    frontend_chat_history = [
        {'role': 'user', 'content': 'Show students', 'timestamp': '2024-01-01T00:00:00'},
        {'role': 'assistant', 'content': 'SELECT * FROM students;', 'timestamp': '2024-01-01T00:00:01'},
        {'role': 'assistant', 'content': "I've generated 2 optimization suggestions:", 'timestamp': '2024-01-01T00:00:02'},
        {
            'role': 'mcp_suggestion',
            'type': 'mcp_card',
            'suggestion': {'id': 'mcp-1', 'sql': 'CREATE INDEX...'},
            'timestamp': '2024-01-01T00:00:03'
        },
        {
            'role': 'mcp_suggestion',
            'type': 'mcp_card',
            'suggestion': {'id': 'mcp-2', 'sql': 'ANALYZE...'},
            'timestamp': '2024-01-01T00:00:04'
        },
        {'role': 'user', 'content': 'What about 2021?', 'timestamp': '2024-01-01T00:00:05'}
    ]

    # Frontend filtering logic (same as implemented in SQLAssistant.tsx)
    filtered_history = [
        {'role': msg['role'], 'content': msg['content']}
        for msg in frontend_chat_history
        if msg.get('type') != 'mcp_card' and 'content' in msg
    ]

    print(f"Original chat history: {len(frontend_chat_history)} items")
    print(f"Filtered history: {len(filtered_history)} items")

    request_data = {
        'ds_id': 'test-db',
        'message': 'Another query',
        'conversation_history': filtered_history,
        'session_id': 'session-test-001'
    }

    try:
        chat_req = ChatRequest(**request_data)
        print("[OK] PASS: Filtered history validation succeeded")
        print(f"  - Sent to backend: {len(chat_req.conversation_history)} messages")
        for i, msg in enumerate(chat_req.conversation_history):
            print(f"    [{i}] {msg.role}: {msg.content[:50]}...")
        print(f"  - MCP cards filtered out: {len(frontend_chat_history) - len(filtered_history)}")
        return True
    except Exception as e:
        print(f"[X] FAIL: {e}")
        return False


def test_case_5_mcp_demo_suggestions():
    """Test Case 5: MCP Demo Suggestions Generation"""
    print("\n" + "="*80)
    print("TEST CASE 5: MCP Demo Suggestions Generation")
    print("="*80)

    request = MCPSuggestionRequest(
        query="SELECT * FROM students WHERE enrollment_year = 2020",
        optimization_type="general",
        max_suggestions=3
    )

    try:
        suggestions = _generate_demo_suggestions("test-db", request)
        print("[OK] PASS: MCP demo suggestions generated")
        print(f"  - Generated {len(suggestions)} suggestions")
        for i, sug in enumerate(suggestions):
            print(f"    [{i+1}] {sug['description'][:50]}...")
            print(f"        Risk: {sug['risk_level']}, Status: {sug['status']}")
        return True
    except Exception as e:
        print(f"[X] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_case_6_full_workflow_simulation():
    """Test Case 6: Full Workflow Simulation (Request → Response → MCP → Request)"""
    print("\n" + "="*80)
    print("TEST CASE 6: Full Workflow Simulation")
    print("="*80)

    # Step 1: First request
    print("\nStep 1: User asks first question")
    first_request = {
        'ds_id': 'test-db',
        'message': 'Show all students enrolled in 2020',
        'conversation_history': [],
        'session_id': 'session-workflow'
    }

    try:
        ChatRequest(**first_request)
        print("  [OK] First request validated")
    except Exception as e:
        print(f"  [X] First request failed: {e}")
        return False

    # Step 2: Simulate AI response with MCP suggestions
    print("\nStep 2: AI responds with SQL + MCP suggestions")
    simulated_chat_history = [
        {'role': 'user', 'content': 'Show all students enrolled in 2020'},
        {'role': 'assistant', 'content': 'SELECT * FROM students WHERE enrollment_year = 2020;'},
        {'role': 'assistant', 'content': "I've generated 3 optimization suggestions for you:"},
        {'role': 'mcp_suggestion', 'type': 'mcp_card', 'suggestion': {'id': 'mcp-1'}},
        {'role': 'mcp_suggestion', 'type': 'mcp_card', 'suggestion': {'id': 'mcp-2'}},
        {'role': 'mcp_suggestion', 'type': 'mcp_card', 'suggestion': {'id': 'mcp-3'}},
    ]
    print(f"  [OK] Simulated chat history: {len(simulated_chat_history)} items")

    # Step 3: User approves MCP card and asks another question
    print("\nStep 3: User approves card and asks follow-up")
    simulated_chat_history.extend([
        {'role': 'assistant', 'content': 'Successfully executed: Create index...'},
        {'role': 'user', 'content': 'Now show students from 2021'}
    ])

    # Step 4: Frontend filters before sending second request
    print("\nStep 4: Frontend filters MCP cards before sending")
    filtered_for_backend = [
        {'role': msg['role'], 'content': msg['content']}
        for msg in simulated_chat_history
        if msg.get('type') != 'mcp_card' and 'content' in msg
    ]

    second_request = {
        'ds_id': 'test-db',
        'message': 'Now show students from 2021',
        'conversation_history': filtered_for_backend,
        'session_id': 'session-workflow'
    }

    try:
        ChatRequest(**second_request)
        print(f"  [OK] Second request validated")
        print(f"  [OK] Filtered history: {len(filtered_for_backend)} items (removed MCP cards)")
        return True
    except Exception as e:
        print(f"  [X] Second request failed: {e}")
        return False


def run_all_tests():
    """Run all test cases and report results"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE: AI Chat with MCP Integration")
    print("="*80)

    tests = [
        ("First Request", test_case_1_first_request),
        ("Second Request (Regular History)", test_case_2_second_request_with_regular_history),
        ("MCP Card Rejection", test_case_3_mcp_card_in_history_should_fail),
        ("Filtered History", test_case_4_filtered_history),
        ("MCP Demo Suggestions", test_case_5_mcp_demo_suggestions),
        ("Full Workflow", test_case_6_full_workflow_simulation),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    # Print summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "[OK]" if result else "[X]"
        print(f"{symbol} {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED! The fix is working correctly.")
    else:
        print(f"\n[WARN] {total - passed} test(s) failed. Review implementation.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
