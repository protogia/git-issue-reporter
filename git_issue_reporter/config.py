"""Configuration management for GitHub Error Reporter."""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Configuration for ErrorReporter."""
    
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    local_mode: bool = False
    error_reports_dir: str = "error_reports"
    auto_create_dir: bool = True
    github_api_timeout: int = 10
    deduplicate_issues: bool = True
    deduplicate_hash_length: int = 8
    include_environment_info: bool = True
    include_git_info: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.
        
        Environment variables:
            - GITHUB_TOKEN: GitHub personal access token
            - GITHUB_REPO: GitHub repository (format: owner/repo)
            - ERROR_REPORTER_LOCAL_MODE: Set to "true" to use local mode
            - ERROR_REPORTER_DIR: Directory to save error reports (default: error_reports)
            - ERROR_REPORTER_DEDUPLICATE: Set to "false" to disable deduplication
            - ERROR_REPORTER_INCLUDE_ENV: Set to "false" to exclude environment info
            - ERROR_REPORTER_INCLUDE_GIT: Set to "false" to exclude git info
        
        Returns:
            Config instance with values from environment.
        """
        def str_to_bool(value: Optional[str], default: bool = False) -> bool:
            if value is None:
                return default
            return value.lower() in ("true", "1", "yes", "on")
        
        return cls(
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repo=os.getenv("GITHUB_REPO"),
            local_mode=str_to_bool(os.getenv("ERROR_REPORTER_LOCAL_MODE")),
            error_reports_dir=os.getenv("ERROR_REPORTER_DIR", "error_reports"),
            deduplicate_issues=str_to_bool(
                os.getenv("ERROR_REPORTER_DEDUPLICATE"), 
                default=True
            ),
            include_environment_info=str_to_bool(
                os.getenv("ERROR_REPORTER_INCLUDE_ENV"), 
                default=True
            ),
            include_git_info=str_to_bool(
                os.getenv("ERROR_REPORTER_INCLUDE_GIT"), 
                default=True
            ),
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Load configuration from a dictionary.
        
        Args:
            data: Dictionary with configuration keys.
        
        Returns:
            Config instance.
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    
    def validate(self) -> None:
        """Validate configuration.
        
        Raises:
            ValueError: If configuration is invalid.
        """
        if not self.local_mode and (not self.github_token or not self.github_repo):
            raise ValueError(
                "GitHub token and repo are required when not in local mode. "
                "Set GITHUB_TOKEN and GITHUB_REPO environment variables."
            )
        
        if self.github_repo and "/" not in self.github_repo:
            raise ValueError(
                f"Invalid GitHub repo format: {self.github_repo}. "
                "Expected format: owner/repo"
            )
        
        if self.github_api_timeout <= 0:
            raise ValueError("github_api_timeout must be greater than 0")
        
        if self.deduplicate_hash_length <= 0:
            raise ValueError("deduplicate_hash_length must be greater than 0")
