# GitHub Error Reporter

Utility to automatically publish github issues when errors occur in python scripts.

- creates template-based issues
- avoids duplicates
- allows custom labeling

## Install
```bash
poetry add github-error-reporter
```

## Set token and repo

First you need to create a fine-grained-token. Go to GitHub Settings → Developer Settings → Personal Access Tokens
- repository: read and write
- issues: read and write

```bash
# avoid publishing of secrets:
nano .gitignore
# add .env
git add .gitignore
git commit -m '.env'

nano .env
#GITHUB_TOKEN=
#GITHUB_REPO=USERNAME/REPO_NAME
```

## Use the decorator

```python
from github_error_reporter import report_on_error

@report_on_error(labels=["parsing", "data"])
def parse_file(filepath):
    with open(filepath) as f:
        return json.load(f)

# If parse_file() raises an exception, a GitHub issue is created automatically
parse_file("data.json")
```

## or use `ErrorReporter` directly

```python
from github_error_reporter import ErrorReporter

reporter = ErrorReporter()

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

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub personal access token | Required (unless `local_mode=true`) |
| `GITHUB_REPO` | Repository in format `owner/repo` | Required (unless `local_mode=true`) |
| `ERROR_REPORTER_LOCAL_MODE` | Save reports locally instead of GitHub | `false` |
| `ERROR_REPORTER_DIR` | Directory for local reports | `error_reports` |
| `ERROR_REPORTER_DEDUPLICATE` | Prevent duplicate issues | `true` |
| `ERROR_REPORTER_INCLUDE_ENV` | Include Python/OS environment info | `true` |
| `ERROR_REPORTER_INCLUDE_GIT` | Include git branch/commit info | `true` |


In your code you can use:

```python
from github_error_reporter import ErrorReporter, Config

config = Config(
    github_token="ghp_xxx",
    github_repo="owner/repo",
    local_mode=False,
    error_reports_dir="error_reports",
    deduplicate_issues=True,
    include_environment_info=True,
    include_git_info=True,
)

reporter = ErrorReporter(config=config)
```

## Examples

### Example 1: Simple Error Reporting

```python
from github_error_reporter import report_on_error

@report_on_error(labels=["api", "external"])
def fetch_user_data(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    response.raise_for_status()
    return response.json()

# If this fails, a GitHub issue is created with the traceback
fetch_user_data(123)
```

### Example 2: With Custom Context

```python
from github_error_reporter import report_on_error
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
from github_error_reporter import ErrorReporter

reporter = ErrorReporter()

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
from github_error_reporter import report_on_assert

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
from github_error_reporter import report_on_error

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
from github_error_reporter import ErrorReporter, Config

# Test locally without GitHub
config = Config(local_mode=True)
reporter = ErrorReporter(config=config)

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

### `ErrorReporter`

Main class for error reporting.

```python
reporter = ErrorReporter(config=None, console=None, github_token=None, github_repo=None, local_mode=None)

# Report an error
issue_url = reporter.report_error(
    exception=Exception(...),
    title="Issue Title",
    context={"key": "value"},
    labels=["label1", "label2"],
)
```

**Returns:**
- GitHub issue URL if created successfully
- Local file path if saved locally
- `None` if failed

### `Config`

Configuration dataclass.

```python
from github_error_reporter import Config

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
    github_token="ghp_xxx",
    github_repo="owner/repo",
    local_mode=False,
    error_reports_dir="error_reports",
)

# Validate
config.validate()  # Raises ValueError if invalid
```

## Testing

### Test Locally Without GitHub

```python
from github_error_reporter import ErrorReporter, Config

config = Config(local_mode=True)
reporter = ErrorReporter(config=config)

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

### Test with Mock GitHub API

```python
from unittest.mock import patch
from github_error_reporter import ErrorReporter

with patch('requests.post') as mock_post:
    mock_post.return_value.status_code = 201
    mock_post.return_value.json.return_value = {
        "number": 123,
        "html_url": "https://github.com/owner/repo/issues/123",
    }
    
    reporter = ErrorReporter()
    try:
        1 / 0
    except Exception as e:
        reporter.report_error(
            exception=e,
            title="Test",
            labels=["test"],
        )
    
    assert mock_post.called
```

## Troubleshooting

### "GitHub token and repo are required"

Check .env

```bash
nano .env
GITHUB_TOKEN="ghp_xxx"
GITHUB_REPO="owner/repo"
```

### Issues are created but not appearing

Check that:
1. GitHub token is valid and has `repo` + `issues` scopes
2. Repository exists and is accessible
3. No duplicate issue exists (deduplication is enabled by default)

### Want to test locally first?

```python
config = Config(local_mode=True)
reporter = ErrorReporter(config=config)
```

Reports will be saved to `error_reports/` instead of GitHub.

---

## License

MIT License. See LICENSE