"""Example 2: Decorator-based error reporting with mixed labels"""
import sys
from git_issue_reporter.decorators import report_on_error
import requests

def get_context():
    """Provide dynamic context for the error."""
    return {
        "endpoint": "/api/v1/users",
        "method": "GET",
        "status_code": 500,
        "response_time": "2.5s",
        "timestamp": "2026-03-24T10:30:00Z",
    }

@report_on_error(
    title="API Request Error: {func_name}",
    labels=["automated-error", "example", "api", "external-service", "high-priority"],
    context_fn=get_context,
)
def fetch_user_data(user_id: int):
    """Simulate an API request that fails."""
    response = requests.get(f"https://api.example.com/users/{user_id}")
    response.raise_for_status()
    return response.json()

# Test the decorator
if __name__ == "__main__":
    try:
        # This will fail and automatically create a GitHub issue
        fetch_user_data(12345)
    except Exception as e:
        print(f"✓ Error was caught and reported by decorator")
