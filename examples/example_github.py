"""Example: Parsing error with default labels"""

from git_issue_reporter.config import Config
from git_issue_reporter.core import IssueReporter
from dotenv import load_dotenv
import os

load_dotenv()

# test with github

c = Config(
    local_mode=False,
    # github_repo=,
    # github_token=,
    )

reporter = IssueReporter(
)

# Simulate a data parsing error
try:
    data = '{"invalid json'
    parsed = eval(data)
except Exception as e:
    context = {
        "file_type": "JSON",
        "file_path": "/data/input.json",
        "season": "2026 Spring",
        "event": "Marathon",
        "session": "Qualifying Round",
    }
    
    issue_url = reporter.report_error(
        exception=e,
        title="Data Ingestion Error: JSON - Marathon (2026 Spring)",
        context=context,
        labels=["automated-error", "example", "data-ingestion"],  # Default labels
    )
    
    print(f"\n✓ Issue created: {issue_url}")
