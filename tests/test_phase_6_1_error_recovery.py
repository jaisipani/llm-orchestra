"""Test script for Phase 6.1: Error Recovery

This script validates that:
1. Retry logic with exponential backoff works
2. Error detection is correct
3. Quota tracking functions
4. Error recovery provides helpful messages
"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.resilience import (
    RetryConfig,
    QuotaTracker,
    retry_with_backoff,
    is_retryable_error,
    get_friendly_error_message,
    ErrorRecovery
)
from googleapiclient.errors import HttpError
from unittest.mock import Mock


def test_retry_config():
    """Test 6.1.1: Retry configuration"""
    print("\n" + "="*60)
    print("TEST 6.1.1: Retry Configuration")
    print("="*60)
    
    config = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0
    )
    
    # Test delay calculation
    delay0 = config.get_delay(0)
    delay1 = config.get_delay(1)
    delay2 = config.get_delay(2)
    
    assert delay0 < delay1 < delay2, "? Delays should increase exponentially"
    print(f"? Exponential backoff: {delay0:.2f}s -> {delay1:.2f}s -> {delay2:.2f}s")
    
    # Test max delay
    delay_large = config.get_delay(10)
    assert delay_large <= config.max_delay, "? Delay should not exceed max"
    print(f"? Max delay enforced: {delay_large:.2f}s <= {config.max_delay}s")
    
    print("\n? TEST 6.1.1 PASSED\n")


def test_retry_decorator():
    """Test 6.1.2: Retry decorator"""
    print("\n" + "="*60)
    print("TEST 6.1.2: Retry Decorator")
    print("="*60)
    
    # Test successful function
    attempt_count = [0]
    
    @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.1))
    def successful_func():
        attempt_count[0] += 1
        return "success"
    
    result = successful_func()
    assert result == "success", "? Should return success"
    assert attempt_count[0] == 1, "? Should only call once"
    print("? Successful function executes once")
    
    # Test function that fails then succeeds
    fail_count = [0]
    
    @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.1))
    def eventually_successful():
        fail_count[0] += 1
        if fail_count[0] < 2:
            # Create mock HttpError
            resp = Mock()
            resp.status = 500
            raise HttpError(resp, b'Server error')
        return "success"
    
    result = eventually_successful()
    assert result == "success", "? Should succeed after retry"
    assert fail_count[0] == 2, f"? Should try twice, tried {fail_count[0]}"
    print("? Function retries on failure and succeeds")
    
    # Test function that always fails
    always_fail_count = [0]
    
    @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.1))
    def always_fails():
        always_fail_count[0] += 1
        resp = Mock()
        resp.status = 500
        raise HttpError(resp, b'Server error')
    
    try:
        always_fails()
        assert False, "? Should have raised exception"
    except HttpError:
        pass
    
    assert always_fail_count[0] == 3, f"? Should try 3 times, tried {always_fail_count[0]}"
    print("? Function retries max times then fails")
    
    print("\n? TEST 6.1.2 PASSED\n")


def test_error_detection():
    """Test 6.1.3: Retryable error detection"""
    print("\n" + "="*60)
    print("TEST 6.1.3: Error Detection")
    print("="*60)
    
    # Test retryable HTTP errors
    resp_500 = Mock()
    resp_500.status = 500
    error_500 = HttpError(resp_500, b'Server error')
    assert is_retryable_error(error_500), "? 500 should be retryable"
    print("? HTTP 500 detected as retryable")
    
    resp_429 = Mock()
    resp_429.status = 429
    error_429 = HttpError(resp_429, b'Rate limit')
    assert is_retryable_error(error_429), "? 429 should be retryable"
    print("? HTTP 429 (rate limit) detected as retryable")
    
    # Test non-retryable HTTP errors
    resp_400 = Mock()
    resp_400.status = 400
    error_400 = HttpError(resp_400, b'Bad request')
    assert not is_retryable_error(error_400), "? 400 should not be retryable"
    print("? HTTP 400 detected as non-retryable")
    
    resp_404 = Mock()
    resp_404.status = 404
    error_404 = HttpError(resp_404, b'Not found')
    assert not is_retryable_error(error_404), "? 404 should not be retryable"
    print("? HTTP 404 detected as non-retryable")
    
    # Test connection errors
    conn_error = ConnectionError("Network error")
    assert is_retryable_error(conn_error), "? ConnectionError should be retryable"
    print("? Connection errors detected as retryable")
    
    print("\n? TEST 6.1.3 PASSED\n")


def test_friendly_error_messages():
    """Test 6.1.4: Friendly error messages"""
    print("\n" + "="*60)
    print("TEST 6.1.4: Friendly Error Messages")
    print("="*60)
    
    # Test HTTP error messages
    resp_401 = Mock()
    resp_401.status = 401
    error_401 = HttpError(resp_401, b'Unauthorized')
    msg = get_friendly_error_message(error_401)
    assert "auth" in msg.lower(), "? Should mention authentication"
    print(f"? 401 error: {msg}")
    
    resp_404 = Mock()
    resp_404.status = 404
    error_404 = HttpError(resp_404, b'Not found')
    msg = get_friendly_error_message(error_404)
    assert "not found" in msg.lower(), "? Should mention not found"
    print(f"? 404 error: {msg}")
    
    resp_429 = Mock()
    resp_429.status = 429
    error_429 = HttpError(resp_429, b'Rate limit')
    msg = get_friendly_error_message(error_429)
    assert "rate limit" in msg.lower() or "wait" in msg.lower(), "? Should mention rate limit"
    print(f"? 429 error: {msg}")
    
    # Test connection error
    conn_error = ConnectionError("Connection failed")
    msg = get_friendly_error_message(conn_error)
    assert "network" in msg.lower() or "connection" in msg.lower(), "? Should mention network"
    print(f"? Connection error: {msg}")
    
    print("\n? TEST 6.1.4 PASSED\n")


def test_quota_tracking():
    """Test 6.1.5: Quota tracking"""
    print("\n" + "="*60)
    print("TEST 6.1.5: Quota Tracking")
    print("="*60)
    
    tracker = QuotaTracker()
    
    # Record requests
    tracker.record_request('gmail', cost=100)
    tracker.record_request('gmail', cost=50)
    tracker.record_request('calendar', cost=10)
    
    assert tracker.usage['gmail'] == 150, "? Gmail usage should be 150"
    assert tracker.usage['calendar'] == 10, "? Calendar usage should be 10"
    print("? Quota usage tracked correctly")
    
    # Check quota
    has_quota, usage_pct = tracker.check_quota('gmail')
    assert has_quota, "? Should have quota available"
    assert usage_pct < 1.0, "? Usage should be minimal"
    print(f"? Quota check works: {usage_pct:.6f}% used")
    
    # Test high usage warning
    tracker.usage['drive'] = int(tracker.daily_limits['drive'] * 0.96)
    has_quota, usage_pct = tracker.check_quota('drive')
    assert not has_quota, "? Should warn at 95%"
    assert usage_pct > 95.0, "? Usage should be over 95%"
    print(f"? High usage warning triggered: {usage_pct:.1f}%")
    
    print("\n? TEST 6.1.5 PASSED\n")


def test_error_recovery():
    """Test 6.1.6: Error recovery tracking"""
    print("\n" + "="*60)
    print("TEST 6.1.6: Error Recovery")
    print("="*60)
    
    recovery = ErrorRecovery()
    
    # Record errors
    resp_500 = Mock()
    resp_500.status = 500
    error1 = HttpError(resp_500, b'Server error')
    recovery.record_error(error1, context="send_email")
    
    error2 = ValueError("Invalid input")
    recovery.record_error(error2, context="parse_parameters")
    
    assert len(recovery.last_errors) == 2, "? Should have 2 errors recorded"
    print("? Errors recorded correctly")
    
    # Get error stats
    stats = recovery.get_error_stats()
    assert stats['HttpError'] == 1, "? Should have 1 HttpError"
    assert stats['ValueError'] == 1, "? Should have 1 ValueError"
    print(f"? Error stats: {stats}")
    
    # Get summary
    summary = recovery.get_error_summary()
    assert "2" in summary or "two" in summary.lower(), "? Summary should mention 2 errors"
    print(f"? Error summary generated")
    
    # Test suggestions
    resp_401 = Mock()
    resp_401.status = 401
    error_401 = HttpError(resp_401, b'Unauthorized')
    suggestion = recovery.suggest_action(error_401)
    assert suggestion is not None, "? Should suggest action for 401"
    assert "--auth" in suggestion, "? Should suggest re-authentication"
    print(f"? Action suggested: {suggestion}")
    
    # Clear history
    recovery.clear_history()
    assert len(recovery.last_errors) == 0, "? History should be cleared"
    print("? Error history cleared")
    
    print("\n? TEST 6.1.6 PASSED\n")


def main():
    """Run all Phase 6.1 tests"""
    print("\n" + "??"*30)
    print("PHASE 6.1 - ERROR RECOVERY - VALIDATION TESTS")
    print("??"*30)
    
    try:
        test_retry_config()
        test_retry_decorator()
        test_error_detection()
        test_friendly_error_messages()
        test_quota_tracking()
        test_error_recovery()
        
        print("\n" + "="*60)
        print("?? ALL PHASE 6.1 TESTS PASSED! ??")
        print("="*60)
        print("\nPhase 6.1 is fully implemented and working:")
        print("  ? 6.1.1: Retry logic with exponential backoff")
        print("  ? 6.1.2: Retry decorator for services")
        print("  ? 6.1.3: Retryable error detection")
        print("  ? 6.1.4: Friendly error messages")
        print("  ? 6.1.5: API quota tracking")
        print("  ? 6.1.6: Error recovery and suggestions")
        print("\nNext: Integrate with all services and test live")
        
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
