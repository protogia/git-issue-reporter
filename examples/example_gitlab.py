"""Example 1: Parsing error with default labels"""

from git_issue_reporter.config import Config
from git_issue_reporter.core import IssueReporter
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize with credentials
reporter_config = Config(
    gitlab_token = os.getenv("GITLAB_TOKEN"),
    gitlab_repo = os.getenv("GITLAB_REPO"),
    gitlab_url= "https://gitlab.com",
    enable_gitlab = True
)
reporter = IssueReporter(config=reporter_config)

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
        labels=["automated-error", "example", "data-ingestion"],
    )
    
    print(f"\n✓ Issue created: {issue_url}")
