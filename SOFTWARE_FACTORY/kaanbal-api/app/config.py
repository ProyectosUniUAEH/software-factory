from pydantic_settings import BaseSettings
from typing import Optional

from app.defaults import (
    MONGODB_URI,
    SECRET_KEY_DEV,
    WORKSPACE_PATH,
)


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = MONGODB_URI

    # Git/Bitbucket - MUST be configured via .env, env vars, or system_config
    git_username: str = ""
    git_token: str = ""
    bitbucket_workspace: str = ""
    infra_repo_url: str = ""

    # DockerHub - MUST be configured
    dockerhub_username: str = ""
    dockerhub_token: str = ""

    # Domain - MUST be configured
    domain: str = ""

    # Workspace paths (use /tmp for container compatibility)
    workspace_path: str = WORKSPACE_PATH

    # Security
    SECRET_KEY: str = SECRET_KEY_DEV

    class Config:
        env_file = ".env"


settings = Settings()
