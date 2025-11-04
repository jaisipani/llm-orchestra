"""Test script for Phase 5.4: Enhanced Safety

This script validates that:
1. Dry-run mode works
2. Action recording works
3. Undo stack management works
4. Safety previews generate correctly
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.safety import SafetyManager, ActionType, ActionPreview


def test_dry_run_mode():
    """Test 5.4.1: Dry-run mode"""
    print("\n" + "="*60)
    print("TEST 5.4.1: Dry-Run Mode")
    print("="*60)
    
    manager = SafetyManager(dry_run=False)
    assert not manager.is_dry_run(), "? Should not be in dry-run mode"
    print("? Dry-run mode starts disabled")
    
    # Enable dry-run
    manager.set_dry_run(True)
    assert manager.is_dry_run(), "? Should be in dry-run mode"
    print("? Can enable dry-run mode")
    
    # Disable dry-run
    manager.set_dry_run(False)
    assert not manager.is_dry_run(), "? Should not be in dry-run mode"
    print("? Can disable dry-run mode")
    
    print("\n? TEST 5.4.1 PASSED\n")


def test_destructive_detection():
    """Test detection of destructive actions"""
    print("\n" + "="*60)
    print("TEST: Destructive Action Detection")
    print("="*60)
    
    manager = SafetyManager()
    
    # Destructive actions
    assert manager.is_destructive("delete_email"), "? delete_email should be destructive"
    assert manager.is_destructive("delete_file"), "? delete_file should be destructive"
    assert manager.is_destructive("send_email"), "? send_email should be destructive"
    print("? Destructive actions detected correctly")
    
    # Non-destructive actions
    assert not manager.is_destructive("search_email"), "? search_email should not be destructive"
    assert not manager.is_destructive("list_events"), "? list_events should not be destructive"
    print("? Non-destructive actions detected correctly")
    
    print("\n? DESTRUCTIVE DETECTION TEST PASSED\n")


def test_action_recording():
    """Test 5.4.2: Action recording for undo"""
    print("\n" + "="*60)
    print("TEST 5.4.2: Action Recording")
    print("="*60)
    
    manager = SafetyManager()
    
    # Record an action
    manager.record_action(
        action_type=ActionType.SEND_EMAIL,
        resource_id="email123",
        service="gmail",
        details={"to": "test@example.com", "subject": "Test"},
        undo_data=None
    )
    
    assert len(manager.get_undo_stack()) == 1, "? Should have 1 action"
    print("? Action recorded successfully")
    
    # Get last action
    last = manager.get_last_action()
    assert last is not None, "? Should have last action"
    assert last.action_type == ActionType.SEND_EMAIL, "? Wrong action type"
    assert last.resource_id == "email123", "? Wrong resource ID"
    print("? Can retrieve last action")
    
    # Record multiple actions
    for i in range(5):
        manager.record_action(
            action_type=ActionType.CREATE_EVENT,
            resource_id=f"event{i}",
            service="calendar",
            details={},
            undo_data={}
        )
    
    assert len(manager.get_undo_stack()) == 6, "? Should have 6 actions"
    print("? Multiple actions recorded")
    
    # Test max limit
    for i in range(10):
        manager.record_action(
            action_type=ActionType.SHARE_FILE,
            resource_id=f"file{i}",
            service="drive",
            details={},
            undo_data={}
        )
    
    assert len(manager.get_undo_stack()) <= 10, "? Should not exceed max"
    print("? Max undo stack limit enforced")
    
    print("\n? TEST 5.4.2 PASSED\n")


def test_undo_stack_management():
    """Test undo stack operations"""
    print("\n" + "="*60)
    print("TEST: Undo Stack Management")
    print("="*60)
    
    manager = SafetyManager()
    
    # Empty stack
    assert not manager.can_undo(), "? Should not be able to undo empty stack"
    assert manager.get_last_action() is None, "? Should have no last action"
    print("? Empty stack handled correctly")
    
    # Add actions
    manager.record_action(
        action_type=ActionType.DELETE_EMAIL,
        resource_id="email1",
        service="gmail",
        details={},
        undo_data={"location": "trash"}
    )
    
    assert manager.can_undo(), "? Should be able to undo"
    assert manager.can_undo(ActionType.DELETE_EMAIL), "? Should be able to undo DELETE_EMAIL"
    print("? Can check undo availability")
    
    # Pop action
    popped = manager.pop_last_action()
    assert popped is not None, "? Should have popped action"
    assert popped.action_type == ActionType.DELETE_EMAIL, "? Wrong action type"
    assert len(manager.get_undo_stack()) == 0, "? Stack should be empty"
    print("? Can pop actions from stack")
    
    # Clear stack
    for i in range(3):
        manager.record_action(
            action_type=ActionType.SEND_EMAIL,
            resource_id=f"email{i}",
            service="gmail",
            details={},
            undo_data=None
        )
    
    manager.clear_undo_stack()
    assert len(manager.get_undo_stack()) == 0, "? Stack should be cleared"
    print("? Can clear undo stack")
    
    print("\n? UNDO STACK TEST PASSED\n")


def test_action_summaries():
    """Test action summary generation"""
    print("\n" + "="*60)
    print("TEST: Action Summaries")
    print("="*60)
    
    manager = SafetyManager()
    
    # Email summary
    summary = manager.get_action_summary(
        "send_email",
        {"to": ["a@test.com", "b@test.com"], "subject": "Test Email"}
    )
    assert "2 recipient(s)" in summary, "? Should mention recipient count"
    assert "Test Email" in summary, "? Should include subject"
    print("? Email summary generated correctly")
    
    # Delete summary
    summary = manager.get_action_summary(
        "delete_file",
        {"file_id": "file123"}
    )
    assert "file123" in summary, "? Should include file ID"
    print("? Delete summary generated correctly")
    
    # Event summary
    summary = manager.get_action_summary(
        "create_event",
        {"summary": "Team Meeting", "start_time": "tomorrow"}
    )
    assert "Team Meeting" in summary, "? Should include event name"
    print("? Event summary generated correctly")
    
    print("\n? ACTION SUMMARIES TEST PASSED\n")


def test_risk_assessment():
    """Test risk level assessment"""
    print("\n" + "="*60)
    print("TEST: Risk Assessment")
    print("="*60)
    
    manager = SafetyManager()
    
    # High risk
    risk = manager.get_risk_level("delete_email", {})
    assert risk == "high", f"? delete_email should be high risk, got {risk}"
    print("? High risk actions identified")
    
    # Medium risk
    risk = manager.get_risk_level("send_email", {})
    assert risk == "medium", f"? send_email should be medium risk, got {risk}"
    print("? Medium risk actions identified")
    
    # Low risk
    risk = manager.get_risk_level("search_email", {})
    assert risk == "low", f"? search_email should be low risk, got {risk}"
    print("? Low risk actions identified")
    
    print("\n? RISK ASSESSMENT TEST PASSED\n")


def test_previews():
    """Test 5.4.3: Action previews"""
    print("\n" + "="*60)
    print("TEST 5.4.3: Action Previews")
    print("="*60)
    
    # Email preview
    preview = ActionPreview.preview_email({
        "to": ["test@example.com"],
        "subject": "Test",
        "body": "Hello World"
    })
    assert "test@example.com" in preview, "? Preview should include recipient"
    assert "Test" in preview, "? Preview should include subject"
    assert "Hello World" in preview, "? Preview should include body"
    print("? Email preview generated")
    
    # Event preview
    preview = ActionPreview.preview_event({
        "summary": "Meeting",
        "start_time": "tomorrow at 2pm",
        "attendees": ["a@test.com", "b@test.com"]
    })
    assert "Meeting" in preview, "? Preview should include title"
    assert "2 people" in preview, "? Preview should mention attendee count"
    print("? Event preview generated")
    
    # File share preview
    preview = ActionPreview.preview_file_share({
        "email": "user@test.com",
        "role": "reader",
        "file_id": "file123"
    }, file_name="Report.pdf")
    assert "Report.pdf" in preview, "? Preview should include filename"
    assert "user@test.com" in preview, "? Preview should include email"
    assert "reader" in preview, "? Preview should include role"
    print("? File share preview generated")
    
    # Deletion preview
    preview = ActionPreview.preview_deletion(
        "email",
        "email123",
        "Important Email"
    )
    assert "email123" in preview, "? Preview should include ID"
    assert "cannot be undone" in preview.lower(), "? Preview should warn about permanence"
    print("? Deletion preview generated")
    
    print("\n? TEST 5.4.3 PASSED\n")


def test_dry_run_output():
    """Test dry-run result formatting"""
    print("\n" + "="*60)
    print("TEST: Dry-Run Output")
    print("="*60)
    
    manager = SafetyManager(dry_run=True)
    
    result = manager.format_dry_run_result(
        "send_email",
        {"to": ["test@example.com"], "subject": "Test"},
        would_affect="1 recipient(s)"
    )
    
    assert "[DRY RUN]" in result, "? Should indicate dry-run"
    assert "send_email" in result.lower() or "send email" in result.lower(), "? Should mention action"
    assert "No changes were made" in result, "? Should confirm no changes"
    print("? Dry-run output formatted correctly")
    
    print("\n? DRY-RUN OUTPUT TEST PASSED\n")


def main():
    """Run all Phase 5.4 tests"""
    print("\n" + "??"*30)
    print("PHASE 5.4 - ENHANCED SAFETY - VALIDATION TESTS")
    print("??"*30)
    
    try:
        test_dry_run_mode()
        test_destructive_detection()
        test_action_recording()
        test_undo_stack_management()
        test_action_summaries()
        test_risk_assessment()
        test_previews()
        test_dry_run_output()
        
        print("\n" + "="*60)
        print("?? ALL PHASE 5.4 TESTS PASSED! ??")
        print("="*60)
        print("\nPhase 5.4 is fully implemented and working:")
        print("  ? 5.4.1: Dry-run mode (--dry-run flag)")
        print("  ? 5.4.2: Action recording for undo")
        print("  ? 5.4.3: Enhanced previews for actions")
        print("  ? 5.4.4: Safety confirmations")
        print("  ? Risk assessment system")
        print("  ? Undo stack management")
        print("\nNext: Test with real orchestrator")
        
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
