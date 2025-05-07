# NOVAGUARD-AI/src/core/shared_context.py

from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .config_loader import Config


class ChangedFile(BaseModel):
    """
    Represents a changed file along with its content and related information.
    This model's field descriptions can be used to inform LLMs about the data structure.
    """
    path: str = Field(
        description="The relative path of the file from the repository root."
    )
    content: str = Field(
        description="The full content of the file."
    )
    diff_hunks: Optional[List[str]] = Field(
        default=None,
        description="A list of 'hunk' sections from the git diff output, if available. Useful for focusing LLM attention on specific changes."
    )
    language: Optional[str] = Field(
        default=None,
        description="The programming language of the file (e.g., 'python', 'javascript'). This can be determined later in the pipeline."
    )


class SharedReviewContext(BaseModel):
    """
    Contains shared contextual information about the Pull Request and repository,
    available throughout the code review process.
    Field descriptions are in English to aid LLM understanding if this model is used in prompts.
    """
    repository_name: str = Field(
        description="The name of the repository (e.g., 'owner/repo')."
    )
    repo_local_path: Path = Field(
        description="The absolute path to the repository's working directory on the self-hosted runner."
    )
    sha: str = Field(
        description="The SHA of the commit being reviewed (typically the HEAD commit of the PR)."
    )
    
    pr_url: Optional[str] = Field(default=None, description="The URL of the Pull Request on GitHub.")
    pr_title: Optional[str] = Field(default=None, description="The title of the Pull Request.")
    pr_body: Optional[str] = Field(default=None, description="The description body of the Pull Request.")
    pr_diff_url: Optional[str] = Field(default=None, description="The URL pointing to the diff of the Pull Request.")
    pr_number: Optional[int] = Field(default=None, description="The number of the Pull Request.")

    base_ref: Optional[str] = Field(default=None, description="The ref of the base branch (target branch) for the Pull Request.")
    head_ref: Optional[str] = Field(default=None, description="The ref of the head branch (source branch) of the Pull Request.")

    github_event_name: Optional[str] = Field(default=None, description="The name of the GitHub event that triggered the workflow.")
    github_event_payload: Dict[str, Any] = Field(default_factory=dict, description="The full GitHub event payload as a dictionary.")

    # Add the application config object here
    config_obj: Config = Field(description="The loaded application configuration object.")


    class Config:
        arbitrary_types_allowed = True # Allow Path and our Config type

    def get_full_file_path(self, relative_file_path: str) -> Path:
        """Returns the absolute path of a file within the repository."""
        return self.repo_local_path / relative_file_path