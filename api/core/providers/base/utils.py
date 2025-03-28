import os

from core.domain.errors import MissingEnvVariablesError


def get_provider_config_env(key: str, index: int, default: str | None = None):
    """Retrieve a value for a given env. If no default is provided
    raises a MissingEnvVariablesError error"""
    env_var = f"{key}_{index}" if index > 0 else key
    if default:
        return os.environ.get(env_var, default)
    try:
        return os.environ[env_var]
    except KeyError:
        raise MissingEnvVariablesError([env_var])
