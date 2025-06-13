"""
OpenAPI Route Selection Configuration

This module provides utilities and examples for selecting specific routes
to include in the FastAPI OpenAPI schema generation.

Environment Variables:
- ONLY_RUN_ROUTES: If "true", includes only run and probe routes
- INCLUDE_OPENAPI_PROXY: If "false", excludes OpenAI proxy routes
- INCLUDE_PROBES: If "false", excludes health check/probe routes
- OPENAPI_ROUTES_FILTER: Comma-separated list of tags to include

Examples:
1. Only include runs and models:
   export OPENAPI_ROUTES_FILTER="runs,models"

2. Exclude probes and OpenAI proxy:
   export INCLUDE_PROBES=false
   export INCLUDE_OPENAPI_PROXY=false

3. Minimal API (only core run functionality):
   export ONLY_RUN_ROUTES=true

4. Custom subset for documentation:
   export OPENAPI_ROUTES_FILTER="agents,runs,models"
"""

import os
from typing import Any

from api.tags import RouteTags


def get_openapi_config() -> dict[str, Any]:
    """Get current OpenAPI configuration from environment variables"""
    return {
        "only_run_routes": os.getenv("ONLY_RUN_ROUTES") == "true",
        "include_openapi_proxy": os.getenv("INCLUDE_OPENAPI_PROXY", "true") == "true",
        "include_probes": os.getenv("INCLUDE_PROBES", "true") == "true",
        "routes_filter": os.getenv("OPENAPI_ROUTES_FILTER", "").split(",")
        if os.getenv("OPENAPI_ROUTES_FILTER")
        else [],
    }


def print_available_tags():
    """Print all available route tags that can be used for filtering"""
    print("Available route tags for OPENAPI_ROUTES_FILTER:")
    for tag_name in dir(RouteTags):
        if not tag_name.startswith("_"):
            tag_value = getattr(RouteTags, tag_name)
            print(f"  {tag_name}: {tag_value}")


# Common filtering presets
PRESETS = {
    "minimal": {
        "description": "Only core execution routes",
        "env_vars": {
            "ONLY_RUN_ROUTES": "true",
        },
    },
    "api_only": {
        "description": "API routes without webhooks or internal tools",
        "env_vars": {
            "OPENAPI_ROUTES_FILTER": f"{RouteTags.AGENTS},{RouteTags.RUNS},{RouteTags.MODELS}",
        },
    },
    "public_api": {
        "description": "Public-facing API routes only",
        "env_vars": {
            "OPENAPI_ROUTES_FILTER": f"{RouteTags.AGENTS},{RouteTags.RUNS},{RouteTags.MODELS},{RouteTags.AGENT_SCHEMAS}",
            "INCLUDE_PROBES": "false",
        },
    },
    "documentation": {
        "description": "Routes suitable for public documentation",
        "env_vars": {
            "OPENAPI_ROUTES_FILTER": f"{RouteTags.AGENTS},{RouteTags.RUNS},{RouteTags.MODELS},{RouteTags.AGENT_SCHEMAS},{RouteTags.EXAMPLES}",
            "INCLUDE_PROBES": "false",
        },
    },
}


def apply_preset(preset_name: str) -> dict[str, str]:
    """Apply a preset configuration and return the environment variables to set"""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}")

    preset = PRESETS[preset_name]
    env_vars = preset["env_vars"]
    print(f"Applying preset '{preset_name}': {preset['description']}")
    print("Set these environment variables:")

    for key, value in env_vars.items():
        print(f"  export {key}={value}")

    return env_vars


if __name__ == "__main__":
    print("=== FastAPI OpenAPI Route Selection ===")
    print()
    print("Current configuration:")
    config = get_openapi_config()
    for key, value in config.items():
        print(f"  {key}: {value}")

    print()
    print_available_tags()

    print()
    print("Available presets:")
    for name, preset in PRESETS.items():
        print(f"  {name}: {preset['description']}")
