"""Decorators for automatic error reporting."""
import functools
from typing import Any, Callable, List, Optional, Dict

from .core import IssueReporter
from .config import Config


def report_on_error(
    title: Optional[str] = None,
    labels: Optional[List[str]] = None,
    context_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    reraise: bool = True,
    config: Optional[Config] = None,
) -> Callable:
    """Decorator to automatically report function errors to GitHub.
    
    This decorator wraps a function and catches any exceptions, automatically
    creating a GitHub issue with the error details. The original exception is
    re-raised by default so your code flow isn't interrupted.
    
    Args:
        title: Issue title template. Can use {func_name}, {exception_type}, {exception_message}.
               If None, defaults to "Error in {func_name}".
        labels: GitHub issue labels to apply. Default: ["automated-error"].
        context_fn: Callable that returns a dict of context info. Called with the same
                    args/kwargs as the decorated function. If it raises an exception,
                    it's logged but doesn't prevent issue creation.
        reraise: If True (default), re-raises the exception after reporting.
                If False, exception is swallowed and None is returned.
        config: Config instance. If None, loads from environment.
    
    Returns:
        Decorated function that reports errors automatically.
    
    Examples:
        Basic usage:
        >>> @report_on_error(labels=["parsing", "data"])
        ... def parse_file(filepath):
        ...     with open(filepath) as f:
        ...         return json.load(f)
        
        With custom title and context:
        >>> def get_context(user_id, **kwargs):
        ...     return {"user_id": user_id, "timestamp": datetime.now()}
        >>> 
        >>> @report_on_error(
        ...     title="Failed to fetch user {exception_type}",
        ...     labels=["api", "critical"],
        ...     context_fn=get_context,
        ... )
        ... def fetch_user(user_id: int):
        ...     response = requests.get(f"https://api.example.com/users/{user_id}")
        ...     response.raise_for_status()
        ...     return response.json()
        
        Without re-raising (fail silently):
        >>> @report_on_error(reraise=False, labels=["non-critical"])
        ... def optional_task():
        ...     # If this fails, issue is created but execution continues
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                reporter = IssueReporter(config=config)
                
                # Build context
                context = {}
                if context_fn is not None:
                    try:
                        context = context_fn(*args, **kwargs)
                    except Exception as ctx_error:
                        reporter.console.print(
                            f"[yellow]⚠ Error in context_fn: {ctx_error}[/yellow]"
                        )
                
                # Build title
                issue_title = title or "Error in {func_name}"
                issue_title = issue_title.format(
                    func_name=func.__name__,
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )
                
                # Report error
                reporter.report_error(
                    exception=e,
                    title=issue_title,
                    context=context,
                    labels=labels or ["automated-error"],
                )
                
                # Re-raise or swallow
                if reraise:
                    raise
                return None
        
        return wrapper
    
    return decorator


def report_on_assert(
    title: Optional[str] = None,
    labels: Optional[List[str]] = None,
    context_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    config: Optional[Config] = None,
) -> Callable:
    """Decorator to report assertion failures as GitHub issues.
    
    Similar to report_on_error, but specifically catches AssertionError
    and creates issues with a specific label pattern.
    
    Args:
        title: Issue title template. Default: "Assertion Failed in {func_name}".
        labels: GitHub issue labels. Default: ["automated-error", "assertion"].
        context_fn: Callable that returns context dict.
        config: Config instance. If None, loads from environment.
    
    Returns:
        Decorated function.
    
    Example:
        >>> @report_on_assert(
        ...     labels=["test", "regression"],
        ...     context_fn=lambda: {"test_name": "test_user_creation"}
        ... )
        ... def validate_user(user):
        ...     assert user.email, "Email is required"
        ...     assert user.age >= 18, "User must be 18+"
    """
    return report_on_error(
        title=title or "Assertion Failed in {func_name}",
        labels=labels or ["automated-error", "assertion"],
        context_fn=context_fn,
        reraise=True,
        config=config,
    )