"""Shared pytest setup. Loads the repo .env so integration tests can find the API key."""

from twin.config import load_env_file

load_env_file()
