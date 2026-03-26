# git-issue-reporter

Utility to automatically publish issues when errors occur in python scripts.

- allows publishing to GitHub and GitLab
- allows template-based issues
- avoids and indicates duplicates
- allows custom labeling

## Install
```bash
poetry add git+https://github.com/protogia/git-issue-repoter
```

## Set token and repo

First you need to create a fine-grained-token. 

_For Github:_
Go to Settings → Developer Settings → Personal Access Tokens
- repository: read and write
- issues: read and write

_For Gitlab:_
In you project go to Settings →  Access Tokens
- role: Guest
- scopes: api 

```bash
# avoid publishing of secrets:
nano .gitignore
# add .env
git add .gitignore
git commit -m '.env'

nano .env
#GITHUB_TOKEN=
#GITHUB_REPO=USERNAME/REPO_NAME

#GITLAB_TOKEN=
#GITLAB_REPO=USERNAME/REPO_NAME
```

## Use the decorator

```python
from git_issue_reporter import report_on_error

@report_on_error(labels=["parsing", "data"])
def parse_file(filepath):
    with open(filepath) as f:
        return json.load(f)

# If parse_file() raises an exception, an issue is created automatically
parse_file("data.json")
```

## or use `IssueReporter` directly

```python
from git_issue_reporter import IssueReporter

reporter = IssueReporter()

try:
    result = risky_operation()
except Exception as e:
    reporter.report_error(
        exception=e,
        title="Data Processing Failed",
        context={"file": "data.json", "operation": "parse"},
        labels=["error", "data-pipeline"],
    )
```

## Configuration

| Environment Variable | Config Property | Default |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | `github_token` | `None` |
| `GITHUB_REPO` | `github_repo` | `None` |
| `ENABLE_GITHUB` | `enable_github` | `true` |
| `GITLAB_TOKEN` | `gitlab_token` | `None` |
| `GITLAB_REPO` | `gitlab_repo` | `None` |
| `GITLAB_URL` | `gitlab_url` | `https://gitlab.com` |
| `ENABLE_GITLAB` | `enable_gitlab` | `false` |
| `ERROR_REPORTER_LOCAL_MODE` | `local_mode` | `false` |
| `ERROR_REPORTER_DIR` | `error_reports_dir` | `error_reports` |
| `ERROR_REPORTER_DEDUPLICATE` | `deduplicate_issues` | `true` |
| `ISSUE_TEMPLATE` | `issue_template` | `None` |

In your code you can use for specific configuration:

```python
from git_issue_reporter import IssueReporter, Config

config = Config(
    github_token="ghp_xxx",
    github_repo="owner/repo",
    gitlab_token="ghp_xxx",
    gitlab_repo="owner/repo",
    local_mode=False,
    error_reports_dir="error_reports",
    deduplicate_issues=True,
    include_environment_info=True,
)

reporter = IssueReporter(config=config)
```

## Examples

### Example 1: Simple Error Reporting

```python
from git_issue_reporter.decorators import report_on_error

@report_on_error(labels=["api", "external"])
def fetch_user_data(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    response.raise_for_status()
    return response.json()

# If this fails, a GitHub/GitLab issue is created with the traceback
fetch_user_data(123)
```

### Example 2: With Custom Context

```python
from git_issue_reporter.decorators import report_on_error
from datetime import datetime

def get_context(user_id, **kwargs):
    return {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "environment": "production",
    }

@report_on_error(
    title="Failed to fetch user {exception_type}",
    labels=["api", "critical"],
    context_fn=get_context,
)
def fetch_user(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    response.raise_for_status()
    return response.json()

fetch_user(123)
```

### Example 3: Data Pipeline with Manual Reporting

```python
from git_issue_reporter.core import IssueReporter

reporter = IssueReporter()

def process_data_file(filepath):
    try:
        with open(filepath) as f:
            data = json.load(f)
        # ... process data
    except Exception as e:
        reporter.report_error(
            exception=e,
            title=f"Data Processing Error: {filepath}",
            context={
                "file": filepath,
                "file_size": os.path.getsize(filepath),
                "format": "json",
            },
            labels=["data-pipeline", "ingestion"],
        )
        raise

for file in glob.glob("data/*.json"):
    process_data_file(file)
```

### Example 4: Assertion Monitoring

```python
from git_issue_reporter.decorators import report_on_assert

@report_on_assert(
    labels=["test", "validation"],
    context_fn=lambda: {"environment": "staging"},
)
def validate_user(user):
    assert user.email, "Email is required"
    assert user.age >= 18, "User must be 18+"
    assert len(user.name) > 0, "Name cannot be empty"

validate_user(user)  # Creates issue if any assertion fails
```

### Example 5: Silent Failure (No Re-raise)

```python
from git_issue_reporter.decorators import report_on_error

@report_on_error(
    labels=["optional", "non-critical"],
    reraise=False,  # Don't re-raise the exception
)
def optional_cleanup():
    # If this fails, issue is created but execution continues
    pass

optional_cleanup()
print("This still runs even if optional_cleanup() fails")
```

### Example 6: Local Testing

```python
from git_issue_reporter.core import IssueReporter
from git_issue_reporter.config import Config

# Test locally without GitHub/GitLab
config = Config(local_mode=True)
reporter = IssueReporter(config=config)

try:
    1 / 0
except Exception as e:
    reporter.report_error(
        exception=e,
        title="Test Error",
        labels=["test"],
    )
    # Check error_reports/ directory for saved file
```

## Decorator Reference

### `@report_on_error()`

Catches any exception and creates a GitHub issue.

**Parameters:**
- `title` (str, optional): Issue title. Supports template variables: `{func_name}`, `{exception_type}`, `{exception_message}`
- `labels` (list, optional): GitHub labels. Default: `["automated-error"]`
- `context_fn` (callable, optional): Function that returns a dict of context. Called with the same args/kwargs as the decorated function
- `reraise` (bool): Re-raise the exception after reporting. Default: `True`
- `config` (Config, optional): Custom configuration

**Returns:**
- Original return value if no exception
- `None` if exception and `reraise=False`
- Re-raises exception if `reraise=True`

### `@report_on_assert()`

Catches `AssertionError` specifically.

**Parameters:**
- Same as `@report_on_error()`, but defaults to `labels=["automated-error", "assertion"]`

---

## API Reference

### `IssueReporter`

Main class for error reporting.

```python
reporter = IssueReporter(config=None, console=None, destination_token=None, repo=None, local_mode=None)

# Report an error
issue_url = reporter.report_error(
    exception=Exception(...),
    title="Issue Title",
    context={"key": "value"},
    labels=["label1", "label2"],
)
```

**Returns:**
- Issue URL if created successfully
- Local file path if saved locally
- `None` if failed

### `Config`

Configuration dataclass.

```python
from git_issue_reporter import Config

# Load from environment
config = Config.from_env()

# Load from dict
config = Config.from_dict({
    "github_token": "ghp_xxx",
    "github_repo": "owner/repo",
    "local_mode": False,
})

# Create manually
config = Config(
    gitlab_token="ghp_xxx",
    gitlab_repo="owner/repo",
    local_mode=False,
    error_reports_dir="error_reports",
)

# Validate
config.validate()  # Raises ValueError if invalid
```

## Testing

### Test Locally Without GitHub/GitLab

```python
from git_issue_reporter import IssueReporter, Config

config = Config(local_mode=True)
reporter = IssueReporter(config=config)

try:
    1 / 0
except Exception as e:
    reporter.report_error(
        exception=e,
        title="Test Error",
        labels=["test"],
    )

# Check error_reports/ directory
```

## Troubleshooting

### "Token and repo are required"

Check .env

```bash
nano .env
GITHUB_TOKEN="ghp_xxx"
GITHUB_REPO="owner/repo"
```

### Issues are created but not appearing

Check that:
1. GitHub/GitLab token is valid and has `repo` + `issues` scopes
2. Repository exists and is accessible
3. No duplicate issue exists (deduplication is enabled by default)