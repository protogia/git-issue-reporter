"""Configuration management for Multi-Platform Error Reporter."""
import os
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # GitHub Settings
    github_token: Optional[str] = None
    github_repo: Optional[str] = None  # owner/repo
    enable_github: bool = True

    # GitLab Settings
    gitlab_token: Optional[str] = None
    gitlab_repo: Optional[str] = None  # project_id or path/to/repo
    gitlab_url: str = "https://gitlab.com"
    enable_gitlab: bool = False

    # General Settings
    local_mode: bool = False
    error_reports_dir: str = "error_reports"
    auto_create_dir: bool = True
    api_timeout: int = 10
    deduplicate_issues: bool = True
    deduplicate_hash_length: int = 8
    include_environment_info: bool = True
    include_git_info: bool = True
    issue_template: str = None    
    @classmethod
    def from_env(cls) -> "Config":
        def str_to_bool(value: Optional[str], default: bool = False) -> bool:
            if value is None: return default
            return value.lower() in ("true", "1", "yes", "on")
        
        return cls(
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repo=os.getenv("GITHUB_REPO"),
            enable_github=str_to_bool(os.getenv("ENABLE_GITHUB"), default=True),
            
            gitlab_token=os.getenv("GITLAB_TOKEN"),
            gitlab_repo=os.getenv("GITLAB_REPO"),
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            enable_gitlab=str_to_bool(os.getenv("ENABLE_GITLAB"), default=False),
            
            local_mode=str_to_bool(os.getenv("ERROR_REPORTER_LOCAL_MODE")),
            error_reports_dir=os.getenv("ERROR_REPORTER_DIR", "error_reports"),
            deduplicate_issues=str_to_bool(os.getenv("ERROR_REPORTER_DEDUPLICATE"), default=True),
            issue_template=os.getenv("ISSUE_TEMPLATE")
        )

    def validate(self) -> None:
        if self.local_mode:
            return

        active_services = []
        if self.enable_github and self.github_token and self.github_repo:
            active_services.append("github")
        if self.enable_gitlab and self.gitlab_token and self.gitlab_repo:
            active_services.append("gitlab")

        if not active_services:
            raise ValueError("No reporting services (GitHub/GitLab) are configured and enabled.")