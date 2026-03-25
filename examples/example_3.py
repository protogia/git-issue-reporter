"""Example 3: Database error with custom labels"""
from git_issue_reporter.core import IssueReporter

reporter = IssueReporter()

# Simulate a database connection error
try:
    import psycopg2
    conn = psycopg2.connect("dbname=nonexistent user=postgres")
except ImportError:
    # Fallback: simulate the error manually
    raise ConnectionError("Failed to connect to PostgreSQL database on localhost:3222")
except Exception as e:
    context = {
        "database": "production_db",
        "host": "localhost",
        "port": 3222,
        "environment": "staging",
        "retry_count": 3,
    }
    
    issue_url = reporter.report_error(
        exception=e,
        title="Database Connection Error: PostgreSQL Production DB",
        context=context,
        labels=["automated-error", "example", "database", "critical", "postgres"],  # Custom labels
    )
    
    print(f"\n✓ Issue created: {issue_url}")
