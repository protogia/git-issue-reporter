"""Decorators for automatic error reporting."""
import functools
from typing import Any, Callable, List, Optional, Dict

from .core import IssueReporter
from .config import Config


def report_on_error(
    title: Optional[str] = None,
    labels: Optional[List[str]] = None,
    context_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    template: Optional[str] = None,
    reraise: bool = True,
    config: Optional[Config] = None,
) -> Callable:
    """Decorator to automatically report function errors to GitHub.

    Adds optional support for selecting a GitHub issue template.

    Args:
        title: Issue title template. Supports:
               {func_name}, {exception_type}, {exception_message}.
        labels: GitHub issue labels.
        context_fn: Callable returning a dict of context info.
        template: Optional template filename (e.g. "bug_report.md").
                  Overrides config.issue_template for this decorator.
        reraise: If True, re-raises the exception after reporting.
        config: Config instance. If None, loads from environment.

    Returns:
        Decorated function that reports errors automatically.

    Notes:
        - Template variables are populated from the standard rendering context
          (exception, traceback, context, env, git).
        - No additional template-specific injection is performed.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)

            except Exception as e:
                reporter_config = config or Config.from_env()
                reporter = IssueReporter(config=reporter_config)
                if template:
                    reporter.config.issue_template = template
                
                # Build context
                context: Dict[str, Any] = {}
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
                results = reporter.report_error(
                    exception=e,
                    title=issue_title,
                    context=context,
                    labels=labels or ["automated-error"],
                )

                if results:
                    summary = ", ".join([f"{k}: {v}" for k, v in results.items()])
                    reporter.console.print(f"[green]Reported to: {summary}[/green]")

                if reraise:
                    raise

                return None

        return wrapper

    return decorator


def report_on_assert(
    title: Optional[str] = None,
    labels: Optional[List[str]] = None,
    context_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    template: Optional[str] = None,
    config: Optional[Config] = None,
) -> Callable:
    """Decorator to report assertion failures as GitHub issues.

    Args:
        title: Issue title template.
        labels: GitHub issue labels.
        context_fn: Callable returning context dict.
        template: Optional template filename override.
        config: Config instance.

    Returns:
        Decorated function.
    """
    return report_on_error(
        title=title or "Assertion Failed in {func_name}",
        labels=labels or ["automated-error", "assertion"],
        context_fn=context_fn,
        template=template,
        reraise=True,
        config=config,
    )