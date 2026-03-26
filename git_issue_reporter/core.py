"""Core error reporting functionality."""
import hashlib
import json
import os
import platform
import subprocess
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import re
import requests
import urllib
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Config

class IssueReporter:
    def __init__(self, config: Optional[Config] = None, console: Optional[Console] = None):
        self.config = config or Config.from_env()
        self.config.validate()
        self.console = console or Console()
        self._issue_cache = {}

    def report_error(self, exception: Exception, title: str, context: Optional[Dict] = None, labels: Optional[List] = None) -> Dict[str, str]:
        """Reports to all enabled providers. Returns dict of {provider: result_url}."""
        results = {}
        tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        body = self._format_issue_body(exception, tb_str, context)
        
        # Fallback
        if self.config.local_mode:
            path = self._save_locally(title, body)
            return {"local": path}

        # GitHub
        if self.config.enable_github and self.config.github_token:
            res = self._create_github_issue(title, body, labels or ["automated-error"])
            if res: results["github"] = res

        # GitLab
        if self.config.enable_gitlab and self.config.gitlab_token:
            res = self._create_gitlab_issue(title, body, labels or ["automated-error"])
            if res: results["gitlab"] = res

        return results


    def _create_gitlab_issue(self, title: str, body: str, labels: List[str]) -> Optional[str]:
        """GitLab specific implementation."""
        project_id = urllib.parse.quote(self.config.gitlab_repo, safe='')
        url = f"{self.config.gitlab_url.rstrip('/')}/api/v4/projects/{project_id}/issues"
        print(url)
        headers = {"PRIVATE-TOKEN": self.config.gitlab_token}
        
        # Check for existing
        try:
            check_res = requests.get(url, headers=headers, params={"state": "opened", "search": title}, timeout=5)
            if check_res.status_code == 200:
                for issue in check_res.json():
                    print(issue)
                    if issue['title'] == title:
                        self.console.print(f"[yellow]ℹ GitLab: Issue already exists: {issue['web_url']}[/yellow]")
                        return issue['web_url']
        except Exception: 
            traceback.print_exception()

        # Create new
        data = {"title": title, "description": body, "labels": ",".join(labels)}
        try:
            response = requests.post(url, headers=headers, json=data, timeout=self.config.api_timeout)
            if response.status_code == 201:
                return response.json().get("web_url")
            else:
                self.console.print(f"[red]GitLab Error: {response.text}[/red]")
        except Exception as e:
            self.console.print(f"[red]GitLab Connection Failed: {e}[/red]")
        return None
    
    def _format_issue_body(
        self,
        exception: Exception,
        tb_str: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        context = context or {}

        template = self._load_issue_template()

        if template:
            return self._render_template(
                template,
                exception=exception,
                traceback=tb_str,
                context=context,
            )

        # fallback
        return self._format_default_body(exception, tb_str, context)


    def _format_default_body(
        self,
        exception: Exception,
        tb_str: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format the issue body with context and traceback.
        
        Args:
            exception: The exception object.
            tb_str: Formatted traceback string.
            context: Additional context dictionary.
        
        Returns:
            Formatted markdown body for GitHub issue.
        """

        body = "### Automated Issue Report\n\n"
        
        # Timestamp
        body += f"**Reported:** {datetime.now().isoformat()}\n\n"
        
        # Exception details
        body += f"**Exception Type:** `{type(exception).__name__}`\n"
        body += f"**Message:** {str(exception)}\n\n"
        
        # User context
        if context:
            body += "### Context\n"
            for key, value in context.items():
                value_str = str(value).replace("|", "\\|")
                body += f"- **{key}:** `{value_str}`\n"
            body += "\n"
        
        # Environment info
        if self.config.include_environment_info:
            env_info = self._get_environment_info()
            if env_info:
                body += "### Environment\n"
                for key, value in env_info.items():
                    body += f"- **{key}:** `{value}`\n"
                body += "\n"
        
        # Git info
        if self.config.include_git_info:
            git_info = self._get_git_info()
            if git_info:
                body += "### Git Info\n"
                for key, value in git_info.items():
                    body += f"- **{key}:** `{value}`\n"
                body += "\n"
        
        # Traceback
        body += "### Traceback\n"
        body += f"```python\n{tb_str}\n```\n"
        
        return body
    
    
    def _get_environment_info(self) -> Dict[str, str]:
        """Collect environment information.
        
        Returns:
            Dictionary with environment details.
        """
        try:
            import sys
            return {
                "Python Version": f"{sys.version.split()[0]}",
                "Platform": platform.system(),
                "Platform Release": platform.release(),
                "Machine": platform.machine(),
            }
        except Exception:
            return {}
    
    
    def _get_git_info(self) -> Dict[str, str]:
        """Collect git repository information.
        
        Returns:
            Dictionary with git details.
        """
        try:
            git_info = {}
            
            # Current branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            git_info["Branch"] = branch
            
            # Latest commit
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            git_info["Commit"] = commit
            
            # Remote URL
            remote = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            git_info["Remote"] = remote
            
            return git_info
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}
    
    def _hash_issue(self, title: str, exception: Exception) -> str:
        """Create a hash for issue deduplication.
        
        Args:
            title: Issue title.
            exception: The exception object.
        
        Returns:
            Shortened hash string.
        """
        content = f"{title}:{type(exception).__name__}:{str(exception)}"
        hash_obj = hashlib.sha256(content.encode())
        return hash_obj.hexdigest()[: self.config.deduplicate_hash_length]
    
    
    def _create_github_issue(
        self, 
        title: str, 
        body: str, 
        labels: List[str]
    ) -> Optional[str]:
        """Create a GitHub issue.
        
        Args:
            title: Issue title.
            body: Issue body (markdown).
            labels: List of label names.
        
        Returns:
            Issue URL if successful, None otherwise.
        """
        url = f"https://api.github.com/repos/{self.config.github_repo}/issues"
        headers = {
            "Authorization": f"token {self.config.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data = {"title": title, "body": body, "labels": labels}
        
        try:
            # Check for existing issue
            existing = self._find_existing_issue(url, headers, title)
            if existing:
                issue_url = existing.get("html_url")
                self.console.print(
                    f"[yellow]ℹ Issue already exists: {issue_url}[/yellow]"
                )
                return issue_url
            
            # Create new issue
            self.console.print(f"[dim]Creating GitHub issue: {title}[/dim]")
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=self.config.api_timeout,
            )
            print(f"DEBUG: Status {response.status_code} | URL: {url}")
            if response.status_code == 201:
                issue_data = response.json()
                issue_number = issue_data.get("number")
                issue_url = issue_data.get("html_url")
                
                self._print_success_panel(issue_number, issue_url, title)
                return issue_url
            else:
                self.console.print(
                    f"[red]✗ Failed to create GitHub issue: "
                    f"HTTP {response.status_code}[/red]"
                )
                self.console.print(f"[red]{response.text}[/red]")
                return None
        
        except requests.exceptions.RequestException as e:
            self.console.print(f"[red]✗ Network error: {e}[/red]")
            return None
    

    def _find_existing_issue(
        self, 
        url: str, 
        headers: Dict[str, str], 
        title: str
    ) -> Optional[Dict[str, Any]]:
        """Find an existing open issue with the same title.
        
        Args:
            url: GitHub API issues endpoint.
            headers: Request headers with authorization.
            title: Issue title to search for.
        
        Returns:
            Issue data if found, None otherwise.
        """
        try:
            params = {"state": "open", "per_page": 100}
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.config.api_timeout,
            )
            response.raise_for_status()
            
            for issue in response.json():
                if issue.get("title") == title:
                    return issue
            
            return None
        except requests.exceptions.RequestException:
            return None
    
    def _save_locally(self, title: str, body: str) -> Optional[str]:
        """Save issue report locally.
        
        Args:
            title: Issue title.
            body: Issue body (markdown).
        
        Returns:
            Path to saved file.
        """
        if self.config.auto_create_dir:
            os.makedirs(self.config.error_reports_dir, exist_ok=True)
        elif not os.path.exists(self.config.error_reports_dir):
            self.console.print(
                f"[red]✗ Directory does not exist: {self.config.error_reports_dir}[/red]"
            )
            return None
        
        # Generate filename
        safe_title = (
            title.lower()
            .replace(" ", "_")
            .replace("/", "-")
            .replace(":", "")[:50]
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(
            self.config.error_reports_dir, f"{safe_title}_{timestamp}.md"
        )
        
        # Write file
        try:
            with open(file_path, "w") as f:
                f.write(f"# {title}\n\n{body}")
            
            mode = "LOCAL_MODE" if self.config.local_mode else "NO_CREDENTIALS"
            self.console.print(
                f"[yellow]⚠ ({mode}) Issue saved locally: {file_path}[/yellow]"
            )
            return file_path
        except IOError as e:
            self.console.print(f"[red]✗ Failed to save file: {e}[/red]")
            return None
    
    
    def _sanitize_branch_name(self, title, issue_number=None):
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if issue_number:
            return f"issue-{issue_number}/{slug[:50]}"
        return f"issue/{slug[:50]}"

    
    def _print_success_panel(
        self, issue_number: int, issue_url: str, title: str
    ) -> None:
        """Print a success panel with workflow instructions.
        
        Args:
            issue_number: GitHub issue number.
            issue_url: GitHub issue URL.
            title: Issue title.
        """
        branch = self._sanitize_branch_name(title, issue_number)
        
        workflow_text = Text()
        workflow_text.append("Issue: ", style="bold cyan")
        workflow_text.append(f"#{issue_number}\n", style="cyan")
        workflow_text.append("URL: ", style="bold cyan")
        workflow_text.append(f"{issue_url}\n\n", style="cyan")


    def _load_issue_template(self) -> Optional[str]:
        """Load an issue template from GitHub (with caching).

        This method attempts to retrieve a Markdown issue template from the configured
        GitHub repository. It supports both:
            - Named templates: `.github/ISSUE_TEMPLATE/<template_name>`
            - Fallback template: `.github/ISSUE_TEMPLATE.md`

        The result is cached per template name to avoid repeated API calls during the
        lifetime of the IssueReporter instance.

        Returns:
            The raw template content as a string if found, otherwise None.

        Behavior:
            - If `config.issue_template` is not set, returns None immediately.
            - If the template was previously fetched, returns the cached value.
            - If fetching fails (network/auth/etc.), returns None silently.
        """
        if not self.config.issue_template:
            return None
        
        if self.config.local_mode:
            return None

        try:
            repo = self.config.github_repo
            path = f".github/ISSUE_TEMPLATE/{self.config.issue_template}"

            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            headers = {
                "Authorization": f"token {self.config.github_token}",
                "Accept": "application/vnd.github.v3.raw",
            }

            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.text

            # fallback: single template file
            fallback_url = f"https://api.github.com/repos/{repo}/contents/.github/ISSUE_TEMPLATE.md"
            response = requests.get(fallback_url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.text

        except requests.exceptions.RequestException:
            pass

        return None


    def _render_template(
        self,
        template: str,
        exception: Exception,
        traceback: str,
        context: Dict[str, Any],
    ) -> str:
        """Render a template string using error and runtime data.

        This method performs lightweight variable substitution using a Jinja-like
        syntax (`{{ variable }}`) without introducing external dependencies.

        Supported features:
            - Top-level variables (e.g. {{ exception_type }})
            - Nested dictionary access (e.g. {{ context.user_id }}, {{ env.Platform }})
            - Graceful fallback for missing variables (placeholders remain unchanged)

        Available template variables:
            exception_type: Name of the exception class
            message: Exception message string
            traceback: Full formatted traceback
            timestamp: ISO timestamp of report generation
            context: User-provided context dictionary
            env: Environment information dictionary
            git: Git metadata dictionary

        Args:
            template: Raw template string containing placeholders.
            exception: The exception instance being reported.
            traceback: Preformatted traceback string.
            context: Additional user-provided metadata.

        Returns:
            Rendered template string with placeholders replaced.

        Notes:
            - Missing or invalid keys are left untouched in the output.
            - Attribute access is supported for objects, dict-style for mappings.
            - This is intentionally minimal and not a full templating engine.
        """
        
        data = {
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "env": self._get_environment_info(),
            "git": self._get_git_info(),
        }

        def replace(match):
            key = match.group(1).strip()

            # nested access: context.user_id
            parts = key.split(".")
            value = data

            try:
                for part in parts:
                    value = value[part] if isinstance(value, dict) else getattr(value, part)
                return str(value)
            except Exception:
                return f"{{{{ {key} }}}}"  # leave unresolved

        return re.sub(r"\{\{\s*(.*?)\s*\}\}", replace, template)