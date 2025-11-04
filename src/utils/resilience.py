import time
import functools
from typing import Callable, Any, Optional, Type, Tuple
from datetime import datetime, timedelta

from googleapiclient.errors import HttpError

from src.utils.logger import logger

class RetryConfig:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    def get_delay(self, attempt: int) -> float:
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay

class QuotaTracker:
    def __init__(self):
        self.daily_limits = {
            'gmail': 1000000000,  # Gmail API daily quota
            'calendar': 1000000,   # Calendar API daily quota
            'drive': 1000000000    # Drive API daily quota
        }
        self.usage = {
            'gmail': 0,
            'calendar': 0,
            'drive': 0
        }
        
        self.reset_time = datetime.now() + timedelta(days=1)
    
    def record_request(self, service: str, cost: int = 1) -> None:
        if service in self.usage:
            self.usage[service] += cost
            logger.debug(f"API usage: {service} = {self.usage[service]}/{self.daily_limits[service]}")
    def check_quota(self, service: str) -> Tuple[bool, float]:
        if service not in self.usage:
            return (True, 0.0)
        usage_pct = (self.usage[service] / self.daily_limits[service]) * 100
        has_quota = usage_pct < 95.0
        
        return (has_quota, usage_pct)
    
    def reset_if_needed(self) -> None:
        if datetime.now() >= self.reset_time:
            self.usage = {k: 0 for k in self.usage}
            self.reset_time = datetime.now() + timedelta(days=1)
            logger.info("API quota counters reset")

def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (HttpError,)
):
    if config is None:
        config = RetryConfig()
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if not is_retryable_error(e):
                        logger.warning(f"{func.__name__} failed with non-retryable error: {e}")
                        raise
                    
                    if attempt == config.max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {config.max_attempts} attempts")
                        raise
                    
                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                
                except Exception as e:
                    logger.error(f"{func.__name__} failed with unexpected error: {e}")
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator

def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, HttpError):
        status_code = error.resp.status
        if status_code in [500, 502, 503, 504]:
            return True
        
        if status_code == 429:
            return True
        
        if 400 <= status_code < 500:
            return False
    
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    
    error_msg = str(error).lower()
    retryable_patterns = [
        'timeout',
        'connection',
        'network',
        'unavailable',
        'try again'
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_msg:
            return True
    
    return False

def get_friendly_error_message(error: Exception) -> str:
    if isinstance(error, HttpError):
        status_code = error.resp.status
        if status_code == 400:
            return "Invalid request. Please check your parameters."
        elif status_code == 401:
            return "Authentication failed. Please run with --auth to re-authenticate."
        elif status_code == 403:
            return "Permission denied. You may not have access to this resource."
        elif status_code == 404:
            return "Resource not found. It may have been deleted or moved."
        elif status_code == 429:
            return "Rate limit exceeded. Please wait a moment and try again."
        elif status_code == 500:
            return "Google API server error. This is temporary - please try again."
        elif status_code == 503:
            return "Service temporarily unavailable. Please try again in a few moments."
        else:
            return f"API error (code {status_code}). Please try again or check your request."
    
    elif isinstance(error, ConnectionError):
        return "Network connection error. Please check your internet connection."
    
    elif isinstance(error, TimeoutError):
        return "Request timed out. Please try again."
    
    elif isinstance(error, KeyError):
        return f"Missing required field: {str(error)}"
    
    elif isinstance(error, ValueError):
        return f"Invalid value: {str(error)}"
    
    else:
        error_type = type(error).__name__
        return f"{error_type}: {str(error)}"

class ErrorRecovery:
    def __init__(self):
        self.quota_tracker = QuotaTracker()
        self.error_counts = {}
        self.last_errors = []
        self.max_error_history = 10
    def record_error(self, error: Exception, context: str = "") -> None:
        error_type = type(error).__name__
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        self.last_errors.append({
            'error': error,
            'type': error_type,
            'context': context,
            'timestamp': datetime.now(),
            'message': str(error)
        })
        
        if len(self.last_errors) > self.max_error_history:
            self.last_errors.pop(0)
        
        logger.debug(f"Error recorded: {error_type} in {context}")
    
    def get_error_summary(self) -> str:
        if not self.last_errors:
            return "No recent errors"
        summary = f"Recent errors ({len(self.last_errors)}):\n"
        
        for i, err_info in enumerate(self.last_errors[-5:], 1):
            time_str = err_info['timestamp'].strftime("%H:%M:%S")
            summary += f"  {i}. [{time_str}] {err_info['type']}: {err_info['message'][:50]}\n"
        
        return summary
    
    def get_error_stats(self) -> dict:
        return self.error_counts.copy()
    def clear_history(self) -> None:
        self.last_errors.clear()
        self.error_counts.clear()
        logger.debug("Error history cleared")
    def suggest_action(self, error: Exception) -> Optional[str]:
        if isinstance(error, HttpError):
            status_code = error.resp.status
            if status_code == 401:
                return "Try: python -m src.main --auth"
            elif status_code == 429:
                return "Wait a few minutes before trying again"
            elif status_code == 403:
                return "Check that you have granted necessary permissions"
            elif status_code >= 500:
                return "This is a temporary server issue. Try again in a moment."
        
        elif isinstance(error, ConnectionError):
            return "Check your internet connection and try again"
        
        return None

default_retry_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0
)

quota_tracker = QuotaTracker()
error_recovery = ErrorRecovery()
