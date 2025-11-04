"""Test script for Phase 5.1: Context Memory

This script validates that:
1. Session storage system works
2. Conversation history is maintained
3. Reference resolution works
4. History display works
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.session import SessionContext, SessionManager
from datetime import datetime


def test_session_storage():
    """Test 5.1.1: Session storage system"""
    print("\n" + "="*60)
    print("TEST 5.1.1: Session Storage System")
    print("="*60)
    
    session = SessionContext(session_id="test_user")
    
    # Add some commands
    session.add_command(
        command="search for emails from google",
        service="gmail",
        intent="search_email",
        parameters={"from": "google"},
        result=[
            {"id": "123", "subject": "Test Email 1"},
            {"id": "456", "subject": "Test Email 2"}
        ],
        success=True
    )
    
    assert len(session.history) == 1, "? Session should have 1 command"
    print("? Session storage works")
    
    # Verify command is stored
    last_cmd = session.get_last_command()
    assert last_cmd is not None, "? Should have last command"
    assert last_cmd.service == "gmail", "? Service should be gmail"
    print("? Command retrieval works")
    
    print("\n? TEST 5.1.1 PASSED\n")


def test_conversation_history():
    """Test 5.1.2: Conversation history"""
    print("\n" + "="*60)
    print("TEST 5.1.2: Conversation History")
    print("="*60)
    
    session = SessionContext(session_id="test_user")
    
    # Add multiple commands
    commands = [
        ("search for emails", "gmail", "search_email", [{"id": "1"}]),
        ("list my events", "calendar", "list_events", [{"id": "event1"}]),
        ("find files", "drive", "search_file", [{"id": "file1"}])
    ]
    
    for cmd, service, intent, result in commands:
        session.add_command(
            command=cmd,
            service=service,
            intent=intent,
            parameters={},
            result=result,
            success=True
        )
    
    assert len(session.history) == 3, f"? Should have 3 commands, got {len(session.history)}"
    print(f"? History contains {len(session.history)} commands")
    
    # Test get_last_n_commands
    last_2 = session.get_last_n_commands(2)
    assert len(last_2) == 2, "? Should get last 2 commands"
    assert last_2[0].service == "calendar", "? First should be calendar"
    assert last_2[1].service == "drive", "? Second should be drive"
    print("? Last N commands retrieval works")
    
    print("\n? TEST 5.1.2 PASSED\n")


def test_reference_resolution():
    """Test 5.1.3: Reference resolution"""
    print("\n" + "="*60)
    print("TEST 5.1.3: Reference Resolution")
    print("="*60)
    
    session = SessionContext(session_id="test_user")
    
    # Add email search
    session.add_command(
        command="search for emails",
        service="gmail",
        intent="search_email",
        parameters={},
        result=[
            {"id": "email123", "payload": {"headers": [{"name": "Subject", "value": "Important"}]}}
        ],
        success=True
    )
    
    # Test email reference
    ref_type, ref_value = session.resolve_reference("that email")
    assert ref_type == "email", f"? Should resolve to email, got {ref_type}"
    assert ref_value is not None, "? Should have email value"
    print("? 'that email' resolves correctly")
    
    # Test "last email"
    ref_type, ref_value = session.resolve_reference("last email")
    assert ref_type == "email", "? Should resolve to email"
    print("? 'last email' resolves correctly")
    
    # Add calendar event
    session.add_command(
        command="list events",
        service="calendar",
        intent="list_events",
        parameters={},
        result=[
            {"id": "event123", "summary": "Meeting"}
        ],
        success=True
    )
    
    # Test meeting reference
    ref_type, ref_value = session.resolve_reference("that meeting")
    assert ref_type == "event", f"? Should resolve to event, got {ref_type}"
    print("? 'that meeting' resolves correctly")
    
    # Test "next meeting"
    ref_type, ref_value = session.resolve_reference("next meeting")
    assert ref_type == "event", "? Should resolve to event"
    print("? 'next meeting' resolves correctly")
    
    # Test "the first one"
    ref_type, ref_value = session.resolve_reference("the first one")
    assert ref_type == "calendar", f"? Should resolve to calendar, got {ref_type}"
    print("? 'the first one' resolves correctly")
    
    print("\n? TEST 5.1.3 PASSED\n")


def test_context_summary():
    """Test 5.1.4: Context summary for LLM"""
    print("\n" + "="*60)
    print("TEST 5.1.4: Context Summary")
    print("="*60)
    
    session = SessionContext(session_id="test_user")
    
    # Add commands
    session.add_command(
        command="search emails",
        service="gmail",
        intent="search_email",
        parameters={},
        result=[{"id": "1"}],
        success=True
    )
    
    session.add_command(
        command="list events",
        service="calendar",
        intent="list_events",
        parameters={},
        result=[{"id": "event1"}],
        success=True
    )
    
    summary = session.get_context_summary()
    assert "Recent commands:" in summary, "? Summary should have recent commands"
    assert "gmail" in summary.lower(), "? Summary should mention gmail"
    assert "calendar" in summary.lower(), "? Summary should mention calendar"
    print("? Context summary generated correctly")
    
    # Check references in summary
    assert "Available references:" in summary, "? Summary should list references"
    print("? References included in summary")
    
    print("\n? TEST 5.1.4 PASSED\n")


def test_session_manager():
    """Test SessionManager"""
    print("\n" + "="*60)
    print("TEST: Session Manager")
    print("="*60)
    
    manager = SessionManager()
    
    # Start session
    session = manager.start_session("user123")
    assert session is not None, "? Session should be created"
    assert session.session_id == "user123", "? Session ID should match"
    print("? Session creation works")
    
    # Get current session
    current = manager.get_session()
    assert current == session, "? Should get same session"
    print("? Session retrieval works")
    
    # End session
    manager.end_session()
    assert manager.current_session is None, "? Session should be ended"
    print("? Session termination works")
    
    print("\n? SESSION MANAGER TEST PASSED\n")


def main():
    """Run all Phase 5.1 tests"""
    print("\n" + "??"*30)
    print("PHASE 5.1 - CONTEXT MEMORY - VALIDATION TESTS")
    print("??"*30)
    
    try:
        test_session_storage()
        test_conversation_history()
        test_reference_resolution()
        test_context_summary()
        test_session_manager()
        
        print("\n" + "="*60)
        print("?? ALL PHASE 5.1 TESTS PASSED! ??")
        print("="*60)
        print("\nPhase 5.1 is fully implemented and working:")
        print("  ? 5.1.1: Session storage system")
        print("  ? 5.1.2: Conversation history")
        print("  ? 5.1.3: Reference resolution")
        print("  ? 5.1.4: Context summary")
        print("\nNext: Test with real orchestrator in interactive mode")
        
        return 0
        
    except AssertionError as e:
        print(f"\n? TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n? UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
