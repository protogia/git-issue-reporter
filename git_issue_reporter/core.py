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
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Config

class IssueReporter:
    """Automatically create GitHub issues for errors in your Python scripts."""
    
    def __init__(
        self,
        config: Optional[Config] = None,
        console: Optional[Console] = None,
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None,
        local_mode: Optional[bool] = None,
    ):
        """Initialize IssueReporter.
        
        Args:
            config: Config instance. If None, loads from environment.
            console: Rich Console instance for output. If None, creates new one.
            github_token: Override config GitHub token.
            github_repo: Override config GitHub repo.
            local_mode: Override config local mode.
        """
        self.config = config or Config.from_env()
        
        # Override config with explicit parameters
        if github_token is not None:
            self.config.github_token = github_token
        if github_repo is not None:
            self.config.github_repo = github_repo
        if local_mode is not None:
            self.config.local_mode = local_mode
        
        # Validate configuration
        self.config.validate()
        
        self.console = console or Console()
        self._issue_cache: Dict[str, str] = {}  # For deduplication
    
    def report_error(
        self,
        exception: Exception,
        title: str,
        context: Optional[Dict[str, Any]] = None,
        labels: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Report an error to GitHub or save locally.
        
        Args:
            exception: The exception that occurred.
            title: GitHub issue title.
            context: Additional context to include in the issue (e.g., file paths, user info).
            labels: GitHub issue labels.
        
        Returns:
            The issue URL if successful, local file path if saved locally, None on failure.
        """
        labels = labels or []
        context = context or {}
        
        # Format traceback
        tb_str = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        
        # Build issue body
        body = self._format_issue_body(exception, tb_str, context)
        
        # Check for duplicates
        if self.config.deduplicate_issues:
            issue_hash = self._hash_issue(title, exception)
            if issue_hash in self._issue_cache:
                self.console.print(
                    f"[yellow]⚠ Duplicate issue detected (cached). "
                    f"Skipping: {self._issue_cache[issue_hash]}[/yellow]"
                )
                return self._issue_cache[issue_hash]
        
        # Report to GitHub or save locally
        if self.config.local_mode or not self.config.github_token or not self.config.github_repo:
            result = self._save_locally(title, body)
        else:
            result = self._create_github_issue(title, body, labels)
        
        # Cache the result
        if self.config.deduplicate_issues and result:
            issue_hash = self._hash_issue(title, exception)
            self._issue_cache[issue_hash] = result
        
        return result
    
    def _format_issue_body(
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
                # Escape special markdown characters
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
        self, title: str, body: str, labels: List[str]
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
                timeout=self.config.github_api_timeout,
            )
            
            if response.status_code == 201:
                issue_data = response.json()
                issue_number = issue_data.get("number")
                issue_url = issue_data.get("html_url")
                
                # Print success panel
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
        self, url: str, headers: Dict[str, str], title: str
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
                timeout=self.config.github_api_timeout,
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
        # Create directory
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
